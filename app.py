# app.py — Login-protected flashcards with basic usage tracking

import os
import json
import sqlite3
import uuid
import hashlib
from datetime import datetime
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
    session,
    g,
)

# --- Paths / config ---------------------------------------------------------

ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"
CARDS_DIR = STATIC_DIR / "cards"
DATA_DIR = ROOT / "data"
CARDS_JSON = DATA_DIR / "cards.json"

DB_PATH = os.environ.get("DB_PATH", str(ROOT / "app.db"))
BUILD_ID = os.environ.get("BUILD_ID", str(uuid.uuid4())[:8])

app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="/static")
app.secret_key = os.environ.get("FLASK_SECRET", "dev-secret-change-me")

# --- Bootstrap dirs ---------------------------------------------------------

STATIC_DIR.mkdir(parents=True, exist_ok=True)
CARDS_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

# --- Helpers ----------------------------------------------------------------

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

# --- DB + users -------------------------------------------------------------

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def verify_password(password: str, password_hash: str) -> bool:
    return hash_password(password) == password_hash

def find_user_by_email(email: str) -> Optional[sqlite3.Row]:
    db = get_db()
    cur = db.execute(
        "SELECT * FROM users WHERE email = ? AND is_active = 1",
        (email.strip().lower(),),
    )
    return cur.fetchone()

def create_user(email: str, raw_password: str) -> int:
    email_norm = email.strip().lower()
    if not email_norm:
        raise ValueError("email is required")
    if not raw_password:
        raise ValueError("password is required")

    db = get_db()
    cur = db.execute(
        """
        INSERT INTO users (email, password_hash, is_active, created_at)
        VALUES (?, ?, 1, ?)
        """,
        (email_norm, hash_password(raw_password), datetime.utcnow().isoformat()),
    )
    db.commit()
    return cur.lastrowid

def init_db():
    db = get_db()

    # Users table
    db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        )
    """)

    # Basic usage tracking: one row per login event
    db.execute("""
        CREATE TABLE IF NOT EXISTS login_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            ts TEXT NOT NULL,
            ip TEXT,
            user_agent TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)

    db.commit()

    # Bootstrap: if no users exist, create one so you can log in
    cur = db.execute("SELECT COUNT(*) AS c FROM users")
    count = cur.fetchone()["c"]
    if count == 0:
        bootstrap_email = os.environ.get(
            "BOOTSTRAP_USER_EMAIL",
            "owner@example.com",
        ).strip().lower()
        bootstrap_password = os.environ.get(
            "BOOTSTRAP_USER_PASSWORD",
            "changeme123",
        )

        if bootstrap_email and bootstrap_password:
            db.execute(
                """
                INSERT INTO users (email, password_hash, is_active, created_at)
                VALUES (?, ?, 1, ?)
                """,
                (
                    bootstrap_email,
                    hash_password(bootstrap_password),
                    datetime.utcnow().isoformat(),
                ),
            )
            db.commit()
            print(
                f"[{BUILD_ID}] Bootstrap user created: "
                f"{bootstrap_email} / {bootstrap_password}"
            )

with app.app_context():
    init_db()

# --- Login UI ---------------------------------------------------------------

LOGIN_HTML = """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>Private Pilot Flashcards – Login</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
      body {
        font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        padding: 2rem;
        background: #f5f5f5;
      }
      .card {
        max-width: 400px;
        margin: 3rem auto;
        background: #ffffff;
        padding: 2rem;
        border-radius: 8px;
        box-shadow: 0 2px 6px rgba(0,0,0,.1);
      }
      label {
        display: block;
        margin-top: 1rem;
      }
      input {
        width: 100%;
        padding: 0.5rem;
        margin-top: 0.25rem;
        box-sizing: border-box;
      }
      button {
        margin-top: 1.5rem;
        padding: 0.6rem 1.2rem;
        cursor: pointer;
      }
      .error {
        color: #c00;
        margin-top: 0.5rem;
      }
    </style>
  </head>
  <body>
    <div class="card">
      <h1>Sign in</h1>
      <p>Enter the email and password you received after purchase.</p>
      {% if error %}
        <div class="error">{{ error }}</div>
      {% endif %}
      <form method="post">
        <label>Email
          <input type="email" name="email" value="{{ email or '' }}" required>
        </label>
        <label>Password
          <input type="password" name="password" required>
        </label>
        <button type="submit">Sign in</button>
      </form>
    </div>
  </body>
</html>
"""

from flask import render_template_string  # placed here to avoid cluttering the main import

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        user = find_user_by_email(email)

        if not user or not verify_password(password, user["password_hash"]):
            return (
                render_template_string(
                    LOGIN_HTML,
                    error="Invalid email or password",
                    email=email,
                ),
                401,
            )

        # Track login event for theft/usage analysis
        db = get_db()
        db.execute(
            """
            INSERT INTO login_events (user_id, ts, ip, user_agent)
            VALUES (?, ?, ?, ?)
            """,
            (
                int(user["id"]),
                datetime.utcnow().isoformat(),
                request.headers.get("X-Forwarded-For", request.remote_addr),
                request.headers.get("User-Agent", ""),
            ),
        )
        db.commit()

        session["user_id"] = int(user["id"])
        session["user_email"] = user["email"]
        return redirect("/")

    # GET
    if session.get("user_id"):
        return redirect("/")
    return render_template_string(LOGIN_HTML, error=None, email="")

@app.route("/logout", methods=["GET", "POST"])
def logout():
    session.clear()
    return redirect("/login")

# --- Auth guard: protect UI + API unless logged in --------------------------

@app.before_request
def require_login():
    path = request.path

    # Always allow static files, login/logout, logo, and health checks
    if (
        path.startswith("/static/")
        or path.startswith("/cards/")
        or path == "/logo.jpg"
        or path == "/login"
        or path == "/logout"
        or path == "/health"
    ):
        return None

    # Already logged in?
    if session.get("user_id"):
        return None

    # Block API for guests
    if path.startswith("/api/"):
        return jsonify({"error": "Unauthorized"}), 401

    # Everything else (/, client routes) -> login
    return redirect("/login")

@app.route("/health")
def health():
    return jsonify({"status": "ok", "build": BUILD_ID})

# --- Cards loader -----------------------------------------------------------

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

# --- Static assets ----------------------------------------------------------

@app.route("/logo.jpg")
def serve_logo():
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

# --- UI shell (SPA) ---------------------------------------------------------

@app.route("/")
def index():
    resp = make_response(send_from_directory(app.static_folder, "index.html"))
    return _nocache(resp)

@app.route("/index.html")
def index_html():
    return redirect("/")

@app.route("/<path:maybe_client_route>")
def spa_fallback(maybe_client_route):
    if not maybe_client_route.startswith("api/"):
        resp = make_response(send_from_directory(app.static_folder, "index.html"))
        return _nocache(resp)
    return jsonify({"error": "Not found"}), 404

# --- API --------------------------------------------------------------------

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

@app.route("/api/categories", methods=["GET"])
def api_categories():
    cards = load_cards()
    cats = sorted({
        str(c.get("category", "")).strip()
        for c in cards
        if str(c.get("category", "")).strip()
    })
    return jsonify(cats)

# Stub endpoints for future per-user state, currently no-ops
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

# --- Entrypoint -------------------------------------------------------------

if __name__ == "__main__":
    host = os.environ.get("FLASK_HOST", "127.0.0.1")
    port = int(os.environ.get("FLASK_PORT", "5000"))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    print(f"[{BUILD_ID}] UI:    http://{host}:{port}/")
    print(f"[{BUILD_ID}] API:   http://{host}:{port}/api")
    print(f"[{BUILD_ID}] Files: http://{host}:{port}/cards/<file>  -> {CARDS_DIR}")
    print(f"[{BUILD_ID}] Logo:  http://{host}:{port}/logo.jpg      -> {STATIC_DIR/'logo.jpg'}")
    app.run(host=host, port=port, debug=debug)
