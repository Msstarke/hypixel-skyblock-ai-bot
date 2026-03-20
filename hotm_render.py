"""
Render a Heart of the Mountain (HotM) tree visualization.
Layout matches SkyCrypt's 9-column, 10-row grid exactly.
"""
import io
from PIL import Image, ImageDraw, ImageFont

# SkyCrypt grid: 9 columns, 10 rows. Tier 10 = row 0 (top), tier 1 = row 9 (bottom).
# Position = row * 9 + col (0-indexed internally, but SkyCrypt uses 1-indexed positions)
# So: row = (pos - 1) // 9, col = (pos - 1) % 9

# api_id -> (display_name, skycrypt_position, max_level, powder_type, is_ability)
PERKS = {
    # Tier 10 (row 0)
    "gemstone_infusion":     ("Gemstone\nInfusion",     1,   3,   "token",    True),
    "crystalline":           ("Crystalline",            2,   50,  "glacite",  False),
    "gifts_from_the_departed": ("Gifts from\nDeparted", 3,   100, "glacite",  False),
    "mining_master":         ("Mining\nMaster",          4,   50,  "glacite",  False),
    "hungry_for_more":       ("Dead Man's\nChest",       5,   50,  "glacite",  False),
    "vanguard_seeker":       ("Vanguard\nSeeker",        6,   50,  "glacite",  False),
    "sheer_force":           ("Sheer\nForce",            7,   3,   "token",    True),
    # Tier 9 (row 1)
    "metal_head":            ("Metal\nHead",             11,  20,  "glacite",  False),
    "rags_to_riches":        ("Rags to\nRiches",         13,  50,  "glacite",  False),
    "eager_adventurer":      ("Eager\nAdventurer",       15,  100, "glacite",  False),
    # Tier 8 (row 2)
    "miners_blessing":       ("Miner's\nBlessing",       19,  1,   "token",    False),
    "no_stone_unturned":     ("No Stone\nUnturned",      20,  50,  "glacite",  False),
    "strong_arm":            ("Strong\nArm",             21,  100, "glacite",  False),
    "steady_hand":           ("Steady\nHand",            22,  50,  "glacite",  False),
    "warm_hearted":          ("Warm\nHeart",             23,  50,  "glacite",  False),
    "surveyor":              ("Surveyor",                24,  20,  "glacite",  False),
    "mineshaft_mayhem":      ("Mineshaft\nMayhem",       25,  1,   "token",    False),
    # Tier 7 (row 3)
    "mining_speed_2":        ("Speedy\nMineman",         29,  50,  "gemstone", False),
    "powder_buff":           ("Powder\nBuff",            31,  50,  "gemstone", False),
    "mining_fortune_2":      ("Fortunate\nMineman",      33,  50,  "gemstone", False),
    # Tier 6 (row 4)
    "anomalous_desire":      ("Anomalous\nDesire",       37,  3,   "token",    True),
    "blockhead":             ("Blockhead",               38,  20,  "gemstone", False),
    "subterranean_fisher":   ("Subterranean\nFisher",    39,  40,  "glacite",  False),
    "keep_it_cool":          ("Keep It\nCool",           40,  50,  "glacite",  False),
    "lonesome_miner":        ("Lonesome\nMiner",         41,  45,  "gemstone", False),
    "great_explorer":        ("Great\nExplorer",         42,  20,  "gemstone", False),
    "maniac_miner":          ("Maniac\nMiner",           43,  3,   "token",    True),
    # Tier 5 (row 5)
    "daily_grind":           ("Daily\nGrind",            47,  100, "gemstone", False),
    "special_0":             ("Core of the\nMountain",   49,  10,  "all",      False),
    "daily_powder":          ("Daily\nPowder",           51,  100, "gemstone", False),
    # Tier 4 (row 6)
    "daily_effect":          ("Sky Mall",                55,  1,   "token",    False),
    "old_school":            ("Old School",              56,  20,  "mithril",  False),
    "professional":          ("Professional",            57,  140, "gemstone", False),
    "mole":                  ("Mole",                    58,  200, "mithril",  False),
    "fortunate":             ("Gem Lover",               59,  20,  "gemstone", False),
    "mining_experience":     ("Seasoned\nMineman",       60,  100, "mithril",  False),
    "front_loaded":          ("Front\nLoaded",           61,  1,   "token",    False),
    # Tier 3 (row 7)
    "random_event":          ("Luck of\nthe Cave",       65,  45,  "mithril",  False),
    "efficient_miner":       ("Efficient\nMiner",        67,  100, "mithril",  False),
    "forge_time":            ("Quick\nForge",            69,  20,  "mithril",  False),
    # Tier 2 (row 8)
    "mining_speed_boost":    ("Speed\nBoost",            74,  3,   "token",    True),
    "precision_mining":      ("Precision\nMining",       75,  1,   "token",    False),
    "mining_fortune":        ("Mining\nFortune",         76,  50,  "mithril",  False),
    "titanium_insanium":     ("Titanium\nInsanium",      77,  50,  "mithril",  False),
    "pickaxe_toss":          ("Pickobulus",              78,  3,   "token",    True),
    # Tier 1 (row 9)
    "mining_speed":          ("Mining\nSpeed",           85,  50,  "mithril",  False),
}

# Alternative API IDs — Hypixel API uses different names for some perks
ALT_IDS = {
    "pickaxe_toss": "pickobulus",
    "forge_time": "quick_forge",
    "random_event": "luck_of_the_cave",
    "mining_experience": "seasoned_mineman",
    "fortunate": "gem_lover",
    "daily_effect": "sky_mall",
    "special_0": "core_of_the_mountain",
    "mining_speed_2": "speedy_mineman",
    "mining_fortune_2": "fortunate_mineman",
    "hungry_for_more": "dead_mans_chest",
}

# Colors
BG = (18, 18, 28)
NODE_BG = (32, 34, 48)
NODE_LOCKED = (26, 26, 36)
NODE_BORDER_LOCKED = (42, 42, 56)
ACCENT = {
    "mithril":  (0, 190, 170),
    "gemstone": (190, 50, 190),
    "glacite":  (60, 170, 230),
    "token":    (230, 190, 50),
    "all":      (230, 140, 40),
}
MAXED_GOLD = (255, 210, 0)
ABILITY_GREEN = (40, 220, 90)
WHITE = (235, 235, 240)
GREY = (100, 100, 120)
DIM = (45, 45, 58)
BAR_BG = (22, 22, 34)

# Layout
NODE_W = 56
NODE_H = 48
GAP_X = 3
GAP_Y = 3
GRID_COLS = 7  # only 7 columns are used (0-6)
GRID_ROWS = 10
MARGIN = 14
HEADER_H = 28
FOOTER_H = 42

GRID_W = GRID_COLS * NODE_W + (GRID_COLS - 1) * GAP_X
GRID_H = GRID_ROWS * NODE_H + (GRID_ROWS - 1) * GAP_Y
IMG_W = MARGIN * 2 + GRID_W
IMG_H = HEADER_H + 6 + GRID_H + 6 + FOOTER_H


def _pos_to_rc(pos):
    """Convert SkyCrypt position to (row, col) in the 9-wide grid."""
    row = (pos - 1) // 9
    col = (pos - 1) % 9
    return row, col


def _fmt(n):
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.0f}K"
    return str(n)


def _font(size):
    for p in [
        "C:/Windows/Fonts/consola.ttf",
        "C:/Windows/Fonts/cascadiamono.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]:
        try:
            return ImageFont.truetype(p, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def _center_text(draw, text, font, x, y, w, fill):
    bb = draw.textbbox((0, 0), text, font=font)
    tw = bb[2] - bb[0]
    draw.text((x + (w - tw) / 2, y), text, fill=fill, font=font)


def _get_level(hotm_perks, api_id):
    """Get perk level, checking both SkyCrypt and Hypixel API ID variants."""
    lvl = hotm_perks.get(api_id, 0)
    if lvl == 0:
        alt = ALT_IDS.get(api_id)
        if alt:
            lvl = hotm_perks.get(alt, 0)
    return lvl


def render_hotm_tree(hotm_perks: dict, powder: dict, hotm_level: int,
                     selected_ability: str = "", username: str = "") -> io.BytesIO:
    img = Image.new("RGB", (IMG_W, IMG_H), BG)
    draw = ImageDraw.Draw(img)

    f_title = _font(12)
    f_name = _font(8)
    f_lvl = _font(9)
    f_powder = _font(10)
    f_plabel = _font(7)

    # Header
    title = f"{username}  ·  HotM {hotm_level}" if username else f"HotM {hotm_level}"
    _center_text(draw, title, f_title, 0, 7, IMG_W, WHITE)

    grid_x = MARGIN
    grid_y = HEADER_H + 6

    # Build position lookup for connection drawing
    perk_positions = {}  # (row, col) -> api_id
    for api_id, (_, pos, _, _, _) in PERKS.items():
        row, col = _pos_to_rc(pos)
        perk_positions[(row, col)] = api_id

    # Draw connection lines
    for api_id, (_, pos, _, _, _) in PERKS.items():
        row, col = _pos_to_rc(pos)
        x = grid_x + col * (NODE_W + GAP_X)
        y = grid_y + row * (NODE_H + GAP_Y)
        cx = x + NODE_W // 2
        cy_bot = y + NODE_H

        # Vertical down
        if (row + 1, col) in perk_positions:
            ny = grid_y + (row + 1) * (NODE_H + GAP_Y)
            draw.line([(cx, cy_bot), (cx, ny)], fill=DIM, width=1)

        # Horizontal right
        if (row, col + 1) in perk_positions:
            rx = grid_x + (col + 1) * (NODE_W + GAP_X)
            mid_y = y + NODE_H // 2
            draw.line([(x + NODE_W, mid_y), (rx, mid_y)], fill=DIM, width=1)

    # Draw nodes
    for api_id, (name, pos, max_lvl, ptype, is_ability) in PERKS.items():
        row, col = _pos_to_rc(pos)
        x = grid_x + col * (NODE_W + GAP_X)
        y = grid_y + row * (NODE_H + GAP_Y)

        lvl = _get_level(hotm_perks, api_id)
        unlocked = lvl > 0
        maxed = lvl >= max_lvl
        tier = 10 - row
        tier_unlocked = hotm_level >= tier
        accent = ACCENT.get(ptype, ACCENT["mithril"])

        # Check if this is the active ability
        active = False
        if is_ability:
            # Match against both SkyCrypt and API IDs
            possible_ids = {api_id}
            if api_id in ALT_IDS:
                possible_ids.add(ALT_IDS[api_id])
            active = selected_ability in possible_ids

        # Colors
        if not unlocked:
            fill = NODE_LOCKED
            border = NODE_BORDER_LOCKED if tier_unlocked else (28, 28, 36)
        elif maxed:
            fill = (35, 33, 12)
            border = MAXED_GOLD
        elif active:
            fill = (12, 40, 20)
            border = ABILITY_GREEN
        else:
            fill = (accent[0] // 8 + 8, accent[1] // 8 + 8, accent[2] // 8 + 8)
            border = accent

        draw.rectangle([x, y, x + NODE_W - 1, y + NODE_H - 1], fill=fill, outline=border, width=1)

        # Progress bar (2px at bottom)
        if unlocked and max_lvl > 1:
            bar_y = y + NODE_H - 4
            bar_w = NODE_W - 4
            progress = min(lvl / max_lvl, 1.0)
            draw.rectangle([x + 2, bar_y, x + 2 + bar_w, bar_y + 2], fill=BAR_BG)
            if progress > 0:
                c = MAXED_GOLD if maxed else accent
                draw.rectangle([x + 2, bar_y, x + 2 + int(bar_w * progress), bar_y + 2], fill=c)

        # Name text
        lines = name.split("\n")
        name_color = WHITE if unlocked else GREY
        for i, line in enumerate(lines):
            _center_text(draw, line, f_name, x, y + 3 + i * 11, NODE_W, name_color)

        # Level text
        if is_ability:
            if active:
                lt, lc = "ON", ABILITY_GREEN
            elif unlocked:
                lt, lc = f"Lvl {lvl}", accent
            else:
                lt, lc = "·", DIM
        elif maxed:
            lt, lc = "MAX", MAXED_GOLD
        elif unlocked:
            lt, lc = f"{lvl}/{max_lvl}", WHITE
        else:
            lt, lc = "·", DIM

        lvl_y = y + 5 + len(lines) * 11
        _center_text(draw, lt, f_lvl, x, lvl_y, NODE_W, lc)

    # Footer
    fy = IMG_H - FOOTER_H
    draw.line([(MARGIN, fy + 2), (IMG_W - MARGIN, fy + 2)], fill=DIM, width=1)

    powders = [
        ("Mithril", powder.get("mithril", 0), ACCENT["mithril"]),
        ("Gemstone", powder.get("gemstone", 0), ACCENT["gemstone"]),
        ("Glacite", powder.get("glacite", 0), ACCENT["glacite"]),
    ]
    sw = (IMG_W - MARGIN * 2) // 3
    for i, (label, amt, color) in enumerate(powders):
        px = MARGIN + i * sw
        draw.text((px + 2, fy + 7), label, fill=color, font=f_plabel)
        draw.text((px + 2, fy + 20), _fmt(amt), fill=WHITE, font=f_powder)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf
