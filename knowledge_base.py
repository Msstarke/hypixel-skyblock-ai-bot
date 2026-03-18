import re
from pathlib import Path

KNOWLEDGE_DIR = Path(__file__).parent / "knowledge"

# Keywords that map to knowledge files — extended to cover all scraped categories
TOPIC_KEYWORDS = {
    "skills.md":      ["skill", "farming", "mining", "combat", "fishing", "foraging",
                       "enchanting", "alchemy", "taming", "carpentry", "runecrafting", "xp", "level up"],
    "dungeons.md":    ["dungeon", "floor", "catacombs", "class", "archer", "berserk", "healer",
                       "mage", "tank", "secret", "boss", "fairy soul", "chest", "f1", "f2", "f3",
                       "f4", "f5", "f6", "f7", "m1", "m2", "m3", "m4", "m5", "m6", "m7",
                       "master mode", "dungeon hub", "scoring"],
    "slayer.md":      ["slayer", "revenant", "tarantula", "sven", "voidgloom", "inferno demonlord",
                       "vampire slayer", "slayer boss", "slayer xp", "slayer level"],
    "minions.md":     ["minion", "fuel", "storage", "compactor", "super compactor", "inferno",
                       "enchanted lava", "minion upgrade", "minion slot"],
    "items.md":       ["reforge", "talisman", "accessory", "armor", "sword", "bow", "wither",
                       "necron", "hyperion", "livid", "terminator", "aspect", "aote", "weapon",
                       "chestplate", "leggings", "helmet", "boots", "crystal"],
    "pets.md":        ["pet", "pet item", "pet leveling", "pet xp", "pet ability",
                       "legendary pet", "epic pet", "common pet", "rare pet"],
    "collections.md": ["collection", "collections", "unlock", "mining collection",
                       "farming collection", "combat collection", "fishing collection"],
    "locations.md":   ["location", "zone", "area", "spider den", "the end", "crimson isle",
                       "the park", "deep caverns", "dwarven mines", "crystal hollows",
                       "glacite", "hub island", "the rift", "where to", "where is"],
    "economy.md":     ["bazaar", "auction", "npc", "coin", "profit", "flip", "instabuy",
                       "instasell", "trade", "sell", "buy price", "market"],
    "bestiary.md":    ["bestiary", "bestiaries", "mob kill", "mob grind", "kill count",
                       "grind mob", "grind mobs", "mob farming", "monster grind",
                       "kills", "mob", "spawn", "grind spot"],
    "general.md":     ["fairy soul", "essence", "magic find", "kuudra", "skyblock level",
                       "how to", "what is", "guide", "tip", "start", "beginner"],
}

# Fallback keywords for files not explicitly listed (auto-derived from filename)
def _filename_keywords(name: str) -> list[str]:
    stem = name.replace(".md", "").replace("_", " ")
    return [stem, stem.rstrip("s")]


class KnowledgeBase:
    def __init__(self):
        self._files: dict[str, str] = {}
        self._load_all()

    def _load_all(self):
        if not KNOWLEDGE_DIR.exists():
            return
        for f in KNOWLEDGE_DIR.glob("*.md"):
            self._files[f.name] = f.read_text(encoding="utf-8")

    def reload(self):
        """Reload all knowledge files from disk (call after wiki scrape)."""
        self._files.clear()
        self._load_all()

    def get_relevant_knowledge(self, question: str, max_chars: int = 6000) -> str:
        """Return knowledge sections relevant to the question."""
        q = question.lower()
        included: dict[str, int] = {}  # filename → match score

        for filename, keywords in TOPIC_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in q)
            if score > 0:
                included[filename] = score

        # Check any loaded files not in TOPIC_KEYWORDS
        for filename in self._files:
            if filename not in included:
                for kw in _filename_keywords(filename):
                    if kw in q:
                        included[filename] = 1
                        break

        # Always include general if nothing matched
        if not included and "general.md" in self._files:
            included["general.md"] = 1

        # Sort by match score descending, take top 3 files
        top = sorted(included.items(), key=lambda x: x[1], reverse=True)[:3]

        parts = []
        total = 0
        for filename, _ in top:
            if filename not in self._files:
                continue
            content = self._files[filename]
            # Trim very large files to avoid bloating the AI context
            if total + len(content) > max_chars:
                content = content[: max_chars - total] + "\n...[truncated]"
            parts.append(f"### {filename.replace('.md', '').title()} Info\n{content}")
            total += len(content)
            if total >= max_chars:
                break

        return "\n\n".join(parts)

    def get_all_knowledge(self) -> str:
        return "\n\n".join(self._files.values())

    def list_files(self) -> list[str]:
        return list(self._files.keys())
