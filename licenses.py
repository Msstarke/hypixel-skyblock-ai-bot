"""
License key management — UUID lock + single session + rate limiting.

Tables:
  licenses     — one row per license key (key, uuid, plan, created_at, expires_at)
  sessions     — one active session per license (token, last_seen)
"""

import hashlib
import secrets
import sqlite3
import time

from data_dir import DATA_DIR

DB_PATH = DATA_DIR / "licenses.db"


def _connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")

    con.execute("""
        CREATE TABLE IF NOT EXISTS licenses (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            license_key  TEXT NOT NULL UNIQUE,
            mc_uuid      TEXT,
            mc_username  TEXT,
            plan         TEXT NOT NULL DEFAULT 'basic',
            created_at   INTEGER NOT NULL,
            expires_at   INTEGER,
            active       INTEGER NOT NULL DEFAULT 1
        )
    """)

    con.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            license_id   INTEGER PRIMARY KEY,
            session_token TEXT NOT NULL,
            created_at   INTEGER NOT NULL,
            last_seen    INTEGER NOT NULL,
            FOREIGN KEY (license_id) REFERENCES licenses(id)
        )
    """)

    con.execute("""
        CREATE TABLE IF NOT EXISTS request_log (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            license_id   INTEGER NOT NULL,
            created_at   INTEGER NOT NULL
        )
    """)

    con.commit()
    return con


_con = _connect()

# Rate limit: max requests per hour per license
RATE_LIMITS = {
    "basic": 30,
    "pro": 100,
    "unlimited": 999999,
}


# ── Key generation ────────────────────────────────────────────────────────

def generate_key(plan: str = "basic", expires_days: int | None = 30) -> str:
    """Generate a new license key. Returns the key string."""
    key = "SKYAI-" + secrets.token_hex(12).upper()
    now = int(time.time())
    expires = now + (expires_days * 86400) if expires_days else None

    _con.execute(
        "INSERT INTO licenses (license_key, plan, created_at, expires_at) VALUES (?, ?, ?, ?)",
        (key, plan, now, expires),
    )
    _con.commit()
    return key


def generate_keys(count: int, plan: str = "basic", expires_days: int | None = 30) -> list[str]:
    """Generate multiple license keys at once."""
    return [generate_key(plan, expires_days) for _ in range(count)]


# ── Validation ────────────────────────────────────────────────────────────

def validate_key(license_key: str, mc_uuid: str, mc_username: str) -> dict:
    """
    Validate a license key + UUID.
    Returns {"ok": True, "session": "...", "plan": "..."} on success,
    or {"ok": False, "error": "..."} on failure.
    """
    row = _con.execute(
        "SELECT * FROM licenses WHERE license_key = ?", (license_key,)
    ).fetchone()

    if not row:
        return {"ok": False, "error": "Invalid license key"}

    if not row["active"]:
        return {"ok": False, "error": "License has been deactivated"}

    # Check expiry
    if row["expires_at"] and row["expires_at"] < int(time.time()):
        return {"ok": False, "error": "License has expired"}

    lid = row["id"]

    # UUID lock: first use binds to this UUID
    if row["mc_uuid"] is None:
        _con.execute(
            "UPDATE licenses SET mc_uuid = ?, mc_username = ? WHERE id = ?",
            (mc_uuid, mc_username, lid),
        )
        _con.commit()
    elif row["mc_uuid"] != mc_uuid:
        return {"ok": False, "error": "License is bound to a different Minecraft account"}

    # Update username if it changed
    if row["mc_username"] != mc_username:
        _con.execute("UPDATE licenses SET mc_username = ? WHERE id = ?", (mc_username, lid))
        _con.commit()

    # Create / refresh session (single session per license)
    token = secrets.token_hex(16)
    now = int(time.time())
    _con.execute(
        "INSERT OR REPLACE INTO sessions (license_id, session_token, created_at, last_seen) VALUES (?, ?, ?, ?)",
        (lid, token, now, now),
    )
    _con.commit()

    return {"ok": True, "session": token, "plan": row["plan"]}


def validate_session(session_token: str) -> dict | None:
    """
    Validate a session token. Returns license info or None if invalid.
    Also checks rate limits.
    """
    row = _con.execute(
        """SELECT s.license_id, s.session_token, l.license_key, l.mc_uuid, l.mc_username,
                  l.plan, l.active, l.expires_at
           FROM sessions s JOIN licenses l ON s.license_id = l.id
           WHERE s.session_token = ?""",
        (session_token,),
    ).fetchone()

    if not row:
        return None

    if not row["active"]:
        return None

    # Check expiry
    if row["expires_at"] and row["expires_at"] < int(time.time()):
        return None

    # Session timeout: 30 minutes of inactivity
    now = int(time.time())

    # Update last_seen
    _con.execute("UPDATE sessions SET last_seen = ? WHERE license_id = ?", (now, row["license_id"]))

    # Check rate limit
    limit = RATE_LIMITS.get(row["plan"], 30)
    hour_ago = now - 3600
    count = _con.execute(
        "SELECT COUNT(*) FROM request_log WHERE license_id = ? AND created_at > ?",
        (row["license_id"], hour_ago),
    ).fetchone()[0]

    if count >= limit:
        return {"rate_limited": True, "plan": row["plan"], "limit": limit}

    # Log this request
    _con.execute(
        "INSERT INTO request_log (license_id, created_at) VALUES (?, ?)",
        (row["license_id"], now),
    )
    _con.commit()

    return {
        "license_id": row["license_id"],
        "mc_uuid": row["mc_uuid"],
        "mc_username": row["mc_username"],
        "plan": row["plan"],
    }


# ── Admin helpers ─────────────────────────────────────────────────────────

def list_licenses(limit: int = 50) -> list[dict]:
    """List all licenses."""
    rows = _con.execute(
        "SELECT * FROM licenses ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    return [dict(r) for r in rows]


def deactivate_key(license_key: str) -> bool:
    """Deactivate a license key."""
    cur = _con.execute("UPDATE licenses SET active = 0 WHERE license_key = ?", (license_key,))
    _con.commit()
    return cur.rowcount > 0


def reactivate_key(license_key: str) -> bool:
    """Reactivate a license key."""
    cur = _con.execute("UPDATE licenses SET active = 1 WHERE license_key = ?", (license_key,))
    _con.commit()
    return cur.rowcount > 0


def unbind_key(license_key: str) -> bool:
    """Unbind a license key from its UUID (allow re-binding)."""
    cur = _con.execute(
        "UPDATE licenses SET mc_uuid = NULL, mc_username = NULL WHERE license_key = ?",
        (license_key,),
    )
    _con.commit()
    return cur.rowcount > 0


def get_license_info(license_key: str) -> dict | None:
    """Get info about a specific license."""
    row = _con.execute("SELECT * FROM licenses WHERE license_key = ?", (license_key,)).fetchone()
    return dict(row) if row else None


def cleanup_old_logs(days: int = 7):
    """Delete request logs older than N days."""
    cutoff = int(time.time()) - (days * 86400)
    _con.execute("DELETE FROM request_log WHERE created_at < ?", (cutoff,))
    _con.commit()
