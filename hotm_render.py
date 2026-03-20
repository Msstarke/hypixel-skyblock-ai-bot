"""
Render a Heart of the Mountain (HotM) tree visualization.
Layout matches SkyCrypt's 7-column grid exactly.
"""
import io
from PIL import Image, ImageDraw, ImageFont

# SkyCrypt grid: 7 columns per row, 10 rows (tier 10 at top = row 0, tier 1 at bottom = row 9)
# Position formula: pos = row * 7 + col (1-indexed within each row)
# So col = ((pos - 1) % 7), row = (pos - 1) // 7
# But SkyCrypt uses a flat numbering: tier 10 = pos 1-7, tier 9 = pos 8-14 (but only odd cols used), etc.

# Complete perk list with SkyCrypt positions and API node IDs
# Format: api_id -> (display_name, position, max_level, powder_type, is_ability)
PERKS = {
    # Tier 10 (pos 1-7)
    "gemstone_infusion":    ("Gemstone\nInfusion",    1,   3,   "token",    True),
    "crystalline":          ("Crystalline",           2,   50,  "glacite",  False),
    "gifts_from_the_departed": ("Gifts from\nDeparted", 3, 100, "glacite",  False),
    "mining_master":        ("Mining\nMaster",         4,   50,  "glacite",  False),
    "hungry_for_more":      ("Dead Man's\nChest",      5,   50,  "glacite",  False),
    "vanguard_seeker":      ("Vanguard\nSeeker",       6,   50,  "glacite",  False),
    "sheer_force":          ("Sheer\nForce",           7,   3,   "token",    True),
    # Tier 9 (pos 8-14, only 11,13,15 used)
    "metal_head":           ("Metal\nHead",            11,  20,  "glacite",  False),
    "rags_to_riches":       ("Rags to\nRiches",        13,  50,  "glacite",  False),
    "eager_adventurer":     ("Eager\nAdventurer",      15,  100, "glacite",  False),
    # Tier 8 (pos 15-21 -> 19-25)
    "miners_blessing":      ("Miner's\nBlessing",      19,  1,   "token",    False),
    "no_stone_unturned":    ("No Stone\nUnturned",     20,  50,  "glacite",  False),
    "strong_arm":           ("Strong\nArm",            21,  100, "glacite",  False),
    "steady_hand":          ("Steady\nHand",           22,  50,  "glacite",  False),
    "warm_hearted":         ("Warm\nHeart",            23,  50,  "glacite",  False),
    "surveyor":             ("Surveyor",               24,  20,  "glacite",  False),
    "mineshaft_mayhem":     ("Mineshaft\nMayhem",      25,  1,   "token",    False),
    # Tier 7 (pos 22-28 -> 29,31,33)
    "mining_speed_2":       ("Speedy\nMineman",        29,  50,  "gemstone", False),
    "powder_buff":          ("Powder\nBuff",           31,  50,  "gemstone", False),
    "mining_fortune_2":     ("Fortunate\nMineman",     33,  50,  "gemstone", False),
    # Tier 6 (pos 29-35 -> 37-43)
    "anomalous_desire":     ("Anomalous\nDesire",      37,  3,   "token",    True),
    "blockhead":            ("Blockhead",              38,  20,  "gemstone", False),
    "subterranean_fisher":  ("Subterranean\nFisher",   39,  40,  "glacite",  False),
    "keep_it_cool":         ("Keep It\nCool",          40,  50,  "glacite",  False),
    "lonesome_miner":       ("Lonesome\nMiner",        41,  45,  "gemstone", False),
    "great_explorer":       ("Great\nExplorer",        42,  20,  "gemstone", False),
    "maniac_miner":         ("Maniac\nMiner",          43,  3,   "token",    True),
    # Tier 5 (pos 36-42 -> 47,49,51)
    "daily_grind":          ("Daily\nGrind",           47,  100, "gemstone", False),
    "special_0":            ("Core of the\nMountain",  49,  10,  "all",      False),
    "daily_powder":         ("Daily\nPowder",          51,  100, "gemstone", False),
    # Tier 4 (pos 43-49 -> 55-61)
    "daily_effect":         ("Sky Mall",               55,  1,   "token",    False),
    "old_school":           ("Old School",             56,  20,  "mithril",  False),
    "professional":         ("Professional",           57,  140, "gemstone", False),
    "mole":                 ("Mole",                   58,  200, "mithril",  False),
    "fortunate":            ("Gem Lover",              59,  20,  "gemstone", False),
    "mining_experience":    ("Seasoned\nMineman",      60,  100, "mithril",  False),
    "front_loaded":         ("Front\nLoaded",          61,  1,   "token",    False),
    # Tier 3 (pos 50-56 -> 65,67,69)
    "random_event":         ("Luck of\nthe Cave",      65,  45,  "mithril",  False),
    "efficient_miner":      ("Efficient\nMiner",       67,  100, "mithril",  False),
    "forge_time":           ("Quick\nForge",           69,  20,  "mithril",  False),
    # Tier 2 (pos 57-63 -> 74-78)
    "mining_speed_boost":   ("Speed\nBoost",           74,  3,   "token",    True),
    "precision_mining":     ("Precision\nMining",      75,  1,   "token",    False),
    "mining_fortune":       ("Mining\nFortune",        76,  50,  "mithril",  False),
    "titanium_insanium":    ("Titanium\nInsanium",     77,  50,  "mithril",  False),
    "pickaxe_toss":         ("Pickobulus",             78,  3,   "token",    True),
    # Tier 1 (pos 64-70 -> 85)
    "mining_speed":         ("Mining\nSpeed",          85,  50,  "mithril",  False),
}

# Map from SkyCrypt flat position to (col, row) in a 7-wide grid
# pos 1-7 = row 0, pos 8-14 = row 1, etc.
def _pos_to_grid(pos):
    row = (pos - 1) // 7
    col = (pos - 1) % 7
    return col, row

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
DIM = (50, 50, 65)
BAR_BG = (22, 22, 34)

# Layout
NODE_W = 52
NODE_H = 44
GAP_X = 4
GAP_Y = 4
COLS = 7
ROWS = 10
MARGIN = 16
HEADER_H = 30
FOOTER_H = 44

GRID_W = COLS * NODE_W + (COLS - 1) * GAP_X
GRID_H = ROWS * NODE_H + (ROWS - 1) * GAP_Y
IMG_W = MARGIN * 2 + GRID_W
IMG_H = HEADER_H + 8 + GRID_H + 8 + FOOTER_H


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


def _draw_text_centered(draw, text, font, x, y, w, fill):
    bb = draw.textbbox((0, 0), text, font=font)
    tw = bb[2] - bb[0]
    draw.text((x + (w - tw) / 2, y), text, fill=fill, font=font)


def render_hotm_tree(hotm_perks: dict, powder: dict, hotm_level: int,
                     selected_ability: str = "", username: str = "") -> io.BytesIO:
    img = Image.new("RGB", (IMG_W, IMG_H), BG)
    draw = ImageDraw.Draw(img)

    f_title = _font(13)
    f_name = _font(7)
    f_lvl = _font(9)
    f_powder = _font(10)
    f_powder_label = _font(8)

    # Header
    title = f"{username}  ·  HotM {hotm_level}" if username else f"HotM {hotm_level}"
    _draw_text_centered(draw, title, f_title, 0, 8, IMG_W, WHITE)

    grid_x = MARGIN
    grid_y = HEADER_H + 8

    # Connection lines between nodes
    for api_id, (name, pos, max_lvl, ptype, is_ab) in PERKS.items():
        col, row = _pos_to_grid(pos)
        cx = grid_x + col * (NODE_W + GAP_X) + NODE_W // 2
        cy = grid_y + row * (NODE_H + GAP_Y) + NODE_H

        # Draw down-connection if there's a perk directly below
        for other_id, (_, opos, _, _, _) in PERKS.items():
            if other_id == api_id:
                continue
            oc, orow = _pos_to_grid(opos)
            if oc == col and orow == row + 1:
                oy = grid_y + orow * (NODE_H + GAP_Y)
                draw.line([(cx, cy), (cx, oy)], fill=DIM, width=1)

        # Horizontal connections within same row for adjacent perks
        for other_id, (_, opos, _, _, _) in PERKS.items():
            if other_id == api_id:
                continue
            oc, orow = _pos_to_grid(opos)
            if orow == row and oc == col + 1:
                ox = grid_x + oc * (NODE_W + GAP_X)
                my_right = grid_x + col * (NODE_W + GAP_X) + NODE_W
                mid_y = grid_y + row * (NODE_H + GAP_Y) + NODE_H // 2
                draw.line([(my_right, mid_y), (ox, mid_y)], fill=DIM, width=1)

    # Draw nodes
    for api_id, (name, pos, max_lvl, ptype, is_ability) in PERKS.items():
        col, row = _pos_to_grid(pos)
        x = grid_x + col * (NODE_W + GAP_X)
        y = grid_y + row * (NODE_H + GAP_Y)

        # Remap API IDs: the Hypixel API uses different IDs for some perks
        # Check both the SkyCrypt ID and common variants
        lvl = hotm_perks.get(api_id, 0)
        # Handle API ID differences
        if lvl == 0:
            alt_ids = {
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
                "daily_grind": "daily_grind",
                "anomalous_desire": "anomalous_desire",
            }
            alt = alt_ids.get(api_id)
            if alt:
                lvl = hotm_perks.get(alt, 0)

        unlocked = lvl > 0
        maxed = lvl >= max_lvl
        tier = 10 - row
        tier_unlocked = hotm_level >= tier
        active_ab = is_ability and (api_id == selected_ability or
                                     api_id == "pickaxe_toss" and selected_ability == "pickobulus" or
                                     api_id == "mining_speed_boost" and selected_ability == "mining_speed_boost")

        accent = ACCENT.get(ptype, ACCENT["mithril"])

        # Node fill + border
        if not unlocked:
            fill = NODE_LOCKED
            border = NODE_BORDER_LOCKED if tier_unlocked else (30, 30, 38)
        elif maxed:
            fill = (38, 35, 15)
            border = MAXED_GOLD
        elif active_ab:
            fill = (15, 42, 22)
            border = ABILITY_GREEN
        else:
            fill = (accent[0] // 7 + 10, accent[1] // 7 + 10, accent[2] // 7 + 10)
            border = accent

        draw.rectangle([x, y, x + NODE_W - 1, y + NODE_H - 1], fill=fill, outline=border, width=1)

        # Powder type indicator (tiny 3px dot in top-right)
        if unlocked:
            draw.rectangle([x + NODE_W - 5, y + 2, x + NODE_W - 3, y + 4], fill=accent)

        # Progress bar (2px, bottom of node)
        if unlocked and max_lvl > 1:
            bar_y = y + NODE_H - 4
            bar_w = NODE_W - 4
            progress = min(lvl / max_lvl, 1.0)
            draw.rectangle([x + 2, bar_y, x + 2 + bar_w, bar_y + 2], fill=BAR_BG)
            if progress > 0:
                c = MAXED_GOLD if maxed else accent
                draw.rectangle([x + 2, bar_y, x + 2 + int(bar_w * progress), bar_y + 2], fill=c)

        # Name
        lines = name.split("\n")
        name_color = WHITE if unlocked else GREY
        for i, line in enumerate(lines):
            _draw_text_centered(draw, line, f_name, x, y + 2 + i * 10, NODE_W, name_color)

        # Level
        if is_ability:
            if active_ab:
                lt, lc = "ON", ABILITY_GREEN
            elif unlocked:
                lt, lc = f"L{lvl}", accent
            else:
                lt, lc = "·", DIM
        elif maxed:
            lt, lc = "MAX", MAXED_GOLD
        elif unlocked:
            lt, lc = f"{lvl}/{max_lvl}", WHITE
        else:
            lt, lc = "·", DIM

        name_lines = len(lines)
        lvl_y = y + 4 + name_lines * 10
        _draw_text_centered(draw, lt, f_lvl, x, lvl_y, NODE_W, lc)

    # Footer — powder
    fy = IMG_H - FOOTER_H
    draw.line([(MARGIN, fy + 2), (IMG_W - MARGIN, fy + 2)], fill=DIM, width=1)

    powders = [
        ("Mithril", powder.get("mithril", 0), ACCENT["mithril"]),
        ("Gemstone", powder.get("gemstone", 0), ACCENT["gemstone"]),
        ("Glacite", powder.get("glacite", 0), ACCENT["glacite"]),
    ]
    section_w = (IMG_W - MARGIN * 2) // 3
    for i, (label, amt, color) in enumerate(powders):
        px = MARGIN + i * section_w
        draw.text((px + 2, fy + 8), label, fill=color, font=f_powder_label)
        draw.text((px + 2, fy + 22), _fmt(amt), fill=WHITE, font=f_powder)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf
