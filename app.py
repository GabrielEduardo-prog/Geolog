"""GeoLog: plataforma Streamlit de persistencia poliglota.

SQLite concentra dados cadastrais/transacionais; MongoDB concentra telemetria
com GeoJSON e indice 2dsphere.
"""
from __future__ import annotations

import os
import random
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import folium
import pandas as pd
import plotly.express as px
import streamlit as st
from folium.plugins import MarkerCluster
from pymongo import ASCENDING, MongoClient
from pymongo.collection import Collection
from pymongo.errors import PyMongoError
from streamlit_folium import st_folium


BASE_DIR = Path(__file__).resolve().parent
SQLITE_PATH = BASE_DIR / "logitech.db"
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DATABASE = os.getenv("MONGO_DATABASE", "geolog_db")
MONGO_COLLECTION = os.getenv("MONGO_COLLECTION", "telemetria")
MAP_CENTER = [-7.115, -34.873]

MOTORISTAS = [
    (1, "Carlos Andrade", "123456789", "Ativo"),
    (2, "Mariana Silva", "987654321", "Ativo"),
    (3, "Roberto Souza", "456789123", "Em Descanso"),
]
VEICULOS = [
    (101, "ABC-1A23", "Volvo FH 540", 1),
    (102, "XYZ-9876", "Scania R450", 2),
    (103, "KGB-4567", "Mercedes Actros", 3),
]
TELEMETRIA_SEED = [
    {
        "veiculo_id": 101,
        "location": {"type": "Point", "coordinates": [-34.873, -7.115]},
        "temperatura": 4.2,
        "velocidade": 65,
        "timestamp": "2026-09-11T10:00:00Z",
    },
    {
        "veiculo_id": 102,
        "location": {"type": "Point", "coordinates": [-34.832, -7.121]},
        "temperatura": -18.5,
        "velocidade": 85,
        "timestamp": "2026-09-11T10:05:00Z",
    },
    {
        "veiculo_id": 103,
        "location": {"type": "Point", "coordinates": [-34.950, -7.150]},
        "temperatura": 22.0,
        "velocidade": 0,
        "timestamp": "2026-09-11T09:45:00Z",
    },
]


def get_sqlite_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(SQLITE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_sqlite() -> None:
    with get_sqlite_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS motoristas (
                id INTEGER PRIMARY KEY,
                nome TEXT NOT NULL,
                cnh TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL CHECK (status IN ('Ativo', 'Em Descanso', 'Afastado'))
            );
            CREATE TABLE IF NOT EXISTS veiculos (
                id INTEGER PRIMARY KEY,
                placa TEXT NOT NULL UNIQUE,
                modelo TEXT NOT NULL,
                motorista_id INTEGER NOT NULL,
                FOREIGN KEY (motorista_id) REFERENCES motoristas(id)
            );
            """
        )
        connection.executemany(
            "INSERT OR IGNORE INTO motoristas (id, nome, cnh, status) VALUES (?, ?, ?, ?)",
            MOTORISTAS,
        )
        connection.executemany(
            "INSERT OR IGNORE INTO veiculos (id, placa, modelo, motorista_id) VALUES (?, ?, ?, ?)",
            VEICULOS,
        )


def get_fleet() -> pd.DataFrame:
    with get_sqlite_connection() as connection:
        return pd.read_sql_query(
            """
            SELECT v.id AS veiculo_id, v.placa, v.modelo, m.nome AS motorista,
                   m.status
            FROM veiculos v
            JOIN motoristas m ON m.id = v.motorista_id
            ORDER BY v.id
            """,
            connection,
        )


def connect_mongo() -> tuple[MongoClient | None, Collection | None, str | None]:
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=1500)
        client.admin.command("ping")
        collection = client[MONGO_DATABASE][MONGO_COLLECTION]
        collection.create_index([("location", "2dsphere")], name="location_2dsphere")
        return client, collection, None
    except (PyMongoError, OSError) as error:
        return None, None, str(error)


def seed_mongo(collection: Collection) -> None:
    if collection.count_documents({}) == 0:
        collection.insert_many(TELEMETRIA_SEED)
    else:
        for record in TELEMETRIA_SEED:
            collection.update_one(
                {"veiculo_id": record["veiculo_id"], "timestamp": record["timestamp"]},
                {"$setOnInsert": record},
                upsert=True,
            )


def simulate_movement(collection: Collection) -> int:
    latest_documents = collection.aggregate(
        [
            {"$sort": {"timestamp": -1}},
            {"$group": {"_id": "$veiculo_id", "telemetria": {"$first": "$$ROOT"}}},
            {"$replaceWith": "$telemetria"},
        ]
    )
    simulated_records = []
    for document in latest_documents:
        longitude, latitude = document["location"]["coordinates"]
        simulated_records.append(
            {
                "veiculo_id": document["veiculo_id"],
                "location": {
                    "type": "Point",
                    "coordinates": [
                        longitude + random.uniform(-0.0025, 0.0025),
                        latitude + random.uniform(-0.0025, 0.0025),
                    ],
                },
                "temperatura": round(document["temperatura"] + random.uniform(-0.8, 0.8), 1),
                "velocidade": max(0, min(110, document["velocidade"] + random.randint(-8, 8))),
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            }
        )
    if simulated_records:
        collection.insert_many(simulated_records)
    return len(simulated_records)


def telemetry_dataframe(collection: Collection) -> pd.DataFrame:
    documents = list(collection.find({}, {"_id": 0}).sort("timestamp", ASCENDING))
    rows: list[dict[str, Any]] = []
    for document in documents:
        longitude, latitude = document["location"]["coordinates"]
        rows.append(
            {
                "veiculo_id": document["veiculo_id"],
                "temperatura": document["temperatura"],
                "velocidade": document["velocidade"],
                "timestamp": pd.to_datetime(document["timestamp"], utc=True),
                "longitude": longitude,
                "latitude": latitude,
            }
        )
    return pd.DataFrame(rows)


def latest_telemetry(collection: Collection) -> pd.DataFrame:
    pipeline = [
        {"$sort": {"timestamp": -1}},
        {"$group": {"_id": "$veiculo_id", "telemetria": {"$first": "$$ROOT"}}},
        {"$replaceWith": "$telemetria"},
        {"$project": {"_id": 0, "veiculo_id": 1, "temperatura": 1, "velocidade": 1,
                      "timestamp": 1, "location": 1}},
    ]
    documents = list(collection.aggregate(pipeline))
    rows = []
    for document in documents:
        longitude, latitude = document["location"]["coordinates"]
        rows.append(
            {
                "veiculo_id": document["veiculo_id"],
                "temperatura": document["temperatura"],
                "velocidade": document["velocidade"],
                "timestamp": document["timestamp"],
                "longitude": longitude,
                "latitude": latitude,
            }
        )
    return pd.DataFrame(rows)


def search_near(collection: Collection, latitude: float, longitude: float, radius_km: float) -> pd.DataFrame:
    documents = collection.find(
        {"location": {"$near": {"$geometry": {"type": "Point", "coordinates": [longitude, latitude]},
                                  "$maxDistance": radius_km * 1000}}},
        {"_id": 0},
    )
    rows = []
    for document in documents:
        point_longitude, point_latitude = document["location"]["coordinates"]
        rows.append(
            {"veiculo_id": document["veiculo_id"], "temperatura": document["temperatura"],
             "velocidade": document["velocidade"], "timestamp": document["timestamp"],
             "longitude": point_longitude, "latitude": point_latitude}
        )
    return pd.DataFrame(rows)


def build_map(telemetry: pd.DataFrame, latitude: float, longitude: float, radius_km: float) -> folium.Map:
    fmap = folium.Map(location=[latitude, longitude], zoom_start=11, tiles="CartoDB positron")
    folium.Circle(
        location=[latitude, longitude], radius=radius_km * 1000, color="#e76f51",
        fill=True, fill_opacity=0.08, tooltip=f"Raio de busca: {radius_km:.1f} km",
    ).add_to(fmap)
    folium.Marker([latitude, longitude], tooltip="Ponto de referência",
                  icon=folium.Icon(color="red", icon="flag")).add_to(fmap)
    cluster = MarkerCluster(name="Veículos encontrados").add_to(fmap)
    for row in telemetry.itertuples():
        status = "ALERTA" if row.velocidade > 80 else "Normal"
        folium.Marker(
            [row.latitude, row.longitude],
            tooltip=f"Veículo {row.veiculo_id} | {status}",
            popup=(f"Temperatura: {row.temperatura:.1f} °C<br>"
                   f"Velocidade: {row.velocidade} km/h<br>"
                   f"Coordenadas: {row.latitude:.4f}, {row.longitude:.4f}"),
            icon=folium.Icon(color="red" if row.velocidade > 80 else "blue", icon="truck", prefix="fa"),
        ).add_to(cluster)
    folium.LayerControl().add_to(fmap)
    return fmap


def render_dashboard(fleet: pd.DataFrame, telemetry: pd.DataFrame) -> None:
    latest = telemetry.sort_values("timestamp").drop_duplicates("veiculo_id", keep="last")
    active_fleet = int((fleet["status"] == "Ativo").sum())
    average_temperature = float(latest["temperatura"].mean()) if not latest.empty else 0
    speed_alerts = int((latest["velocidade"] > 80).sum())
    kpi_columns = st.columns(3)
    kpi_columns[0].metric("Frotas ativas", active_fleet, f"de {len(fleet)} veículos")
    kpi_columns[1].metric("Temperatura média", f"{average_temperature:.1f} °C")
    kpi_columns[2].metric("Alertas de velocidade", speed_alerts, "> 80 km/h")
    st.subheader("Leituras de temperatura")
    history = telemetry.merge(fleet[["veiculo_id", "placa"]], on="veiculo_id", how="left")
    if not history.empty:
        chart = px.line(history, x="timestamp", y="temperatura", color="placa", markers=True,
                        labels={"timestamp": "Horário", "temperatura": "Temperatura (°C)", "placa": "Veículo"})
        chart.update_layout(height=330, margin={"t": 20, "b": 10})
        st.plotly_chart(chart, use_container_width=True)
    status_chart = px.pie(fleet, names="status", hole=0.55, title="Status dos motoristas",
                          color_discrete_sequence=["#2a9d8f", "#e9c46a", "#e76f51"])
    st.plotly_chart(status_chart, use_container_width=True)


def main() -> None:
    st.set_page_config(page_title="GeoLog | Operação", page_icon="🚚", layout="wide")
    st.markdown("""
        <style>
        .block-container { padding-top: 2rem; max-width: 1400px; }
        [data-testid="stMetricValue"] { color: #0f766e; }
        </style>
    """, unsafe_allow_html=True)
    initialize_sqlite()
    mongo_client, collection, _ = connect_mongo()
    fleet = get_fleet()

    st.title("GeoLog")
    st.caption("Centro operacional da LogiTech Express · persistência poliglota")
    if collection is None:
        st.error("MongoDB indisponível. Inicie o serviço e recarregue a página para habilitar telemetria e mapa.")
        st.info(f"URI configurada: {MONGO_URI}")
        st.subheader("Frota cadastral no SQLite")
        st.dataframe(fleet, use_container_width=True, hide_index=True)
        return

    try:
        seed_mongo(collection)
        telemetry = telemetry_dataframe(collection)
        st.sidebar.success("SQLite conectado")
        st.sidebar.success("MongoDB conectado · índice 2dsphere ativo")
        st.sidebar.caption(f"{collection.count_documents({})} leituras disponíveis")
        if st.sidebar.button("Simular Movimentação", use_container_width=True):
            simulated_count = simulate_movement(collection)
            st.toast(f"{simulated_count} posições simuladas com sucesso.")
            st.rerun()
        tabs = st.tabs(["Visão geral", "Busca geoespacial", "Join operacional"])
        with tabs[0]:
            render_dashboard(fleet, telemetry)
        with tabs[1]:
            st.subheader("Veículos por proximidade")
            controls = st.columns([1, 1, 1])
            latitude = controls[0].number_input("Latitude", value=MAP_CENTER[0], format="%.4f")
            longitude = controls[1].number_input("Longitude", value=MAP_CENTER[1], format="%.4f")
            radius = controls[2].slider("Raio (km)", min_value=1.0, max_value=50.0, value=15.0, step=1.0)
            nearby = search_near(collection, latitude, longitude, radius)
            st.metric("Veículos no raio", len(nearby))
            st_folium(build_map(nearby, latitude, longitude, radius), width=None, height=500)
            if not nearby.empty:
                st.dataframe(nearby, use_container_width=True, hide_index=True)
            else:
                st.warning("Nenhuma leitura encontrada neste raio.")
        with tabs[2]:
            st.subheader("Join poliglota em memória")
            joined = fleet.merge(latest_telemetry(collection), on="veiculo_id", how="left")
            joined = joined.rename(columns={"nome": "motorista"})
            st.dataframe(joined[["motorista", "placa", "temperatura", "velocidade",
                                 "latitude", "longitude", "timestamp"]],
                         use_container_width=True, hide_index=True)
    except PyMongoError as error:
        st.error(f"Falha ao consultar a telemetria: {error}")
    finally:
        if mongo_client is not None:
            mongo_client.close()


if __name__ == "__main__":
    main()
