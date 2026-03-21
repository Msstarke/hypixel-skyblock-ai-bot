"""
SQLite storage for community corrections to the bot's knowledge base.
Users submit corrections, owner reviews and approves/rejects them.
"""
import sqlite3
import time
from pathlib import Path
from data_dir import DATA_DIR

DB_PATH = DATA_DIR / "corrections.db"
CORRECTIONS_FILE = DATA_DIR / "community_corrections.md"
MAX_CORRECTION_LEN = 1000
MAX_PENDING_PER_USER = 3


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("""
        CREATE TABLE IF NOT EXISTS corrections (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            discord_id   INTEGER NOT NULL,
            discord_name TEXT NOT NULL,
            topic        TEXT NOT NULL,
            correction   TEXT NOT NULL,
            status       TEXT NOT NULL DEFAULT 'pending',
            submitted_at INTEGER NOT NULL,
            reviewed_at  INTEGER
        )
    """)
    return con


_con = _connect()


def submit_correction(discord_id: int, discord_name: str, topic: str, correction: str) -> int | None:
    """Submit a correction. Returns the row ID, or None if rate-limited."""
    pending = _con.execute(
        "SELECT COUNT(*) FROM corrections WHERE discord_id = ? AND status = 'pending'",
        (discord_id,),
    ).fetchone()[0]
    if pending >= MAX_PENDING_PER_USER:
        return None

    cur = _con.execute(
        "INSERT INTO corrections (discord_id, discord_name, topic, correction, submitted_at) VALUES (?, ?, ?, ?, ?)",
        (discord_id, discord_name, topic.strip()[:200], correction.strip()[:MAX_CORRECTION_LEN], int(time.time())),
    )
    _con.commit()
    return cur.lastrowid


def get_pending(limit: int = 10) -> list[dict]:
    """Get pending corrections for review."""
    rows = _con.execute(
        "SELECT * FROM corrections WHERE status = 'pending' ORDER BY submitted_at ASC LIMIT ?",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


def approve_correction(correction_id: int) -> dict | None:
    """Approve a correction. Returns the row if found, else None."""
    row = _con.execute(
        "SELECT * FROM corrections WHERE id = ? AND status = 'pending'",
        (correction_id,),
    ).fetchone()
    if not row:
        return None
    _con.execute(
        "UPDATE corrections SET status = 'approved', reviewed_at = ? WHERE id = ?",
        (int(time.time()), correction_id),
    )
    _con.commit()
    data = dict(row)
    apply_to_knowledge(data["topic"], data["correction"], data["discord_name"])
    return data


def reject_correction(correction_id: int) -> bool:
    """Reject a correction. Returns True if found."""
    cur = _con.execute(
        "UPDATE corrections SET status = 'rejected', reviewed_at = ? WHERE id = ? AND status = 'pending'",
        (int(time.time()), correction_id),
    )
    _con.commit()
    return cur.rowcount > 0


def apply_to_knowledge(topic: str, correction: str, submitter: str) -> None:
    """Append an approved correction to the community corrections knowledge file."""
    CORRECTIONS_FILE.parent.mkdir(exist_ok=True)
    header = ""
    if not CORRECTIONS_FILE.exists():
        header = "# Community Corrections\n\n"
    with open(CORRECTIONS_FILE, "a", encoding="utf-8") as f:
        f.write(f"{header}## {topic}\n{correction}\n\n")
