"""
User accounts for the SkyAI website.
Simple username + password system for the web dashboard.
"""

import hashlib
import secrets
import sqlite3
import time

from data_dir import DATA_DIR

DB_PATH = DATA_DIR / "accounts.db"


def _connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")

    con.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            mc_username  TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            created_at   INTEGER NOT NULL
        )
    """)

    con.execute("""
        CREATE TABLE IF NOT EXISTS web_sessions (
            token        TEXT PRIMARY KEY,
            mc_username  TEXT NOT NULL,
            created_at   INTEGER NOT NULL,
            expires_at   INTEGER NOT NULL
        )
    """)

    con.commit()
    return con


_con = _connect()

SESSION_DURATION = 7 * 86400  # 7 days


def _hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}:{h}"


def _verify_password(password: str, stored: str) -> bool:
    salt, h = stored.split(":", 1)
    return hashlib.sha256((salt + password).encode()).hexdigest() == h


def register(mc_username: str, password: str) -> dict:
    """Register a new account. Returns {ok, error}."""
    if len(mc_username) < 3 or len(mc_username) > 16:
        return {"ok": False, "error": "Username must be 3-16 characters"}
    if len(password) < 4:
        return {"ok": False, "error": "Password must be at least 4 characters"}

    existing = _con.execute(
        "SELECT id FROM accounts WHERE mc_username = ?", (mc_username,)
    ).fetchone()
    if existing:
        return {"ok": False, "error": "Username already registered"}

    _con.execute(
        "INSERT INTO accounts (mc_username, password_hash, created_at) VALUES (?, ?, ?)",
        (mc_username, _hash_password(password), int(time.time())),
    )
    _con.commit()
    return {"ok": True}


def login(mc_username: str, password: str) -> dict:
    """Login and return a session token. Returns {ok, token, error}."""
    row = _con.execute(
        "SELECT password_hash FROM accounts WHERE mc_username = ?", (mc_username,)
    ).fetchone()
    if not row:
        return {"ok": False, "error": "Account not found"}
    if not _verify_password(password, row["password_hash"]):
        return {"ok": False, "error": "Wrong password"}

    token = secrets.token_urlsafe(32)
    now = int(time.time())
    _con.execute(
        "INSERT INTO web_sessions (token, mc_username, created_at, expires_at) VALUES (?, ?, ?, ?)",
        (token, mc_username, now, now + SESSION_DURATION),
    )
    _con.commit()
    return {"ok": True, "token": token}


def get_session_user(token: str) -> str | None:
    """Get username from session token. Returns None if invalid/expired."""
    if not token:
        return None
    row = _con.execute(
        "SELECT mc_username, expires_at FROM web_sessions WHERE token = ?", (token,)
    ).fetchone()
    if not row or row["expires_at"] < int(time.time()):
        return None
    return row["mc_username"]


def logout(token: str):
    """Delete a session."""
    _con.execute("DELETE FROM web_sessions WHERE token = ?", (token,))
    _con.commit()
