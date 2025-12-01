# app.py — Public (no login), serve HTML + /logo.jpg + /cards/**

import os
import json
import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional

from flask import (
    Flask,
    request,
    jsonify,
    send_from_directory,
    abort,
    make_response,
    redirect,
)

ROOT       = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"
CARDS_DIR  = STATIC_DIR / "cards"
DATA_DIR   = ROOT / "data"
CARDS_JSON = DATA_DIR / "cards.json"
BUILD_ID   = os.environ.get("BUILD_ID", str(uuid.uuid4())[:8])

app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="/static")

# --- Bootstrap
STATIC_DIR.mkdir(parents=True, exist_ok=True)
CARDS_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

def _nocache(resp):
    resp.cache_control.no_store = True
    resp.cache_control.max_age = 0
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp

@app.before_request
def _log_req():
    print(
        f"[{BUILD_ID}] {request.method} {request.path} "
        f"Accept={request.headers.get('Accept','')} "
        f"Sec-Fetch-Mode={request.headers.get('Sec-Fetch-Mode','')}"
    )

# --- Cards loader
_cards_cache: Optional[List[Dict[str, Any]]] = None

def load_cards() -> List[Dict[str, Any]]:
    global _cards_cache
    if _cards_cache is not None:
        return _cards_cache

    if not CARDS_JSON.exists():
        _cards_cache = [{
            "id": 999,
            "category": "Demo",
            "question": "Demo Q",
            "image": "/cards/demo_front.jpg",
            "answer": "Demo A",
            "answer_image": "/cards/demo_back.jpg",
            "url": ""
        }]
        return _cards_cache

    with CARDS_JSON.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("cards.json must be a list")

    for c in data:
        c.setdefault("id", None)
        c.setdefault("category", "")
        c.setdefault("question", "")
        c.setdefault("image", "")
        c.setdefault("answer", "")
        c.setdefault("answer_image", "")
        c.setdefault("url", "")

    _cards_cache = data
    return _cards_cache

# --- Routes to serve your assets exactly as referenced by your HTML

@app.route("/logo.jpg")
def serve_logo():
    # Your HTML uses /logo.jpg at the root; serve static/logo.jpg here.
    path = STATIC_DIR / "logo.jpg"
    if not path.exists():
        abort(404)
    return send_from_directory(str(STATIC_DIR), "logo.jpg")

@app.route("/cards/<path:filename>")
def serve_card_file(filename):
    file_path = CARDS_DIR / filename
    if not file_path.exists() or not file_path.is_file():
        abort(404)
    return send_from_directory(str(CARDS_DIR), filename)

# --- UI (shell HTML) with no-cache so updates show immediately

@app.route("/")
def index():
    resp = make_response(send_from_directory(app.static_folder, "index.html"))
    return _nocache(resp)

@app.route("/index.html")
def index_html():
    return redirect("/")

# SPA fallback for any non-API path
@app.route("/<path:maybe_client_route>")
def spa_fallback(maybe_client_route):
    if not maybe_client_route.startswith("api/"):
        resp = make_response(send_from_directory(app.static_folder, "index.html"))
        return _nocache(resp)
    return jsonify({"error": "Not found"}), 404

# --- API (your HTML uses only /api/cards)

@app.route("/api/cards", methods=["GET"])
def api_get_cards():
    # If someone navigates here in the address bar, bounce back to UI.
    if request.headers.get("Sec-Fetch-Mode", "") == "navigate":
        return redirect("/", code=302)

    cards = load_cards()
    categories_param = request.args.get("categories", "").strip()
    if categories_param:
        wanted = {c for c in categories_param.split(",") if c}
        cards = [
            c for c in cards
            if str(c.get("category", "")).strip() in wanted
        ]
    return jsonify(cards)

# Optional endpoints kept as harmless stubs
@app.route("/api/state", methods=["GET"])
def api_get_state():
    return jsonify({
        "current_index": 0,
        "correct": 0,
        "incorrect": 0,
        "seen": 0,
        "deck_order": [],
        "category_filters": []
    })

@app.route("/api/state", methods=["POST"])
def api_set_state():
    return jsonify({"ok": True})

@app.route("/api/restart", methods=["POST"])
def api_restart():
    return jsonify({"ok": True})

@app.route("/api/hide", methods=["POST"])
def api_hide():
    return jsonify({"ok": True})

@app.route("/api/unhide_all", methods=["POST"])
def api_unhide_all():
    return jsonify({"ok": True})

@app.route("/api/categories", methods=["GET"])
def api_categories():
    cards = load_cards()
    cats = sorted({
        str(c.get("category", "")).strip()
        for c in cards
        if str(c.get("category", "")).strip()
    })
    return jsonify(cats)

# --- Entrypoint

if __name__ == "__main__":
    host = os.environ.get("FLASK_HOST", "127.0.0.1")
    port = int(os.environ.get("FLASK_PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    print(f"[{BUILD_ID}] UI:    http://{host}:{port}/")
    print(f"[{BUILD_ID}] API:   http://{host}:{port}/api")
    print(f"[{BUILD_ID}] Files: http://{host}:{port}/cards/<file>  -> {CARDS_DIR}")
    print(f"[{BUILD_ID}] Logo:  http://{host}:{port}/logo.jpg      -> {STATIC_DIR/'logo.jpg'}")
    app.run(host=host, port=port, debug=debug)
