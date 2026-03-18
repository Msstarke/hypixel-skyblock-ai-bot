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

    # ── Gear (NBT) ───────────────────────────────────────────────────────────
    inv = member.get('inventory', {})
    stats['armor']     = parse_nbt_items(inv.get('inv_armor', {}).get('data', ''))
    stats['equipment'] = parse_nbt_items(inv.get('equipment_contents', {}).get('data', ''))
    stats['wardrobe']  = parse_nbt_items(inv.get('wardrobe_contents', {}).get('data', ''))
    stats['inventory'] = parse_nbt_items(inv.get('inv_contents', {}).get('data', ''))
    stats['ender_chest'] = parse_nbt_items(inv.get('ender_chest_contents', {}).get('data', ''))

    return stats


def format_for_ai(username: str, profile_name: str, stats: dict) -> str:
    """Condense parsed stats into a string for the AI system prompt."""
    from hypixel_api import HOTM_XP
    lines = [f"=== Player: {username} | Profile: {profile_name} ==="]

    # Skills
    skill_parts = [f"{k} {v['level']}" for k, v in stats.get('skills', {}).items() if v['level'] > 0]
    if skill_parts:
        lines.append("Skills: " + " | ".join(skill_parts))

    # Slayer
    slayer_parts = [f"{k} {v['level']}" for k, v in stats.get('slayer', {}).items()]
    lines.append("Slayer: " + " | ".join(slayer_parts))

    # Dungeons
    cata = stats.get('catacombs_level', 0)
    sel_class = stats.get('selected_class', '')
    lines.append(f"Catacombs: {cata} | Selected class: {sel_class}")

    class_parts = [f"{k} {v['level']}" for k, v in stats.get('dungeon_classes', {}).items() if v['level'] > 0]
    if class_parts:
        lines.append("Classes: " + " | ".join(class_parts))

    completions = stats.get('floor_completions', {})
    if completions:
        comp_parts = [f"{k}:{v}" for k, v in sorted(completions.items())]
        lines.append("Floor completions: " + " ".join(comp_parts))

    # HotM
    hotm_xp = stats.get('hotm_xp', 0)
    hotm_lvl = sum(1 for req in HOTM_XP[1:] if hotm_xp >= req)
    lines.append(f"HotM: {hotm_lvl} ({hotm_xp:,.0f} XP)")

    # Misc
    lines.append(f"Fairy souls: {stats.get('fairy_souls', 0)}")
    purse = stats.get('purse', 0)
    if purse:
        lines.append(f"Purse: {purse:,.0f} coins")

    # Gear
    armor = [a['name'] for a in stats.get('armor', []) if a.get('name')]
    if armor:
        lines.append("Armor (head→feet): " + ", ".join(armor))

    equip = [e['name'] for e in stats.get('equipment', []) if e.get('name')]
    if equip:
        lines.append("Equipment: " + ", ".join(equip))

    hotbar = [i['name'] for i in stats.get('inventory', [])[:9] if i.get('name')]
    if hotbar:
        lines.append("Hotbar: " + ", ".join(hotbar))

    return "\n".join(lines)
