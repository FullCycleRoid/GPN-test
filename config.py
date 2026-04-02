LLM_PROVIDER = "openrouter"  # "yandex", "deepseek" или "openrouter"

# YandexGPT
YANDEX_API_KEY = ""
YANDEX_FOLDER_ID = ""
YANDEX_GPT_MODEL = "yandexgpt/latest"

# DeepSeek
DEEPSEEK_API_KEY = ""
DEEPSEEK_MODEL = "deepseek-chat"
DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"

# OpenRouter
OPENROUTER_API_KEY = ""
OPENROUTER_MODEL = "deepseek/deepseek-chat-v3-0324"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_FALLBACK_MODELS = [
    "deepseek/deepseek-chat-v3-0324",
    "google/gemini-2.5-flash-preview",
    "meta-llama/llama-4-maverick",
]

# Сервисы
SEARCH_SERVICE_HOST = "127.0.0.1"
SEARCH_SERVICE_PORT = 5010

LLM_SERVICE_HOST = "127.0.0.1"
LLM_SERVICE_PORT = 5011

WEB_CLIENT_HOST = "127.0.0.1"
WEB_CLIENT_PORT = 5012

DATA_PATH = "data/synthetic_data.json"
SEARCH_TOP_K = 3

# Retry
LLM_MAX_RETRIES = 3
LLM_RETRY_BACKOFF = 1.5
LLM_REQUEST_TIMEOUT = 60
SERVICE_MAX_RETRIES = 3
SERVICE_RETRY_BACKOFF = 0.5
