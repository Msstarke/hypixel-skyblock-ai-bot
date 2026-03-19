"""
SQLite storage for bot response feedback (thumbs up/down) and unanswered question logging.
"""
import sqlite3
import time
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "feedback.db"


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            discord_id   INTEGER NOT NULL,
            discord_name TEXT NOT NULL,
            question     TEXT NOT NULL,
            response     TEXT NOT NULL,
            vote         TEXT NOT NULL,
            created_at   INTEGER NOT NULL
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS unanswered (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            question     TEXT NOT NULL,
            discord_id   INTEGER,
            created_at   INTEGER NOT NULL
        )
    """)
    return con


_con = _connect()


def log_vote(discord_id: int, discord_name: str, question: str, response: str, vote: str) -> int:
    """Log a thumbs up/down vote. vote should be 'up' or 'down'."""
    cur = _con.execute(
        "INSERT INTO feedback (discord_id, discord_name, question, response, vote, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (discord_id, discord_name, question[:500], response[:1000], vote, int(time.time())),
    )
    _con.commit()
    return cur.lastrowid


def log_unanswered(question: str, discord_id: int = None) -> None:
    """Log a question the bot couldn't answer."""
    _con.execute(
        "INSERT INTO unanswered (question, discord_id, created_at) VALUES (?, ?, ?)",
        (question[:500], discord_id, int(time.time())),
    )
    _con.commit()


def get_bad_responses(limit: int = 10) -> list[dict]:
    """Get recent thumbs-down responses for review."""
    rows = _con.execute(
        "SELECT * FROM feedback WHERE vote = 'down' ORDER BY created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_unanswered(limit: int = 20) -> list[dict]:
    """Get recent unanswered questions."""
    rows = _con.execute(
        "SELECT * FROM unanswered ORDER BY created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_feedback_stats() -> dict:
    """Get summary stats."""
    up = _con.execute("SELECT COUNT(*) FROM feedback WHERE vote = 'up'").fetchone()[0]
    down = _con.execute("SELECT COUNT(*) FROM feedback WHERE vote = 'down'").fetchone()[0]
    unans = _con.execute("SELECT COUNT(*) FROM unanswered").fetchone()[0]
    return {"thumbs_up": up, "thumbs_down": down, "unanswered": unans}
