import os
import sys
import time
import logging
import requests as http_requests
from flask import Flask, request, jsonify

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config

app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("LLMService")

SYSTEM_PROMPT = """Ты — справочная система по внутренним документам нефтегазовой компании.
Твоя задача — отвечать на вопросы сотрудников, опираясь ТОЛЬКО на предоставленные документы.
Никогда не упоминай, что ты ИИ, нейросеть, языковая модель или чат-бот. Отвечай как справочная система.

Правила:
1. Отвечай строго на основе предоставленного контекста. Не выдумывай информацию.
2. Для каждого утверждения указывай источник: название документа и его ID.
3. Если в документах нет ответа — честно скажи об этом.
4. Приводи конкретные цитаты из документов.
5. В конце добавь предупреждение: итоговая юридическая интерпретация требует проверки профильным специалистом.

Формат ответа:
- Краткий ответ на вопрос
- Источники с цитатами
- Предупреждение"""

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def build_context(documents):
    parts = []
    for i, doc in enumerate(documents, 1):
        parts.append(
            f"--- Документ {i} ---\n"
            f"ID: {doc['document_id']}\n"
            f"Название: {doc['title']}\n"
            f"Тип: {doc.get('doc_type', 'N/A')}\n"
            f"Департамент: {doc.get('department', 'N/A')}\n"
            f"Текст: {doc['text']}\n"
        )
    return "\n".join(parts)


def _request_with_retry(method, url, *, headers, json_body, timeout,
                         max_retries=None, backoff=None, label="LLM"):
    max_retries = max_retries or config.LLM_MAX_RETRIES
    backoff = backoff or config.LLM_RETRY_BACKOFF
    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            resp = http_requests.request(
                method, url, json=json_body, headers=headers, timeout=timeout,
            )
            if resp.status_code < 400:
                return resp, None

            if resp.status_code in RETRYABLE_STATUS_CODES and attempt < max_retries:
                delay = backoff * (2 ** (attempt - 1))
                log.warning(f"[{label}] Попытка {attempt}/{max_retries} — HTTP {resp.status_code}, повтор через {delay:.1f}с")
                time.sleep(delay)
                last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
                continue

            last_error = f"HTTP {resp.status_code}: {resp.text[:300]}"
            log.error(f"[{label}] {last_error}")
            return None, f"[{label}] {last_error}"

        except http_requests.exceptions.Timeout:
            last_error = f"Таймаут ({timeout}с)"
            if attempt < max_retries:
                delay = backoff * (2 ** (attempt - 1))
                log.warning(f"[{label}] Попытка {attempt}/{max_retries} — таймаут, повтор через {delay:.1f}с")
                time.sleep(delay)
            else:
                log.error(f"[{label}] Все {max_retries} попыток исчерпаны: таймаут")
                return None, f"[{label}] {last_error}"

        except http_requests.exceptions.ConnectionError as e:
            last_error = f"Нет соединения: {e}"
            if attempt < max_retries:
                delay = backoff * (2 ** (attempt - 1))
                log.warning(f"[{label}] Попытка {attempt}/{max_retries} — connection error, повтор через {delay:.1f}с")
                time.sleep(delay)
            else:
                log.error(f"[{label}] Все {max_retries} попыток исчерпаны: {last_error}")
                return None, f"[{label}] {last_error}"

        except http_requests.exceptions.RequestException as e:
            last_error = str(e)
            log.error(f"[{label}] {last_error}")
            return None, f"[{label}] {last_error}"

    return None, f"[{label}] Все {max_retries} попыток исчерпаны: {last_error}"


def _call_openai_compatible(url, api_key, model, user_message, context, label, timeout=None):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    body = {
        "model": model,
        "temperature": 0.3,
        "max_tokens": 2000,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Контекст из документов:\n{context}\n\nВопрос пользователя: {user_message}"},
        ],
    }
    resp, err = _request_with_retry(
        "POST", url, headers=headers, json_body=body,
        timeout=timeout or config.LLM_REQUEST_TIMEOUT, label=label,
    )
    if err:
        return None, err
    try:
        data = resp.json()
        return data["choices"][0]["message"]["content"], None
    except (KeyError, IndexError, ValueError) as e:
        return None, f"[{label}] Ошибка разбора ответа: {e}"


def call_yandex_gpt(user_message, context):
    url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Api-Key {config.YANDEX_API_KEY}",
        "x-folder-id": config.YANDEX_FOLDER_ID,
    }
    body = {
        "modelUri": f"gpt://{config.YANDEX_FOLDER_ID}/{config.YANDEX_GPT_MODEL}",
        "completionOptions": {"stream": False, "temperature": 0.3, "maxTokens": 2000},
        "messages": [
            {"role": "system", "text": SYSTEM_PROMPT},
            {"role": "user", "text": f"Контекст из документов:\n{context}\n\nВопрос пользователя: {user_message}"},
        ],
    }
    resp, err = _request_with_retry(
        "POST", url, headers=headers, json_body=body,
        timeout=config.LLM_REQUEST_TIMEOUT, label="YandexGPT",
    )
    if err:
        return None, err
    try:
        data = resp.json()
        return data["result"]["alternatives"][0]["message"]["text"], None
    except (KeyError, IndexError, ValueError) as e:
        return None, f"[YandexGPT] Ошибка разбора ответа: {e}"


def call_deepseek(user_message, context):
    url = f"{config.DEEPSEEK_BASE_URL}/chat/completions"
    return _call_openai_compatible(url, config.DEEPSEEK_API_KEY, config.DEEPSEEK_MODEL,
                                   user_message, context, "DeepSeek")


def call_openrouter(user_message, context, model=None):
    url = f"{config.OPENROUTER_BASE_URL}/chat/completions"
    model = model or config.OPENROUTER_MODEL
    return _call_openai_compatible(url, config.OPENROUTER_API_KEY, model,
                                   user_message, context, f"OpenRouter/{model}")


def call_openrouter_with_fallback(user_message, context):
    models = [config.OPENROUTER_MODEL] + [
        m for m in getattr(config, "OPENROUTER_FALLBACK_MODELS", [])
        if m != config.OPENROUTER_MODEL
    ]
    errors = []
    for model in models:
        log.info(f"Попытка: {model}")
        answer, err = call_openrouter(user_message, context, model=model)
        if answer:
            return answer, model
        errors.append(f"{model}: {err}")
        log.warning(f"Модель {model} не сработала, пробуем следующую...")

    return f"Все модели недоступны. Попробуйте позже.\n\nДетали: {' | '.join(errors)}", "none"


def call_llm(user_message, context):
    provider = config.LLM_PROVIDER.lower()

    if provider == "yandex":
        answer, err = call_yandex_gpt(user_message, context)
        return (answer, "yandex") if answer else (err, "yandex/error")

    elif provider == "deepseek":
        answer, err = call_deepseek(user_message, context)
        if answer:
            return answer, "deepseek"
        if getattr(config, "OPENROUTER_API_KEY", ""):
            log.warning("DeepSeek недоступен, fallback на OpenRouter")
            return call_openrouter_with_fallback(user_message, context)
        return err, "deepseek/error"

    elif provider == "openrouter":
        return call_openrouter_with_fallback(user_message, context)

    return f"Неизвестный провайдер: {provider}", "error"


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "provider": config.LLM_PROVIDER})


@app.route("/ask", methods=["POST"])
def ask():
    try:
        body = request.get_json(force=True, silent=True) or {}
        question = body.get("question", "").strip()
        docs = body.get("documents", [])

        if not question:
            return jsonify({"error": "Пустой вопрос"}), 400

        if not docs:
            return jsonify({
                "answer": "По вашему запросу не найдено релевантных документов. Попробуйте переформулировать вопрос.",
                "provider": config.LLM_PROVIDER,
                "sources": [],
            })

        context = build_context(docs)
        answer, provider_used = call_llm(question, context)

        sources = [{"document_id": d["document_id"], "title": d["title"]} for d in docs]

        return jsonify({"answer": answer, "provider": provider_used, "sources": sources})

    except Exception as e:
        log.exception("Ошибка в /ask")
        return jsonify({"error": f"Внутренняя ошибка: {e}"}), 500


if __name__ == "__main__":
    provider = config.LLM_PROVIDER
    log.info(f"Провайдер: {provider}")

    if provider == "yandex" and not config.YANDEX_API_KEY:
        log.warning("YANDEX_API_KEY не задан!")
    elif provider == "deepseek" and not config.DEEPSEEK_API_KEY:
        log.warning("DEEPSEEK_API_KEY не задан!")
    elif provider == "openrouter" and not config.OPENROUTER_API_KEY:
        log.warning("OPENROUTER_API_KEY не задан!")

    if provider == "openrouter":
        log.info(f"Модель: {config.OPENROUTER_MODEL}")
        log.info(f"Fallback: {getattr(config, 'OPENROUTER_FALLBACK_MODELS', [])}")

    log.info(f"Retry: {config.LLM_MAX_RETRIES}x, backoff: {config.LLM_RETRY_BACKOFF}s, timeout: {config.LLM_REQUEST_TIMEOUT}s")
    log.info(f"Запуск на {config.LLM_SERVICE_HOST}:{config.LLM_SERVICE_PORT}")
    app.run(host=config.LLM_SERVICE_HOST, port=config.LLM_SERVICE_PORT, debug=False)
