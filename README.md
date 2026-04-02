# Справочная система по внутренним документам

Поиск и ответы по внутренним документам нефтегазовой компании.

## Архитектура

- **Search Service** (`:5010`) — BM25-поиск по базе документов
- **LLM Service** (`:5011`) — генерация ответов (OpenRouter / DeepSeek / YandexGPT)
- **Web Client** (`:5012`) — веб-интерфейс

## Запуск

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Укажите провайдера и API-ключ в `config.py`, затем:

**Linux / macOS:**
```bash
python start.py
```

**Windows:**
```cmd
start.bat
```

Откройте `http://localhost:5012`

## API

**Search Service:**
- `GET /health`
- `POST /search` — `{"query": "...", "top_k": 3}`
- `POST /reload`

**LLM Service:**
- `GET /health`
- `POST /ask` — `{"question": "...", "documents": [...]}`

**Web Client:**
- `GET /` — интерфейс
- `GET /api/health`
- `POST /api/ask` — `{"question": "..."}`
