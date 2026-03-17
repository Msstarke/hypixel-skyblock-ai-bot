import os
import re
from pathlib import Path

KNOWLEDGE_DIR = Path(__file__).parent / "knowledge"

# Keywords that map to knowledge files
TOPIC_KEYWORDS = {
    "skills.md": ["skill", "farming", "mining", "combat", "fishing", "foraging", "enchanting",
                  "alchemy", "taming", "carpentry", "runecrafting", "xp", "level"],
    "dungeons.md": ["dungeon", "floor", "catacombs", "class", "archer", "berserk", "healer",
                    "mage", "tank", "secret", "boss", "fairy soul", "chest"],
    "minions.md": ["minion", "fuel", "storage", "compactor", "super compactor", "inferno",
                   "enchanted lava"],
    "items.md": ["reforge", "talisman", "accessory", "armor", "sword", "bow", "wither",
                 "necron", "hyperion", "livid", "terminator", "aspect", "aote"],
    "general.md": ["coin", "profit", "flip", "npc", "collection", "recipe", "craft", "island",
                   "hub", "slayer", "revenant", "tarantula", "sven", "voidgloom"],
}


class KnowledgeBase:
    def __init__(self):
        self._files: dict[str, str] = {}
        self._load_all()

    def _load_all(self):
        if not KNOWLEDGE_DIR.exists():
            return
        for f in KNOWLEDGE_DIR.glob("*.md"):
            self._files[f.name] = f.read_text(encoding="utf-8")

    def get_relevant_knowledge(self, question: str) -> str:
        """Return knowledge sections relevant to the question."""
        q = question.lower()
        included = set()

        for filename, keywords in TOPIC_KEYWORDS.items():
            if any(kw in q for kw in keywords):
                included.add(filename)

        # Always include general if nothing else matched
        if not included and "general.md" in self._files:
            included.add("general.md")

        parts = []
        for filename in included:
            if filename in self._files:
                parts.append(f"### {filename.replace('.md', '').title()} Info\n{self._files[filename]}")

        return "\n\n".join(parts)

    def get_all_knowledge(self) -> str:
        return "\n\n".join(self._files.values())
