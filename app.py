# app.py — Flask app for Render (works with `gunicorn app:app`)
import os
import json
from pathlib import Path
from flask import Flask, send_from_directory, jsonify, make_response, abort

# --- Paths & env
ROOT        = Path(__file__).resolve().parent
STATIC_DIR  = ROOT / "static"
CARDS_DIR   = STATIC_DIR / "cards"
DATA_DIR    = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
CARDS_JSON  = DATA_DIR / "cards.json"
DB_PATH     = os.environ.get("DB_PATH", str(ROOT / "app.db"))  # kept for future use

app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="/static")

# --- Minimal default deck if data/cards.json is missing
DEFAULT_DECK = [
    {"id": 1, "front": "What does ‘IM SAFE’ stand for?", "back": "Illness, Medication, Stress, Alcohol, Fatigue, Emotion/Eating"},
    {"id": 2, "front": "VFR weather minima (Class E, <10,000’ MSL)?", "back": "3 SM, 500 below, 1,000 above, 2,000 horizontal"},
]

def load_cards():
    if CARDS_JSON.exists():
        try:
            with CARDS_JSON.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list) and data:
                return data
        except Exception:
            pass
    return DEFAULT_DECK

# --- HTML UI
INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Flashcards</title>
<link rel="icon" href="/logo.jpg">
<style>
:root { --bg:#0b1b34; --panel:#12284d; --ink:#e7eefc; --muted:#a9b8d9; --accent:#6aa9ff; }
* { box-sizing:border-box; }
html, body { height:100%; }
body {
  margin:0; font-family: system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif;
  color: var(--ink);
  background: radial-gradient(1200px 600px at 20% -10%, #1a3d7a 0%, transparent 60%),
              radial-gradient(900px 500px at 110% 20%, #0e213f 0%, transparent 55%),
              linear-gradient(180deg, #081427 0%, #0b1b34 60%, #0a1830 100%);
}
.header {
  display:flex; align-items:center; gap:.75rem; padding:1rem 1.25rem; border-bottom:1px solid rgba(255,255,255,.06);
  backdrop-filter: blur(4px);
}
.header img { width:32px; height:32px; border-radius:6px; }
.header .title { font-weight:700; letter-spacing:.2px; }
.wrapper { max-width:960px; margin:2rem auto; padding:0 1rem; }
.panel {
  background: linear-gradient(180deg, rgba(255,255,255,.06), rgba(255,255,255,.03));
  border:1px solid rgba(255,255,255,.12); border-radius:16px; padding:1.25rem; box-shadow: 0 10px 30px rgba(0,0,0,.25);
}
.controls { display:flex; gap:.5rem; flex-wrap:wrap; margin-bottom:1rem; }
button {
  border:1px solid rgba(255,255,255,.15); background:rgba(255,255,255,.06);
  color:var(--ink); padding:.6rem .9rem; border-radius:12px; cursor:pointer;
}
button:hover { background:rgba(255,255,255,.12); }
.card {
  display:flex; align-items:center; justify-content:center; text-align:center; min-height:220px;
  border:1px dashed rgba(255,255,255,.2); border-radius:14px; padding:1.25rem; font-size:1.25rem;
}
.meta { margin-top:.75rem; color:var(--muted); font-size:.9rem; }
.badge { display:inline-block; padding:.2rem .5rem; border:1px solid rgba(255,255,255,.2); border-radius:999px; font-size:.8rem; }
.footer { text-align:center; color:var(--muted); font-size:.85rem; padding:2rem 0; }
</style>
</head>
<body>
  <div class="header">
    <img src="/logo.jpg" alt="logo" />
    <div class="title">Flashcards</div>
    <div class="badge" style="margin-left:auto;">Render</div>
  </div>
  <div class="wrapper">
    <div class="panel">
      <div class="controls">
        <button id="prev">Prev</button>
        <button id="flip">Flip</button>
        <button id="next">Next</button>
      </div>
      <div id="card" class="card">Loading…</div>
      <div class="meta"><span id="pos">0/0</span></div>
    </div>
    <div class="footer">Serving <code>/logo.jpg</code> and files under <code>/static/cards/…</code>. Data from <code>/api/cards</code>.</div>
  </div>
<script>
let cards=[], i=0, back=false;
async function load(){ try{
  const r = await fetch('/api/cards'); cards = await r.json();
  if(!Array.isArray(cards) || cards.length===0) cards=[{front:'No cards', back:'Add data/cards.json'}];
  i=0; back=false; render();
}catch(e){ document.getElementById('card').textContent='Failed to load cards.'; } }
function render(){
  const c = cards[i]||{front:'—',back:'—'};
  document.getElementById('card').textContent = back ? (c.back||'') : (c.front||'');
  document.getElementById('pos').textContent = `${i+1}/${cards.length}`;
}
document.getElementById('prev').onclick = ()=>{ i=(i-1+cards.length)%cards.length; back=false; render(); };
document.getElementById('next').onclick = ()=>{ i=(i+1)%cards.length; back=false; render(); };
document.getElementById('flip').onclick = ()=>{ back=!back; render(); };
load();
</script>
</body>
</html>
"""

# --- Routes
@app.get("/")
def index():
    return make_response(INDEX_HTML, 200, {"Content-Type": "text/html; charset=utf-8"})

@app.get("/logo.jpg")
def logo():
    if not (STATIC_DIR / "logo.jpg").exists():
        abort(404)
    return send_from_directory(STATIC_DIR, "logo.jpg")

@app.get("/cards/<path:filename>")
def cards_static(filename: str):
    path = CARDS_DIR / filename
    if not path.exists():
        abort(404)
    return send_from_directory(CARDS_DIR, filename)

@app.get("/api/cards")
def api_cards():
    return jsonify(load_cards())

# --- Entrypoint for local dev (Render uses gunicorn)
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("FLASK_PORT", "5000")), debug=True)
