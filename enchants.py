"""
Enchantment data for Hypixel Skyblock hypermax calculator.
Defines which enchants go on which item types and which use cases they serve.
Prices are fetched live from bazaar — this file only defines the enchant sets.
"""

# ── Item type sets ──────────────────────────────────────────────────────────────
ARMOR_TYPES = {"HELMET", "CHESTPLATE", "LEGGINGS", "BOOTS"}
SWORD_TYPES = {"SWORD"}
BOW_TYPES   = {"BOW"}
HELMET_ONLY = {"HELMET"}
BOOTS_ONLY  = {"BOOTS"}
LEGS_ONLY   = {"LEGGINGS"}

# ── Use case tags ───────────────────────────────────────────────────────────────
# combat   = general melee/berserk
# dungeons = dungeon-specific enchants
# mage     = intelligence/mana builds
# mining   = mining armor or tools
# fishing  = fishing gear
# tank     = health/defense focused
# archer   = bow/ranged builds
# farming  = farming gear

# ── Enchantment database ────────────────────────────────────────────────────────
# bazaar_id: the ENCHANTMENT_X_N id on bazaar (highest useful tier)
# types: which item types this applies to
# use_cases: set of tags — item only gets this enchant if its inferred use matches
# priority: higher = more important to include (used to cap total enchant cost)
# note: short description

ENCHANTS: list[dict] = [
    # ═══════════════════════════════════════════════════════════════════════════
    # ARMOR — ALL SLOTS (combat / dungeons)
    # ═══════════════════════════════════════════════════════════════════════════
    {
        "name": "Protection 7",
        "bazaar_id": "ENCHANTMENT_PROTECTION_7",
        "types": ARMOR_TYPES,
        "use_cases": {"combat", "dungeons", "tank"},
        "priority": 10,
    },
    {
        "name": "Protection 6",
        "bazaar_id": "ENCHANTMENT_PROTECTION_6",
        "types": ARMOR_TYPES,
        "use_cases": {"mining", "mage"},
        "priority": 8,
    },
    {
        "name": "Growth 7",
        "bazaar_id": "ENCHANTMENT_GROWTH_7",
        "types": ARMOR_TYPES,
        "use_cases": {"combat", "dungeons", "tank"},
        "priority": 10,
    },
    {
        "name": "Growth 6",
        "bazaar_id": "ENCHANTMENT_GROWTH_6",
        "types": ARMOR_TYPES,
        "use_cases": {"mining", "mage"},
        "priority": 8,
    },
    {
        "name": "Rejuvenate 5",
        "bazaar_id": "ENCHANTMENT_REJUVENATE_5",
        "types": ARMOR_TYPES,
        "use_cases": {"combat", "dungeons", "tank", "mage", "mining"},
        "priority": 7,
    },
    {
        "name": "Thorns 3",
        "bazaar_id": "ENCHANTMENT_THORNS_3",
        "note": "Not on bazaar — crafted or dropped. Negligible cost.",
        "skip_price": True,
        "types": ARMOR_TYPES,
        "use_cases": {"combat", "dungeons", "tank"},
        "priority": 3,
        "note": "Free/very cheap, minor reflect damage.",
    },
    {
        "name": "Reflection 5",
        "bazaar_id": "ENCHANTMENT_REFLECTION_5",
        "types": ARMOR_TYPES,
        "use_cases": {"combat", "dungeons", "tank"},
        "priority": 5,
    },

    # ═══════════════════════════════════════════════════════════════════════════
    # ARMOR — ALL SLOTS (mage)
    # ═══════════════════════════════════════════════════════════════════════════
    {
        "name": "Big Brain 5",
        "bazaar_id": "ENCHANTMENT_BIG_BRAIN_5",
        "types": ARMOR_TYPES,
        "use_cases": {"mage"},
        "priority": 9,
    },
    {
        "name": "Smarty Pants 5",
        "bazaar_id": "ENCHANTMENT_SMARTY_PANTS_5",
        "types": ARMOR_TYPES,
        "use_cases": {"mage"},
        "priority": 8,
    },


    # ═══════════════════════════════════════════════════════════════════════════
    # ARMOR — HELMET ONLY
    # ═══════════════════════════════════════════════════════════════════════════
    {
        "name": "Respiration 4",
        "bazaar_id": "ENCHANTMENT_RESPIRATION_4",
        "types": HELMET_ONLY,
        "use_cases": {"combat", "dungeons", "tank", "mage", "mining", "fishing"},
        "priority": 6,
    },

    # ═══════════════════════════════════════════════════════════════════════════
    # ARMOR — BOOTS ONLY
    # ═══════════════════════════════════════════════════════════════════════════
    {
        "name": "Feather Falling 10",
        "bazaar_id": "ENCHANTMENT_FEATHER_FALLING_10",
        "types": BOOTS_ONLY,
        "use_cases": {"combat", "dungeons", "tank", "mage", "mining"},
        "priority": 7,
    },

    # ═══════════════════════════════════════════════════════════════════════════
    # ARMOR — ULTIMATE ENCHANTS (only 1 per piece)
    # ═══════════════════════════════════════════════════════════════════════════
    {
        "name": "Legion 5",
        "bazaar_id": "ENCHANTMENT_ULTIMATE_LEGION_5",
        "types": ARMOR_TYPES,
        "use_cases": {"combat", "dungeons", "tank"},
        "ultimate": True,
        "priority": 10,
    },
    {
        "name": "Wisdom 5",
        "bazaar_id": "ENCHANTMENT_ULTIMATE_WISDOM_5",
        "types": ARMOR_TYPES,
        "use_cases": {"mage", "mining"},
        "ultimate": True,
        "priority": 10,
    },
    {
        "name": "Last Stand 5",
        "bazaar_id": "ENCHANTMENT_ULTIMATE_LAST_STAND_5",
        "types": ARMOR_TYPES,
        "use_cases": {"tank"},
        "ultimate": True,
        "priority": 9,
    },

    # ═══════════════════════════════════════════════════════════════════════════
    # SWORDS — regular enchants
    # ═══════════════════════════════════════════════════════════════════════════
    {
        "name": "Sharpness 7",
        "bazaar_id": "ENCHANTMENT_SHARPNESS_7",
        "types": SWORD_TYPES,
        "use_cases": {"combat", "dungeons"},
        "priority": 10,
    },
    {
        "name": "Critical 7",
        "bazaar_id": "ENCHANTMENT_CRITICAL_7",
        "types": SWORD_TYPES,
        "use_cases": {"combat", "dungeons"},
        "priority": 10,
    },
    {
        "name": "Giant Killer 7",
        "bazaar_id": "ENCHANTMENT_GIANT_KILLER_7",
        "types": SWORD_TYPES,
        "use_cases": {"combat", "dungeons"},
        "priority": 9,
    },
    {
        "name": "Smite 6",
        "bazaar_id": "ENCHANTMENT_SMITE_6",
        "types": SWORD_TYPES,
        "use_cases": {"dungeons"},
        "priority": 8,
        "note": "Good for undead dungeons mobs. Conflicts with Sharpness.",
        "conflicts": {"Sharpness 7"},
    },
    {
        "name": "Looting 5",
        "bazaar_id": "ENCHANTMENT_LOOTING_5",
        "types": SWORD_TYPES,
        "use_cases": {"combat", "dungeons"},
        "priority": 7,
    },
    {
        "name": "Execute 6",
        "bazaar_id": "ENCHANTMENT_EXECUTE_6",
        "types": SWORD_TYPES,
        "use_cases": {"combat", "dungeons"},
        "priority": 8,
    },
    {
        "name": "First Strike 5",
        "bazaar_id": "ENCHANTMENT_FIRST_STRIKE_5",
        "types": SWORD_TYPES,
        "use_cases": {"combat", "dungeons"},
        "priority": 7,
    },
    {
        "name": "Lethality 6",
        "bazaar_id": "ENCHANTMENT_LETHALITY_6",
        "types": SWORD_TYPES,
        "use_cases": {"combat", "dungeons"},
        "priority": 5,
    },
    {
        "name": "Scavenger 5",
        "bazaar_id": "ENCHANTMENT_SCAVENGER_5",
        "types": SWORD_TYPES,
        "use_cases": {"combat", "dungeons"},
        "priority": 4,
    },
    {
        "name": "Vampirism 6",
        "bazaar_id": "ENCHANTMENT_VAMPIRISM_6",
        "types": SWORD_TYPES,
        "use_cases": {"combat", "dungeons"},
        "priority": 6,
    },
    {
        "name": "Life Steal 5",
        "bazaar_id": "ENCHANTMENT_LIFE_STEAL_5",
        "types": SWORD_TYPES,
        "use_cases": {"combat", "dungeons"},
        "priority": 6,
    },
    {
        "name": "Ender Slayer 6",
        "bazaar_id": "ENCHANTMENT_ENDER_SLAYER_6",
        "types": SWORD_TYPES,
        "use_cases": {"combat"},
        "priority": 6,
    },
    {
        "name": "Fire Aspect 3",
        "bazaar_id": "ENCHANTMENT_FIRE_ASPECT_3",
        "types": SWORD_TYPES,
        "use_cases": {"combat"},
        "priority": 3,
    },
    {
        "name": "Venomous 6",
        "bazaar_id": "ENCHANTMENT_VENOMOUS_6",
        "types": SWORD_TYPES,
        "use_cases": {"combat", "dungeons"},
        "priority": 4,
    },
    {
        "name": "Luck 7",
        "bazaar_id": "ENCHANTMENT_LUCK_7",
        "types": SWORD_TYPES,
        "use_cases": {"combat"},
        "priority": 5,
    },
    {
        "name": "Syphon 5",
        "bazaar_id": "ENCHANTMENT_SYPHON_5",
        "types": SWORD_TYPES,
        "use_cases": {"combat", "dungeons"},
        "priority": 5,
    },
    {
        "name": "Prosecute 6",
        "bazaar_id": "ENCHANTMENT_PROSECUTE_6",
        "types": SWORD_TYPES,
        "use_cases": {"combat", "dungeons"},
        "priority": 8,
    },
    {
        "name": "Cubism 6",
        "bazaar_id": "ENCHANTMENT_CUBISM_6",
        "types": SWORD_TYPES,
        "use_cases": {"combat"},
        "priority": 5,
    },
    {
        "name": "Champion 1",
        "bazaar_id": "ENCHANTMENT_CHAMPION_1",
        "types": SWORD_TYPES,
        "use_cases": {"combat", "dungeons"},
        "priority": 5,
    },
    {
        "name": "Vicious 5",
        "bazaar_id": "ENCHANTMENT_VICIOUS_5",
        "types": SWORD_TYPES,
        "use_cases": {"combat", "dungeons"},
        "priority": 6,
    },

    # ═══════════════════════════════════════════════════════════════════════════
    # SWORDS — ultimate enchants (only 1 per piece)
    # ═══════════════════════════════════════════════════════════════════════════
    {
        "name": "Soul Eater 5",
        "bazaar_id": "ENCHANTMENT_ULTIMATE_SOUL_EATER_5",
        "types": SWORD_TYPES,
        "use_cases": {"combat"},
        "ultimate": True,
        "priority": 10,
    },
    {
        "name": "One For All 1",
        "bazaar_id": "ENCHANTMENT_ULTIMATE_ONE_FOR_ALL_1",
        "types": SWORD_TYPES,
        "use_cases": set(),  # special — replaces all other enchants
        "ultimate": True,
        "priority": 0,
        "note": "Replaces ALL other enchants. Only used on specific items.",
    },
    {
        "name": "Swarm 5",
        "bazaar_id": "ENCHANTMENT_ULTIMATE_SWARM_5",
        "types": SWORD_TYPES,
        "use_cases": {"combat"},
        "ultimate": True,
        "priority": 8,
    },
    {
        "name": "Chimera 5",
        "bazaar_id": "ENCHANTMENT_ULTIMATE_CHIMERA_5",
        "types": SWORD_TYPES,
        "use_cases": {"combat", "dungeons"},
        "ultimate": True,
        "priority": 10,
        "note": "Best ultimate for endgame swords. Copies pet stats. AH only (~430M).",
    },

    # ═══════════════════════════════════════════════════════════════════════════
    # BOWS — regular enchants
    # ═══════════════════════════════════════════════════════════════════════════
    {
        "name": "Power 7",
        "bazaar_id": "ENCHANTMENT_POWER_7",
        "types": BOW_TYPES,
        "use_cases": {"archer", "combat"},
        "priority": 10,
    },
    {
        "name": "Overload 5",
        "bazaar_id": "ENCHANTMENT_OVERLOAD_5",
        "types": BOW_TYPES,
        "use_cases": {"archer", "combat"},
        "priority": 9,
    },
    {
        "name": "Dragon Hunter 6",
        "bazaar_id": "ENCHANTMENT_DRAGON_HUNTER_6",
        "types": BOW_TYPES,
        "use_cases": {"archer"},
        "priority": 7,
    },
    {
        "name": "Snipe 4",
        "bazaar_id": "ENCHANTMENT_SNIPE_4",
        "types": BOW_TYPES,
        "use_cases": {"archer", "combat"},
        "priority": 8,
    },
    {
        "name": "Infinite Quiver 10",
        "bazaar_id": "ENCHANTMENT_INFINITE_QUIVER_10",
        "types": BOW_TYPES,
        "use_cases": {"archer", "combat"},
        "priority": 5,
    },

    # ═══════════════════════════════════════════════════════════════════════════
    # BOWS — ultimate enchants (only 1 per piece)
    # ═══════════════════════════════════════════════════════════════════════════
    {
        "name": "Soul Eater 5",
        "bazaar_id": "ENCHANTMENT_ULTIMATE_SOUL_EATER_5",
        "types": BOW_TYPES,
        "use_cases": {"archer", "combat"},
        "ultimate": True,
        "priority": 10,
    },
    {
        "name": "Rend 5",
        "bazaar_id": "ENCHANTMENT_ULTIMATE_REND_5",
        "types": BOW_TYPES,
        "use_cases": {"archer"},
        "ultimate": True,
        "priority": 7,
    },
]


def get_item_type(item_id: str) -> str:
    """Infer item slot type from item ID."""
    for t in ("HELMET", "CHESTPLATE", "LEGGINGS", "BOOTS"):
        if item_id.endswith(t):
            return t
    if any(x in item_id for x in ("HYPERION", "ASTRAEA", "LIVID", "AOTE", "DAGGER",
                                    "SHADOW_FURY", "MIDAS_SWORD", "NECRON_BLADE",
                                    "VALKYRIE", "SCYLLA", "CLAYMORE")):
        return "SWORD"
    if any(x in item_id for x in ("TERMINATOR", "RUNAAN", "HURRICANE", "JUJU",
                                    "BONEMERANG", "LAST_BREATH")):
        return "BOW"
    return "SWORD"  # default for weapons


def _infer_use_case(item_id: str) -> str:
    """Infer what an item is used for based on its ID."""
    item = item_id.lower()
    if any(x in item for x in ("divan", "glacite", "mineral", "mithril")):
        return "mining"
    # Specific wither set roles
    if "wise_wither" in item or "storm" in item:
        return "mage"
    if "tank_wither" in item or "goldor" in item:
        return "tank"
    if "speed_wither" in item or "maxor" in item:
        return "dungeons"  # Maxor is speed/berserk
    if any(x in item for x in ("power_wither", "shadow_assassin", "necron",
                                "aurora", "terror")):
        return "dungeons"
    if any(x in item for x in ("hyperion", "astraea", "scylla", "valkyrie")):
        return "dungeons"
    if any(x in item for x in ("terminator", "juju")):
        return "archer"
    if any(x in item for x in ("livid", "aote", "midas")):
        return "combat"
    return "combat"


def pick_enchants(item_id: str, use_case_override: str | None = None) -> list[dict]:
    """
    Pick the best enchant set for an item based on its type and use case.
    Returns list of enchant dicts: [{name, bazaar_id, ultimate}]
    Only one ultimate enchant is included (highest priority for the use case).
    """
    item_type = get_item_type(item_id)
    use_case = use_case_override or _infer_use_case(item_id)

    candidates = []
    for e in ENCHANTS:
        # Must apply to this item type
        if item_type not in e["types"]:
            continue
        # Must match use case
        if e["use_cases"] and use_case not in e["use_cases"]:
            continue
        candidates.append(e)

    # Pick best ultimate (only 1 allowed per piece)
    ultimates = [e for e in candidates if e.get("ultimate")]
    regulars  = [e for e in candidates if not e.get("ultimate")]

    # Sort ultimates by priority descending, pick the best
    ultimates.sort(key=lambda e: e["priority"], reverse=True)
    best_ultimate = ultimates[0] if ultimates else None

    # Handle conflicts (e.g. Sharpness vs Smite — keep higher priority)
    selected = []
    used_names = set()
    for e in sorted(regulars, key=lambda x: x["priority"], reverse=True):
        conflicts = e.get("conflicts", set())
        if conflicts & used_names:
            continue
        selected.append(e)
        used_names.add(e["name"])

    if best_ultimate:
        selected.append(best_ultimate)

    return [{"name": e["name"], "bazaar_id": e["bazaar_id"],
             "ultimate": e.get("ultimate", False)} for e in selected]
