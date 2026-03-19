"""
Simple SQLite storage for Discord → Minecraft account links.
"""
import sqlite3
import time
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "user_links.db"


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("""
        CREATE TABLE IF NOT EXISTS links (
            discord_id   INTEGER PRIMARY KEY,
            mc_username  TEXT NOT NULL,
            linked_at    INTEGER NOT NULL
        )
    """)
    return con


_con = _connect()


def link_user(discord_id: int, mc_username: str) -> None:
    """Link a Discord user to a Minecraft username."""
    _con.execute(
        "INSERT OR REPLACE INTO links (discord_id, mc_username, linked_at) VALUES (?, ?, ?)",
        (discord_id, mc_username.strip(), int(time.time())),
    )
    _con.commit()


def unlink_user(discord_id: int) -> bool:
    """Unlink a Discord user. Returns True if a link existed."""
    cur = _con.execute("DELETE FROM links WHERE discord_id = ?", (discord_id,))
    _con.commit()
    return cur.rowcount > 0


def get_linked_username(discord_id: int) -> str | None:
    """Get the Minecraft username for a Discord user, or None."""
    row = _con.execute(
        "SELECT mc_username FROM links WHERE discord_id = ?", (discord_id,)
    ).fetchone()
    return row[0] if row else None
