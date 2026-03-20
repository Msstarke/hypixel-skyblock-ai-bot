"""
Parses Hypixel Skyblock profile member data into readable stats.
Handles skills, slayer, dungeons, HotM, gear (NBT-decoded), purse.
"""
import base64
import io
import re
from typing import Optional

try:
    import nbtlib
    HAS_NBT = True
except ImportError:
    HAS_NBT = False

STRIP_COLOR = re.compile(r'§.')

SKILL_NAMES = {
    'SKILL_FARMING': 'Farming',
    'SKILL_MINING': 'Mining',
    'SKILL_COMBAT': 'Combat',
    'SKILL_FORAGING': 'Foraging',
    'SKILL_FISHING': 'Fishing',
    'SKILL_ENCHANTING': 'Enchanting',
    'SKILL_ALCHEMY': 'Alchemy',
    'SKILL_TAMING': 'Taming',
    'SKILL_CARPENTRY': 'Carpentry',
    'SKILL_RUNECRAFTING': 'Runecrafting',
    'SKILL_SOCIAL': 'Social',
}

SKILL_MAX = {
    'Farming': 60, 'Mining': 60, 'Combat': 60, 'Foraging': 50,
    'Fishing': 50, 'Enchanting': 60, 'Alchemy': 50, 'Taming': 50,
    'Carpentry': 50, 'Runecrafting': 25, 'Social': 25,
}

# Cumulative XP required per level (index = level)
SKILL_XP = [
    0, 50, 175, 375, 675, 1175, 1925, 2925, 4425, 6425, 9925, 14925, 22425,
    32425, 47425, 67425, 97425, 147425, 222425, 322425, 522425, 822425,
    1222425, 1722425, 2322425, 3022425, 3822425, 4722425, 5722425, 6822425,
    8022425, 9322425, 10722425, 12222425, 13822425, 15522425, 17322425,
    19222425, 21222425, 23322425, 25522425, 27822425, 30222425, 32722425,
    35322425, 38072425, 40972425, 44072425, 47472425, 51172425, 55172425,
    59472425, 64072425, 68972425, 74172425, 79672425, 85472425, 91572425,
    97972425, 104672425, 111672425,
]

SLAYER_NAMES = {
    'zombie': 'Revenant',
    'spider': 'Tarantula',
    'wolf': 'Sven',
    'enderman': 'Voidgloom',
    'blaze': 'Inferno',
    'vampire': 'Vampire',
}

SLAYER_XP = [0, 5, 15, 200, 1000, 5000, 20000, 100000, 400000, 1000000]

DUNGEON_CLASS_XP = [
    0, 50, 125, 250, 500, 1000, 2500, 7500, 20000, 50000, 100000,
    200000, 300000, 400000, 500000, 600000, 800000, 1000000, 1200000,
    1400000, 1600000, 1800000, 2000000, 2400000, 2800000, 3200000,
    3600000, 4000000, 4400000, 4800000, 5200000,
]


def xp_to_level(xp: float, table: list, cap: int = None) -> int:
    level = 0
    for i, req in enumerate(table):
        if cap and i > cap:
            break
        if xp >= req:
            level = i
        else:
            break
    return level


def parse_nbt_items(b64data: str) -> list[dict]:
    """Decode base64 gzipped NBT into a list of {id, name} dicts."""
    if not HAS_NBT or not b64data:
        return []
    try:
        raw = base64.b64decode(b64data)
        f = nbtlib.load(fileobj=io.BytesIO(raw))
        items = []
        for item in f.get('i', []):
            if not item:
                continue
            tag = item.get('tag', nbtlib.Compound())
            extra = tag.get('ExtraAttributes', nbtlib.Compound())
            display = tag.get('display', nbtlib.Compound())
            item_id = str(extra.get('id', ''))
            raw_name = str(display.get('Name', ''))
            name = STRIP_COLOR.sub('', raw_name).strip() or item_id.replace('_', ' ').title()
            if item_id:
                items.append({'id': item_id, 'name': name})
        return items
    except Exception:
        return []


def parse_member(member: dict) -> dict:
    """Parse a profile member dict into structured stats."""
    stats = {}

    # ── Skills ──────────────────────────────────────────────────────────────
    # v2 API: player_data.experience.SKILL_*
    # v1 API: experience_skill_farming, etc.
    xp_src = member.get('player_data', {}).get('experience', {})
    if not xp_src:
        # v1 fallback
        xp_src = {
            'SKILL_FARMING':     member.get('experience_skill_farming', 0),
            'SKILL_MINING':      member.get('experience_skill_mining', 0),
            'SKILL_COMBAT':      member.get('experience_skill_combat', 0),
            'SKILL_FORAGING':    member.get('experience_skill_foraging', 0),
            'SKILL_FISHING':     member.get('experience_skill_fishing', 0),
            'SKILL_ENCHANTING':  member.get('experience_skill_enchanting', 0),
            'SKILL_ALCHEMY':     member.get('experience_skill_alchemy', 0),
            'SKILL_TAMING':      member.get('experience_skill_taming', 0),
        }

    skills = {}
    for key, label in SKILL_NAMES.items():
        xp = float(xp_src.get(key, 0))
        cap = SKILL_MAX.get(label, 50)
        lvl = xp_to_level(xp, SKILL_XP, cap)
        skills[label] = {'level': lvl, 'xp': xp}
    stats['skills'] = skills

    # ── Slayer ───────────────────────────────────────────────────────────────
    slayer_bosses = (
        member.get('slayer', {}).get('slayer_bosses') or
        member.get('slayer_bosses', {})
    )
    slayers = {}
    for key, label in SLAYER_NAMES.items():
        boss = slayer_bosses.get(key, {})
        xp = boss.get('xp', 0)
        lvl = xp_to_level(xp, SLAYER_XP)
        slayers[label] = {'level': lvl, 'xp': xp}
    stats['slayer'] = slayers

    # ── Dungeons ─────────────────────────────────────────────────────────────
    dungeons = member.get('dungeons', {})
    dungeon_types = dungeons.get('dungeon_types', {})
    cata = dungeon_types.get('catacombs', {})
    cata_xp = cata.get('experience', 0)
    stats['catacombs_level'] = xp_to_level(cata_xp, SKILL_XP, 50)
    stats['catacombs_xp'] = cata_xp

    floor_completions = {}
    for floor, data in cata.get('tier_completions', {}).items():
        floor_completions[f'F{floor}'] = data
    master = dungeon_types.get('master_catacombs', {})
    for floor, data in master.get('tier_completions', {}).items():
        floor_completions[f'M{floor}'] = data
    stats['floor_completions'] = floor_completions

    classes = {}
    for cls in ['healer', 'mage', 'berserk', 'archer', 'tank']:
        xp = dungeons.get('player_classes', {}).get(cls, {}).get('experience', 0)
        classes[cls.capitalize()] = {
            'level': xp_to_level(xp, DUNGEON_CLASS_XP, 50),
            'xp': xp,
        }
    stats['dungeon_classes'] = classes
    stats['selected_class'] = dungeons.get('selected_dungeon_class', 'none').capitalize()

    # ── HotM ─────────────────────────────────────────────────────────────────
    # v2 API: skill_tree.experience.mining (NOT mining_core.experience)
    skill_tree = member.get('skill_tree', {})
    hotm_xp_raw = skill_tree.get('experience', {})
    if isinstance(hotm_xp_raw, dict):
        stats['hotm_xp'] = float(hotm_xp_raw.get('mining', 0))
    else:
        stats['hotm_xp'] = float(hotm_xp_raw or 0)

    # ── Fairy Souls ──────────────────────────────────────────────────────────
    stats['fairy_souls'] = member.get('fairy_soul', {}).get('total_collected', 0)

    # ── Purse ────────────────────────────────────────────────────────────────
    stats['purse'] = (
        member.get('currencies', {}).get('coin_purse') or
        member.get('coin_purse', 0)
    )

    # ── Collections ───────────────────────────────────────────────────────────
    stats['collections'] = member.get('collection') or {}

    # ── Bank ────────────────────────────────────────────────────────────────
    stats['bank'] = member.get('_bank_balance', 0)

    # ── Pets ────────────────────────────────────────────────────────────────
    raw_pets = member.get('pets_data', {}).get('pets', [])
    pets = []
    for pet in raw_pets:
        pets.append({
            'type': pet.get('type', ''),
            'tier': pet.get('tier', ''),
            'active': pet.get('active', False),
            'xp': pet.get('exp', 0),
            'held_item': pet.get('heldItem', ''),
        })
    stats['pets'] = pets

    # ── Accessories / Magic Power ──────────────────────────────────────────
    acc = member.get('accessory_bag_storage', {})
    stats['magical_power'] = acc.get('highest_magical_power', 0)
    stats['selected_power'] = acc.get('selected_power', '')

    # ── Essence ─────────────────────────────────────────────────────────────
    essence_raw = member.get('currencies', {}).get('essence', {})
    stats['essence'] = {k: v.get('current', 0) for k, v in essence_raw.items() if isinstance(v, dict)}

    # ── Mining (powder) ─────────────────────────────────────────────────────
    mc = member.get('mining_core', {})
    stats['mithril_powder'] = mc.get('powder_mithril', 0)
    stats['gemstone_powder'] = mc.get('powder_gemstone', 0)
    stats['glacite_powder'] = mc.get('powder_glacite', 0)

    # ── Kuudra ──────────────────────────────────────────────────────────────
    kuudra = member.get('nether_island_player_data', {}).get('kuudra_completed_tiers', {})
    stats['kuudra'] = {k: v for k, v in kuudra.items() if not k.startswith('highest_wave')}

    # ── Crimson Isle ────────────────────────────────────────────────────────
    nether = member.get('nether_island_player_data', {})
    stats['crimson_faction'] = nether.get('selected_faction', '')
    stats['crimson_reputation'] = {
        'barbarians': nether.get('barbarians_reputation', 0),
        'mages': nether.get('mages_reputation', 0),
    }

    # ── Skyblock Level ──────────────────────────────────────────────────────
    stats['sb_xp'] = member.get('leveling', {}).get('experience', 0)

    # ── Bestiary ────────────────────────────────────────────────────────────
    bestiary = member.get('bestiary', {})
    stats['bestiary_milestone'] = bestiary.get('milestone', {}).get('last_claimed_milestone', 0)

    # ── Trophy Fish ─────────────────────────────────────────────────────────
    stats['trophy_fish_total'] = member.get('trophy_fish', {}).get('total_caught', 0)

    # ── Gear (NBT) ───────────────────────────────────────────────────────────
    inv = member.get('inventory', {})
    stats['armor']     = parse_nbt_items(inv.get('inv_armor', {}).get('data', ''))
    stats['equipment'] = parse_nbt_items(inv.get('equipment_contents', {}).get('data', ''))
    stats['wardrobe']  = parse_nbt_items(inv.get('wardrobe_contents', {}).get('data', ''))
    stats['inventory'] = parse_nbt_items(inv.get('inv_contents', {}).get('data', ''))
    stats['ender_chest'] = parse_nbt_items(inv.get('ender_chest_contents', {}).get('data', ''))

    return stats


def _format_number(n: float) -> str:
    """Format large numbers compactly: 1.5M, 23.4K, etc."""
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.1f}B"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return f"{n:,.0f}"


# Pet XP table (cumulative) for LEGENDARY rarity — used to estimate pet level
PET_XP_LEGENDARY = [
    0, 660, 1390, 2190, 3070, 4030, 5080, 6230, 7490, 8870, 10380, 12030, 13830,
    15780, 17880, 20130, 22530, 25080, 27780, 30630, 33630, 36780, 40080, 43530,
    47130, 50880, 54780, 58830, 63030, 67380, 71880, 76530, 81330, 86280, 91380,
    96630, 102030, 107580, 113280, 119130, 125130, 131280, 137580, 144030, 150630,
    157380, 164280, 171330, 178530, 185880, 193380, 201030, 208830, 216780, 224880,
    233130, 241530, 250080, 258780, 267630, 276630, 285780, 295080, 304530, 314130,
    323880, 333780, 343830, 354030, 364380, 374880, 385530, 396330, 407280, 418380,
    429630, 441030, 452580, 464280, 476130, 488130, 500280, 512580, 525030, 537630,
    550380, 563280, 576330, 589530, 602880, 616380, 630030, 643830, 657780, 671880,
    686130, 700530, 715080, 729780, 744630,
]


def _pet_level(xp: float, tier: str = 'LEGENDARY') -> int:
    """Estimate pet level from XP. Uses legendary table as approximation."""
    table = PET_XP_LEGENDARY
    lvl = 1
    for i, req in enumerate(table):
        if xp >= req:
            lvl = i + 1
    return min(lvl, 100)


COLLECTION_CATEGORIES = {
    'Mining': ['COBBLESTONE', 'COAL', 'IRON_INGOT', 'GOLD_INGOT', 'DIAMOND', 'LAPIS_LAZULI',
               'EMERALD', 'REDSTONE', 'QUARTZ', 'OBSIDIAN', 'GLOWSTONE_DUST', 'GRAVEL',
               'ICE', 'NETHERRACK', 'SAND', 'ENDER_STONE', 'MITHRIL_ORE', 'HARD_STONE',
               'GEMSTONE_COLLECTION', 'SULPHUR_ORE', 'MYCEL', 'RED_SAND'],
    'Combat': ['ROTTEN_FLESH', 'BONE', 'STRING', 'SPIDER_EYE', 'GUNPOWDER', 'ENDER_PEARL',
                'GHAST_TEAR', 'SLIME_BALL', 'BLAZE_ROD', 'MAGMA_CREAM'],
    'Farming': ['WHEAT', 'CARROT_ITEM', 'POTATO_ITEM', 'PUMPKIN', 'MELON', 'SEEDS',
                'MUSHROOM_COLLECTION', 'NETHER_STALK', 'CACTUS', 'SUGAR_CANE',
                'FEATHER', 'LEATHER', 'PORK', 'RAW_CHICKEN', 'MUTTON', 'RABBIT', 'COCOA'],
    'Fishing': ['RAW_FISH', 'RAW_FISH:1', 'RAW_FISH:2', 'RAW_FISH:3', 'PRISMARINE_SHARD',
                'PRISMARINE_CRYSTALS', 'CLAY_BALL', 'WATER_LILY', 'INK_SACK',
                'SPONGE', 'MAGMA_FISH'],
    'Foraging': ['LOG', 'LOG:1', 'LOG:2', 'LOG_2:1', 'LOG_2', 'LOG:3'],
}


def format_for_ai(username: str, profile_name: str, stats: dict) -> str:
    """Condense parsed stats into a string for the AI system prompt."""
    from hypixel_api import HOTM_XP
    lines = [f"=== Player: {username} | Profile: {profile_name} ==="]

    # Skyblock Level
    sb_xp = stats.get('sb_xp', 0)
    if sb_xp:
        lines.append(f"Skyblock Level: {int(sb_xp / 100)}")

    # Networth + Money
    nw = stats.get('networth')
    if nw and nw.get('total'):
        lines.append(f"Estimated Networth: {_format_number(nw['total'])} (Purse: {_format_number(nw.get('purse', 0))} | Bank: {_format_number(nw.get('bank', 0))} | Items: {_format_number(nw.get('items_total', 0))})")
        cats = nw.get('categories', {})
        cat_parts = [f"{k}: {_format_number(v)}" for k, v in cats.items() if v > 0]
        if cat_parts:
            lines.append("NW breakdown: " + " | ".join(cat_parts))
        top = nw.get('top_items', [])
        if top:
            top_parts = [f"{name}: {_format_number(price)}" for name, price in top[:5]]
            lines.append("Top items: " + " | ".join(top_parts))
    else:
        purse = stats.get('purse', 0)
        bank = stats.get('bank', 0)
        money_parts = []
        if purse:
            money_parts.append(f"Purse: {_format_number(purse)}")
        if bank:
            money_parts.append(f"Bank: {_format_number(bank)}")
        if money_parts:
            lines.append(" | ".join(money_parts))

    # Skills
    skill_parts = [f"{k} {v['level']}" for k, v in stats.get('skills', {}).items() if v['level'] > 0]
    if skill_parts:
        lines.append("Skills: " + " | ".join(skill_parts))

    # Slayer
    slayer_parts = [f"{k} {v['level']}" for k, v in stats.get('slayer', {}).items() if v['level'] > 0]
    if slayer_parts:
        lines.append("Slayer: " + " | ".join(slayer_parts))

    # Dungeons
    cata = stats.get('catacombs_level', 0)
    sel_class = stats.get('selected_class', '')
    lines.append(f"Catacombs: {cata} | Class: {sel_class}")

    class_parts = [f"{k} {v['level']}" for k, v in stats.get('dungeon_classes', {}).items() if v['level'] > 0]
    if class_parts:
        lines.append("Class levels: " + " | ".join(class_parts))

    completions = stats.get('floor_completions', {})
    if completions:
        comp_parts = [f"{k}:{v}" for k, v in sorted(completions.items())]
        lines.append("Floors: " + " ".join(comp_parts))

    # HotM + Powder
    hotm_xp = stats.get('hotm_xp', 0)
    hotm_lvl = sum(1 for req in HOTM_XP[1:] if hotm_xp >= req)
    mithril_p = stats.get('mithril_powder', 0)
    gemstone_p = stats.get('gemstone_powder', 0)
    glacite_p = stats.get('glacite_powder', 0)
    hotm_line = f"HotM: {hotm_lvl}"
    powder_parts = []
    if mithril_p:
        powder_parts.append(f"Mithril: {_format_number(mithril_p)}")
    if gemstone_p:
        powder_parts.append(f"Gemstone: {_format_number(gemstone_p)}")
    if glacite_p:
        powder_parts.append(f"Glacite: {_format_number(glacite_p)}")
    if powder_parts:
        hotm_line += " | Powder: " + ", ".join(powder_parts)
    lines.append(hotm_line)

    # Accessories / Magic Power
    mp = stats.get('magical_power', 0)
    power = stats.get('selected_power', '')
    if mp:
        lines.append(f"Magic Power: {mp:,} | Power: {power}")

    # Essence
    essence = stats.get('essence', {})
    if essence:
        ess_parts = [f"{k}: {_format_number(v)}" for k, v in essence.items() if v > 0]
        if ess_parts:
            lines.append("Essence: " + " | ".join(ess_parts))

    # Kuudra
    kuudra = stats.get('kuudra', {})
    if kuudra:
        kuudra_parts = [f"{k}: {v}" for k, v in kuudra.items() if v > 0]
        if kuudra_parts:
            lines.append("Kuudra: " + " | ".join(kuudra_parts))

    # Crimson Isle
    faction = stats.get('crimson_faction', '')
    if faction:
        rep = stats.get('crimson_reputation', {})
        lines.append(f"Crimson Isle: {faction} | Barbarian rep: {rep.get('barbarians', 0):,} | Mage rep: {rep.get('mages', 0):,}")

    # Misc
    lines.append(f"Fairy souls: {stats.get('fairy_souls', 0)}")

    bestiary = stats.get('bestiary_milestone', 0)
    if bestiary:
        lines.append(f"Bestiary milestone: {bestiary}")

    trophy = stats.get('trophy_fish_total', 0)
    if trophy:
        lines.append(f"Trophy fish caught: {trophy:,}")

    # Pets (active + top 5 by level)
    pets = stats.get('pets', [])
    if pets:
        active = [p for p in pets if p.get('active')]
        if active:
            p = active[0]
            lvl = _pet_level(p['xp'], p['tier'])
            held = p['held_item'].replace('PET_ITEM_', '').replace('_', ' ').title() if p['held_item'] else 'none'
            lines.append(f"Active pet: {p['type'].title()} ({p['tier'].title()}) Lvl {lvl} | Held: {held}")

        # Top pets by XP
        top = sorted(pets, key=lambda x: x['xp'], reverse=True)[:10]
        pet_parts = []
        for p in top:
            if p.get('active'):
                continue
            lvl = _pet_level(p['xp'], p['tier'])
            pet_parts.append(f"{p['type'].title()} {p['tier'][0]}{lvl}")
        if pet_parts:
            lines.append("Top pets: " + ", ".join(pet_parts[:8]))

    # Gear
    armor = [a['name'] for a in stats.get('armor', []) if a.get('name')]
    if armor:
        lines.append("Armor: " + ", ".join(armor))

    equip = [e['name'] for e in stats.get('equipment', []) if e.get('name')]
    if equip:
        lines.append("Equipment: " + ", ".join(equip))

    hotbar = [i['name'] for i in stats.get('inventory', [])[:9] if i.get('name')]
    if hotbar:
        lines.append("Hotbar: " + ", ".join(hotbar))

    # Collections (group by category)
    collections = stats.get('collections', {})
    if collections:
        for cat, item_ids in COLLECTION_CATEGORIES.items():
            cat_colls = []
            for cid in item_ids:
                if cid in collections:
                    name = cid.replace('_', ' ').title().replace(':1', '').replace(':2', '').replace(':3', '')
                    cat_colls.append(f"{name}: {_format_number(collections[cid])}")
            if cat_colls:
                lines.append(f"Collections ({cat}): " + " | ".join(cat_colls))

    return "\n".join(lines)
