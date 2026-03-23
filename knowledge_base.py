import re
from pathlib import Path
from data_dir import DATA_DIR

KNOWLEDGE_DIR = Path(__file__).parent / "knowledge"

FILE_KEYWORDS = {
    "mining.md":      ["mining", "pickaxe", "drill", "hotm", "heart of the mountain",
                       "dwarven mines", "crystal hollows", "mining armor", "mining pet",
                       "mining setup", "divan", "mineral armor", "pickonimbus", "scatha",
                       "mithril golem", "silverfish pet", "bal pet", "gemstone gauntlet",
                       "powder", "commission", "glacite", "best mining"],
    "skills.md":      ["skill", "combat", "foraging",
                       "enchanting", "alchemy", "taming", "carpentry", "runecrafting",
                       "xp", "level up", "skill level", "skill xp",
                       "farming skill", "farming level"],
    "dungeons.md":    ["dungeon", "catacombs", "class", "archer", "berserk", "healer",
                       "mage", "tank", "secret", "dungeon armor", "dungeon weapon",
                       "dungeon setup", "dungeon gear", "dungeon mechanic", "dungeon item",
                       "essence upgrade", "dungeonize", "dungeon star", "class level",
                       "cata 0", "cata 1", "cata 2", "cata 3", "cata 4", "cata 5"],
    "dungeon_floors.md": ["floor", "boss", "f1", "f2", "f3", "f4", "f5", "f6", "f7",
                       "m1", "m2", "m3", "m4", "m5", "m6", "m7", "master mode", "scoring",
                       "bonzo", "scarf", "professor", "thorn", "livid", "sadan", "necron",
                       "maxor", "storm armor", "goldor", "wither lord", "wither king",
                       "shadow assassin", "hyperion", "livid dagger", "juju",
                       "wither armor", "wither set", "spirit bow", "frag run",
                       "dungeon progression", "dungeon loot", "dungeon guide",
                       "reward chest", "bedrock chest", "s+", "s rank",
                       "floor guide", "boss guide", "boss mechanic",
                       "dark claymore", "giant sword", "necron armor",
                       "master star", "dungeon hub", "mort", "ophelia"],
    "slayer.md":      ["slayer", "revenant", "tarantula", "sven", "voidgloom", "inferno",
                       "vampire slayer", "slayer boss", "slayer xp", "slayer level"],
    "minions.md":     ["minion", "fuel", "storage", "compactor", "super compactor",
                       "minion upgrade", "minion slot", "minion speed",
                       "diamond spreading", "coins per day", "best minion",
                       "money minion", "minion fuel", "enchanted lava bucket",
                       "inferno minion", "snow minion", "clay minion",
                       "revenant minion", "tarantula minion", "minion tier",
                       "corrupt soil", "hopper", "minion expander",
                       "flycatcher", "beacon", "minion crystal"],
    "items.md":       ["armor", "sword", "bow", "wither",
                       "necron", "hyperion", "livid", "terminator", "aspect", "aote", "weapon",
                       "chestplate", "leggings", "helmet", "boots", "divan", "best weapon",
                       "best armor", "best sword"],
    "pets.md":        ["pet", "pet item", "pet xp", "pet ability", "best pet",
                       "golden dragon", "ender dragon pet", "baby yeti", "blue whale",
                       "tiger pet", "lion pet", "wither skeleton pet", "scatha pet",
                       "black cat", "griffin pet", "elephant pet", "mooshroom cow",
                       "rabbit pet", "bee pet", "sheep pet", "parrot pet",
                       "skeleton pet", "jellyfish pet", "flying fish", "megalodon",
                       "dolphin pet", "armadillo pet", "mithril golem", "silverfish pet",
                       "bal pet", "hedgehog pet", "spirit pet", "phoenix pet",
                       "grandma wolf", "enderman pet", "guardian pet",
                       "pet score", "pet leveling", "kat upgrade", "tier boost",
                       "autopet", "pet rarity", "combat pet", "mining pet",
                       "farming pet", "fishing pet", "dungeon pet",
                       "lucky clover", "textbook pet", "antique remedies",
                       "crochet tiger plushie", "minos relic", "exp share",
                       "carrot candy", "pet training"],
    "collections.md": ["collection", "unlock", "collection reward", "collection tier",
                       "what collection", "how to unlock", "recipe unlock", "minion recipe",
                       "accessory bag", "personal compactor", "super compactor",
                       "budget hopper", "enchanted lava bucket", "diamond spreading",
                       "aspect of the end", "aote", "treecapitator", "runaan",
                       "compactor recipe", "what unlocks", "collection level",
                       "boss collection", "potion bag", "quiver", "hot potato book"],
    "locations.md":   ["location", "zone", "area", "spider den", "the end",
                       "the park", "deep caverns", "dwarven mines", "crystal hollows",
                       "glacite", "where to", "where is", "grind spot", "best place"],
    "economy.md":     ["bazaar", "auction", "npc price", "coin", "profit", "flip",
                       "instabuy", "instasell", "trade", "market"],
    "bestiary.md":    ["bestiary", "bestiaries", "mob kill", "mob grind", "kill count",
                       "grind mob", "grind mobs", "mob farming", "monster grind", "mob family"],
    "essence.md":     ["essence", "star upgrade", "stars", "wither essence", "undead essence",
                       "dragon essence", "spider essence", "ice essence", "gold essence",
                       "diamond essence", "crimson essence", "essence shop", "essence perk",
                       "dungeon star", "master star", "starring", "dungeonize", "salvage essence",
                       "forbidden perk", "star cost"],
    "fairy_souls.md": ["fairy soul", "fairy souls", "tia", "tia the fairy", "soul exchange"],
    "general.md":     ["magic find", "how to", "guide",
                       "tip", "beginner", "what is"],
    "garden.md":      ["garden", "crop", "farming fortune", "visitor", "composter",
                       "organic matter", "plot", "crop milestone", "jacob", "farming contest",
                       "pumpkin", "melon", "wheat", "carrot", "potato", "sugar cane",
                       "nether wart", "cocoa", "cactus", "mushroom", "pest"],
    "rift.md":        ["rift", "motes", "timecharm", "mirrorverse", "enigma soul",
                       "mcgrubber", "rift time", "wyld armor", "vampiric"],
    "kuudra.md":      ["kuudra", "kuudra tier", "kuudra gear", "kuudra loot",
                       "kuudra guide", "kuudra strategy", "attribute", "crimson essence",
                       "kuudra key", "infernal kuudra", "fiery kuudra",
                       "burning kuudra", "hot kuudra", "molten equipment",
                       "kuudra armor", "attribute shard", "dominance", "veteran"],
    "crimson_isle.md":["crimson isle", "faction", "mage faction", "barbarian",
                       "dojo", "nether", "crimson armor", "terror armor", "aurora armor",
                       "fervor armor", "hollow armor", "vanquisher",
                       "inferno minion", "nether star"],
    "enchantments.md":["enchant", "enchantment", "ultimate enchant", "fortune iv",
                       "efficiency", "sharpness", "critical", "first strike",
                       "smelting touch", "compact", "pristine", "protection",
                       "growth", "thorns", "rejuvenate", "what enchant",
                       "best enchant", "enchant for"],
    "reforges.md":    ["reforge", "reforge stone", "auspicious", "withered", "fabled",
                       "ancient", "renowned", "loving", "submerged", "hurtful",
                       "strong reforge", "best reforge", "reforge for",
                       "what reforge"],
    "accessories.md": ["accessory", "talisman", "magical power", "mp", "accessory bag",
                       "power stone", "thaumaturgy", "enrichment", "tuning",
                       "best accessory", "which accessory"],
    "gemstones.md":   ["gemstone", "gem", "jade", "amber", "sapphire", "ruby", "amethyst",
                       "topaz", "jasper", "opal", "gem slot", "perfect gem", "flawless gem",
                       "gemstone slot", "which gem"],
    "mayors.md":      ["mayor", "election", "aatrox", "cole", "diana", "diaz", "finnegan",
                       "foxy", "jerry mayor", "marina", "paul", "scorpius", "derpy",
                       "barry mayor", "dante", "perk", "mayor perk"],
    "forging.md":     ["forge", "forging", "drill part", "drill upgrade", "refined mithril",
                       "refined diamond", "fuel tank", "drill engine", "quick forge",
                       "forge recipe", "forge time"],
    "fishing.md":     ["fishing", "sea creature", "trophy fish", "fishing rod", "fishing pet",
                       "sea creature chance", "fishing festival", "lava fishing",
                       "barn fishing", "fishing fortune", "squid pet", "dolphin pet",
                       "fishing setup", "best fishing"],
    "recent_changes.md": ["update", "patch", "nerf", "buff", "change", "new feature",
                       "rework", "removed", "added", "recent", "latest",
                       "current meta", "meta"],
    "chocolate_factory.md": ["chocolate", "chocolate factory", "hoppity", "rabbit",
                       "easter", "dark cacao", "chocolate egg", "chocolate production",
                       "cps", "time tower", "rabbit barn", "chocolate shop",
                       "stray rabbit", "golden rabbit", "hoppity hunt",
                       "egglocator", "coach jackrabbit", "rabbit shrine"],
    "potions.md":     ["potion", "brew", "brewing", "god potion", "strength potion",
                       "critical potion", "haste potion", "speed potion", "wisdom potion",
                       "potion effect", "splash potion", "dungeon potion", "archery potion",
                       "regeneration potion", "resistance potion", "mana potion",
                       "absorption potion", "adrenaline potion", "spirit potion",
                       "magic find potion", "pet luck potion", "true resistance",
                       "agility potion", "spelunker", "potion duration",
                       "god pot", "potion stacking"],
    "events.md":      ["event", "spooky", "jerry workshop", "fishing festival", "mining fiesta",
                       "dark auction", "traveling zoo", "mythological", "diana event", "griffin",
                       "burrow", "candy", "festival", "new year cake", "season of jerry",
                       "jerry box", "fear mongerer", "shark", "oringo", "hoppity",
                       "chocolate egg", "jacob contest", "farming contest", "mayor event",
                       "spooky festival", "mythological ritual", "mining event",
                       "sphinx", "inquisitor", "minotaur", "chimera", "manticore",
                       "daedalus", "minos"],
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
    text = re.sub(r"[^\w\s]", "", (heading + " " + content[:500]).lower())
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
        # Also load community corrections from persistent data dir (Railway volume)
        corrections_file = DATA_DIR / "community_corrections.md"
        if corrections_file.exists():
            self._files["community_corrections.md"] = corrections_file.read_text(encoding="utf-8")

    def reload(self):
        self._files.clear()
        self._load_all()

    def list_files(self) -> list[str]:
        return list(self._files.keys())

    def get_corrections(self) -> str:
        """Return community corrections content, or empty string if none."""
        return self._files.get("community_corrections.md", "")

    def get_relevant_knowledge(self, question: str, max_chars: int = 35000,
                                is_price_question: bool = False) -> str:
        """Get relevant knowledge base content for a question.

        For price questions, reduces budget to leave room for live data.
        """
        if is_price_question:
            max_chars = min(max_chars, 15000)

        q = question.lower()
        q_norm = re.sub(r"[^\w\s]", "", q)
        q_words = set(q_norm.split())

        # Pick top matching files (up to 3)
        file_scores: dict[str, int] = {}
        for fname, keywords in FILE_KEYWORDS.items():
            if fname not in self._files:
                continue
            score = sum(1 for kw in keywords if kw in q_norm)
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
                chunk = (f"**{heading}**\n{body}" if heading else body)[:5000]
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
