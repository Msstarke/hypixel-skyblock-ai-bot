"""
Reforge data for Hypixel Skyblock.
Stats are per-piece values at LEGENDARY rarity (approximate).
Stone prices are fetched live from AH (lowestbin.json).
"""

# ── Stat aliases ─────────────────────────────────────────────────────────────
STAT_ALIASES: dict[str, str] = {
    # Mining
    "mining fortune": "mining_fortune",
    "mining_fortune": "mining_fortune",
    "fortune":        "mining_fortune",
    # Intelligence / Mana
    "intelligence":   "intelligence",
    "int":            "intelligence",
    "mana":           "intelligence",
    "magic":          "intelligence",
    # Strength
    "strength":       "strength",
    "str":            "strength",
    "damage":         "damage",
    "dmg":            "damage",
    # Crit
    "crit damage":    "crit_damage",
    "crit_damage":    "crit_damage",
    "cd":             "crit_damage",
    "crit chance":    "crit_chance",
    "crit_chance":    "crit_chance",
    "cc":             "crit_chance",
    # Defense / HP
    "defense":        "defense",
    "def":            "defense",
    "health":         "health",
    "hp":             "health",
    # Fishing
    "sea creature chance": "sea_creature_chance",
    "scc":                 "sea_creature_chance",
    "fishing speed":       "fishing_speed",
    # Magic find
    "magic find":     "magic_find",
    "mf":             "magic_find",
    # Speed
    "speed":          "speed",
}

ARMOR_SLOTS = {"HELMET", "CHESTPLATE", "LEGGINGS", "BOOTS"}
SWORD_SLOTS = {"SWORD"}
BOW_SLOTS   = {"BOW"}

# ── Reforge database ─────────────────────────────────────────────────────────
# stats: approximate LEGENDARY per-piece values
# stone: Hypixel item ID for the reforge stone (None = free from Blacksmith)
# types: which item types this reforge applies to
# use_cases: set of tags used for inferred-use scoring
REFORGES: dict[str, dict] = {
    # ─── Armor ───────────────────────────────────────────────────────────────
    "jaded": {
        "stone":      "JADERALD",
        "types":      ARMOR_SLOTS,
        "stats":      {"mining_fortune": 20},
        "use_cases":  {"mining"},
        "note":       "Best mining fortune reforge (~3.4M stone).",
    },
    "ancient": {
        "stone":      "PRECURSOR_GEAR",
        "types":      ARMOR_SLOTS,
        "stats":      {"crit_chance": 2, "strength": 4, "crit_damage": 6, "intelligence": 7, "health": 7},
        "use_cases":  {"combat", "dungeons", "berserk", "archer"},
        "note":       "Best reforge for dungeon armor (Necron, SA, etc). +1 crit damage per Catacombs level (~1.2M stone).",
    },
    "renowned": {
        "stone":      "DRAGON_HORN",
        "types":      ARMOR_SLOTS,
        "stats":      {"strength": 4, "crit_damage": 4, "defense": 15, "health": 15},
        "use_cases":  {"tank", "general"},
        "note":       "Good all-round reforge with defense (~5.8M stone). Outclassed by Ancient for damage builds.",
    },
    "necrotic": {
        "stone":      "NECROMANCER_BROOCH",
        "types":      ARMOR_SLOTS,
        "stats":      {"intelligence": 40},
        "use_cases":  {"mage"},
        "note":       "Best intelligence armor reforge (~14k stone, very cheap).",
    },
    "submerged": {
        "stone":      "DEEP_SEA_ORB",
        "types":      ARMOR_SLOTS,
        "stats":      {"sea_creature_chance": 5, "fishing_speed": 5},
        "use_cases":  {"fishing"},
        "note":       "Best reforge for fishing armor (~3.1M stone).",
    },
    "blessed": {
        "stone":      "BLESSED_FRUIT",
        "types":      ARMOR_SLOTS,
        "stats":      {"health": 25, "defense": 10},
        "use_cases":  {"tank"},
        "note":       "Good HP/defense reforge (~1.1M stone).",
    },
    "cubic": {
        "stone":      "DIAMOND_ATOM",
        "types":      ARMOR_SLOTS,
        "stats":      {"defense": 25, "health": 15},
        "use_cases":  {"tank"},
        "note":       "Budget defense reforge (~109k stone).",
    },
    "glaciated": {
        "stone":      "GLACITE_SHARD",
        "types":      ARMOR_SLOTS,
        "stats":      {"defense": 15, "mining_fortune": 5},
        "use_cases":  {"mining"},
        "note":       "Budget mining/defense reforge for Glacite Tunnels (~62k stone).",
    },
    "searing": {
        "stone":      "SEARING_STONE",
        "types":      ARMOR_SLOTS,
        "stats":      {"strength": 8, "crit_damage": 5},
        "use_cases":  {"combat", "crimson"},
        "note":       "Good for Crimson Isle combat builds (~200k stone).",
    },
    "loving": {
        "stone":      None,
        "types":      ARMOR_SLOTS,
        "stats":      {"health": 20, "defense": 5},
        "use_cases":  {"tank"},
        "note":       "Free from Blacksmith.",
    },
    "fierce": {
        "stone":      None,
        "types":      ARMOR_SLOTS,
        "stats":      {"strength": 4, "crit_damage": 3},
        "use_cases":  {"combat"},
        "note":       "Free from Blacksmith.",
    },
    # ─── Swords ──────────────────────────────────────────────────────────────
    "withered": {
        "stone":      "WITHER_BLOOD",
        "types":      SWORD_SLOTS,
        "stats":      {"crit_damage": 35, "strength": 30, "damage": 15},
        "use_cases":  {"combat", "dungeons"},
        "note":       "Best reforge for Wither-class swords (Hyperion, Astraea) (~1.7M stone).",
    },
    "fabled": {
        "stone":      "DRAGON_CLAW",
        "types":      SWORD_SLOTS | BOW_SLOTS,
        "stats":      {"crit_chance": 10, "crit_damage": 30, "damage": 15},
        "use_cases":  {"combat", "archer"},
        "note":       "Best for Terminator, bows, general archer (~862k stone).",
    },
    "warped": {
        "stone":      "AOTE_STONE",
        "types":      SWORD_SLOTS,
        "stats":      {"speed": 10, "intelligence": 15, "crit_damage": 10},
        "use_cases":  {"speed", "mage"},
        "note":       "Best for teleportation swords (AOTE, Aspect of the Void) (~6.5M stone).",
    },
    "necrotic_weapon": {
        "stone":      "NECROMANCER_BROOCH",
        "types":      SWORD_SLOTS,
        "stats":      {"intelligence": 50},
        "use_cases":  {"mage"},
        "note":       "Best intelligence weapon reforge (~14k stone).",
    },
    "legendary": {
        "stone":      None,
        "types":      SWORD_SLOTS | BOW_SLOTS,
        "stats":      {"crit_damage": 50, "damage": 10},
        "use_cases":  {"combat"},
        "note":       "Free from Blacksmith, strong crit damage.",
    },
    "spicy": {
        "stone":      None,
        "types":      SWORD_SLOTS,
        "stats":      {"crit_damage": 40, "damage": 15, "strength": 5},
        "use_cases":  {"combat"},
        "note":       "Free from Blacksmith, balanced combat stats.",
    },
}


def get_item_type(item_id: str) -> str:
    """Infer item slot type from item ID suffix."""
    for t in ("HELMET", "CHESTPLATE", "LEGGINGS", "BOOTS", "SWORD", "BOW"):
        if item_id.endswith(t):
            return t
    # Common weapon IDs without type suffix
    if any(x in item_id for x in ("HYPERION", "ASTRAEA", "LIVID", "AOTE", "DAGGER")):
        return "SWORD"
    if any(x in item_id for x in ("TERMINATOR", "RUNAAN", "HURRICANE")):
        return "BOW"
    return "SWORD"


def _infer_use_case(item_id: str) -> str:
    item = item_id.lower()
    if any(x in item for x in ("divan", "glacite", "mineral", "mithril")):
        return "mining"
    if any(x in item for x in ("necron", "storm", "aurora", "terror", "goldor", "maxor")):
        return "dungeons"
    if any(x in item for x in ("hyperion", "astraea", "livid", "aote")):
        return "combat"
    if any(x in item for x in ("terminator", "runaan", "hurricane")):
        return "archer"
    return "combat"


def pick_reforge(
    item_id: str,
    desired_stat: str | None = None,
    item_price: float = 0,
    stone_prices: dict | None = None,
) -> dict | None:
    """
    Pick the best reforge for an item.

    Args:
        item_id:      Hypixel item ID (e.g. DIVAN_HELMET)
        desired_stat: Normalised stat key (e.g. 'mining_fortune', 'intelligence')
        item_price:   Lowest BIN price of the item (used to gauge affordability)
        stone_prices: Dict of {stone_id: price} from lowestbin

    Returns:
        Best reforge dict {name, stone, stone_price, stats, note, affordable} or None.
    """
    stone_prices = stone_prices or {}
    item_type = get_item_type(item_id)
    inferred_use = _infer_use_case(item_id)

    candidates = []
    for name, data in REFORGES.items():
        if item_type not in data["types"]:
            continue

        stone_id    = data["stone"]
        stone_price = stone_prices.get(stone_id, 0) if stone_id else 0
        affordable  = True

        # Score first
        if desired_stat:
            stat_key = STAT_ALIASES.get(desired_stat.lower(), desired_stat.lower().replace(" ", "_"))
            score = data["stats"].get(stat_key, 0)
        else:
            if inferred_use in data["use_cases"]:
                score = max(data["stats"].values()) if data["stats"] else 0
            else:
                score = 0

        # Penalise if stone costs vastly more than the item — signals wrong build tier.
        # Threshold: 10x (not 5x or 1x) because mining builds routinely use Jaderald (~3.4M)
        # on mid-tier armor like Mineral Helmet (~1-3M). Only truly absurd ratios get penalised.
        if item_price > 0 and stone_price > 0:
            if stone_price > item_price * 10:
                # Stone costs 10x+ the item — essentially unusable
                affordable = False
                score = score * 0.001
            elif stone_price > item_price * 3:
                # Stone costs 3–10x the item — warn but still consider
                affordable = False
                score = score * 0.5
            elif stone_price > item_price * 0.5:
                affordable = False

        if score > 0:
            candidates.append({
                "name":        name.replace("_weapon", ""),
                "stone":       stone_id,
                "stone_price": stone_price,
                "stats":       data["stats"],
                "note":        data["note"],
                "affordable":  affordable,
                "score":       score,
            })

    if not candidates:
        return None

    # Prefer affordable first, then score
    candidates.sort(key=lambda x: (x["affordable"], x["score"]), reverse=True)
    return candidates[0]


def normalize_stat(raw: str) -> str | None:
    """Normalise a raw stat string from user input to internal key."""
    raw = raw.lower().strip()
    return STAT_ALIASES.get(raw)
