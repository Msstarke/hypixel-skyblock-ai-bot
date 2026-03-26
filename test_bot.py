"""
Auto-tester for the Hypixel AI bot.
Fires a set of questions at the live Railway endpoint and grades each response
against expected keywords / patterns.

Usage:
    python test_bot.py                  # test prod (Railway)
    python test_bot.py --local          # test localhost:5000
    python test_bot.py --verbose        # print full responses
    python test_bot.py --suite mining   # run only one suite
"""

import argparse
import json
import re
import sys
import time
import urllib.request
import urllib.error

RAILWAY_URL = "https://worker-production-f916.up.railway.app/api/ask"
LOCAL_URL   = "http://localhost:5000/api/ask"

# ---------------------------------------------------------------------------
# Test cases
# Format: (question, required_keywords_any, required_keywords_all, bad_keywords, suite)
#   required_any  — at least ONE of these must appear in the response
#   required_all  — ALL of these must appear
#   bad_keywords  — NONE of these should appear  (hallucination markers)
# ---------------------------------------------------------------------------
TESTS = [
    # ── Diana / Mythological Ritual ─────────────────────────────────────────
    {
        "suite": "diana",
        "question": "How much profit can I make per hour doing Diana?",
        "required_any": ["70", "100", "12m", "12 m", "common", "legendary"],
        "required_all": [],
        "bad_keywords": ["1.5m", "2.5m", "1-2m", "2-3m", "1.5 million", "2 million per hour"],
    },
    {
        "suite": "diana",
        "question": "What is the drop rate for Inquisitor from Diana?",
        "required_any": ["1/81", "1.23%", "1.2%", "81", "inquisitor"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "diana",
        "question": "What mobs spawn from Diana's mythological ritual?",
        "required_any": ["griffin", "minotaur", "minos", "inquisitor", "chimera"],
        "required_all": [],
        "bad_keywords": [],
    },
    # ── Mining ───────────────────────────────────────────────────────────────
    {
        "suite": "mining",
        "question": "What mining speed do I need to 4-tick gray mithril?",
        "required_any": ["3334", "3,334", "3300", "3500"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "mining",
        "question": "What mining speed do I need to 4-tick blue mithril?",
        "required_any": ["10000", "10,000"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "mining",
        "question": "How many ticks does it take to break mithril?",
        "required_any": ["4", "tick", "mining speed", "block strength"],
        "required_all": [],
        "bad_keywords": [],
    },
    # ── SkyBlock time ────────────────────────────────────────────────────────
    {
        "suite": "time",
        "question": "What SkyBlock year is it right now?",
        "required_any": ["year", "386", "385", "384"],  # ~year 385-387 in 2026
        "required_all": [],
        "bad_keywords": ["i don't know", "i do not know", "cannot determine"],
    },
    {
        "suite": "time",
        "question": "When is Jerry's Workshop?",
        "required_any": ["late winter", "december", "winter"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "time",
        "question": "When is Shen's Auction?",
        "required_any": ["late spring", "spring"],
        "required_all": [],
        "bad_keywords": [],
    },
    # ── Dungeons ─────────────────────────────────────────────────────────────
    {
        "suite": "dungeons",
        "question": "What gear should I use as a cata 0 mage in dungeons?",
        "required_any": ["zombie", "spider", "lapis", "wise dragon", "crystal", "mage"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "dungeons",
        "question": "Is the Rogue Sword good for dungeons?",
        "required_any": ["free", "hub", "not a dungeon", "speed"],
        "required_all": [],
        "bad_keywords": [],
    },
    # ── Mayors & Perks ───────────────────────────────────────────────────────
    {
        "suite": "mayors",
        "question": "How many pelts per hour can I get with Finnegan as mayor?",
        "required_any": ["150", "200", "550", "pelt"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "mayors",
        "question": "What does the Scorpius mayor do?",
        "required_any": ["bribe", "corrupt", "dark auction", "scorpius"],
        "required_all": [],
        "bad_keywords": [],
    },
    # ── General knowledge ────────────────────────────────────────────────────
    {
        "suite": "general",
        "question": "What is the best sword for early game in SkyBlock?",
        "required_any": ["aspect", "livid", "shadow fury", "dreadlord", "sword"],
        "required_all": [],
        "bad_keywords": [],
    },
    {
        "suite": "general",
        "question": "How do I get to the Crystal Hollows?",
        "required_any": ["deep", "cavern", "dwarven", "hotm", "heart of the mountain", "mining 6"],
        "required_all": [],
        "bad_keywords": [],
    },
]

# ---------------------------------------------------------------------------

def ask(url: str, question: str) -> tuple[str, float]:
    payload = json.dumps({"question": question}).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read())
            elapsed = time.time() - t0
            return body.get("response") or body.get("answer") or str(body), elapsed
    except urllib.error.HTTPError as e:
        return f"HTTP {e.code}: {e.read().decode()[:200]}", time.time() - t0
    except Exception as ex:
        return f"ERROR: {ex}", time.time() - t0


def grade(response: str, test: dict) -> tuple[bool, str]:
    low = response.lower()
    for bad in test.get("bad_keywords", []):
        if bad.lower() in low:
            return False, f"HALLUCINATION: found '{bad}'"
    any_kw = test.get("required_any", [])
    if any_kw and not any(k.lower() in low for k in any_kw):
        return False, f"MISSING any of {any_kw}"
    for req in test.get("required_all", []):
        if req.lower() not in low:
            return False, f"MISSING required '{req}'"
    return True, "OK"


def run(url: str, suite_filter: str | None, verbose: bool):
    tests = TESTS
    if suite_filter:
        tests = [t for t in TESTS if t["suite"] == suite_filter]
        if not tests:
            print(f"No tests found for suite '{suite_filter}'")
            sys.exit(1)

    passed = failed = 0
    results = []

    for t in tests:
        resp, elapsed = ask(url, t["question"])
        ok, reason = grade(resp, t)
        status = "PASS" if ok else "FAIL"
        if ok:
            passed += 1
        else:
            failed += 1
        results.append((status, t["suite"], t["question"], reason, resp, elapsed))

    # ── Print results ─────────────────────────────────────────────────────
    print(f"\n{'='*70}")
    print(f"  Hypixel AI Bot — Auto Test Results")
    print(f"  URL: {url}")
    print(f"{'='*70}")

    for status, suite, question, reason, resp, elapsed in results:
        icon = "+" if status == "PASS" else "X"
        print(f"\n[{icon}] [{suite}] {question}")
        print(f"    → {reason}  ({elapsed:.1f}s)")
        if verbose or status == "FAIL":
            short = resp[:300].replace("\n", " ")
            print(f"    Response: {short}")

    print(f"\n{'='*70}")
    total = passed + failed
    pct = int(passed / total * 100) if total else 0
    print(f"  PASSED: {passed}/{total}  ({pct}%)")
    if failed:
        print(f"  FAILED: {failed}")
    print(f"{'='*70}\n")

    return failed == 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--local",   action="store_true", help="Test localhost:5000 instead of Railway")
    parser.add_argument("--verbose", action="store_true", help="Print full responses")
    parser.add_argument("--suite",   type=str,            help="Run only this suite (diana/mining/time/dungeons/mayors/general)")
    args = parser.parse_args()

    url = LOCAL_URL if args.local else RAILWAY_URL
    success = run(url, args.suite, args.verbose)
    sys.exit(0 if success else 1)
