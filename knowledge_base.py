import re
from pathlib import Path

KNOWLEDGE_DIR = Path(__file__).parent / "knowledge"

# Maps question keywords to which files are likely relevant
FILE_KEYWORDS = {
    "skills.md":      ["skill", "farming", "mining", "combat", "fishing", "foraging",
                       "enchanting", "alchemy", "taming", "carpentry", "runecrafting",
                       "xp", "level up", "skill level", "skill xp"],
    "dungeons.md":    ["dungeon", "floor", "catacombs", "class", "archer", "berserk", "healer",
                       "mage", "tank", "secret", "boss", "fairy soul", "chest", "f1", "f2",
                       "f3", "f4", "f5", "f6", "f7", "m1", "m2", "m3", "m4", "m5", "m6", "m7",
                       "master mode", "dungeon hub", "scoring", "s+", "dungeon gear"],
    "slayer.md":      ["slayer", "revenant", "tarantula", "sven", "voidgloom", "inferno demonlord",
                       "vampire slayer", "slayer boss", "slayer xp", "slayer level", "slayer drop"],
    "minions.md":     ["minion", "fuel", "storage", "compactor", "super compactor",
                       "minion upgrade", "minion slot", "minion speed", "minion profit"],
    "items.md":       ["reforge", "talisman", "accessory", "armor", "sword", "bow", "wither",
                       "necron", "hyperion", "livid", "terminator", "aspect", "aote", "weapon",
                       "chestplate", "leggings", "helmet", "boots", "divan", "gemstone",
                       "enchant", "reforge stone", "best weapon", "best armor", "best sword"],
    "pets.md":        ["pet", "pet item", "pet xp", "pet ability", "legendary pet",
                       "epic pet", "common pet", "rare pet", "best pet"],
    "collections.md": ["collection", "unlock", "collection reward", "collection level"],
    "locations.md":   ["location", "zone", "area", "spider den", "the end", "crimson isle",
                       "the park", "deep caverns", "dwarven mines", "crystal hollows",
                       "glacite", "hub island", "the rift", "where to", "where is", "grind spot",
                       "grind location", "best place"],
    "economy.md":     ["bazaar", "auction", "npc price", "coin", "profit", "flip", "instabuy",
                       "instasell", "trade", "market", "sell price", "buy price"],
    "bestiary.md":    ["bestiary", "bestiaries", "mob kill", "mob grind", "kill count",
                       "grind mob", "grind mobs", "mob farming", "monster grind",
                       "mob family", "bestiary tier", "bestiary milestone"],
    "general.md":     ["fairy soul", "essence", "magic find", "kuudra", "how to", "guide",
                       "tip", "start", "beginner", "what is"],
}

# Inline topic→keyword map for section scoring
SECTION_SCORE_BOOST = {
    "mining":    ["mining", "pickaxe", "drill", "hotm", "dwarven", "crystal", "gemstone",
                  "mining speed", "mining fortune", "powder", "commission", "peak", "mithril",
                  "titanium", "glacite", "scatha", "mining setup", "best mining"],
    "farming":   ["farming", "crop", "wheat", "carrot", "potato", "pumpkin", "melon",
                  "sugarcane", "mushroom", "cactus", "farming speed", "farming fortune",
                  "garden", "plot", "visitor", "jacob"],
    "combat":    ["combat", "fight", "damage", "strength", "crit", "weapon", "sword",
                  "bow", "kill", "mob", "arena", "grinding"],
    "dungeon":   ["dungeon", "catacombs", "floor", "boss", "secret", "class", "scoring",
                  "chest", "essence", "f7", "m7"],
    "slayer":    ["slayer", "boss", "revenant", "tarantula", "sven", "voidgloom",
                  "inferno", "vampire", "rng meter", "miniboss"],
    "fishing":   ["fishing", "rod", "trophy", "sea creature", "lava fishing", "shark",
                  "squid", "fishing speed", "sea"],
    "bestiary":  ["bestiary", "mob", "kill", "grind", "family", "tier", "milestone"],
    "pet":       ["pet", "level", "exp boost", "pet item", "candy", "tier boost"],
    "reforge":   ["reforge", "stone", "stat", "legendary", "sharp", "fierce", "wise"],
}


def _split_sections(text: str) -> list[tuple[str, str]]:
    """
    Split a markdown document into (heading, content) tuples.
    Top-level and second-level headings create new sections.
    """
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


def _score_section(heading: str, content: str, q_words: set[str]) -> int:
    """Score a section's relevance to the question keywords."""
    text = (heading + " " + content[:500]).lower()
    score = 0
    for word in q_words:
        if word in text:
            # Heading matches are worth more
            score += 3 if word in heading.lower() else 1
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

    def get_relevant_knowledge(self, question: str, max_chars: int = 8000) -> str:
        q = question.lower()
        q_words = set(re.sub(r"[^\w\s]", "", q).split())

        # ── Step 1: pick relevant files ───────────────────────────────────────
        file_scores: dict[str, int] = {}
        for fname, keywords in FILE_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in q)
            if score:
                file_scores[fname] = score

        # Fallback to general if nothing matched
        if not file_scores and "general.md" in self._files:
            file_scores["general.md"] = 1

        # Sort files by relevance, take top 3
        top_files = sorted(file_scores, key=lambda f: file_scores[f], reverse=True)[:3]

        # ── Step 2: extract best sections from each file ──────────────────────
        result_parts = []
        total_chars = 0

        for fname in top_files:
            if fname not in self._files:
                continue
            content = self._files[fname]
            sections = _split_sections(content)

            # Score every section
            scored = [(s, _score_section(s[0], s[1], q_words)) for s in sections]
            scored.sort(key=lambda x: x[1], reverse=True)

            # Take top sections up to budget
            file_budget = max_chars // len(top_files)
            file_parts = []
            used = 0

            for (heading, body), score in scored:
                if score == 0:
                    continue
                chunk = f"**{heading}**\n{body}" if heading else body
                chunk = chunk[:2000]  # cap single section at 2000 chars
                if used + len(chunk) > file_budget:
                    break
                file_parts.append(chunk)
                used += len(chunk)

            if file_parts:
                label = fname.replace(".md", "").title()
                result_parts.append(f"=== {label} ===\n" + "\n\n".join(file_parts))
                total_chars += used

        return "\n\n".join(result_parts)

    def get_all_knowledge(self) -> str:
        return "\n\n".join(self._files.values())
