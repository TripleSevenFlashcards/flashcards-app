import os
import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from flask import Flask, jsonify, send_from_directory, request, make_response

# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "app.db"))  # override via env if needed

# Try loading .env if python-dotenv is available; otherwise ignore.
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
    DB_PATH = os.getenv("DB_PATH", DB_PATH)
except Exception:
    pass

app = Flask(
    __name__,
    static_folder=str(STATIC_DIR),
    static_url_path="/static"
)

# -----------------------------------------------------------------------------
# Data access
# -----------------------------------------------------------------------------
CARD_COL_CANDIDATES = {
    "question": {"question", "q", "front", "prompt"},
    "answer": {"answer", "a", "back", "response"},
    "category": {"category", "cat", "section", "topic"},
    "tags": {"tags", "tag", "keywords"},
}

def _connect() -> Optional[sqlite3.Connection]:
    if not DB_PATH or not Path(DB_PATH).exists():
        return None
    try:
        con = sqlite3.connect(DB_PATH)
        con.row_factory = sqlite3.Row
        return con
    except Exception:
        return None

def _table_and_mapping(con: sqlite3.Connection) -> Optional[Tuple[str, Dict[str, str]]]:
    """
    Find a table that looks like a flashcards table by checking for likely columns.
    Returns (table_name, column_map), where column_map maps canonical keys
    ('question','answer','category','tags') to actual column names in the table.
    """
    cur = con.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]
    for t in tables:
        try:
            cur.execute(f"PRAGMA table_info('{t}')")
            cols = [row[1] for row in cur.fetchall()]
            lower_cols = {c.lower(): c for c in cols}  # map lowercase -> original case
            colmap: Dict[str, str] = {}
            ok = True
            # Require at least question + answer
            for key in ("question", "answer", "category", "tags"):
                found = None
                for candidate in CARD_COL_CANDIDATES[key]:
                    if candidate in lower_cols:
                        found = lower_cols[candidate]
                        break
                if key in ("question", "answer") and not found:
                    ok = False
                    break
                if found:
                    colmap[key] = found
            if ok:
                return t, colmap
        except Exception:
            continue
    return None

def load_cards_from_db() -> Optional[List[Dict]]:
    con = _connect()
    if not con:
        return None
    try:
        probe = _table_and_mapping(con)
        if not probe:
            return None
        table, cmap = probe

        # Build SELECT with available columns; missing fields become NULL
        select_parts = []
        select_parts.append(f"{cmap['question']} AS question")
        select_parts.append(f"{cmap['answer']} AS answer")
        if "category" in cmap:
            select_parts.append(f"{cmap['category']} AS category")
        else:
            select_parts.append("NULL AS category")
        if "tags" in cmap:
            select_parts.append(f"{cmap['tags']} AS tags")
        else:
            select_parts.append("NULL AS tags")

        sql = f"SELECT {', '.join(select_parts)} FROM '{table}'"
        rows = con.execute(sql).fetchall()

        out: List[Dict] = []
        for r in rows:
            q = (r["question"] or "").strip()
            a = (r["answer"] or "").strip()
            cat = (r["category"] or "").strip() if "category" in r.keys() else ""
            raw_tags = r["tags"] if "tags" in r.keys() else None

            tags: List[str] = []
            if isinstance(raw_tags, str) and raw_tags.strip():
                # split on comma/semicolon
                parts = [p.strip() for p in raw_tags.replace(";", ",").split(",")]
                tags = [p for p in parts if p]

            out.append({
                "question": q,
                "answer": a,
                "category": cat,
                "tags": tags
            })
        return out
    except Exception:
        return None
    finally:
        try:
            con.close()
        except Exception:
            pass

def load_cards_from_json() -> Optional[List[Dict]]:
    json_path = STATIC_DIR / "cards.json"
    if not json_path.exists():
        return None
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        out: List[Dict] = []
        for c in data if isinstance(data, list) else []:
            out.append({
                "question": str(c.get("question") or c.get("q") or "").strip(),
                "answer": str(c.get("answer") or c.get("a") or "").strip(),
                "category": str(c.get("category") or "").strip(),
                "tags": c.get("tags") or []
            })
        return out
    except Exception:
        return None

def load_cards() -> List[Dict]:
    # Priority: DB -> static/cards.json -> empty
    cards = load_cards_from_db()
    if cards is None:
        cards = load_cards_from_json()
    return cards or []

# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------
@app.after_request
def add_no_cache_headers(resp):
    # Ensure fresh data while iterating; adjust as needed.
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp

@app.route("/")
def index():
    # Serve the static SPA shell
    return send_from_directory(app.static_folder, "index.html")

@app.route("/health")
def health():
    return jsonify({"ok": True})

@app.route("/api/cards")
def api_cards():
    cards = load_cards()
    return jsonify(cards)

@app.route("/api/categories")
def api_categories():
    cards = load_cards()
    cats = sorted({(c.get("category") or "").strip() for c in cards if (c.get("category") or "").strip()})
    return jsonify(cats)

# Optional: serve other top-level routes to index.html if needed for SPA routing.
@app.errorhandler(404)
def not_found(e):
    # If the path looks like a file, keep 404. Otherwise, serve index for SPA routes.
    p = request.path
    if "." in p.split("/")[-1]:
        return e
    try:
        return send_from_directory(app.static_folder, "index.html")
    except Exception:
        return e

# -----------------------------------------------------------------------------
# Entry
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=os.getenv("FLASK_DEBUG", "0") == "1")
