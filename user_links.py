"""
Simple SQLite storage for Discord → Minecraft account links.
Stores UUID (permanent) alongside username (display only).
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
    # Add mc_uuid column (safe to re-run)
    try:
        con.execute("ALTER TABLE links ADD COLUMN mc_uuid TEXT")
    except sqlite3.OperationalError:
        pass  # column already exists
    return con


_con = _connect()


def link_user(discord_id: int, mc_username: str, mc_uuid: str = None) -> None:
    """Link a Discord user to a Minecraft username and UUID."""
    _con.execute(
        "INSERT OR REPLACE INTO links (discord_id, mc_username, mc_uuid, linked_at) VALUES (?, ?, ?, ?)",
        (discord_id, mc_username.strip(), mc_uuid, int(time.time())),
    )
    _con.commit()


def update_uuid(discord_id: int, mc_uuid: str) -> None:
    """Store a resolved UUID for an existing link."""
    _con.execute(
        "UPDATE links SET mc_uuid = ? WHERE discord_id = ?",
        (mc_uuid, discord_id),
    )
    _con.commit()


def update_username(discord_id: int, mc_username: str) -> None:
    """Update the cached display username for an existing link."""
    _con.execute(
        "UPDATE links SET mc_username = ? WHERE discord_id = ?",
        (mc_username, discord_id),
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


def get_linked_uuid(discord_id: int) -> str | None:
    """Get the stored UUID for a Discord user, or None."""
    row = _con.execute(
        "SELECT mc_uuid FROM links WHERE discord_id = ?", (discord_id,)
    ).fetchone()
    return row[0] if row else None
