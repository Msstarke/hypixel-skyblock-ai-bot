"""
Live Hypixel Skyblock wiki lookup.
Searches the Fandom wiki API and returns concise content for AI context injection.
"""
import aiohttp
import re

WIKI_API = "https://hypixel-skyblock.fandom.com/api.php"
HEADERS = {
    "User-Agent": "HypixelSkyblockBot/1.0 (educational Discord bot)",
    "Accept": "application/json",
}

# Simple cache: {query: (content, timestamp)}
_cache: dict[str, tuple[str, float]] = {}
CACHE_TTL = 600  # 10 minutes


async def search_wiki(query: str, limit: int = 3) -> list[dict]:
    """Search the wiki and return matching page titles."""
    params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srlimit": limit,
        "format": "json",
    }
    try:
        async with aiohttp.ClientSession(headers=HEADERS) as session:
            async with session.get(WIKI_API, params=params, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
                return data.get("query", {}).get("search", [])
    except Exception:
        return []


async def fetch_page(title: str, max_chars: int = 3000) -> str:
    """Fetch a wiki page and return cleaned text content."""
    import time
    cache_key = title.lower()
    if cache_key in _cache:
        content, ts = _cache[cache_key]
        if time.time() - ts < CACHE_TTL:
            return content

    params = {
        "action": "parse",
        "page": title,
        "prop": "text",
        "format": "json",
        "disableeditsection": "1",
        "disabletoc": "1",
    }
    try:
        async with aiohttp.ClientSession(headers=HEADERS) as session:
            async with session.get(WIKI_API, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return ""
                data = await resp.json()
                html = data.get("parse", {}).get("text", {}).get("*", "")
                if not html:
                    return ""
                text = _html_to_text(html)
                if len(text) > max_chars:
                    text = text[:max_chars] + "..."
                _cache[cache_key] = (text, time.time())
                return text
    except Exception:
        return ""


def _html_to_text(html: str) -> str:
    """Convert wiki HTML to clean text."""
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
    except ImportError:
        # Fallback: basic regex stripping
        text = re.sub(r'<[^>]+>', ' ', html)
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    # Remove navboxes, infobox sidebars, script/style tags
    for tag in soup.find_all(["script", "style", "nav"]):
        tag.decompose()
    for cls in ["navbox", "portable-infobox", "mw-empty-elt", "toc"]:
        for tag in soup.find_all(class_=cls):
            tag.decompose()

    text = soup.get_text(separator="\n")
    # Clean up whitespace
    lines = []
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("[") and len(line) > 2:
            lines.append(line)
    return "\n".join(lines)


async def wiki_context(query: str, max_chars: int = 3000) -> str:
    """Search wiki and return relevant content for AI context."""
    results = await search_wiki(query, limit=2)
    if not results:
        return ""

    parts = []
    total = 0
    for result in results:
        title = result.get("title", "")
        content = await fetch_page(title, max_chars=max_chars - total)
        if content:
            parts.append(f"## {title}\n{content}")
            total += len(content)
            if total >= max_chars:
                break

    return "\n\n".join(parts) if parts else ""
