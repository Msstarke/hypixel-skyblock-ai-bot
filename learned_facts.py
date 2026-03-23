"""
Learned Facts — persistent cache for answers discovered via web search.
When the AI doesn't know something, it searches the web, answers with what it finds,
and caches the result here so future identical/similar questions are instant.
"""
import sqlite3
import time
from pathlib import Path
from data_dir import DATA_DIR

DB_PATH = DATA_DIR / "learned_facts.db"
FACT_TTL = 60 * 60 * 24 * 30  # 30 days before a fact expires


def _conn():
    c = sqlite3.connect(str(DB_PATH))
    c.execute("""CREATE TABLE IF NOT EXISTS facts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        question TEXT NOT NULL,
        keywords TEXT NOT NULL,
        answer TEXT NOT NULL,
        source TEXT DEFAULT '',
        created_at INTEGER NOT NULL,
        hit_count INTEGER DEFAULT 0
    )""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_keywords ON facts(keywords)")
    c.commit()
    return c


def save_fact(question: str, keywords: str, answer: str, source: str = ""):
    """Save a learned fact to the database."""
    c = _conn()
    # Check if we already have a similar fact (same keywords)
    existing = c.execute(
        "SELECT id FROM facts WHERE keywords = ?", (keywords.lower(),)
    ).fetchone()
    if existing:
        c.execute(
            "UPDATE facts SET answer = ?, source = ?, created_at = ? WHERE id = ?",
            (answer, source, int(time.time()), existing[0])
        )
    else:
        c.execute(
            "INSERT INTO facts (question, keywords, answer, source, created_at) VALUES (?, ?, ?, ?, ?)",
            (question, keywords.lower(), answer, source, int(time.time()))
        )
    c.commit()
    c.close()


def find_fact(question: str, max_results: int = 3) -> list[dict]:
    """Search for relevant cached facts. Returns list of {question, answer, source}."""
    import re
    c = _conn()
    q_words = set(re.sub(r"[^\w\s]", "", question.lower()).split())
    # Remove common stopwords
    stopwords = {"what", "is", "the", "a", "an", "of", "for", "how", "much",
                 "does", "do", "in", "and", "or", "to", "my", "i", "me",
                 "whats", "can", "you", "tell", "about", "where", "when",
                 "why", "are", "should", "would", "get", "best", "good"}
    q_words -= stopwords
    if not q_words:
        c.close()
        return []

    now = int(time.time())
    rows = c.execute(
        "SELECT id, question, keywords, answer, source, created_at FROM facts"
    ).fetchall()

    scored = []
    for row_id, q, kw, ans, src, created in rows:
        if now - created > FACT_TTL:
            continue
        kw_words = set(kw.split())
        overlap = len(q_words & kw_words)
        if overlap >= max(1, len(q_words) // 2):
            scored.append((overlap, {"question": q, "answer": ans, "source": src, "id": row_id}))

    scored.sort(key=lambda x: x[0], reverse=True)
    results = [s[1] for s in scored[:max_results]]

    # Bump hit counts
    for r in results:
        c.execute("UPDATE facts SET hit_count = hit_count + 1 WHERE id = ?", (r["id"],))
    c.commit()
    c.close()
    return results
