"""
Web API server for the in-game Minecraft mod.
Provides endpoints for asking questions, linking accounts, health checks, and mod updates.
"""
import os
import re
import time
import asyncio
import threading
from pathlib import Path

from flask import Flask, request, jsonify, redirect, make_response
from dotenv import load_dotenv

load_dotenv()

DASHBOARD_PORT = int(os.getenv("PORT", os.getenv("DASHBOARD_PORT", 5000)))

app = Flask(__name__)

# Set by bot.py so the API can use the live AI handler
_live_knowledge_base = None
_live_ai_handler = None

# API key for in-game mod authentication (set in .env as INGAME_API_KEY)
INGAME_API_KEY = os.getenv("INGAME_API_KEY", "")


async def _extract_hotm_data(ai_handler, mc_username, linked_ign):
    """Extract HOTM perk data for pixel art rendering if player is linked."""
    ign = linked_ign or mc_username
    if not ign or not ai_handler:
        return None
    pdata = await ai_handler.hypixel.get_player_data(ign)
    if not pdata or 'stats' not in pdata:
        return None
    stats = pdata['stats']
    from hypixel_api import HOTM_XP
    hotm_xp = stats.get('hotm_xp', 0)
    hotm_lvl = sum(1 for req in HOTM_XP[1:] if hotm_xp >= req)
    return {
        "level": hotm_lvl,
        "perks": stats.get('hotm_perks', {}),
        "selected_ability": stats.get('hotm_selected_ability', ''),
        "powder": {
            "mithril": stats.get('mithril_powder', 0),
            "gemstone": stats.get('gemstone_powder', 0),
            "glacite": stats.get('glacite_powder', 0),
        }
    }


# --- In-game API endpoint ---

@app.route("/api/activate", methods=["POST"])
def api_activate():
    """Activate a license key — binds it to a Minecraft UUID and returns a session token."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Missing JSON body"}), 400

    license_key = data.get("license_key", "").strip()
    mc_uuid = data.get("mc_uuid", "").strip()
    mc_username = data.get("username", "").strip()

    if not license_key or not mc_uuid:
        return jsonify({"error": "Missing license_key or mc_uuid"}), 400

    from licenses import validate_key
    result = validate_key(license_key, mc_uuid, mc_username)
    if result["ok"]:
        return jsonify({"ok": True, "session": result["session"], "plan": result["plan"]})
    else:
        return jsonify({"ok": False, "error": result["error"]}), 403


@app.route("/api/register", methods=["POST"])
def api_register():
    """Auto-register a free account. Creates a free-tier key bound to this UUID."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Missing JSON body"}), 400

    mc_uuid = data.get("mc_uuid", "").strip()
    mc_username = data.get("username", "").strip()

    if not mc_uuid:
        return jsonify({"error": "Missing mc_uuid"}), 400

    from licenses import _con, generate_key, validate_key

    # Check if this UUID already has a key
    existing = _con.execute(
        "SELECT license_key, plan FROM licenses WHERE mc_uuid = ? AND active = 1", (mc_uuid,)
    ).fetchone()
    if existing:
        # Already registered — just re-activate
        result = validate_key(existing["license_key"], mc_uuid, mc_username)
        if result["ok"]:
            return jsonify({"ok": True, "session": result["session"], "plan": result["plan"], "license_key": existing["license_key"]})
        return jsonify({"ok": False, "error": result.get("error", "Activation failed")}), 403

    # Create a free key bound to this UUID (never expires)
    key = generate_key(plan="free", expires_days=None)
    result = validate_key(key, mc_uuid, mc_username)
    if result["ok"]:
        return jsonify({"ok": True, "session": result["session"], "plan": "free", "license_key": key, "new": True})
    return jsonify({"ok": False, "error": "Registration failed"}), 500


def _auth_session(data: dict) -> tuple:
    """Validate session token from request data. Returns (license_info, error_response)."""
    session = data.get("session", "").strip()
    if not session:
        return None, (jsonify({"error": "Missing session token. Use !aikey to activate."}), 401)

    from licenses import validate_session
    info = validate_session(session)
    if info is None:
        return None, (jsonify({"error": "Session expired or invalid. Use !aikey to re-activate."}), 401)
    if isinstance(info, dict) and info.get("rate_limited"):
        return None, (jsonify({"error": f"Rate limit reached ({info['limit']}/hr on {info['plan']} plan). Try again later."}), 429)
    return info, None


@app.route("/api/ask", methods=["POST"])
def api_ask():
    """API endpoint for in-game mod. Requires session token from /api/activate."""
    if not _live_ai_handler:
        return jsonify({"error": "AI handler not ready"}), 503

    data = request.get_json(silent=True)
    if not data or "question" not in data:
        return jsonify({"error": "Missing 'question' field"}), 400

    # Session-based auth — license key required
    license_info, err = _auth_session(data)
    if err:
        return err

    question = data["question"].strip()
    if not question:
        return jsonify({"error": "Empty question"}), 400
    if len(question) > 500:
        return jsonify({"error": "Question too long (max 500 chars)"}), 400

    mc_username = data.get("username", "")
    _start = time.time()
    print(f"[ingame] {mc_username or 'unknown'} asked: {question[:100]}")

    # Check if in-game user has a linked IGN for personalized responses
    from user_links import get_ingame_linked
    linked_ign = get_ingame_linked(mc_username) if mc_username else None

    # Check if this is a HOTM question — fetch visual data BEFORE AI call
    hotm_data = None
    is_hotm_question = "hotm" in question.lower() or "heart of the mountain" in question.lower()
    if is_hotm_question:
        try:
            loop_hotm = asyncio.new_event_loop()
            hotm_data = loop_hotm.run_until_complete(_extract_hotm_data(_live_ai_handler, mc_username, linked_ign))
            loop_hotm.close()
        except Exception:
            pass

    # Modify question for AI when HOTM visual data will be shown
    ai_question = question
    if hotm_data and is_hotm_question:
        ai_question = (
            question + "\n\n[SYSTEM: The player's HotM tree grid is being displayed visually as a pixel art grid. "
            "Do NOT list individual perks or tiers. Instead, give a brief summary: their HotM level, "
            "key recommendations for what to upgrade next, and powder spending advice. Keep it to 3-6 lines.]"
        )

    # Run the async AI handler in the event loop
    try:
        loop = asyncio.new_event_loop()
        response = loop.run_until_complete(
            _live_ai_handler.get_response(ai_question, ingame=True, mc_ign=linked_ign)
        )
        loop.close()
    except Exception as e:
        print(f"[api] Error processing question: {e}")
        return jsonify({"error": "Failed to generate response"}), 500

    _elapsed = round(time.time() - _start, 1)
    print(f"[ingame] Replied to {mc_username or 'unknown'} in {_elapsed}s ({len(response)} chars)")

    # Convert markdown to color codes for in-game overlay
    # §e = gold (headers/bold), §b = aqua (code/values), §7 = gray (normal)
    clean = response
    clean = re.sub(r'#{1,3}\s+(.+)', r'§e\1', clean)            # headers → gold
    clean = re.sub(r'\*\*(.+?)\*\*', r'§e\1§r', clean)          # bold → gold
    clean = re.sub(r'\*(.+?)\*', r'\1', clean)                   # italic → plain
    clean = re.sub(r'`(.+?)`', r'§b\1§r', clean)                # code → aqua
    clean = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', clean)            # links → plain

    # Split into chat-friendly chunks (Minecraft chat limit ~256 chars per line)
    lines = clean.split("\n")
    chat_lines = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        while len(line) > 250:
            idx = line.rfind(" ", 0, 250)
            if idx == -1:
                idx = 250
            chat_lines.append(line[:idx])
            line = line[idx:].strip()
        if line:
            chat_lines.append(line)

    result = {
        "response": clean,
        "chat_lines": chat_lines[:30],
        "username": mc_username,
    }
    if hotm_data:
        result["hotm"] = hotm_data

    # Log every question
    try:
        from feedback import log_question
        log_question(mc_username or "unknown", question, response)
    except Exception:
        pass

    return jsonify(result)


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
        print(f"[ingame] {mc_username} linked to IGN: {ign}")
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
        print(f"[ingame] {mc_username} unlinked (was_linked={removed})")
        return jsonify({"ok": True, "was_linked": removed})
    except Exception as e:
        print(f"[api/unlink] Error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/feedback", methods=["POST"])
def api_feedback():
    """Log feedback (correct/wrong) from in-game mod."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Missing JSON body"}), 400

    if INGAME_API_KEY:
        if data.get("api_key", "") != INGAME_API_KEY:
            return jsonify({"error": "Invalid API key"}), 401

    vote = data.get("vote", "").strip()
    if vote not in ("up", "down"):
        return jsonify({"error": "vote must be 'up' or 'down'"}), 400

    mc_username = data.get("username", "unknown")
    question = data.get("question", "")
    response_text = data.get("response", "")

    try:
        from feedback import log_vote
        fid = log_vote(0, f"ingame:{mc_username}", question, response_text, vote)
        print(f"[ingame] {mc_username} voted {vote} (id={fid})")
        return jsonify({"ok": True, "id": fid})
    except Exception as e:
        print(f"[api/feedback] Error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/feedback/list")
def api_feedback_list():
    """JSON: feedback stats, downvoted responses, unanswered questions."""
    from feedback import get_feedback_stats, get_bad_responses, get_unanswered
    return jsonify({
        "stats": get_feedback_stats(),
        "wrong": get_bad_responses(limit=50),
        "unanswered": get_unanswered(limit=50),
    })


@app.route("/api/questions")
def api_questions():
    """JSON: recent questions asked to the bot."""
    from feedback import get_questions
    limit = min(int(request.args.get("limit", 50)), 200)
    offset = int(request.args.get("offset", 0))
    return jsonify(get_questions(limit=limit, offset=offset))


@app.route("/api/health")
def api_health():
    """Health check endpoint."""
    return jsonify({"status": "ok", "ai_ready": _live_ai_handler is not None})


# ── License admin endpoints (password-protected) ──────────────────────────

ADMIN_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "skyblock2026")

def _check_admin():
    pwd = request.args.get("pwd", "") or request.headers.get("X-Admin-Password", "")
    return pwd == ADMIN_PASSWORD and ADMIN_PASSWORD != ""


@app.route("/api/licenses/generate", methods=["POST"])
def api_license_generate():
    """Generate license key(s). Requires admin password."""
    if not _check_admin():
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    count = min(int(data.get("count", 1)), 50)
    plan = data.get("plan", "basic")
    days = data.get("expires_days", 30)
    from licenses import generate_keys
    keys = generate_keys(count, plan, days)
    return jsonify({"keys": keys, "plan": plan, "expires_days": days})


@app.route("/api/licenses")
def api_licenses_list():
    """List all licenses. Requires admin password."""
    if not _check_admin():
        return jsonify({"error": "Unauthorized"}), 401
    from licenses import list_licenses
    return jsonify(list_licenses(limit=100))


@app.route("/api/licenses/deactivate", methods=["POST"])
def api_license_deactivate():
    """Deactivate a license key."""
    if not _check_admin():
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    key = data.get("license_key", "")
    from licenses import deactivate_key
    ok = deactivate_key(key)
    return jsonify({"ok": ok})


@app.route("/api/licenses/unbind", methods=["POST"])
def api_license_unbind():
    """Unbind a license key from its UUID (allow re-binding)."""
    if not _check_admin():
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    key = data.get("license_key", "")
    from licenses import unbind_key
    ok = unbind_key(key)
    return jsonify({"ok": ok})


@app.route("/api/admin/reset-password", methods=["POST"])
def api_admin_reset_password():
    """Reset a user's password. Requires admin password."""
    if not _check_admin():
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    username = data.get("username", "")
    new_password = data.get("password", "")
    from accounts import reset_password
    ok = reset_password(username, new_password)
    return jsonify({"ok": ok})


@app.route("/api/admin/promote", methods=["POST"])
def api_admin_promote():
    """Promote a user to admin. Requires admin password."""
    if not _check_admin():
        return jsonify({"error": "Unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    username = data.get("username", "")
    from accounts import make_admin
    ok = make_admin(username)
    return jsonify({"ok": ok, "username": username})


@app.route("/")
def index():
    """Serve the landing page."""
    landing = Path(__file__).parent / "docs" / "index.html"
    if landing.exists():
        return landing.read_text(encoding="utf-8"), 200, {"Content-Type": "text/html"}
    return jsonify({"status": "ok", "service": "hypixel-ai-bot"})


# ── Purchase / Dashboard pages ────────────────────────────────────────────

_RATE_LIMIT_CACHE = {}  # ip -> (count, first_request_time)

def _rate_limit_ip(limit=5, window=3600):
    """Rate limit by IP. Returns True if allowed."""
    ip = request.remote_addr or "unknown"
    now = int(time.time())
    if ip in _RATE_LIMIT_CACHE:
        count, first = _RATE_LIMIT_CACHE[ip]
        if now - first > window:
            _RATE_LIMIT_CACHE[ip] = (1, now)
            return True
        if count >= limit:
            return False
        _RATE_LIMIT_CACHE[ip] = (count + 1, first)
        return True
    _RATE_LIMIT_CACHE[ip] = (1, now)
    return True


_PAGE_STYLE = """
<style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: 'Inter', -apple-system, sans-serif; background: #060611; color: #e2e8f0; min-height: 100vh; display: flex; align-items: center; justify-content: center; }
    .card { background: #10102a; border: 1px solid #1a1a3a; border-radius: 20px; padding: 40px; max-width: 480px; width: 90%; text-align: center; }
    h1 { font-size: 1.6rem; font-weight: 800; margin-bottom: 8px; }
    h1 .gradient { background: linear-gradient(135deg, #3b82f6, #8b5cf6); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    .sub { color: #94a3b8; font-size: 0.9rem; margin-bottom: 28px; }
    .plan-badge { display: inline-block; padding: 4px 14px; border-radius: 100px; font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 20px; }
    .plan-free { background: rgba(34,197,94,0.15); color: #22c55e; }
    .plan-basic { background: rgba(59,130,246,0.15); color: #3b82f6; }
    .plan-pro { background: rgba(139,92,246,0.15); color: #8b5cf6; }
    input { width: 100%; padding: 14px 18px; background: #0c0c1d; border: 1px solid #1a1a3a; border-radius: 10px; color: #e2e8f0; font-size: 0.95rem; outline: none; margin-bottom: 12px; }
    input:focus { border-color: #3b82f6; }
    input::placeholder { color: #4a5568; }
    .btn { display: block; width: 100%; padding: 14px; border: none; border-radius: 10px; font-weight: 700; font-size: 0.95rem; cursor: pointer; transition: all 0.2s; text-decoration: none; text-align: center; }
    .btn-primary { background: linear-gradient(135deg, #3b82f6, #8b5cf6); color: #fff; box-shadow: 0 4px 15px rgba(59,130,246,0.3); }
    .btn-primary:hover { transform: translateY(-1px); box-shadow: 0 6px 25px rgba(59,130,246,0.4); }
    .btn-ghost { background: rgba(255,255,255,0.06); color: #e2e8f0; border: 1px solid #1a1a3a; margin-top: 10px; }
    .btn-ghost:hover { background: rgba(255,255,255,0.1); }
    .key-box { background: #0c0c1d; border: 1px solid #1a1a3a; border-radius: 10px; padding: 16px; margin: 20px 0; font-family: monospace; font-size: 0.95rem; color: #f59e0b; word-break: break-all; letter-spacing: 0.5px; user-select: all; }
    .info { color: #64748b; font-size: 0.82rem; margin-top: 16px; line-height: 1.6; }
    .info code { background: rgba(59,130,246,0.1); color: #3b82f6; padding: 2px 6px; border-radius: 4px; font-size: 0.8rem; }
    .error { color: #ef4444; font-size: 0.88rem; margin-bottom: 16px; }
    .success { color: #22c55e; }
    .step { text-align: left; background: #0c0c1d; border: 1px solid #1a1a3a; border-radius: 10px; padding: 16px; margin: 16px 0; }
    .step-item { display: flex; gap: 12px; padding: 8px 0; color: #94a3b8; font-size: 0.88rem; }
    .step-num { background: rgba(59,130,246,0.15); color: #3b82f6; width: 24px; height: 24px; border-radius: 6px; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 0.75rem; flex-shrink: 0; }
</style>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
"""


import secrets as _secrets

# One-time purchase tokens: {token: (plan, created_at)}
_purchase_tokens = {}


def _get_web_user():
    """Get logged-in username from cookie. Returns None if not logged in."""
    from accounts import get_session_user
    token = request.cookies.get("skyai_session", "")
    return get_session_user(token)


def _login_required_page():
    """Returns HTML redirect to login page."""
    return redirect("/login")


@app.route("/login", methods=["GET", "POST"])
def web_login():
    """Login page."""
    from html import escape
    error = ""
    next_url = request.args.get("next", request.form.get("next", "/dashboard"))
    if request.method == "POST":
        mc_username = request.form.get("mc_username", "").strip()
        password = request.form.get("password", "")
        from accounts import login
        result = login(mc_username, password)
        if result["ok"]:
            resp = make_response(redirect(next_url))
            resp.set_cookie("skyai_session", result["token"], max_age=7*86400, httponly=True, samesite="Lax")
            return resp
        error = result["error"]

    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
    <title>SkyAI — Login</title>{_PAGE_STYLE}</head><body>
    <div class="card">
        <h1><span class="gradient">SkyAI</span></h1>
        <p class="sub">Sign in to your account</p>
        {"<p class='error'>" + escape(error) + "</p>" if error else ""}
        <form method="POST">
            <input type="hidden" name="next" value="{escape(next_url)}">
            <input type="text" name="mc_username" placeholder="Minecraft Username" required autocomplete="off" autofocus>
            <input type="password" name="password" placeholder="Password" required>
            <button type="submit" class="btn btn-primary">Sign In</button>
        </form>
        <a href="/register?next={escape(next_url)}" class="btn btn-ghost">Create Account</a>
    </div>
    </body></html>""", 200, {"Content-Type": "text/html"}


@app.route("/register", methods=["GET", "POST"])
def web_register():
    """Register page."""
    from html import escape
    error = ""
    next_url = request.args.get("next", request.form.get("next", "/dashboard"))
    if request.method == "POST":
        mc_username = request.form.get("mc_username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm", "")

        if password != confirm:
            error = "Passwords don't match"
        else:
            from accounts import register, login
            result = register(mc_username, password)
            if result["ok"]:
                login_result = login(mc_username, password)
                if login_result["ok"]:
                    resp = make_response(redirect(next_url))
                    resp.set_cookie("skyai_session", login_result["token"], max_age=7*86400, httponly=True, samesite="Lax")
                    return resp
            error = result.get("error", "Registration failed")

    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
    <title>SkyAI — Register</title>{_PAGE_STYLE}</head><body>
    <div class="card">
        <h1><span class="gradient">SkyAI</span></h1>
        <p class="sub">Create your SkyAI account</p>
        {"<p class='error'>" + escape(error) + "</p>" if error else ""}
        <form method="POST">
            <input type="hidden" name="next" value="{escape(next_url)}">
            <input type="text" name="mc_username" placeholder="Minecraft Username" required autocomplete="off" autofocus>
            <input type="password" name="password" placeholder="Password" required>
            <input type="password" name="confirm" placeholder="Confirm Password" required>
            <button type="submit" class="btn btn-primary">Create Account</button>
        </form>
        <a href="/login?next={escape(next_url)}" class="btn btn-ghost">Already have an account? Sign In</a>
    </div>
    </body></html>""", 200, {"Content-Type": "text/html"}


@app.route("/logout")
def web_logout():
    """Log out."""
    from accounts import logout
    token = request.cookies.get("skyai_session", "")
    if token:
        logout(token)
    resp = make_response(redirect("/"))
    resp.delete_cookie("skyai_session")
    return resp

def _cleanup_tokens():
    """Remove expired tokens (older than 1 hour)."""
    now = int(time.time())
    expired = [t for t, (_, ts) in _purchase_tokens.items() if now - ts > 3600]
    for t in expired:
        del _purchase_tokens[t]


@app.route("/api/purchase-token")
def api_purchase_token():
    """Generate a one-time token for a paid plan. Called by landing page JS before checkout."""
    plan = request.args.get("plan", "")
    if plan not in ("basic", "pro"):
        return jsonify({"error": "Invalid plan"}), 400
    _cleanup_tokens()
    token = _secrets.token_urlsafe(24)
    _purchase_tokens[token] = (plan, int(time.time()))
    return jsonify({"token": token, "plan": plan})


@app.route("/purchased")
def purchased():
    """Post-checkout page. Requires login. Generates key for the user's account."""
    mc_username = _get_web_user()
    if not mc_username:
        # Save where they were going so we can redirect after login
        plan = request.args.get("plan", "free")
        token = request.args.get("token", "")
        return redirect(f"/login?next=/purchased?plan={plan}&token={token}")

    plan = request.args.get("plan", "free")
    token = request.args.get("token", "")

    if plan not in ("free", "basic", "pro"):
        plan = "free"

    # Paid plans require a valid purchase token
    if plan in ("basic", "pro"):
        if not token or token not in _purchase_tokens:
            return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
            <title>SkyAI — Error</title>{_PAGE_STYLE}</head><body>
            <div class="card">
                <h1><span class="gradient">SkyAI</span></h1>
                <p class="error">Invalid or expired purchase link. Please buy through the website.</p>
                <a href="/" class="btn btn-primary">Go to SkyAI</a>
            </div></body></html>""", 403, {"Content-Type": "text/html"}
        token_plan, _ = _purchase_tokens[token]
        if token_plan != plan:
            return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
            <title>SkyAI — Error</title>{_PAGE_STYLE}</head><body>
            <div class="card">
                <h1><span class="gradient">SkyAI</span></h1>
                <p class="error">Purchase token does not match this plan.</p>
                <a href="/" class="btn btn-primary">Go to SkyAI</a>
            </div></body></html>""", 403, {"Content-Type": "text/html"}
        # Consume the token
        del _purchase_tokens[token]

    # Generate or find existing key for this user
    from licenses import generate_key, _con

    existing = _con.execute(
        "SELECT license_key FROM licenses WHERE mc_username = ? AND plan = ? AND active = 1",
        (mc_username, plan),
    ).fetchone()

    if existing:
        key = existing["license_key"]
    else:
        expires = None if plan == "free" else 30
        key = generate_key(plan=plan, expires_days=expires)
        _con.execute("UPDATE licenses SET mc_username = ? WHERE license_key = ?", (mc_username, key))
        _con.commit()

    return _render_dashboard(mc_username, key, plan)




@app.route("/dashboard")
def dashboard():
    """View your license info. Requires login."""
    mc_username = _get_web_user()
    if not mc_username:
        return redirect("/login")

    from licenses import _con
    # Get the best plan (paid > free)
    row = _con.execute(
        "SELECT license_key, plan, created_at, expires_at FROM licenses WHERE mc_username = ? AND active = 1 ORDER BY CASE plan WHEN 'unlimited' THEN 4 WHEN 'pro' THEN 3 WHEN 'basic' THEN 2 ELSE 1 END DESC LIMIT 1",
        (mc_username,),
    ).fetchone()

    if not row:
        # No license yet — show option to get one
        return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
        <title>SkyAI — Dashboard</title>{_PAGE_STYLE}</head><body>
        <div class="card">
            <h1><span class="gradient">SkyAI</span></h1>
            <p class="sub">Welcome, <strong>{mc_username}</strong>!</p>
            <p class="sub">You don't have a license yet.</p>
            <a href="/purchased?plan=free" class="btn btn-primary">Get Free License</a>
            <a href="/#buy" class="btn btn-ghost">View Plans</a>
            <p class="info" style="margin-top:20px;"><a href="/logout" style="color:#ef4444;">Sign Out</a></p>
        </div></body></html>""", 200, {"Content-Type": "text/html"}

    return _render_dashboard(mc_username, row["license_key"], row["plan"])


def _render_dashboard(mc_username, key, plan):
    """Render the dashboard page with key + download."""
    plan_names = {"free": "Free", "basic": "Basic", "pro": "Pro", "unlimited": "Unlimited"}
    plan_class = f"plan-{plan}" if plan in ("free", "basic", "pro") else "plan-pro"
    limits = {"free": "10", "basic": "30", "pro": "100", "unlimited": "Unlimited"}

    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
    <title>SkyAI — Your License</title>{_PAGE_STYLE}</head><body>
    <div class="card">
        <h1><span class="gradient">SkyAI</span></h1>
        <span class="plan-badge {plan_class}">{plan_names.get(plan, plan)} Plan</span>
        <p class="sub">Welcome, <strong>{mc_username}</strong>! Here's your license.</p>

        <div class="key-box">{key}</div>

        <a href="/download" class="btn btn-primary">Download Mod</a>
        <a href="/#buy" class="btn btn-ghost">Upgrade Plan</a>

        <div class="step">
            <div class="step-item"><div class="step-num">1</div><span>Download the mod above and put it in <code>.minecraft/mods/</code></span></div>
            <div class="step-item"><div class="step-num">2</div><span>You need <strong>Fabric Loader</strong> + <strong>Fabric API</strong> for 1.21.10</span></div>
            <div class="step-item"><div class="step-num">3</div><span>Launch Minecraft, join any server</span></div>
            <div class="step-item"><div class="step-num">4</div><span>Type in chat: <code>!aikey {key}</code></span></div>
            <div class="step-item"><div class="step-num">5</div><span>Done! Ask anything with <code>!ai your question</code></span></div>
        </div>

        <p class="info">
            Plan: <strong>{plan_names.get(plan, plan)}</strong> — {limits.get(plan, "?")} questions/hr<br>
            {"Upgrade anytime at <a href='/#buy' style='color:#3b82f6;'>pricing page</a>" if plan == "free" else "Manage your subscription on <a href='https://whop.com/orders' style='color:#3b82f6;'>Whop</a>"}
            <br><br><a href="/logout" style="color:#ef4444;">Sign Out</a>
        </p>
    </div>
    </body></html>""", 200, {"Content-Type": "text/html"}


# ── Admin Panel ────────────────────────────────────────────────────────────

_ADMIN_STYLE = _PAGE_STYLE.replace("max-width: 480px", "max-width: 900px")

@app.route("/admin")
def admin_panel():
    """Admin dashboard — manage licenses, users, questions, feedback."""
    mc_username = _get_web_user()
    if not mc_username:
        return redirect("/login?next=/admin")
    from accounts import is_admin
    if not is_admin(mc_username):
        return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
        <title>SkyAI — Admin</title>{_PAGE_STYLE}</head><body>
        <div class="card"><h1><span class="gradient">Access Denied</span></h1><p class="sub">You are not an admin.</p>
        <a href="/dashboard" class="btn btn-ghost">Back to Dashboard</a></div></body></html>""", 403, {"Content-Type": "text/html"}

    from html import escape
    from licenses import list_licenses, _con as lcon
    from accounts import list_accounts
    from feedback import get_feedback_stats, get_bad_responses, get_questions
    import datetime

    licenses = list_licenses(100)
    accounts = list_accounts(100)
    stats = get_feedback_stats()
    wrong = get_bad_responses(20)
    questions = get_questions(20)

    # Build license table
    lic_rows = ""
    for l in licenses:
        exp = "Never" if not l.get("expires_at") else datetime.datetime.fromtimestamp(l["expires_at"]).strftime("%Y-%m-%d")
        status = "Active" if l.get("active") else "Inactive"
        s_color = "#22c55e" if l.get("active") else "#ef4444"
        lic_rows += f"""<tr>
            <td style="font-family:monospace;font-size:0.75rem;">{escape(str(l.get('license_key','')))}</td>
            <td>{escape(str(l.get('mc_username','') or '—'))}</td>
            <td>{escape(str(l.get('plan','')))}</td>
            <td style="color:{s_color}">{status}</td>
            <td>{exp}</td>
            <td>
                <form method="POST" action="/admin/action" style="display:inline">
                    <input type="hidden" name="key" value="{escape(str(l.get('license_key','')))}">
                    <button name="action" value="{'deactivate' if l.get('active') else 'reactivate'}" class="btn btn-ghost" style="padding:4px 10px;font-size:0.75rem;">{'Deactivate' if l.get('active') else 'Reactivate'}</button>
                    <button name="action" value="unbind" class="btn btn-ghost" style="padding:4px 10px;font-size:0.75rem;">Unbind</button>
                </form>
            </td></tr>"""

    # Build accounts table
    acc_rows = ""
    for a in accounts:
        admin_badge = '<span style="color:#f59e0b;">Admin</span>' if a.get("is_admin") else "User"
        acc_rows += f"""<tr>
            <td>{escape(str(a.get('mc_username','')))}</td>
            <td>{admin_badge}</td>
            <td>{datetime.datetime.fromtimestamp(a.get('created_at',0)).strftime("%Y-%m-%d")}</td>
            <td>
                {"" if a.get("is_admin") else '<form method="POST" action="/admin/action" style="display:inline"><input type="hidden" name="username" value="' + escape(str(a.get("mc_username",""))) + '"><button name="action" value="make_admin" class="btn btn-ghost" style="padding:4px 10px;font-size:0.75rem;">Make Admin</button></form>'}
            </td></tr>"""

    # Build wrong answers table
    wrong_rows = ""
    for w in wrong[:10]:
        q = escape(str(w.get("question", ""))[:80])
        r = escape(str(w.get("response", ""))[:100])
        wrong_rows += f"<tr><td>{q}</td><td style='font-size:0.75rem;'>{r}</td></tr>"

    # Build questions table
    q_rows = ""
    for q in questions[:10]:
        qu = escape(str(q.get("question", ""))[:80])
        usr = escape(str(q.get("username", "")))
        q_rows += f"<tr><td>{usr}</td><td>{qu}</td></tr>"

    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
    <title>SkyAI — Admin</title>{_ADMIN_STYLE}</head><body style="display:block;padding:24px;">
    <div style="max-width:1000px;margin:0 auto;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:32px;">
            <h1><span class="gradient">SkyAI Admin</span></h1>
            <div><a href="/dashboard" style="color:#94a3b8;margin-right:16px;">Dashboard</a><a href="/" style="color:#94a3b8;margin-right:16px;">Site</a><a href="/logout" style="color:#ef4444;">Logout</a></div>
        </div>

        <!-- Stats -->
        <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:32px;">
            <div class="card" style="padding:20px;text-align:center;"><div style="font-size:2rem;font-weight:800;">{len(licenses)}</div><div style="color:#64748b;font-size:0.8rem;">Licenses</div></div>
            <div class="card" style="padding:20px;text-align:center;"><div style="font-size:2rem;font-weight:800;">{len(accounts)}</div><div style="color:#64748b;font-size:0.8rem;">Accounts</div></div>
            <div class="card" style="padding:20px;text-align:center;"><div style="font-size:2rem;font-weight:800;color:#22c55e;">{stats.get('thumbs_up',0)}</div><div style="color:#64748b;font-size:0.8rem;">Upvotes</div></div>
            <div class="card" style="padding:20px;text-align:center;"><div style="font-size:2rem;font-weight:800;color:#ef4444;">{stats.get('thumbs_down',0)}</div><div style="color:#64748b;font-size:0.8rem;">Downvotes</div></div>
        </div>

        <!-- Generate Keys -->
        <div class="card" style="padding:20px;margin-bottom:24px;">
            <h3 style="margin-bottom:12px;">Generate License Keys</h3>
            <form method="POST" action="/admin/action" style="display:flex;gap:8px;flex-wrap:wrap;">
                <select name="plan" style="padding:8px 12px;background:#0c0c1d;border:1px solid #1a1a3a;border-radius:6px;color:#e2e8f0;">
                    <option value="free">Free</option>
                    <option value="basic" selected>Basic (30d)</option>
                    <option value="pro">Pro (30d)</option>
                    <option value="unlimited">Unlimited (perm)</option>
                </select>
                <input type="number" name="count" value="5" min="1" max="50" style="width:60px;padding:8px;background:#0c0c1d;border:1px solid #1a1a3a;border-radius:6px;color:#e2e8f0;">
                <button name="action" value="generate_keys" class="btn btn-primary" style="padding:8px 20px;">Generate</button>
            </form>
        </div>

        <!-- Generated keys display -->
        <div id="generated-keys"></div>

        <!-- Licenses -->
        <div class="card" style="padding:20px;margin-bottom:24px;">
            <h3 style="margin-bottom:12px;">Licenses ({len(licenses)})</h3>
            <div style="overflow-x:auto;">
            <table style="width:100%;border-collapse:collapse;font-size:0.85rem;">
                <tr style="border-bottom:1px solid #1a1a3a;"><th style="text-align:left;padding:8px;color:#64748b;">Key</th><th style="text-align:left;padding:8px;color:#64748b;">User</th><th style="text-align:left;padding:8px;color:#64748b;">Plan</th><th style="text-align:left;padding:8px;color:#64748b;">Status</th><th style="text-align:left;padding:8px;color:#64748b;">Expires</th><th style="text-align:left;padding:8px;color:#64748b;">Actions</th></tr>
                {lic_rows}
            </table></div>
        </div>

        <!-- Accounts -->
        <div class="card" style="padding:20px;margin-bottom:24px;">
            <h3 style="margin-bottom:12px;">Accounts ({len(accounts)})</h3>
            <table style="width:100%;border-collapse:collapse;font-size:0.85rem;">
                <tr style="border-bottom:1px solid #1a1a3a;"><th style="text-align:left;padding:8px;color:#64748b;">Username</th><th style="text-align:left;padding:8px;color:#64748b;">Role</th><th style="text-align:left;padding:8px;color:#64748b;">Created</th><th style="text-align:left;padding:8px;color:#64748b;">Actions</th></tr>
                {acc_rows}
            </table>
        </div>

        <!-- Wrong Answers -->
        <div class="card" style="padding:20px;margin-bottom:24px;">
            <h3 style="margin-bottom:12px;">Wrong Answers ({stats.get('thumbs_down',0)})</h3>
            <table style="width:100%;border-collapse:collapse;font-size:0.85rem;">
                <tr style="border-bottom:1px solid #1a1a3a;"><th style="text-align:left;padding:8px;color:#64748b;">Question</th><th style="text-align:left;padding:8px;color:#64748b;">Response</th></tr>
                {wrong_rows if wrong_rows else "<tr><td colspan='2' style='padding:8px;color:#22c55e;'>None!</td></tr>"}
            </table>
        </div>

        <!-- Recent Questions -->
        <div class="card" style="padding:20px;margin-bottom:24px;">
            <h3 style="margin-bottom:12px;">Recent Questions</h3>
            <table style="width:100%;border-collapse:collapse;font-size:0.85rem;">
                <tr style="border-bottom:1px solid #1a1a3a;"><th style="text-align:left;padding:8px;color:#64748b;">User</th><th style="text-align:left;padding:8px;color:#64748b;">Question</th></tr>
                {q_rows if q_rows else "<tr><td colspan='2' style='padding:8px;color:#64748b;'>No questions yet</td></tr>"}
            </table>
        </div>
    </div>
    </body></html>""", 200, {"Content-Type": "text/html"}


@app.route("/admin/action", methods=["POST"])
def admin_action():
    """Handle admin actions (generate keys, deactivate, etc)."""
    mc_username = _get_web_user()
    if not mc_username:
        return redirect("/login?next=/admin")
    from accounts import is_admin
    if not is_admin(mc_username):
        return redirect("/dashboard")

    action = request.form.get("action", "")

    if action == "generate_keys":
        plan = request.form.get("plan", "basic")
        count = min(int(request.form.get("count", 5)), 50)
        expires = None if plan == "unlimited" else 30
        from licenses import generate_keys
        keys = generate_keys(count, plan, expires)
        # Show keys on a simple page
        key_list = "<br>".join(keys)
        return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
        <title>Generated Keys</title>{_PAGE_STYLE}</head><body>
        <div class="card">
            <h1><span class="gradient">Keys Generated</span></h1>
            <p class="sub">{count} {plan} keys</p>
            <div class="key-box" style="text-align:left;font-size:0.8rem;line-height:2;">{key_list}</div>
            <a href="/admin" class="btn btn-ghost">Back to Admin</a>
        </div></body></html>""", 200, {"Content-Type": "text/html"}

    elif action == "deactivate":
        key = request.form.get("key", "")
        from licenses import deactivate_key
        deactivate_key(key)

    elif action == "reactivate":
        key = request.form.get("key", "")
        from licenses import reactivate_key
        reactivate_key(key)

    elif action == "unbind":
        key = request.form.get("key", "")
        from licenses import unbind_key
        unbind_key(key)

    elif action == "make_admin":
        username = request.form.get("username", "")
        from accounts import make_admin
        make_admin(username)

    return redirect("/admin")


# --- Mod auto-update endpoints ---

MOD_DIR = Path(__file__).parent / "fabric-mod" / "dist"

@app.route("/api/mod/version")
def api_mod_version():
    """Returns the latest mod version and update message."""
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


@app.route("/download")
def web_download():
    """Download mod jar — requires web login."""
    mc_username = _get_web_user()
    if not mc_username:
        return redirect("/login?next=/download")
    from flask import send_from_directory
    if not MOD_DIR.exists():
        return jsonify({"error": "No mod builds available"}), 404
    jars = list(MOD_DIR.glob("*.jar"))
    if not jars:
        return jsonify({"error": "No mod jar found"}), 404
    return send_from_directory(str(MOD_DIR), jars[0].name, as_attachment=True,
                               download_name="hypixelai-mod.jar")


@app.route("/api/mod/download")
def api_mod_download():
    """Serves the latest mod jar. Requires session token or admin password."""
    # Allow download via session token (from mod auto-updater)
    session = request.args.get("session", "")
    if session:
        from licenses import validate_session
        info = validate_session(session)
        if not info:
            return jsonify({"error": "Invalid session"}), 401
    # Allow download via admin password (for manual distribution)
    elif not _check_admin():
        return jsonify({"error": "Login required to download. Visit the SkyAI website."}), 401

    from flask import send_from_directory
    if not MOD_DIR.exists():
        return jsonify({"error": "No mod builds available"}), 404
    jars = list(MOD_DIR.glob("*.jar"))
    if not jars:
        return jsonify({"error": "No mod jar found"}), 404
    jar = jars[0]
    return send_from_directory(str(MOD_DIR), jar.name, as_attachment=True,
                               download_name="hypixelai-mod.jar")


def run_dashboard():
    """Run the API server."""
    print(f"[api] Starting on port {DASHBOARD_PORT}")
    app.run(host="0.0.0.0", port=DASHBOARD_PORT, debug=False)


def start_dashboard_thread():
    """Start the API server in a background thread (call from bot.py)."""
    t = threading.Thread(target=run_dashboard, daemon=True)
    t.start()
    return t


if __name__ == "__main__":
    run_dashboard()
