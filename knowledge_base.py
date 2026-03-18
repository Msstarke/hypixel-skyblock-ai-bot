import re
from pathlib import Path

KNOWLEDGE_DIR = Path(__file__).parent / "knowledge"

FILE_KEYWORDS = {
    "skills.md":      ["skill", "farming", "mining", "combat", "fishing", "foraging",
                       "enchanting", "alchemy", "taming", "carpentry", "runecrafting",
                       "xp", "level up", "skill level", "skill xp", "mining setup",
                       "pickaxe", "drill", "hotm", "powder", "commission"],
    "dungeons.md":    ["dungeon", "floor", "catacombs", "class", "archer", "berserk", "healer",
                       "mage", "tank", "secret", "boss", "f1", "f2", "f3", "f4", "f5", "f6", "f7",
                       "m1", "m2", "m3", "m4", "m5", "m6", "m7", "master mode", "scoring"],
    "slayer.md":      ["slayer", "revenant", "tarantula", "sven", "voidgloom", "inferno",
                       "vampire slayer", "slayer boss", "slayer xp", "slayer level"],
    "minions.md":     ["minion", "fuel", "storage", "compactor", "super compactor",
                       "minion upgrade", "minion slot", "minion speed"],
    "items.md":       ["reforge", "talisman", "accessory", "armor", "sword", "bow", "wither",
                       "necron", "hyperion", "livid", "terminator", "aspect", "aote", "weapon",
                       "chestplate", "leggings", "helmet", "boots", "divan", "best weapon",
                       "best armor", "best sword", "enchant"],
    "pets.md":        ["pet", "pet item", "pet xp", "pet ability", "best pet"],
    "collections.md": ["collection", "unlock", "collection reward"],
    "locations.md":   ["location", "zone", "area", "spider den", "the end", "crimson isle",
                       "the park", "deep caverns", "dwarven mines", "crystal hollows",
                       "glacite", "where to", "where is", "grind spot", "best place"],
    "economy.md":     ["bazaar", "auction", "npc price", "coin", "profit", "flip",
                       "instabuy", "instasell", "trade", "market"],
    "bestiary.md":    ["bestiary", "bestiaries", "mob kill", "mob grind", "kill count",
                       "grind mob", "grind mobs", "mob farming", "monster grind", "mob family"],
    "general.md":     ["fairy soul", "essence", "magic find", "kuudra", "how to", "guide",
                       "tip", "beginner", "what is"],
}


def _split_sections(text: str) -> list[tuple[str, str]]:
    """Split markdown into (heading, content) pairs."""
    sections = []
    current_heading = ""
    current_lines = []
    for line in text.splitlines():
        if re.match(r"^#{1,3} ", line):
            if current_lines:
                sections.append((current_heading, "\n".join(current_lines).strip()))
            current_heading = line.lstrip("#").strip()
            current_lines = []
        else:
            current_lines.append(line)
    if current_lines:
        sections.append((current_heading, "\n".join(current_lines).strip()))
    return [(h, c) for h, c in sections if c.strip()]


def _score_section(heading: str, content: str, q_words: set) -> int:
    text = (heading + " " + content[:300]).lower()
    score = 0
    for w in q_words:
        if len(w) < 3:
            continue
        if w in heading.lower():
            score += 4
        elif w in text:
            score += 1
    return score


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
        self._files.clear()
        self._load_all()

    def list_files(self) -> list[str]:
        return list(self._files.keys())

    def get_relevant_knowledge(self, question: str, max_chars: int = 25000) -> str:
        q = question.lower()
        q_words = set(re.sub(r"[^\w\s]", "", q).split())

        # Pick top matching files (up to 3)
        file_scores: dict[str, int] = {}
        for fname, keywords in FILE_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in q)
            if score:
                file_scores[fname] = score

        if not file_scores and "general.md" in self._files:
            file_scores["general.md"] = 1

        top_files = sorted(file_scores, key=lambda f: file_scores[f], reverse=True)[:3]

        parts = []
        total = 0
        budget = max_chars // max(len(top_files), 1)

        for fname in top_files:
            if fname not in self._files:
                continue

            sections = _split_sections(self._files[fname])
            scored = sorted(
                [(s, _score_section(s[0], s[1], q_words)) for s in sections],
                key=lambda x: x[1], reverse=True
            )

            file_parts = []
            used = 0
            for (heading, body), score in scored:
                if score == 0:
                    continue
                chunk = (f"**{heading}**\n{body}" if heading else body)[:3000]
                if used + len(chunk) > budget:
                    break
                file_parts.append(chunk)
                used += len(chunk)

            if file_parts:
                label = fname.replace(".md", "").title()
                parts.append(f"=== {label} ===\n" + "\n\n".join(file_parts))
                total += used

        return "\n\n".join(parts)

    def get_all_knowledge(self) -> str:
        return "\n\n".join(self._files.values())
