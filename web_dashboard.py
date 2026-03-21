"""
Web dashboard for managing bot feedback — password-protected, works on phone/laptop/PC.
Run alongside the bot or as a separate process.
"""
import os
import time
import sqlite3
import secrets
import asyncio
import threading
from pathlib import Path
from functools import wraps

from flask import Flask, request, redirect, url_for, session, jsonify, render_template_string
from dotenv import load_dotenv

load_dotenv()

DB_PATH = Path(__file__).parent / "data" / "feedback.db"
DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "changeme")
SECRET_KEY = os.getenv("FLASK_SECRET_KEY", secrets.token_hex(32))
DASHBOARD_PORT = int(os.getenv("DASHBOARD_PORT", 5000))

app = Flask(__name__)

# Set by bot.py so the dashboard can reload the live knowledge base
_live_knowledge_base = None
_live_ai_handler = None  # Set by bot.py for in-game API

# API key for in-game mod authentication (set in .env as INGAME_API_KEY)
INGAME_API_KEY = os.getenv("INGAME_API_KEY", "")
app.secret_key = SECRET_KEY


# --- DB helpers ---

def _db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def get_feedback(show_resolved=False):
    con = _db()
    clause = "" if show_resolved else "WHERE resolved = 0"
    rows = con.execute(
        f"SELECT * FROM feedback WHERE vote = 'down' {'AND resolved = 0' if not show_resolved else ''} "
        f"ORDER BY created_at DESC LIMIT 50"
    ).fetchall()
    result = [dict(r) for r in rows]
    con.close()
    return result


def get_unanswered_list(show_resolved=False):
    con = _db()
    clause = "WHERE resolved = 0" if not show_resolved else ""
    rows = con.execute(
        f"SELECT * FROM unanswered {clause} ORDER BY created_at DESC LIMIT 50"
    ).fetchall()
    result = [dict(r) for r in rows]
    con.close()
    return result


def get_upvoted(limit=20):
    con = _db()
    rows = con.execute(
        "SELECT * FROM feedback WHERE vote = 'up' ORDER BY created_at DESC LIMIT ?",
        (limit,)
    ).fetchall()
    result = [dict(r) for r in rows]
    con.close()
    return result


def get_stats():
    con = _db()
    up = con.execute("SELECT COUNT(*) FROM feedback WHERE vote = 'up'").fetchone()[0]
    down = con.execute("SELECT COUNT(*) FROM feedback WHERE vote = 'down' AND resolved = 0").fetchone()[0]
    down_total = con.execute("SELECT COUNT(*) FROM feedback WHERE vote = 'down'").fetchone()[0]
    unans = con.execute("SELECT COUNT(*) FROM unanswered WHERE resolved = 0").fetchone()[0]
    resolved = con.execute("SELECT COUNT(*) FROM feedback WHERE vote = 'down' AND resolved = 1").fetchone()[0]
    con.close()
    return {"up": up, "down": down, "down_total": down_total, "unanswered": unans, "resolved": resolved}


def resolve_item(table, item_id):
    con = _db()
    con.execute(f"UPDATE {table} SET resolved = 1 WHERE id = ? AND resolved = 0", (item_id,))
    con.commit()
    con.close()


def unresolve_item(table, item_id):
    con = _db()
    con.execute(f"UPDATE {table} SET resolved = 0 WHERE id = ? AND resolved = 1", (item_id,))
    con.commit()
    con.close()


def resolve_all():
    con = _db()
    c1 = con.execute("UPDATE feedback SET resolved = 1 WHERE vote = 'down' AND resolved = 0").rowcount
    c2 = con.execute("UPDATE unanswered SET resolved = 1 WHERE resolved = 0").rowcount
    con.commit()
    con.close()
    return c1 + c2


# --- Auth ---

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("authenticated"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


# --- Routes ---

@app.route("/login", methods=["GET", "POST"])
def login():
    error = ""
    if request.method == "POST":
        pwd = os.getenv("DASHBOARD_PASSWORD", "changeme")
        if request.form.get("password") == pwd:
            session["authenticated"] = True
            session.permanent = True
            return redirect(url_for("dashboard"))
        error = "Wrong password"
    return render_template_string(LOGIN_HTML, error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def dashboard():
    stats = get_stats()
    downvotes = get_feedback(show_resolved=False)
    unanswered = get_unanswered_list(show_resolved=False)
    upvotes = get_upvoted()
    resolved = get_feedback(show_resolved=True)
    resolved = [r for r in resolved if r.get("resolved", 0) == 1][:20]
    return render_template_string(
        DASHBOARD_HTML,
        stats=stats,
        downvotes=downvotes,
        unanswered=unanswered,
        upvotes=upvotes,
        resolved=resolved,
    )


@app.route("/api/resolve", methods=["POST"])
@login_required
def api_resolve():
    data = request.json
    table = "unanswered" if data.get("type") == "unanswered" else "feedback"
    resolve_item(table, data["id"])
    return jsonify({"ok": True})


@app.route("/api/unresolve", methods=["POST"])
@login_required
def api_unresolve():
    data = request.json
    table = "unanswered" if data.get("type") == "unanswered" else "feedback"
    unresolve_item(table, data["id"])
    return jsonify({"ok": True})


@app.route("/api/resolve-all", methods=["POST"])
@login_required
def api_resolve_all():
    count = resolve_all()
    return jsonify({"ok": True, "count": count})


@app.route("/api/analyze", methods=["POST"])
@login_required
def api_analyze():
    from feedback_agent import analyze_feedback, get_last_analysis
    try:
        loop = asyncio.new_event_loop()
        report = loop.run_until_complete(analyze_feedback())
        loop.close()
        return jsonify({"ok": True, "report": report})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@app.route("/api/last-analysis")
@login_required
def api_last_analysis():
    from feedback_agent import get_last_analysis
    report = get_last_analysis()
    return jsonify({"report": report or "No analysis yet. Click 'Run Analysis' to generate one."})


@app.route("/api/fix", methods=["POST"])
@login_required
def api_fix():
    """AI analyzes a downvoted response and suggests a knowledge base fix."""
    data = request.json
    question = data.get("question", "")
    response = data.get("response", "")

    from groq import AsyncGroq
    client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))

    # Load current knowledge for context
    from knowledge_base import KnowledgeBase
    kb = KnowledgeBase()
    relevant = kb.get_relevant_knowledge(question, max_chars=5000)
    corrections = kb.get_corrections()

    prompt = (
        "A user asked a Hypixel Skyblock bot this question and downvoted the response.\n\n"
        f"QUESTION: {question}\n\n"
        f"BOT RESPONSE (downvoted): {response}\n\n"
        f"CURRENT KNOWLEDGE BASE (relevant sections):\n{relevant}\n\n"
        f"EXISTING CORRECTIONS:\n{corrections}\n\n"
        "Analyze what's wrong with the bot's response. Then provide a fix in this exact format:\n\n"
        "TOPIC: <short topic name, e.g. 'Mining Fortune' or 'Catacombs Gear'>\n"
        "CORRECTION: <the correct information that should be added to the knowledge base, "
        "2-4 sentences max, factual and specific>\n\n"
        "If the response was actually correct and the downvote seems unjustified, respond with:\n"
        "TOPIC: No Fix Needed\nCORRECTION: The response appears accurate."
    )

    try:
        loop = asyncio.new_event_loop()
        resp = loop.run_until_complete(client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {"role": "system", "content": "You are a Hypixel Skyblock expert reviewing bot responses. Be specific and factual."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=500,
            temperature=0.2,
        ))
        loop.close()
        text = resp.choices[0].message.content.strip()

        # Parse TOPIC and CORRECTION
        topic = ""
        correction = ""
        for line in text.split("\n"):
            if line.upper().startswith("TOPIC:"):
                topic = line.split(":", 1)[1].strip()
            elif line.upper().startswith("CORRECTION:"):
                correction = line.split(":", 1)[1].strip()

        if not topic:
            topic = "General"
        if not correction:
            correction = text  # fallback to full response

        return jsonify({"ok": True, "topic": topic, "correction": correction, "full": text})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@app.route("/api/apply-fix", methods=["POST"])
@login_required
def api_apply_fix():
    """Apply an AI-suggested fix to the knowledge base."""
    data = request.json
    topic = data.get("topic", "").strip()
    correction = data.get("correction", "").strip()
    feedback_id = data.get("feedback_id")

    if not topic or not correction:
        return jsonify({"ok": False, "error": "Missing topic or correction"})

    from corrections import apply_to_knowledge
    apply_to_knowledge(topic, correction, "AI Feedback Agent")

    # Reload the bot's live knowledge base so it takes effect immediately
    if _live_knowledge_base:
        _live_knowledge_base.reload()

    # Mark the feedback as resolved
    if feedback_id:
        resolve_item("feedback", feedback_id)

    return jsonify({"ok": True})


# --- HTML Templates ---

LOGIN_HTML = """
<!DOCTYPE html>
<html><head>
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Bot Dashboard - Login</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #1a1a2e; color: #eee; display: flex; justify-content: center;
         align-items: center; min-height: 100vh; }
  .login-box { background: #16213e; padding: 2rem; border-radius: 12px;
               width: 90%; max-width: 360px; text-align: center; }
  .login-box h1 { margin-bottom: 1.5rem; color: #e94560; }
  input[type=password] { width: 100%; padding: 12px; border: 1px solid #333;
                          border-radius: 8px; background: #0f3460; color: #fff;
                          font-size: 16px; margin-bottom: 1rem; }
  button { width: 100%; padding: 12px; border: none; border-radius: 8px;
           background: #e94560; color: #fff; font-size: 16px; cursor: pointer; }
  button:hover { background: #c73650; }
  .error { color: #e94560; margin-bottom: 1rem; }
</style>
</head><body>
<div class="login-box">
  <h1>Bot Dashboard</h1>
  {% if error %}<p class="error">{{ error }}</p>{% endif %}
  <form method="POST">
    <input type="password" name="password" placeholder="Password" autofocus>
    <button type="submit">Login</button>
  </form>
</div>
</body></html>
"""

DASHBOARD_HTML = """
<!DOCTYPE html>
<html><head>
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Bot Dashboard</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #1a1a2e; color: #eee; padding: 1rem; }
  .header { display: flex; justify-content: space-between; align-items: center;
            margin-bottom: 1.5rem; flex-wrap: wrap; gap: 0.5rem; }
  .header h1 { color: #e94560; font-size: 1.5rem; }
  .header-actions { display: flex; gap: 0.5rem; }
  .stats { display: flex; gap: 1rem; margin-bottom: 1.5rem; flex-wrap: wrap; }
  .stat-card { background: #16213e; border-radius: 10px; padding: 1rem 1.5rem;
               flex: 1; min-width: 120px; text-align: center; }
  .stat-card .num { font-size: 2rem; font-weight: bold; }
  .stat-card .label { color: #888; font-size: 0.85rem; margin-top: 0.25rem; }
  .stat-card.down .num { color: #e94560; }
  .stat-card.up .num { color: #4ecca3; }
  .stat-card.unans .num { color: #f5a623; }
  .stat-card.fixed .num { color: #7ec8e3; }

  .tabs { display: flex; gap: 0.5rem; margin-bottom: 1rem; flex-wrap: wrap; }
  .tab { padding: 0.5rem 1rem; border-radius: 8px; cursor: pointer;
         background: #16213e; border: 1px solid #333; color: #aaa; }
  .tab.active { background: #e94560; color: #fff; border-color: #e94560; }

  .section { display: none; }
  .section.active { display: block; }

  .card { background: #16213e; border-radius: 10px; padding: 1rem;
          margin-bottom: 0.75rem; border-left: 4px solid #e94560; }
  .card.up { border-left-color: #4ecca3; }
  .card.resolved { border-left-color: #555; opacity: 0.6; }
  .card .meta { color: #888; font-size: 0.8rem; margin-bottom: 0.5rem; }
  .card .question { color: #fff; font-weight: 600; margin-bottom: 0.5rem; }
  .card .response { color: #aaa; font-size: 0.9rem; margin-bottom: 0.75rem;
                    max-height: 120px; overflow: hidden; transition: max-height 0.3s; }
  .card .response.expanded { max-height: none; }
  .card .expand-btn { color: #e94560; cursor: pointer; font-size: 0.8rem;
                      margin-bottom: 0.5rem; display: inline-block; }
  .card .actions { display: flex; gap: 0.5rem; }

  .btn { padding: 6px 14px; border: none; border-radius: 6px; cursor: pointer;
         font-size: 0.85rem; color: #fff; }
  .btn-resolve { background: #4ecca3; }
  .btn-resolve:hover { background: #3db88f; }
  .btn-unresolve { background: #555; }
  .btn-unresolve:hover { background: #777; }
  .btn-danger { background: #e94560; }
  .btn-danger:hover { background: #c73650; }
  .btn-action { background: #0f3460; }
  .btn-action:hover { background: #1a4a8a; }

  .analysis-box { background: #16213e; border-radius: 10px; padding: 1.5rem;
                  white-space: pre-wrap; font-size: 0.9rem; line-height: 1.5;
                  max-height: 70vh; overflow-y: auto; }

  .empty { text-align: center; color: #555; padding: 2rem; }

  .fix-area { margin: 0.75rem 0; padding: 0.75rem; background: #0f3460;
              border-radius: 8px; }
  .fix-loading { color: #f5a623; }
  .fix-topic { margin-bottom: 0.5rem; }
  .fix-correction { background: #1a1a2e; border: 1px solid #333; border-radius: 6px;
                    padding: 0.75rem; color: #eee; min-height: 60px; font-size: 0.9rem;
                    line-height: 1.4; }
  .fix-correction:focus { border-color: #e94560; outline: none; }

  @media (max-width: 600px) {
    .stat-card { padding: 0.75rem; }
    .stat-card .num { font-size: 1.5rem; }
  }
</style>
</head><body>

<div class="header">
  <h1>Hypixel Bot Dashboard</h1>
  <div class="header-actions">
    <button class="btn btn-action" onclick="runAnalysis()">Run Analysis</button>
    <button class="btn btn-danger" onclick="resolveAll()">Resolve All</button>
    <a href="/logout" class="btn btn-unresolve">Logout</a>
  </div>
</div>

<div class="stats">
  <div class="stat-card up"><div class="num">{{ stats.up }}</div><div class="label">Upvotes</div></div>
  <div class="stat-card down"><div class="num">{{ stats.down }}</div><div class="label">Open Issues</div></div>
  <div class="stat-card unans"><div class="num">{{ stats.unanswered }}</div><div class="label">Unanswered</div></div>
  <div class="stat-card fixed"><div class="num">{{ stats.resolved }}</div><div class="label">Resolved</div></div>
</div>

<div class="tabs">
  <div class="tab active" onclick="switchTab('downvotes')">Downvotes ({{ downvotes|length }})</div>
  <div class="tab" onclick="switchTab('unanswered')">Unanswered ({{ unanswered|length }})</div>
  <div class="tab" onclick="switchTab('upvotes')">Upvotes ({{ upvotes|length }})</div>
  <div class="tab" onclick="switchTab('resolved')">Resolved ({{ resolved|length }})</div>
  <div class="tab" onclick="switchTab('analysis')">Analysis</div>
</div>

<div id="downvotes" class="section active">
  {% if not downvotes %}<div class="empty">No open downvoted responses</div>{% endif %}
  {% for item in downvotes %}
  <div class="card" id="feedback-{{ item.id }}">
    <div class="meta">#{{ item.id }} &middot; {{ item.discord_name }} &middot; {{ item.created_at }}</div>
    <div class="question">Q: {{ item.question }}</div>
    <div class="response" id="resp-{{ item.id }}">A: {{ item.response }}</div>
    <span class="expand-btn" onclick="toggleExpand('resp-{{ item.id }}')">Show more</span>
    <div class="fix-area" id="fix-area-{{ item.id }}" style="display:none;">
      <div class="fix-loading" id="fix-loading-{{ item.id }}">Analyzing...</div>
      <div class="fix-result" id="fix-result-{{ item.id }}" style="display:none;">
        <div class="fix-topic"><strong>Topic:</strong> <span id="fix-topic-{{ item.id }}"></span></div>
        <div class="fix-correction" id="fix-correction-{{ item.id }}" contenteditable="true"></div>
        <div class="actions" style="margin-top:0.5rem;">
          <button class="btn btn-resolve" onclick="applyFix({{ item.id }})">Apply Fix</button>
          <button class="btn btn-unresolve" onclick="dismissFix({{ item.id }})">Dismiss</button>
        </div>
      </div>
    </div>
    <div class="actions">
      <button class="btn btn-action" data-id="{{ item.id }}" data-q="{{ item.question|e }}" data-r="{{ item.response|e }}" onclick="fixWithAI(this.dataset.id, this.dataset.q, this.dataset.r)">Fix with AI</button>
      <button class="btn btn-resolve" onclick="resolveItem('feedback', {{ item.id }})">Mark Resolved</button>
    </div>
  </div>
  {% endfor %}
</div>

<div id="unanswered" class="section">
  {% if not unanswered %}<div class="empty">No unanswered questions</div>{% endif %}
  {% for item in unanswered %}
  <div class="card" id="unanswered-{{ item.id }}">
    <div class="meta">#{{ item.id }} &middot; {{ item.created_at }}</div>
    <div class="question">{{ item.question }}</div>
    <div class="actions">
      <button class="btn btn-resolve" onclick="resolveItem('unanswered', {{ item.id }})">Mark Resolved</button>
    </div>
  </div>
  {% endfor %}
</div>

<div id="upvotes" class="section">
  {% if not upvotes %}<div class="empty">No upvoted responses yet</div>{% endif %}
  {% for item in upvotes %}
  <div class="card up">
    <div class="meta">#{{ item.id }} &middot; {{ item.discord_name }} &middot; {{ item.created_at }}</div>
    <div class="question">Q: {{ item.question }}</div>
    <div class="response" id="up-resp-{{ item.id }}">A: {{ item.response }}</div>
    <span class="expand-btn" onclick="toggleExpand('up-resp-{{ item.id }}')">Show more</span>
  </div>
  {% endfor %}
</div>

<div id="resolved" class="section">
  {% if not resolved %}<div class="empty">No resolved items</div>{% endif %}
  {% for item in resolved %}
  <div class="card resolved">
    <div class="meta">#{{ item.id }} &middot; {{ item.discord_name }} &middot; {{ item.created_at }}</div>
    <div class="question">Q: {{ item.question }}</div>
    <div class="response" id="resolved-resp-{{ item.id }}">A: {{ item.response }}</div>
    <span class="expand-btn" onclick="toggleExpand('resolved-resp-{{ item.id }}')">Show more</span>
    <div class="actions">
      <button class="btn btn-unresolve" onclick="unresolveItem('feedback', {{ item.id }})">Reopen</button>
    </div>
  </div>
  {% endfor %}
</div>

<div id="analysis" class="section">
  <div class="analysis-box" id="analysis-content">Loading...</div>
</div>

<script>
function switchTab(name) {
  document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.getElementById(name).classList.add('active');
  event.target.classList.add('active');
  if (name === 'analysis') loadAnalysis();
}

function toggleExpand(id) {
  const el = document.getElementById(id);
  el.classList.toggle('expanded');
  const btn = el.nextElementSibling;
  btn.textContent = el.classList.contains('expanded') ? 'Show less' : 'Show more';
}

async function resolveItem(type, id) {
  await fetch('/api/resolve', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({type, id})
  });
  const el = document.getElementById((type === 'unanswered' ? 'unanswered' : 'feedback') + '-' + id);
  if (el) el.style.display = 'none';
}

async function unresolveItem(type, id) {
  await fetch('/api/unresolve', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({type, id})
  });
  location.reload();
}

async function resolveAll() {
  if (!confirm('Mark ALL open issues as resolved?')) return;
  const resp = await fetch('/api/resolve-all', {method: 'POST'});
  const data = await resp.json();
  alert('Resolved ' + data.count + ' items');
  location.reload();
}

async function runAnalysis() {
  switchTab('analysis');
  document.getElementById('analysis-content').textContent = 'Running analysis... this may take a moment.';
  const resp = await fetch('/api/analyze', {method: 'POST'});
  const data = await resp.json();
  document.getElementById('analysis-content').textContent = data.ok ? data.report : 'Error: ' + data.error;
}

async function loadAnalysis() {
  const resp = await fetch('/api/last-analysis');
  const data = await resp.json();
  document.getElementById('analysis-content').textContent = data.report;
}

// --- Fix with AI ---
const fixData = {};  // store fix data per feedback id

async function fixWithAI(id, question, response) {
  const area = document.getElementById('fix-area-' + id);
  const loading = document.getElementById('fix-loading-' + id);
  const result = document.getElementById('fix-result-' + id);
  area.style.display = 'block';
  loading.style.display = 'block';
  result.style.display = 'none';

  const resp = await fetch('/api/fix', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({question, response})
  });
  const data = await resp.json();
  loading.style.display = 'none';

  if (data.ok) {
    document.getElementById('fix-topic-' + id).textContent = data.topic;
    document.getElementById('fix-correction-' + id).textContent = data.correction;
    fixData[id] = {topic: data.topic};
    result.style.display = 'block';
  } else {
    loading.textContent = 'Error: ' + data.error;
    loading.style.display = 'block';
  }
}

async function applyFix(id) {
  const topic = fixData[id]?.topic || 'General';
  const correction = document.getElementById('fix-correction-' + id).textContent.trim();
  if (!correction) return;

  const resp = await fetch('/api/apply-fix', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({topic, correction, feedback_id: id})
  });
  const data = await resp.json();
  if (data.ok) {
    const card = document.getElementById('feedback-' + id);
    card.style.borderLeftColor = '#4ecca3';
    card.querySelector('.fix-area').innerHTML = '<div style="color:#4ecca3;">Fix applied & resolved</div>';
  }
}

function dismissFix(id) {
  document.getElementById('fix-area-' + id).style.display = 'none';
}

// Format timestamps
document.querySelectorAll('.meta').forEach(el => {
  el.innerHTML = el.innerHTML.replace(/(\d{10,})/, (match) => {
    return new Date(parseInt(match) * 1000).toLocaleString();
  });
});
</script>
</body></html>
"""


# --- In-game API endpoint ---

@app.route("/api/ask", methods=["POST"])
def api_ask():
    """API endpoint for in-game mod. Accepts JSON: {question, api_key, username?}"""
    if not _live_ai_handler:
        return jsonify({"error": "AI handler not ready"}), 503

    data = request.get_json(silent=True)
    if not data or "question" not in data:
        return jsonify({"error": "Missing 'question' field"}), 400

    # Authenticate with API key
    if INGAME_API_KEY:
        provided_key = data.get("api_key", "")
        if provided_key != INGAME_API_KEY:
            return jsonify({"error": "Invalid API key"}), 401

    question = data["question"].strip()
    if not question:
        return jsonify({"error": "Empty question"}), 400
    if len(question) > 500:
        return jsonify({"error": "Question too long (max 500 chars)"}), 400

    mc_username = data.get("username", "")

    # Check if in-game user has a linked IGN for personalized responses
    from user_links import get_ingame_linked
    linked_ign = get_ingame_linked(mc_username) if mc_username else None

    # Run the async AI handler in the event loop
    try:
        loop = asyncio.new_event_loop()
        response = loop.run_until_complete(
            _live_ai_handler.get_response(question, ingame=True, mc_ign=linked_ign)
        )
        loop.close()
    except Exception as e:
        print(f"[api] Error processing question: {e}")
        return jsonify({"error": "Failed to generate response"}), 500

    # Strip markdown formatting for in-game chat
    import re
    clean = response
    clean = re.sub(r'\*\*(.+?)\*\*', r'\1', clean)  # bold
    clean = re.sub(r'\*(.+?)\*', r'\1', clean)       # italic
    clean = re.sub(r'`(.+?)`', r'\1', clean)          # inline code
    clean = re.sub(r'#{1,3}\s+', '', clean)            # headers
    clean = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', clean)  # links

    # Split into chat-friendly chunks (Minecraft chat limit ~256 chars per line)
    lines = clean.split("\n")
    chat_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        while len(line) > 250:
            # Find a space to break at
            idx = line.rfind(" ", 0, 250)
            if idx == -1:
                idx = 250
            chat_lines.append(line[:idx])
            line = line[idx:].strip()
        if line:
            chat_lines.append(line)

    return jsonify({
        "response": clean,
        "chat_lines": chat_lines[:20],  # max 20 lines for chat
        "username": mc_username,
    })


@app.route("/api/link", methods=["POST"])
def api_link():
    """Link an in-game user to a Skyblock IGN."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Missing JSON body"}), 400

    if INGAME_API_KEY:
        if data.get("api_key", "") != INGAME_API_KEY:
            return jsonify({"error": "Invalid API key"}), 401

    mc_username = data.get("username", "").strip()
    ign = data.get("ign", "").strip()

    if not mc_username or not ign:
        return jsonify({"error": "Missing username or ign"}), 400

    try:
        from user_links import link_ingame
        link_ingame(mc_username, ign)
        return jsonify({"ok": True, "linked": ign})
    except Exception as e:
        print(f"[api/link] Error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/unlink", methods=["POST"])
def api_unlink():
    """Unlink an in-game user."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Missing JSON body"}), 400

    if INGAME_API_KEY:
        if data.get("api_key", "") != INGAME_API_KEY:
            return jsonify({"error": "Invalid API key"}), 401

    mc_username = data.get("username", "").strip()
    if not mc_username:
        return jsonify({"error": "Missing username"}), 400

    try:
        from user_links import unlink_ingame
        removed = unlink_ingame(mc_username)
        return jsonify({"ok": True, "was_linked": removed})
    except Exception as e:
        print(f"[api/unlink] Error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/health")
def api_health():
    """Health check endpoint."""
    return jsonify({"status": "ok", "ai_ready": _live_ai_handler is not None})


# --- Mod auto-update endpoints ---

MOD_DIR = Path(__file__).parent / "fabric-mod" / "dist"

@app.route("/api/mod/version")
def api_mod_version():
    """Returns the latest mod version and update message. The mod checks this on startup."""
    version_file = MOD_DIR / "version.txt"
    message_file = MOD_DIR / "update_message.txt"
    if version_file.exists():
        version = version_file.read_text().strip()
    else:
        version = "1.0.0"
    message = ""
    if message_file.exists():
        message = message_file.read_text().strip()
    return jsonify({"version": version, "message": message})


@app.route("/api/mod/download")
def api_mod_download():
    """Serves the latest mod jar for auto-update."""
    from flask import send_from_directory
    # Find the jar in dist/
    if not MOD_DIR.exists():
        return jsonify({"error": "No mod builds available"}), 404
    jars = list(MOD_DIR.glob("*.jar"))
    if not jars:
        return jsonify({"error": "No mod jar found"}), 404
    jar = jars[0]
    return send_from_directory(str(MOD_DIR), jar.name, as_attachment=True,
                               download_name="hypixelai-mod.jar")


def run_dashboard():
    """Run the dashboard as a standalone server."""
    print(f"[dashboard] Starting on port {DASHBOARD_PORT}")
    print(f"[dashboard] Access at http://localhost:{DASHBOARD_PORT}")
    app.run(host="0.0.0.0", port=DASHBOARD_PORT, debug=False)


def start_ngrok():
    """Start ngrok tunnel for public access."""
    import subprocess
    import shutil
    ngrok_path = shutil.which("ngrok")
    if not ngrok_path:
        # Try known winget install path
        candidate = Path.home() / "AppData/Local/Microsoft/WinGet/Packages"
        for p in candidate.rglob("ngrok.exe"):
            ngrok_path = str(p)
            break
    if not ngrok_path:
        print("[ngrok] ngrok not found, skipping tunnel")
        return
    try:
        subprocess.Popen(
            [ngrok_path, "http", str(DASHBOARD_PORT),
             "--url=literate-totally-civet.ngrok-free.app", "--log=false"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        print(f"[ngrok] Tunnel started: https://literate-totally-civet.ngrok-free.app")
    except Exception as e:
        print(f"[ngrok] Failed to start: {e}")


def start_dashboard_thread():
    """Start the dashboard in a background thread (call from bot.py)."""
    t = threading.Thread(target=run_dashboard, daemon=True)
    t.start()
    # Start ngrok tunnel
    start_ngrok()
    return t


if __name__ == "__main__":
    run_dashboard()
