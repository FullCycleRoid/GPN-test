import json
import math
import re
import os
import sys
import logging
from collections import Counter
from flask import Flask, request, jsonify

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config

app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("SearchService")

documents = []
inverted_index = {}
doc_lengths = []
avg_doc_length = 0.0


def simple_stem(word):
    if len(word) <= 3:
        return word
    suffixes = [
        "ского", "ённый", "ённых", "ённом",
        "ивать", "овать", "ывать",
        "ениям", "ением", "ениях", "ений",
        "ности", "ность",
        "ация", "яция", "ении", "ения",
        "ский", "ская", "ское", "ские",
        "тель", "ёнок", "ённ",
        "ным", "ных", "ной", "ного", "ному",
        "ать", "ить", "еть", "уть",
        "ами", "ями", "ием", "ией",
        "ого", "ому", "ную", "ной",
        "ов", "ев", "ей", "ий", "ый", "ая", "ое", "ые", "ие",
        "ам", "ям", "ом", "ем", "им", "ях", "ах", "ую",
        "ок", "ек", "ик",
        "ей", "ью",
        "ть", "ся",
        "а", "о", "е", "и", "у", "ы", "я",
    ]
    for suffix in suffixes:
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[:-len(suffix)]
    return word


def tokenize(text):
    tokens = re.findall(r"[а-яёa-z0-9]+", text.lower())
    return [simple_stem(t) for t in tokens]


def build_index(docs):
    global inverted_index, doc_lengths, avg_doc_length
    inverted_index = {}
    doc_lengths = []

    for idx, doc in enumerate(docs):
        full_text = " ".join([
            doc.get("title", "") or "",
            doc.get("text", "") or "",
            " ".join(doc.get("tags", [])),
            doc.get("department", "") or "",
            doc.get("doc_type", "") or "",
        ])
        tokens = tokenize(full_text)
        doc_lengths.append(len(tokens))
        term_freq = Counter(tokens)

        for term, freq in term_freq.items():
            if term not in inverted_index:
                inverted_index[term] = {}
            inverted_index[term][idx] = freq

    avg_doc_length = sum(doc_lengths) / len(doc_lengths) if doc_lengths else 1.0


def bm25_search(query, top_k=3):
    k1, b = 1.5, 0.75
    n_docs = len(documents)

    query_tokens = tokenize(query)
    if not query_tokens:
        return []

    scores = {}
    for token in query_tokens:
        if token not in inverted_index:
            continue
        posting = inverted_index[token]
        df = len(posting)
        idf = math.log((n_docs - df + 0.5) / (df + 0.5) + 1.0)

        for doc_idx, tf in posting.items():
            dl = doc_lengths[doc_idx]
            tf_norm = (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * dl / avg_doc_length))
            scores[doc_idx] = scores.get(doc_idx, 0.0) + idf * tf_norm

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]

    results = []
    for doc_idx, score in ranked:
        doc = documents[doc_idx]
        results.append({
            "document_id": doc["document_id"],
            "title": doc["title"],
            "doc_type": doc.get("doc_type", ""),
            "department": doc.get("department", ""),
            "text": doc["text"],
            "tags": doc.get("tags", []),
            "score": round(score, 4),
        })
    return results


def load_documents():
    global documents
    data_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", config.DATA_PATH))
    log.info(f"Загрузка документов из {data_path}")

    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    documents = data.get("documents", [])
    log.info(f"Загружено документов: {len(documents)}")

    build_index(documents)
    log.info(f"Индекс построен, термов: {len(inverted_index)}")


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "documents_count": len(documents)})


@app.route("/search", methods=["POST"])
def search():
    try:
        body = request.get_json(force=True, silent=True) or {}
        query = body.get("query", "").strip()
        top_k = body.get("top_k", config.SEARCH_TOP_K)

        if not query:
            return jsonify({"error": "Пустой запрос"}), 400

        results = bm25_search(query, top_k=top_k)
        return jsonify({"query": query, "results": results, "total_found": len(results)})
    except Exception as e:
        log.exception("Ошибка в /search")
        return jsonify({"error": f"Внутренняя ошибка: {e}"}), 500


@app.route("/reload", methods=["POST"])
def reload_data():
    load_documents()
    return jsonify({"status": "reloaded", "documents_count": len(documents)})


if __name__ == "__main__":
    load_documents()
    log.info(f"Запуск на {config.SEARCH_SERVICE_HOST}:{config.SEARCH_SERVICE_PORT}")
    app.run(host=config.SEARCH_SERVICE_HOST, port=config.SEARCH_SERVICE_PORT, debug=False)
