import os
import sys
import time
import logging
import requests as http_requests
from flask import Flask, request, jsonify, render_template_string

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config

app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("WebClient")


def _service_request(method, url, *, json_body=None, timeout=10, label="service"):
    max_retries = config.SERVICE_MAX_RETRIES
    backoff = config.SERVICE_RETRY_BACKOFF
    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            resp = http_requests.request(method, url, json=json_body, timeout=timeout)
            resp.raise_for_status()
            return resp.json(), None
        except http_requests.exceptions.ConnectionError as e:
            last_error = f"Сервис недоступен: {e}"
        except http_requests.exceptions.Timeout:
            last_error = f"Таймаут ({timeout}с)"
        except http_requests.exceptions.HTTPError as e:
            last_error = f"HTTP {e.response.status_code}"
            if e.response.status_code < 500 and e.response.status_code != 429:
                return None, f"[{label}] {last_error}"
        except Exception as e:
            last_error = str(e)
            return None, f"[{label}] {last_error}"

        if attempt < max_retries:
            delay = backoff * (2 ** (attempt - 1))
            log.warning(f"[{label}] Попытка {attempt}/{max_retries} — {last_error}, повтор через {delay:.1f}с")
            time.sleep(delay)

    log.error(f"[{label}] Все {max_retries} попыток исчерпаны: {last_error}")
    return None, f"[{label}] {last_error}"


HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Поиск по документам | Внутренний портал</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Nunito:wght@400;600;700&display=swap');
        * { margin: 0; padding: 0; box-sizing: border-box; }
        :root {
            --bg: #0f1117; --surface: #1a1d27; --surface2: #242834;
            --border: #2e3345; --text: #e2e4eb; --text-dim: #8b90a0;
            --accent: #5b9bf5; --accent-glow: rgba(91,155,245,0.15);
            --green: #4ade80; --orange: #f59e0b; --red: #ef4444;
        }
        body { font-family: 'Nunito', sans-serif; background: var(--bg); color: var(--text); min-height: 100vh; display: flex; flex-direction: column; }
        header { background: var(--surface); border-bottom: 1px solid var(--border); padding: 16px 24px; display: flex; align-items: center; gap: 12px; }
        header .logo { width: 36px; height: 36px; background: linear-gradient(135deg, var(--accent), #8b5cf6); border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 18px; font-weight: 700; color: #fff; }
        header h1 { font-size: 18px; font-weight: 700; }
        header .badge { margin-left: auto; font-family: 'JetBrains Mono', monospace; font-size: 11px; padding: 4px 10px; border-radius: 6px; background: var(--surface2); border: 1px solid var(--border); color: var(--text-dim); }
        .container { max-width: 860px; width: 100%; margin: 0 auto; padding: 24px; flex: 1; display: flex; flex-direction: column; }
        .chat-area { flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 16px; padding-bottom: 16px; }
        .msg { max-width: 90%; padding: 14px 18px; border-radius: 14px; line-height: 1.6; font-size: 14px; animation: fadeIn .3s ease; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
        .msg.user { align-self: flex-end; background: var(--accent); color: #fff; border-bottom-right-radius: 4px; }
        .msg.reply { align-self: flex-start; background: var(--surface); border: 1px solid var(--border); border-bottom-left-radius: 4px; }
        .msg.reply .source-tag { display: inline-block; font-family: 'JetBrains Mono', monospace; font-size: 11px; background: var(--accent-glow); color: var(--accent); padding: 2px 8px; border-radius: 4px; margin: 4px 4px 0 0; }
        .msg.reply .answer-text { white-space: pre-wrap; }
        .msg.err { align-self: center; background: rgba(239,68,68,0.1); border: 1px solid var(--red); color: var(--red); }
        .input-area { display: flex; gap: 10px; padding-top: 16px; border-top: 1px solid var(--border); }
        .input-area textarea { flex: 1; background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 12px 16px; color: var(--text); font-family: 'Nunito', sans-serif; font-size: 14px; resize: none; outline: none; transition: border-color .2s; min-height: 48px; max-height: 120px; }
        .input-area textarea:focus { border-color: var(--accent); }
        .input-area textarea::placeholder { color: var(--text-dim); }
        .input-area button { background: var(--accent); color: #fff; border: none; border-radius: 12px; padding: 0 20px; font-family: 'Nunito', sans-serif; font-size: 14px; font-weight: 600; cursor: pointer; transition: opacity .2s; white-space: nowrap; }
        .input-area button:hover { opacity: 0.85; }
        .input-area button:disabled { opacity: 0.4; cursor: not-allowed; }
        .dots::after { content: ''; animation: dots 1.5s steps(4, end) infinite; }
        @keyframes dots { 0%{content:''} 25%{content:'.'} 50%{content:'..'} 75%{content:'...'} 100%{content:''} }
        .welcome { text-align: center; margin: auto; padding: 40px; }
        .welcome h2 { font-size: 22px; margin-bottom: 8px; }
        .welcome p { color: var(--text-dim); font-size: 14px; max-width: 420px; margin: 0 auto 20px; line-height: 1.5; }
        .welcome .examples { display: flex; flex-direction: column; gap: 8px; }
        .welcome .examples button { background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 10px 16px; color: var(--text); font-family: 'Nunito', sans-serif; font-size: 13px; cursor: pointer; transition: border-color .2s, background .2s; text-align: left; }
        .welcome .examples button:hover { border-color: var(--accent); background: var(--accent-glow); }
    </style>
</head>
<body>
    <header>
        <div class="logo">Д</div>
        <h1>Поиск по внутренним документам</h1>
        <span class="badge" id="badge"></span>
    </header>
    <div class="container">
        <div class="chat-area" id="chat">
            <div class="welcome" id="welcome">
                <h2>Задайте вопрос по документам</h2>
                <p>Система найдёт релевантные внутренние документы и сформирует ответ с указанием источников.</p>
                <div class="examples">
                    <button onclick="askExample(this)">Какой штраф за просрочку поставки?</button>
                    <button onclick="askExample(this)">Как оформить командировку на месторождение?</button>
                    <button onclick="askExample(this)">Как допустить подрядчика на объект?</button>
                    <button onclick="askExample(this)">Какой срок оплаты по договорам поставки?</button>
                </div>
            </div>
        </div>
        <div class="input-area">
            <textarea id="input" rows="1" placeholder="Введите вопрос..." onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();send()}"></textarea>
            <button id="btn" onclick="send()">Отправить</button>
        </div>
    </div>
    <script>
        const chat = document.getElementById('chat');
        const input = document.getElementById('input');
        const btn = document.getElementById('btn');
        const welcome = document.getElementById('welcome');

        input.addEventListener('input', () => { input.style.height = 'auto'; input.style.height = Math.min(input.scrollHeight, 120) + 'px'; });

        function askExample(b) { input.value = b.textContent; send(); }

        function addMsg(cls, html) {
            if (welcome) welcome.style.display = 'none';
            const d = document.createElement('div');
            d.className = 'msg ' + cls;
            d.innerHTML = html;
            chat.appendChild(d);
            chat.scrollTop = chat.scrollHeight;
            return d;
        }

        function esc(t) { const d = document.createElement('div'); d.textContent = t; return d.innerHTML; }

        async function send() {
            const text = input.value.trim();
            if (!text) return;
            addMsg('user', esc(text));
            input.value = '';
            input.style.height = 'auto';
            btn.disabled = true;

            const el = addMsg('reply', '<span class="dots">Поиск по документам</span>');
            try {
                const r = await fetch('/api/ask', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({question: text}) });
                const data = await r.json();
                if (data.error) { el.className = 'msg err'; el.innerHTML = esc(data.error); }
                else {
                    let h = '<div class="answer-text">' + esc(data.answer) + '</div>';
                    if (data.sources && data.sources.length) {
                        h += '<div style="margin-top:10px">';
                        data.sources.forEach(s => { h += '<span class="source-tag">' + esc(s.document_id) + ': ' + esc(s.title) + '</span> '; });
                        h += '</div>';
                    }
                    el.innerHTML = h;
                }
            } catch (e) { el.className = 'msg err'; el.innerHTML = 'Ошибка соединения: ' + esc(e.message); }
            btn.disabled = false;
            input.focus();
        }

        fetch('/api/health').then(r=>r.json()).then(d=>{
            if(d.search_service&&d.search_service.status==='ok') document.getElementById('badge').textContent='Документов: '+(d.search_service.documents_count||'—');
        }).catch(()=>{});
    </script>
</body>
</html>
"""

SEARCH_URL = f"http://{config.SEARCH_SERVICE_HOST}:{config.SEARCH_SERVICE_PORT}"
LLM_URL = f"http://{config.LLM_SERVICE_HOST}:{config.LLM_SERVICE_PORT}"


@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route("/api/health", methods=["GET"])
def health():
    statuses = {"web_client": "ok"}

    data, err = _service_request("GET", f"{SEARCH_URL}/health", timeout=3, label="search")
    statuses["search_service"] = data if data else {"status": "error", "detail": err}

    data, err = _service_request("GET", f"{LLM_URL}/health", timeout=3, label="llm")
    if data:
        statuses["llm_service"] = data
        statuses["provider"] = data.get("provider", "unknown")
    else:
        statuses["llm_service"] = {"status": "error", "detail": err}

    return jsonify(statuses)


@app.route("/api/ask", methods=["POST"])
def ask():
    try:
        body = request.get_json(force=True, silent=True) or {}
        question = body.get("question", "").strip()

        if not question:
            return jsonify({"error": "Пустой вопрос"}), 400

        search_data, err = _service_request(
            "POST", f"{SEARCH_URL}/search",
            json_body={"query": question, "top_k": config.SEARCH_TOP_K},
            timeout=10, label="search",
        )
        if err:
            return jsonify({"error": f"Сервис поиска недоступен: {err}"}), 502

        documents = search_data.get("results", [])

        llm_data, err = _service_request(
            "POST", f"{LLM_URL}/ask",
            json_body={"question": question, "documents": documents},
            timeout=120, label="llm",
        )
        if err:
            return jsonify({"error": f"Сервис ответов недоступен: {err}"}), 502

        return jsonify({
            "answer": llm_data.get("answer", "Нет ответа"),
            "sources": llm_data.get("sources", []),
        })

    except Exception as e:
        log.exception("Ошибка в /api/ask")
        return jsonify({"error": f"Внутренняя ошибка: {e}"}), 500


if __name__ == "__main__":
    log.info(f"Запуск на http://{config.WEB_CLIENT_HOST}:{config.WEB_CLIENT_PORT}")
    app.run(host=config.WEB_CLIENT_HOST, port=config.WEB_CLIENT_PORT, debug=False)
