"""
Hypixel Skyblock Fandom Wiki Scraper
Fetches wiki pages via the MediaWiki API, strips HTML to clean text,
and saves categorized markdown files into the knowledge/ directory.

Usage:
    python wiki_scraper.py
    python wiki_scraper.py --pages Bestiary Skills  # scrape specific categories only
"""

import asyncio
import aiohttp
import re
import argparse
import time
from pathlib import Path
from bs4 import BeautifulSoup

WIKI_API = "https://hypixel-skyblock.fandom.com/api.php"
KNOWLEDGE_DIR = Path(__file__).parent / "knowledge"
RATE_LIMIT = 1.2  # seconds between requests (be polite)

HEADERS = {
    "User-Agent": "HypixelSkyblockBot/1.0 (educational Discord bot; contact via GitHub)",
    "Accept": "application/json",
}

# ── Page groups → output filename ────────────────────────────────────────────
# Each entry: (output_file, [wiki page titles to fetch and merge])
PAGE_GROUPS = [
    ("bestiary.md", [
        "Bestiary",
    ]),
    ("skills.md", [
        "Skills",
        "Farming",
        "Mining",
        "Combat",
        "Foraging",
        "Fishing",
        "Enchanting",
        "Alchemy",
        "Taming",
        "Carpentry",
        "Runecrafting",
    ]),
    ("dungeons.md", [
        "Dungeons",
        "Catacombs",
        "The Catacombs - Floor I",
        "The Catacombs - Floor II",
        "The Catacombs - Floor III",
        "The Catacombs - Floor IV",
        "The Catacombs - Floor V",
        "The Catacombs - Floor VI",
        "The Catacombs - Floor VII",
        "Master Mode Catacombs",
        "Dungeon Classes",
        "Dungeon Hub",
    ]),
    ("slayer.md", [
        "Slayer",
        "Revenant Horror",
        "Tarantula Broodfather",
        "Sven Packmaster",
        "Voidgloom Seraph",
        "Inferno Demonlord",
        "Vampire Slayer",
    ]),
    ("minions.md", [
        "Minions",
        "Minion Fuel",
        "Minion Upgrades",
        "Super Compactor 3000",
    ]),
    ("items.md", [
        "Weapons",
        "Armor",
        "Reforge",
        "Accessories",
        "Talismans",
        "Hyperion",
        "Necron's Blade",
        "Livid Dagger",
        "Terminator",
        "Aspect of the Dragons",
        "Wither Armor",
        "Necron's Armor",
    ]),
    ("pets.md", [
        "Pets",
        "Pet Leveling",
        "Pet Items",
    ]),
    ("collections.md", [
        "Collections",
        "Mining Collections",
        "Farming Collections",
        "Combat Collections",
        "Fishing Collections",
        "Foraging Collections",
    ]),
    ("locations.md", [
        "The Hub",
        "Spider's Den",
        "The End",
        "Crimson Isle",
        "The Park",
        "Deep Caverns",
        "Dwarven Mines",
        "Crystal Hollows",
        "The Rift",
        "Glacite Tunnels",
    ]),
    ("economy.md", [
        "Bazaar",
        "Auction House",
        "NPC",
        "Coins",
        "Trading",
    ]),
    ("general.md", [
        "Hypixel SkyBlock",
        "Fairy Souls",
        "Essence",
        "Kuudra",
        "Magic Find",
        "SkyBlock Level",
    ]),
]


def html_to_text(html: str) -> str:
    """Convert MediaWiki parsed HTML to clean plain text."""
    soup = BeautifulSoup(html, "html.parser")

    # Remove unwanted elements
    for tag in soup.find_all(["script", "style", "sup", "nav", "footer",
                               "aside", ".mw-editsection", ".reference",
                               ".toc", ".navbox", ".infobox-subheader"]):
        tag.decompose()

    # Remove edit section links
    for tag in soup.find_all(class_=["mw-editsection", "editsection"]):
        tag.decompose()

    lines = []
    for elem in soup.find_all(["h1", "h2", "h3", "h4", "p", "li", "tr", "td", "th", "dt", "dd"]):
        tag = elem.name
        text = elem.get_text(" ", strip=True)
        if not text or len(text) < 2:
            continue

        if tag == "h1":
            lines.append(f"\n# {text}")
        elif tag == "h2":
            lines.append(f"\n## {text}")
        elif tag == "h3":
            lines.append(f"\n### {text}")
        elif tag == "h4":
            lines.append(f"\n#### {text}")
        elif tag in ("p", "dd"):
            lines.append(text)
        elif tag == "li":
            lines.append(f"- {text}")
        elif tag in ("th", "td"):
            lines.append(f"  {text}")

    # Clean up excessive blank lines
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


async def fetch_page(session: aiohttp.ClientSession, title: str) -> str | None:
    """Fetch a single wiki page via the MediaWiki parse API."""
    params = {
        "action": "parse",
        "page": title,
        "prop": "text",
        "format": "json",
        "disableeditsection": "1",
        "disabletoc": "1",
    }
    try:
        async with session.get(WIKI_API, params=params, headers=HEADERS,
                                timeout=aiohttp.ClientTimeout(total=20)) as resp:
            if resp.status == 200:
                data = await resp.json()
                if "error" in data:
                    print(f"  [skip] {title}: {data['error'].get('info', 'unknown error')}")
                    return None
                html = data.get("parse", {}).get("text", {}).get("*", "")
                if html:
                    return html_to_text(html)
            else:
                print(f"  [skip] {title}: HTTP {resp.status}")
    except Exception as e:
        print(f"  [error] {title}: {e}")
    return None


async def scrape_group(session: aiohttp.ClientSession, output_file: str, pages: list[str]) -> bool:
    """Fetch all pages in a group and merge into one knowledge file."""
    print(f"\n=== {output_file} ===")
    sections = []

    for title in pages:
        print(f"  Fetching: {title} ...", end=" ", flush=True)
        text = await fetch_page(session, title)
        if text:
            sections.append(f"# {title}\n\n{text}")
            print(f"OK ({len(text):,} chars)")
        await asyncio.sleep(RATE_LIMIT)

    if not sections:
        print(f"  Nothing fetched for {output_file}, skipping.")
        return False

    combined = "\n\n---\n\n".join(sections)
    out_path = KNOWLEDGE_DIR / output_file
    out_path.write_text(combined, encoding="utf-8")
    print(f"  Saved → {out_path} ({len(combined):,} chars, {len(sections)}/{len(pages)} pages)")
    return True


async def main(target_groups: list[str] | None = None):
    KNOWLEDGE_DIR.mkdir(exist_ok=True)

    groups = PAGE_GROUPS
    if target_groups:
        target_lower = {t.lower() for t in target_groups}
        groups = [(f, p) for f, p in PAGE_GROUPS
                  if any(t in f.lower() for t in target_lower)]
        if not groups:
            print(f"No matching groups for: {target_groups}")
            return

    total_pages = sum(len(p) for _, p in groups)
    print(f"Scraping {len(groups)} knowledge files ({total_pages} pages total)")
    print(f"Rate limit: {RATE_LIMIT}s between requests")
    print(f"Estimated time: ~{int(total_pages * RATE_LIMIT / 60)} minutes\n")

    start = time.time()
    async with aiohttp.ClientSession() as session:
        for output_file, pages in groups:
            await scrape_group(session, output_file, pages)

    elapsed = int(time.time() - start)
    print(f"\nDone in {elapsed}s. Knowledge files saved to: {KNOWLEDGE_DIR}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scrape Hypixel Skyblock wiki into knowledge files")
    parser.add_argument("--pages", nargs="*", help="Only scrape these categories (e.g. bestiary skills)")
    args = parser.parse_args()
    asyncio.run(main(args.pages))
