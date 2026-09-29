# GeoLog

Plataforma Streamlit da LogiTech Express para demonstrar persistência poliglota:

- **SQLite** (`logitech.db`) para motoristas e veículos, com chave estrangeira.
- **MongoDB** (`geolog_db.telemetria`) para sensores e telemetria em GeoJSON.
- Índice geoespacial **`2dsphere`** criado automaticamente durante a inicialização.
- Busca geográfica com **`$near`**, mapa Folium, join em memória e dashboard Plotly.
- Simulador de movimentação que insere novas posições no MongoDB e atualiza a tela.

## 1. Pré-requisitos

Tenha disponível no ambiente:

- Python 3.11 ou superior;
- MongoDB local ou uma conta gratuita no MongoDB Atlas;
- VS Code (opcional, mas recomendado).

## 2. Instalar o projeto

Abra o PowerShell na pasta do projeto:

```powershell
cd "C:\caminho\para\Geolog"
```

Instale as bibliotecas:

```powershell
python -m pip install -r requirements.txt
```

## 3. Configurar o MongoDB

### Opção A: MongoDB Atlas (recomendada)

1. Acesse [mongodb.com/atlas](https://www.mongodb.com/atlas) e crie uma conta.
2. Crie um cluster gratuito.
3. Em **Database Access**, crie um usuário e uma senha para a aplicação.
4. Em **Network Access**, adicione seu IP atual. Para um teste temporário, é possível liberar `0.0.0.0/0`, mas isso não é recomendado para produção.
5. Clique em **Connect > Drivers** e copie a URI de conexão.
6. No PowerShell, configure a URI apenas para a sessão atual:

```powershell
$env:MONGO_URI="mongodb+srv://USUARIO:SENHA@cluster.mongodb.net/?retryWrites=true&w=majority"
```

Substitua `USUARIO` e `SENHA`. Se a senha tiver caracteres especiais, use a versão codificada para URL.

### Opção B: MongoDB local

Instale o MongoDB Community Server e inicie o serviço do MongoDB. A aplicação usa, por padrão:

```text
mongodb://localhost:27017
```

Nesse caso, não é necessário configurar `MONGO_URI`.

## 4. Executar a aplicação

Na pasta que contém `app.py`, execute:

```powershell
python -m streamlit run app.py
```

Abra no navegador:


http://localhost:8501
```

Na barra lateral, o indicador esperado é:

```text
MongoDB conectado · índice 2dsphere ativo
```

Na primeira execução, o sistema automaticamente:

1. cria o arquivo `logitech.db`;
2. cria as tabelas `motoristas` e `veiculos`;
3. insere os dados cadastrais de teste;
4. cria o banco `geolog_db` e a coleção `telemetria`;
5. cria o índice `location_2dsphere`;
6. insere as leituras iniciais de telemetria.

## 5. Como testar cada módulo

### Dashboard analítico

Na aba **Visão geral**, confirme:

- total de frotas ativas;
- temperatura média;
- alertas de velocidade acima de 80 km/h;
- histórico de temperatura por placa;
- distribuição do status dos motoristas.

### Busca geoespacial

Na aba **Busca geoespacial**:

1. mantenha o ponto padrão de João Pessoa;
2. use o raio inicial de 15 km;
3. confirme os veículos no resultado;
4. verifique os marcadores no mapa e o círculo do raio;
5. altere latitude, longitude ou raio e confirme que a lista muda.

Essa consulta usa o operador MongoDB `$near` e a distância é convertida de quilômetros para metros.

### Join poliglota

Na aba **Join operacional**, confirme a combinação, em memória, dos dados do SQLite com a última telemetria do MongoDB:

- motorista;
- placa;
- temperatura;
- velocidade;
- latitude e longitude;
- horário da leitura.

### Simulador em tempo real

Na barra lateral:

1. clique em **Simular Movimentação**;
2. observe a mensagem de sucesso;
3. confirme que o contador de leituras aumentou;
4. confira que o mapa recebeu novas posições;
5. observe a atualização do histórico e dos indicadores.

Cada clique cria uma nova leitura para cada veículo com pequena variação aleatória de posição, temperatura e velocidade.

## 6. Teste rápido pelo terminal

Para verificar se o arquivo está sintaticamente correto:

```powershell
python -m py_compile app.py
```

Para confirmar a instalação das bibliotecas:

```powershell
python -m pip show streamlit pymongo pandas folium plotly
```

## 7. Problemas comuns

### Mensagem “MongoDB indisponível”

Confira se:

- o MongoDB local está em execução; ou
- a variável `MONGO_URI` foi configurada no mesmo PowerShell usado para iniciar o Streamlit;
- o IP foi autorizado no MongoDB Atlas;
- usuário e senha estão corretos.

Após corrigir a conexão, recarregue a página do navegador.

### Porta 8501 ocupada

Execute em outra porta:

```powershell
python -m streamlit run app.py --server.port 8502
```

Depois acesse `http://localhost:8502`.

### Encerrar a aplicação

No terminal onde o Streamlit está rodando, pressione `Ctrl+C`.

## 8. Entrega acadêmica

Entregue:

- `app.py`;
- `requirements.txt`;
- `relatorio_tecnico.md` convertido para PDF, com no máximo três páginas.

O relatório deve incluir o diagrama da arquitetura poliglota, mostrando o Streamlit, o SQLite e o MongoDB, além do fluxo de consulta geoespacial e do join em memória.

Não inclua no código, no README ou no relatório a senha do MongoDB Atlas.
