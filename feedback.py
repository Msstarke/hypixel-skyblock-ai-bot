"""
SQLite storage for bot response feedback (thumbs up/down) and unanswered question logging.
"""
import sqlite3
import time
from data_dir import DATA_DIR

DB_PATH = DATA_DIR / "feedback.db"


def _connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
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
    con.execute("""
        CREATE TABLE IF NOT EXISTS question_log (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            username     TEXT NOT NULL,
            question     TEXT NOT NULL,
            response     TEXT NOT NULL,
            created_at   INTEGER NOT NULL
        )
    """)
    # Add resolved column to existing tables (safe to re-run)
    for table in ("feedback", "unanswered"):
        try:
            con.execute(f"ALTER TABLE {table} ADD COLUMN resolved INTEGER NOT NULL DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # column already exists
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
    """Get recent unresolved thumbs-down responses for review."""
    rows = _con.execute(
        "SELECT * FROM feedback WHERE vote = 'down' AND resolved = 0 ORDER BY created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_unanswered(limit: int = 20) -> list[dict]:
    """Get recent unresolved unanswered questions."""
    rows = _con.execute(
        "SELECT * FROM unanswered WHERE resolved = 0 ORDER BY created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_feedback_stats() -> dict:
    """Get summary stats (unresolved only)."""
    up = _con.execute("SELECT COUNT(*) FROM feedback WHERE vote = 'up'").fetchone()[0]
    down = _con.execute("SELECT COUNT(*) FROM feedback WHERE vote = 'down' AND resolved = 0").fetchone()[0]
    unans = _con.execute("SELECT COUNT(*) FROM unanswered WHERE resolved = 0").fetchone()[0]
    return {"thumbs_up": up, "thumbs_down": down, "unanswered": unans}


def resolve_feedback(feedback_id: int) -> bool:
    """Mark a specific feedback entry as resolved (checks both tables)."""
    cur = _con.execute("UPDATE feedback SET resolved = 1 WHERE id = ? AND resolved = 0", (feedback_id,))
    _con.commit()
    if cur.rowcount > 0:
        return True
    cur = _con.execute("UPDATE unanswered SET resolved = 1 WHERE id = ? AND resolved = 0", (feedback_id,))
    _con.commit()
    return cur.rowcount > 0


def log_question(username: str, question: str, response: str) -> None:
    """Log every question asked to the bot."""
    _con.execute(
        "INSERT INTO question_log (username, question, response, created_at) VALUES (?, ?, ?, ?)",
        (username[:100], question[:500], response[:1000], int(time.time())),
    )
    _con.commit()


def get_questions(limit: int = 50, offset: int = 0) -> list[dict]:
    """Get recent questions from the log."""
    rows = _con.execute(
        "SELECT * FROM question_log ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()
    return [dict(r) for r in rows]


def resolve_all_feedback() -> int:
    """Mark all unresolved downvotes and unanswered questions as resolved. Returns count resolved."""
    c1 = _con.execute("UPDATE feedback SET resolved = 1 WHERE vote = 'down' AND resolved = 0").rowcount
    c2 = _con.execute("UPDATE unanswered SET resolved = 1 WHERE resolved = 0").rowcount
    _con.commit()
    return c1 + c2
