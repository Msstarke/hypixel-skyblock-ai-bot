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

from flask import Flask, request, jsonify
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


@app.route("/")
def index():
    """Root endpoint — just confirms the API is running."""
    return jsonify({"status": "ok", "service": "hypixel-ai-bot"})


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


@app.route("/api/mod/download")
def api_mod_download():
    """Serves the latest mod jar for auto-update."""
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
