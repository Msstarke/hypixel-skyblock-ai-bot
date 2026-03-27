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
    return jsonify({
        "status": "ok",
        "ai_ready": _live_ai_handler is not None,
    })


# ── License admin endpoints (password-protected) ──────────────────────────

ADMIN_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "")

def _check_admin():
    pwd = request.headers.get("X-Admin-Password", "")
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


# ── Whop Webhook ──────────────────────────────────────────────────────────

WHOP_WEBHOOK_SECRET = os.getenv("WHOP_WEBHOOK_SECRET", "")

@app.route("/api/whop/webhook", methods=["POST"])
def whop_webhook():
    """Handle Whop webhook events (membership activated/deactivated, payment succeeded)."""
    body = request.get_data(as_text=True)
    data = request.get_json(silent=True)

    if not data:
        return jsonify({"error": "Invalid payload"}), 400

    event_type = data.get("type", "")
    event_data = data.get("data", {})

    print(f"[whop] Webhook received: {event_type}")

    if event_type == "membership.activated":
        membership_id = event_data.get("id", "")
        user = event_data.get("user", {})
        user_email = user.get("email", "")
        plan_id = event_data.get("plan", {}).get("id", "") if isinstance(event_data.get("plan"), dict) else event_data.get("plan_id", "")

        from licenses import whop_activate_membership
        result = whop_activate_membership(membership_id, user_email, plan_id)
        print(f"[whop] Membership activated: {membership_id} -> {result}")
        return jsonify(result)

    elif event_type == "membership.deactivated":
        membership_id = event_data.get("id", "")
        from licenses import whop_deactivate_membership
        result = whop_deactivate_membership(membership_id)
        print(f"[whop] Membership deactivated: {membership_id} -> {result}")
        return jsonify(result)

    elif event_type == "payment.succeeded":
        # Renew membership on recurring payment
        membership_id = event_data.get("membership_id", "") or event_data.get("membership", {}).get("id", "")
        if membership_id:
            from licenses import whop_renew_membership
            result = whop_renew_membership(membership_id)
            print(f"[whop] Payment succeeded, renewed: {membership_id} -> {result}")
            return jsonify(result)

    elif event_type == "payment.failed":
        membership_id = event_data.get("membership_id", "") or event_data.get("membership", {}).get("id", "")
        if membership_id:
            from licenses import whop_deactivate_membership
            result = whop_deactivate_membership(membership_id)
            print(f"[whop] Payment failed, deactivated: {membership_id} -> {result}")
            return jsonify(result)

    return jsonify({"ok": True, "event": event_type})


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


@app.route("/.well-known/<path:filename>")
def well_known(filename):
    """Serve .well-known files (Apple Pay verification etc)."""
    if filename == "apple-developer-merchantid-domain-association":
        return "7b2276657273696f6e223a312c227073704964223a2236343641384242363234393134464232453835354239443531364642353530333338314132444446383545414643463630323336443830413044434235334632222c22637265617465644f6e223a313736303636343737373433327d", 200, {"Content-Type": "text/plain"}
    return "", 404


@app.route("/")
def index():
    """Serve the landing page with dynamic nav based on login state."""
    landing = Path(__file__).parent / "docs" / "index.html"
    if not landing.exists():
        return jsonify({"status": "ok", "service": "hypixel-ai-bot"})

    html = landing.read_text(encoding="utf-8")

    user = _get_web_user()
    if user:
        from accounts import is_admin as _is_admin
        admin_link = '<a href="/admin">Admin</a>' if _is_admin(user) else ""
        new_nav = f"""<a href="/dashboard">Dashboard</a>
            {admin_link}
            <a href="/logout" class="nav-cta" style="color:#ef4444 !important;border-color:rgba(239,68,68,0.25) !important;background:rgba(239,68,68,0.08) !important;">{user}</a>"""
        html = html.replace(
            '<a href="/dashboard">Dashboard</a>\n            <a href="/login" class="nav-cta">Sign In</a>',
            new_nav
        )
    return html, 200, {"Content-Type": "text/html"}


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


_PAGE_CSS = """
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: 'Inter', -apple-system, sans-serif; background: #000; color: #e2e8f0; min-height: 100vh; }
    a { color: #6366f1; text-decoration: none; }
    a:hover { text-decoration: underline; }
    .topnav { position: sticky; top: 0; z-index: 100; padding: 14px 24px; background: rgba(0,0,0,0.8); backdrop-filter: blur(20px); border-bottom: 1px solid rgba(255,255,255,0.04); display: flex; justify-content: space-between; align-items: center; }
    .topnav-logo { font-size: 1.2rem; font-weight: 800; background: linear-gradient(135deg, #6366f1, #a855f7); -webkit-background-clip: text; -webkit-text-fill-color: transparent; text-decoration: none; }
    .topnav-links { display: flex; gap: 20px; align-items: center; }
    .topnav-links a { color: #4a5268; font-size: 0.82rem; font-weight: 500; text-decoration: none; }
    .topnav-links a:hover { color: #e2e8f0; text-decoration: none; }
    .topnav-user { display: flex; align-items: center; gap: 10px; }
    .topnav-avatar { width: 28px; height: 28px; border-radius: 8px; background: linear-gradient(135deg, #6366f1, #a855f7); display: flex; align-items: center; justify-content: center; font-size: 0.7rem; font-weight: 700; }
    .topnav-name { font-size: 0.82rem; font-weight: 600; color: #e2e8f0; }
    .page { max-width: 600px; margin: 0 auto; padding: 60px 24px; }
    .page-wide { max-width: 1000px; margin: 0 auto; padding: 40px 24px; }
    .page-center { display: flex; align-items: center; justify-content: center; min-height: calc(100vh - 56px); }
    .card { background: #0a0a18; border: 1px solid #16162a; border-radius: 20px; padding: 40px; max-width: 420px; width: 100%; text-align: center; }
    h1 { font-size: 1.5rem; font-weight: 800; margin-bottom: 8px; }
    .gradient { background: linear-gradient(135deg, #6366f1, #a855f7); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    .sub { color: #8892a8; font-size: 0.88rem; margin-bottom: 24px; }
    .plan-badge { display: inline-block; padding: 5px 16px; border-radius: 100px; font-size: 0.72rem; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 20px; }
    .plan-free { background: rgba(34,197,94,0.12); color: #22c55e; }
    .plan-basic { background: rgba(99,102,241,0.12); color: #6366f1; }
    .plan-pro { background: rgba(168,85,247,0.12); color: #a855f7; }
    .plan-unlimited { background: rgba(245,158,11,0.12); color: #f59e0b; }
    input, select { width: 100%; padding: 13px 16px; background: #08081a; border: 1px solid #16162a; border-radius: 10px; color: #e2e8f0; font-size: 0.9rem; font-family: inherit; outline: none; margin-bottom: 10px; transition: border-color 0.2s; }
    input:focus, select:focus { border-color: #6366f1; }
    input::placeholder { color: #3a3a5a; }
    .btn { display: block; width: 100%; padding: 13px; border: none; border-radius: 10px; font-weight: 700; font-size: 0.9rem; cursor: pointer; transition: all 0.2s; text-decoration: none; text-align: center; }
    .btn:hover { text-decoration: none; }
    .btn-primary { background: linear-gradient(135deg, #6366f1, #a855f7); color: #fff; box-shadow: 0 4px 20px rgba(99,102,241,0.3); }
    .btn-primary:hover { transform: translateY(-1px); box-shadow: 0 6px 30px rgba(99,102,241,0.45); }
    .btn-ghost { background: rgba(255,255,255,0.04); color: #8892a8; border: 1px solid #16162a; margin-top: 10px; }
    .btn-ghost:hover { background: rgba(255,255,255,0.07); color: #e2e8f0; }
    .btn-sm { display: inline-block; width: auto; padding: 6px 14px; font-size: 0.78rem; border-radius: 8px; }
    .key-box { background: #08081a; border: 1px solid #16162a; border-radius: 12px; padding: 18px; margin: 20px 0; font-family: 'JetBrains Mono', monospace; font-size: 0.9rem; color: #f59e0b; word-break: break-all; letter-spacing: 0.5px; user-select: all; position: relative; }
    .info { color: #4a5268; font-size: 0.8rem; margin-top: 16px; line-height: 1.7; }
    .info code { background: rgba(99,102,241,0.1); color: #6366f1; padding: 2px 7px; border-radius: 5px; font-family: 'JetBrains Mono', monospace; font-size: 0.78rem; }
    .error { color: #ef4444; font-size: 0.85rem; margin-bottom: 16px; background: rgba(239,68,68,0.08); padding: 10px 16px; border-radius: 8px; border: 1px solid rgba(239,68,68,0.15); }
    .dash-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 16px; margin-bottom: 24px; }
    .dash-card { background: #0a0a18; border: 1px solid #16162a; border-radius: 16px; padding: 24px; }
    .dash-card h3 { font-size: 0.82rem; color: #4a5268; font-weight: 600; margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.5px; }
    .dash-card .value { font-size: 1.8rem; font-weight: 800; letter-spacing: -1px; }
    .steps-list { text-align: left; background: #0a0a18; border: 1px solid #16162a; border-radius: 14px; padding: 20px; margin: 16px 0; }
    .step-item { display: flex; gap: 14px; padding: 10px 0; color: #8892a8; font-size: 0.85rem; line-height: 1.5; }
    .step-num { background: rgba(99,102,241,0.12); color: #6366f1; min-width: 26px; height: 26px; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 0.75rem; flex-shrink: 0; }
    table { width: 100%; border-collapse: collapse; font-size: 0.82rem; }
    th { text-align: left; padding: 10px 12px; color: #4a5268; font-weight: 600; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.5px; border-bottom: 1px solid #16162a; }
    td { padding: 10px 12px; border-bottom: 1px solid #0d0d22; }
"""


def _page_head(title="SkyAI"):
    return f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
    <title>{title}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>{_PAGE_CSS}</style></head>"""


def _page_nav(active=""):
    user = _get_web_user()
    from accounts import is_admin as _is_admin
    admin_link = '<a href="/admin">Admin</a>' if user and _is_admin(user) else ""
    if user:
        right = f"""<div class="topnav-user">
            {admin_link}
            <a href="/dashboard">Dashboard</a>
            <div class="topnav-avatar">{user[0].upper()}</div>
            <span class="topnav-name">{user}</span>
            <a href="/logout" style="color:#ef4444;">Logout</a>
        </div>"""
    else:
        right = '<div class="topnav-links"><a href="/login">Sign In</a><a href="/register" style="padding:7px 16px;background:rgba(99,102,241,0.12);border:1px solid rgba(99,102,241,0.25);border-radius:8px;color:#6366f1;font-weight:600;">Sign Up</a></div>'
    return f"""<nav class="topnav">
        <a href="/" class="topnav-logo">SkyAI</a>
        <div class="topnav-links" style="flex:1;justify-content:center;">
            <a href="/#features">Features</a>
            <a href="/#pricing">Pricing</a>
            <a href="/#faq">FAQ</a>
        </div>
        {right}
    </nav>"""


# Legacy alias
_PAGE_STYLE = f'<style>{_PAGE_CSS}</style><link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">'


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
    # If already logged in, go to dashboard
    if _get_web_user():
        return redirect("/dashboard")
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

    return f"""{_page_head("SkyAI — Sign In")}<body>
    {_page_nav()}
    <div class="page-center">
    <div class="card">
        <h1><span class="gradient">Welcome back</span></h1>
        <p class="sub">Sign in to your SkyAI account</p>
        {"<p class='error'>" + escape(error) + "</p>" if error else ""}
        <form method="POST">
            <input type="hidden" name="next" value="{escape(next_url)}">
            <input type="text" name="mc_username" placeholder="Minecraft Username" required autocomplete="off" autofocus>
            <input type="password" name="password" placeholder="Password" required>
            <button type="submit" class="btn btn-primary">Sign In</button>
        </form>
        <a href="/register?next={escape(next_url)}" class="btn btn-ghost">Don't have an account? Sign Up</a>
    </div>
    </div>
    </body></html>""", 200, {"Content-Type": "text/html"}


@app.route("/register", methods=["GET", "POST"])
def web_register():
    """Register page."""
    if _get_web_user():
        return redirect("/dashboard")
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

    return f"""{_page_head("SkyAI — Sign Up")}<body>
    {_page_nav()}
    <div class="page-center">
    <div class="card">
        <h1><span class="gradient">Create account</span></h1>
        <p class="sub">Sign up to get started with SkyAI</p>
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
    """Post-checkout page. Requires login. Generates key for free tier or links Whop key."""
    mc_username = _get_web_user()
    if not mc_username:
        plan = request.args.get("plan", "free")
        return redirect(f"/login?next=/purchased?plan={plan}")

    plan = request.args.get("plan", "free")
    if plan not in ("free", "basic", "pro"):
        plan = "free"

    from licenses import generate_key, _con

    if plan == "free":
        # Free tier — generate directly
        existing = _con.execute(
            "SELECT license_key FROM licenses WHERE mc_username = ? AND plan = 'free' AND active = 1",
            (mc_username,),
        ).fetchone()

        if existing:
            key = existing["license_key"]
        else:
            key = generate_key(plan="free", expires_days=None)
            _con.execute("UPDATE licenses SET mc_username = ? WHERE license_key = ?", (mc_username, key))
            _con.commit()

        return _render_dashboard(mc_username, key, "free")

    # Paid plans — check if Whop webhook already created a key, link it to this user
    # Look for unlinked Whop keys
    whop_key = _con.execute(
        "SELECT wm.license_key, wm.plan FROM whop_memberships wm WHERE wm.mc_username IS NULL AND wm.status = 'active' ORDER BY wm.created_at DESC LIMIT 1"
    ).fetchone()

    if whop_key and whop_key["license_key"]:
        # Link the Whop-generated key to this user
        _con.execute("UPDATE whop_memberships SET mc_username = ? WHERE license_key = ?", (mc_username, whop_key["license_key"]))
        _con.execute("UPDATE licenses SET mc_username = ? WHERE license_key = ?", (mc_username, whop_key["license_key"]))
        _con.commit()
        return _render_dashboard(mc_username, whop_key["license_key"], whop_key["plan"])

    # No Whop key yet — show a waiting message
    return f"""{_page_head("SkyAI — Processing")}<body>
    {_page_nav()}
    <div class="page-center"><div class="card">
        <h1><span class="gradient">Processing Payment</span></h1>
        <p class="sub">Your payment is being processed. This usually takes a few seconds.</p>
        <p class="info">If you just completed checkout on Whop, your key will appear on your dashboard shortly.</p>
        <a href="/dashboard" class="btn btn-primary">Go to Dashboard</a>
        <a href="/#pricing" class="btn btn-ghost">View Plans</a>
    </div></div></body></html>""", 200, {"Content-Type": "text/html"}




@app.route("/dashboard")
def dashboard():
    """View your license info. Requires login."""
    mc_username = _get_web_user()
    if not mc_username:
        return redirect("/login")

    from licenses import _con
    row = _con.execute(
        "SELECT license_key, plan, created_at, expires_at FROM licenses WHERE mc_username = ? AND active = 1 ORDER BY CASE plan WHEN 'unlimited' THEN 4 WHEN 'pro' THEN 3 WHEN 'basic' THEN 2 ELSE 1 END DESC LIMIT 1",
        (mc_username,),
    ).fetchone()

    if not row:
        return f"""{_page_head("SkyAI — Dashboard")}<body>
        {_page_nav("dashboard")}
        <div class="page" style="text-align:center;">
            <h1 style="font-size:2rem;margin-bottom:12px;">Welcome, <span class="gradient">{mc_username}</span></h1>
            <p class="sub">You don't have a license yet. Get started for free.</p>
            <div style="max-width:300px;margin:0 auto;">
                <a href="/purchased?plan=free" class="btn btn-primary">Get Free License</a>
                <a href="/#pricing" class="btn btn-ghost">View Plans</a>
            </div>
        </div></body></html>""", 200, {"Content-Type": "text/html"}

    return _render_dashboard(mc_username, row["license_key"], row["plan"])


def _render_dashboard(mc_username, key, plan):
    """Render the dashboard page with key + download."""
    from accounts import is_admin as _is_admin
    plan_names = {"free": "Free", "basic": "Basic", "pro": "Pro", "unlimited": "Unlimited"}
    plan_class = f"plan-{plan}" if plan in ("free", "basic", "pro", "unlimited") else "plan-free"
    limits = {"free": "10", "basic": "30", "pro": "100", "unlimited": "Unlimited"}
    plan_colors = {"free": "#22c55e", "basic": "#6366f1", "pro": "#a855f7", "unlimited": "#f59e0b"}
    color = plan_colors.get(plan, "#6366f1")
    is_free = plan == "free"
    is_admin_user = _is_admin(mc_username)

    return f"""{_page_head("SkyAI — Dashboard")}
    <style>
        .db-layout {{ display: grid; grid-template-columns: 220px 1fr; min-height: calc(100vh - 56px); }}
        .db-sidebar {{ background: #06060f; border-right: 1px solid #12122a; padding: 32px 0; }}
        .db-sidebar-section {{ padding: 0 16px; margin-bottom: 24px; }}
        .db-sidebar-label {{ font-size: 0.65rem; font-weight: 700; color: #3a3a5a; text-transform: uppercase; letter-spacing: 1.5px; padding: 0 12px; margin-bottom: 8px; }}
        .db-sidebar a {{ display: flex; align-items: center; gap: 10px; padding: 9px 12px; border-radius: 8px; color: #6a6a8a; font-size: 0.84rem; font-weight: 500; text-decoration: none; transition: all 0.15s; }}
        .db-sidebar a:hover {{ background: rgba(99,102,241,0.06); color: #c4c4e4; text-decoration: none; }}
        .db-sidebar a.active {{ background: rgba(99,102,241,0.1); color: #e2e8f0; font-weight: 600; }}
        .db-sidebar-icon {{ font-size: 1rem; width: 20px; text-align: center; }}
        .db-sidebar-user {{ padding: 16px; margin: 0 16px; background: #0a0a18; border: 1px solid #16162a; border-radius: 12px; margin-bottom: 24px; }}
        .db-sidebar-user-name {{ font-weight: 700; font-size: 0.9rem; margin-bottom: 2px; }}
        .db-sidebar-user-plan {{ display: inline-flex; align-items: center; gap: 6px; font-size: 0.72rem; font-weight: 600; color: {color}; }}
        .db-sidebar-user-dot {{ width: 6px; height: 6px; border-radius: 50%; background: {color}; box-shadow: 0 0 8px {color}88; }}

        .db-main {{ padding: 32px 40px; max-width: 780px; }}
        .db-main h1 {{ font-size: 1.5rem; font-weight: 800; margin-bottom: 6px; }}
        .db-main .db-sub {{ color: #4a5268; font-size: 0.84rem; margin-bottom: 32px; }}

        .db-cards {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; margin-bottom: 28px; }}
        .db-stat {{ background: #0a0a18; border: 1px solid #16162a; border-radius: 14px; padding: 20px; }}
        .db-stat-label {{ font-size: 0.7rem; font-weight: 600; color: #3a3a5a; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 6px; }}
        .db-stat-value {{ font-size: 1.4rem; font-weight: 800; letter-spacing: -0.5px; }}

        .db-key-section {{ background: #0a0a18; border: 1px solid #16162a; border-radius: 14px; padding: 24px; margin-bottom: 20px; position: relative; overflow: hidden; }}
        .db-key-section::before {{ content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px; background: linear-gradient(90deg, {color}, {color}44, transparent); }}
        .db-key-section h3 {{ font-size: 0.78rem; font-weight: 700; color: #4a5268; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 12px; }}
        .db-key-val {{ font-family: 'JetBrains Mono', monospace; font-size: 0.92rem; color: #f59e0b; letter-spacing: 0.5px; word-break: break-all; user-select: all; cursor: pointer; padding: 14px 16px; background: #08081a; border: 1px solid #12122a; border-radius: 10px; transition: border-color 0.2s; }}
        .db-key-val:hover {{ border-color: #f59e0b44; }}
        .db-key-hint {{ color: #3a3a5a; font-size: 0.72rem; margin-top: 10px; }}
        .db-key-cmd {{ display: inline-block; margin-top: 8px; background: rgba(99,102,241,0.08); color: #818cf8; padding: 6px 12px; border-radius: 6px; font-family: 'JetBrains Mono', monospace; font-size: 0.78rem; }}

        .db-actions {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 28px; }}
        .db-act {{ display: flex; align-items: center; justify-content: center; gap: 10px; padding: 15px; background: #0a0a18; border: 1px solid #16162a; border-radius: 12px; text-decoration: none; color: #c4c4e4; font-weight: 600; font-size: 0.86rem; transition: all 0.2s; }}
        .db-act:hover {{ background: #0e0e22; border-color: #22224a; text-decoration: none; transform: translateY(-1px); }}
        .db-act-primary {{ background: linear-gradient(135deg, #6366f1, #a855f7); color: #fff; border: none; box-shadow: 0 4px 20px rgba(99,102,241,0.25); }}
        .db-act-primary:hover {{ box-shadow: 0 6px 30px rgba(99,102,241,0.4); }}

        .db-setup {{ background: #0a0a18; border: 1px solid #16162a; border-radius: 14px; overflow: hidden; }}
        .db-setup-title {{ padding: 16px 24px; border-bottom: 1px solid #12122a; font-weight: 700; font-size: 0.82rem; }}
        .db-setup-list {{ padding: 4px 24px; }}
        .db-s {{ display: flex; gap: 14px; padding: 14px 0; border-bottom: 1px solid #0a0a1e; align-items: flex-start; }}
        .db-s:last-child {{ border-bottom: none; }}
        .db-sn {{ min-width: 26px; height: 26px; border-radius: 8px; background: rgba(99,102,241,0.08); color: #6366f1; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 0.72rem; flex-shrink: 0; }}
        .db-st {{ color: #6a6a8a; font-size: 0.82rem; line-height: 1.6; }}
        .db-st code {{ background: rgba(99,102,241,0.06); color: #818cf8; padding: 2px 7px; border-radius: 4px; font-family: 'JetBrains Mono', monospace; font-size: 0.75rem; }}
        .db-st strong {{ color: #c4c4e4; }}

        .db-upgrade {{ margin-top: 20px; background: linear-gradient(135deg, rgba(99,102,241,0.05), rgba(168,85,247,0.03)); border: 1px solid rgba(99,102,241,0.1); border-radius: 14px; padding: 22px; display: flex; justify-content: space-between; align-items: center; gap: 16px; }}
        .db-upgrade h4 {{ font-size: 0.9rem; font-weight: 700; margin-bottom: 3px; }}
        .db-upgrade p {{ color: #4a5268; font-size: 0.78rem; }}

        @media (max-width: 768px) {{
            .db-layout {{ grid-template-columns: 1fr; }}
            .db-sidebar {{ display: none; }}
            .db-main {{ padding: 24px 16px; }}
            .db-cards {{ grid-template-columns: 1fr; }}
            .db-actions {{ grid-template-columns: 1fr; }}
            .db-upgrade {{ flex-direction: column; text-align: center; }}
        }}
    </style>
    <body>
    {_page_nav("dashboard")}
    <div class="db-layout">
        <div class="db-sidebar">
            <div class="db-sidebar-user">
                <div class="db-sidebar-user-name">{mc_username}</div>
                <div class="db-sidebar-user-plan"><span class="db-sidebar-user-dot"></span> {plan_names.get(plan, plan)} Plan</div>
            </div>
            <div class="db-sidebar-section">
                <div class="db-sidebar-label">Account</div>
                <a href="/dashboard" class="active"><span class="db-sidebar-icon">&#9776;</span> Overview</a>
                <a href="/download"><span class="db-sidebar-icon">&#8595;</span> Download Mod</a>
                <a href="{'/#pricing' if is_free else 'https://whop.com/orders'}"><span class="db-sidebar-icon">{'&#9889;' if is_free else '&#9881;'}</span> {'Upgrade' if is_free else 'Manage Plan'}</a>
            </div>
            <div class="db-sidebar-section">
                <div class="db-sidebar-label">Links</div>
                <a href="/"><span class="db-sidebar-icon">&#127968;</span> Homepage</a>
                <a href="/#faq"><span class="db-sidebar-icon">&#63;</span> FAQ</a>
            </div>
            {"<div class='db-sidebar-section'><div class='db-sidebar-label'>Admin</div><a href='/admin'><span class='db-sidebar-icon'>&#9881;</span> Admin Panel</a></div>" if is_admin_user else ""}
            <div class="db-sidebar-section" style="margin-top:auto;">
                <a href="/logout" style="color:#ef4444;"><span class="db-sidebar-icon">&#10140;</span> Sign Out</a>
            </div>
        </div>
        <div class="db-main">
            <h1>Overview</h1>
            <p class="db-sub">Your SkyAI account at a glance.</p>

            <div class="db-cards">
                <div class="db-stat">
                    <div class="db-stat-label">Plan</div>
                    <div class="db-stat-value" style="color:{color};">{plan_names.get(plan, plan)}</div>
                </div>
                <div class="db-stat">
                    <div class="db-stat-label">Rate Limit</div>
                    <div class="db-stat-value">{limits.get(plan, "?")}<span style="font-size:0.7rem;color:#3a3a5a;font-weight:500;">/hr</span></div>
                </div>
                <div class="db-stat">
                    <div class="db-stat-label">Status</div>
                    <div class="db-stat-value" style="color:#22c55e;">Active</div>
                </div>
            </div>

            <div class="db-key-section">
                <h3>License Key</h3>
                <div class="db-key-val" id="license-key">{key}</div>
                <div class="db-key-hint" id="key-hint">Click to copy</div>
                <div class="db-key-cmd">!aikey {key}</div>
            </div>

            <div class="db-actions">
                <a href="/download" class="db-act db-act-primary">&#8595; Download Mod</a>
                <a href="{'/#pricing' if is_free else 'https://whop.com/orders'}" class="db-act">{'&#9889; Upgrade Plan' if is_free else '&#9881; Manage Subscription'}</a>
            </div>

            <div class="db-setup">
                <div class="db-setup-title">Quick Start Guide</div>
                <div class="db-setup-list">
                    <div class="db-s"><div class="db-sn">1</div><div class="db-st">Download the mod and place the <code>.jar</code> file in your <code>.minecraft/mods</code> folder</div></div>
                    <div class="db-s"><div class="db-sn">2</div><div class="db-st">Install <strong>Fabric Loader</strong> and <strong>Fabric API</strong> for Minecraft 1.21.10</div></div>
                    <div class="db-s"><div class="db-sn">3</div><div class="db-st">Launch Minecraft, join any server, type: <code>!aikey {key}</code></div></div>
                    <div class="db-s"><div class="db-sn">4</div><div class="db-st">Ask anything: <code>!ai what's the best money method</code></div></div>
                </div>
            </div>

            {"<div class='db-upgrade'><div><h4>Want more questions?</h4><p>Upgrade to Basic (30/hr) or Pro (100/hr).</p></div><a href='/#pricing' class='btn btn-primary' style='width:auto;padding:11px 22px;margin:0;white-space:nowrap;font-size:0.82rem;'>View Plans</a></div>" if is_free else ""}
        </div>
    </div>

    <script>
    document.getElementById('license-key').addEventListener('click', function() {{
        navigator.clipboard.writeText(this.textContent.trim());
        var h = document.getElementById('key-hint');
        h.innerHTML = '<span style="color:#22c55e;">Copied!</span>';
        setTimeout(function() {{ h.textContent = 'Click to copy'; }}, 2000);
    }});
    </script>
    </body></html>""", 200, {"Content-Type": "text/html"}


# ── Admin Panel ────────────────────────────────────────────────────────────

_ADMIN_STYLE = f'<style>{_PAGE_CSS}</style>'

@app.route("/admin")
def admin_panel():
    """Admin dashboard — manage licenses, users, questions, feedback."""
    mc_username = _get_web_user()
    if not mc_username:
        return redirect("/login?next=/admin")
    from accounts import is_admin
    if not is_admin(mc_username):
        return f"""{_page_head("SkyAI — Admin")}<body>
        {_page_nav()}
        <div class="page-center"><div class="card"><h1><span class="gradient">Access Denied</span></h1><p class="sub">You are not an admin.</p>
        <a href="/dashboard" class="btn btn-ghost">Back to Dashboard</a></div></div></body></html>""", 403, {"Content-Type": "text/html"}

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

    return f"""{_page_head("SkyAI — Admin")}<body>
    {_page_nav("admin")}
    <div class="page-wide">
        <h1 style="font-size:2rem;margin-bottom:32px;"><span class="gradient">Admin Panel</span></h1>

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
        key_list = "<br>".join(keys)
        return f"""{_page_head("Generated Keys")}<body>
        {_page_nav()}
        <div class="page-center"><div class="card">
            <h1><span class="gradient">Keys Generated</span></h1>
            <p class="sub">{count} {plan} keys</p>
            <div class="key-box" style="text-align:left;font-size:0.78rem;line-height:2.2;">{key_list}</div>
            <a href="/admin" class="btn btn-ghost">Back to Admin</a>
        </div></div></body></html>""", 200, {"Content-Type": "text/html"}

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
