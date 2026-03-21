"""
Feedback analysis agent — reviews thumbs down votes and unanswered questions,
identifies patterns, and suggests fixes using AI.
"""
import os
import time
import sqlite3
from collections import Counter
from groq import AsyncGroq

from feedback import get_bad_responses, get_unanswered, get_feedback_stats
from data_dir import DATA_DIR

# How often to auto-analyze (seconds) — default 6 hours
ANALYSIS_INTERVAL = int(os.getenv("FEEDBACK_ANALYSIS_INTERVAL", 21600))

# File to persist last analysis results
ANALYSIS_FILE = DATA_DIR / "last_analysis.txt"
DB_PATH = DATA_DIR / "feedback.db"


def _get_all_feedback(limit: int = 50) -> list[dict]:
    """Get all feedback entries (both up and down) for pattern analysis."""
    try:
        con = sqlite3.connect(DB_PATH)
        con.row_factory = sqlite3.Row
        rows = con.execute(
            "SELECT * FROM feedback WHERE resolved = 0 ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        con.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


def _extract_topics(entries: list[dict]) -> Counter:
    """Extract topic keywords from feedback entries."""
    topic_keywords = {
        "networth": ["networth", "net worth", "worth", "value"],
        "price": ["price", "cost", "bazaar", "auction", "ah", "how much", "coins"],
        "dungeons": ["dungeon", "catacombs", "cata", "floor", "f7", "f5", "master mode"],
        "mining": ["mining", "hotm", "drill", "pickaxe", "dwarven", "crystal hollows"],
        "slayer": ["slayer", "revenant", "tarantula", "sven", "voidgloom"],
        "pets": ["pet", "pet level", "pet xp"],
        "gear": ["gear", "setup", "armor", "weapon", "best"],
        "skills": ["skill", "xp", "level", "farming", "combat"],
        "magical power": ["magical power", "mp", "accessory", "talisman"],
        "minions": ["minion", "minion slot", "minion speed"],
    }

    topic_counts = Counter()
    for entry in entries:
        q = entry.get("question", "").lower()
        for topic, keywords in topic_keywords.items():
            if any(kw in q for kw in keywords):
                topic_counts[topic] += 1
    return topic_counts


async def analyze_feedback() -> str:
    """Run AI-powered analysis on recent feedback to identify issues and suggest fixes.

    Returns a formatted analysis string.
    """
    stats = get_feedback_stats()
    bad = get_bad_responses(20)
    unanswered = get_unanswered(20)
    all_feedback = _get_all_feedback(50)

    if not bad and not unanswered:
        return "No negative feedback or unanswered questions to analyze."

    # Topic breakdown for downvotes
    down_entries = [e for e in all_feedback if e.get("vote") == "down"]
    up_entries = [e for e in all_feedback if e.get("vote") == "up"]
    down_topics = _extract_topics(down_entries)
    up_topics = _extract_topics(up_entries)

    # Build summary for AI
    summary_parts = [
        f"**Feedback Stats:** {stats['thumbs_up']} upvotes, {stats['thumbs_down']} downvotes, {stats['unanswered']} unanswered",
        "",
    ]

    if down_topics:
        summary_parts.append("**Downvoted topics (most common):**")
        for topic, count in down_topics.most_common(10):
            up_count = up_topics.get(topic, 0)
            summary_parts.append(f"  - {topic}: {count} downvotes, {up_count} upvotes")
        summary_parts.append("")

    if bad:
        summary_parts.append("**Recent downvoted Q&A pairs:**")
        for i, b in enumerate(bad[:10], 1):
            ts = time.strftime("%Y-%m-%d", time.localtime(b["created_at"]))
            summary_parts.append(f"{i}. [{ts}] Q: {b['question'][:200]}")
            summary_parts.append(f"   A: {b['response'][:200]}")
        summary_parts.append("")

    if unanswered:
        summary_parts.append("**Unanswered questions:**")
        for i, u in enumerate(unanswered[:10], 1):
            ts = time.strftime("%Y-%m-%d", time.localtime(u["created_at"]))
            summary_parts.append(f"{i}. [{ts}] {u['question'][:200]}")
        summary_parts.append("")

    local_summary = "\n".join(summary_parts)

    # Use AI to generate actionable analysis
    client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))
    try:
        resp = await client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a feedback analysis agent for a Hypixel Skyblock Discord bot. "
                        "Analyze the feedback data and produce a concise, actionable report. "
                        "Focus on:\n"
                        "1. PATTERNS — what topics/areas get the most negative feedback?\n"
                        "2. ROOT CAUSES — why are users unhappy? (wrong info, missing data, bad formatting, etc.)\n"
                        "3. FIXES — specific, actionable improvements ranked by impact\n"
                        "4. KNOWLEDGE GAPS — topics where the bot needs better knowledge base content\n\n"
                        "Keep the report under 800 words. Use markdown formatting."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Analyze this feedback data and suggest improvements:\n\n{local_summary}",
                },
            ],
            max_tokens=1200,
            temperature=0.3,
        )
        ai_analysis = resp.choices[0].message.content
    except Exception as e:
        ai_analysis = f"(AI analysis unavailable: {e})"

    # Combine local stats + AI analysis
    report = f"# Feedback Analysis Report\n_{time.strftime('%Y-%m-%d %H:%M')}_\n\n"
    report += local_summary + "\n---\n\n"
    report += "## AI Analysis\n" + ai_analysis

    # Persist to file
    ANALYSIS_FILE.write_text(report, encoding="utf-8")

    return report


def get_last_analysis() -> str | None:
    """Get the most recent analysis report, if one exists."""
    if ANALYSIS_FILE.exists():
        return ANALYSIS_FILE.read_text(encoding="utf-8")
    return None
