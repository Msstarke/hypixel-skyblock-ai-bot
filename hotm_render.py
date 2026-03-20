"""
Render a Heart of the Mountain (HotM) tree visualization.
Styled to match Minecraft inventory UI aesthetic.
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

# ── Minecraft-inspired color palette ──
BG = (22, 22, 30)
SLOT_BG = (50, 50, 60)           # Minecraft inventory slot gray
SLOT_BORDER_DARK = (20, 20, 28)  # Bottom-right shadow
SLOT_BORDER_LIGHT = (70, 70, 82) # Top-left highlight (3D bevel)
LOCKED_BG = (30, 30, 38)
LOCKED_BORDER = (40, 40, 50)

ACCENT = {
    "mithril":  (0, 210, 190),
    "gemstone": (210, 60, 210),
    "glacite":  (70, 180, 240),
    "token":    (240, 200, 60),
    "all":      (240, 150, 40),
}
MAXED_GOLD = (255, 215, 0)
ABILITY_GREEN = (50, 240, 100)
WHITE = (240, 240, 245)
LIGHT_GREY = (180, 180, 195)
GREY = (110, 110, 130)
DIM_LINE = (55, 55, 70)
BAR_BG = (30, 30, 40)
BAR_BORDER = (20, 20, 28)

# ── Layout ──
NODE_W = 64
NODE_H = 56
GAP_X = 6
GAP_Y = 6
GRID_COLS = 7
GRID_ROWS = 10
MARGIN = 18
HEADER_H = 44
FOOTER_H = 52

GRID_W = GRID_COLS * NODE_W + (GRID_COLS - 1) * GAP_X
GRID_H = GRID_ROWS * NODE_H + (GRID_ROWS - 1) * GAP_Y
IMG_W = MARGIN * 2 + GRID_W
IMG_H = HEADER_H + GRID_H + FOOTER_H


def _pos_to_rc(pos):
    row = (pos - 1) // 9
    col = (pos - 1) % 9
    return row, col


def _fmt(n):
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def _font(size):
    for p in [
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/consola.ttf",
        "C:/Windows/Fonts/cascadiamono.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    ]:
        try:
            return ImageFont.truetype(p, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def _font_bold(size):
    for p in [
        "C:/Windows/Fonts/segoeuib.ttf",
        "C:/Windows/Fonts/consolab.ttf",
        "C:/Windows/Fonts/cascadiamonob.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]:
        try:
            return ImageFont.truetype(p, size)
        except (OSError, IOError):
            continue
    return _font(size)


def _center_text(draw, text, font, x, y, w, fill):
    bb = draw.textbbox((0, 0), text, font=font)
    tw = bb[2] - bb[0]
    draw.text((x + (w - tw) / 2, y), text, fill=fill, font=font)


def _draw_slot(draw, x, y, w, h, fill, border_color=None, glow=False):
    """Draw a Minecraft-style inventory slot with 3D bevel effect."""
    # Main fill
    draw.rectangle([x, y, x + w - 1, y + h - 1], fill=fill)

    if border_color:
        # Colored border (2px)
        draw.rectangle([x, y, x + w - 1, y + h - 1], outline=border_color, width=2)
        if glow:
            # Soft outer glow: draw a slightly transparent border around
            glow_color = (border_color[0], border_color[1], border_color[2])
            draw.rectangle([x - 1, y - 1, x + w, y + h], outline=glow_color, width=1)
    else:
        # Standard Minecraft bevel: light top-left, dark bottom-right
        # Top edge
        draw.line([(x, y), (x + w - 1, y)], fill=SLOT_BORDER_LIGHT, width=1)
        # Left edge
        draw.line([(x, y), (x, y + h - 1)], fill=SLOT_BORDER_LIGHT, width=1)
        # Bottom edge
        draw.line([(x, y + h - 1), (x + w - 1, y + h - 1)], fill=SLOT_BORDER_DARK, width=1)
        # Right edge
        draw.line([(x + w - 1, y), (x + w - 1, y + h - 1)], fill=SLOT_BORDER_DARK, width=1)


def _get_level(hotm_perks, api_id):
    lvl = hotm_perks.get(api_id, 0)
    if lvl == 0:
        alt = ALT_IDS.get(api_id)
        if alt:
            lvl = hotm_perks.get(alt, 0)
    return lvl


def _lerp_color(c1, c2, t):
    """Linearly interpolate between two colors."""
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))


def render_hotm_tree(hotm_perks: dict, powder: dict, hotm_level: int,
                     selected_ability: str = "", username: str = "") -> io.BytesIO:
    img = Image.new("RGB", (IMG_W, IMG_H), BG)
    draw = ImageDraw.Draw(img)

    f_title = _font_bold(14)
    f_subtitle = _font(10)
    f_name = _font(8)
    f_lvl = _font_bold(10)
    f_powder_label = _font_bold(10)
    f_powder_val = _font(12)
    f_tier = _font(8)

    # ── Header ──
    title = username if username else "HotM Tree"
    _center_text(draw, title, f_title, 0, 8, IMG_W, WHITE)
    subtitle = f"Heart of the Mountain {hotm_level}"
    _center_text(draw, subtitle, f_subtitle, 0, 26, IMG_W, LIGHT_GREY)

    grid_x = MARGIN
    grid_y = HEADER_H

    # Build position lookup
    perk_positions = {}
    for api_id, (_, pos, _, _, _) in PERKS.items():
        row, col = _pos_to_rc(pos)
        perk_positions[(row, col)] = api_id

    # ── Connection lines (draw first, behind nodes) ──
    for api_id, (_, pos, _, ptype, _) in PERKS.items():
        row, col = _pos_to_rc(pos)
        x = grid_x + col * (NODE_W + GAP_X)
        y = grid_y + row * (NODE_H + GAP_Y)
        cx = x + NODE_W // 2
        cy_bot = y + NODE_H

        lvl = _get_level(hotm_perks, api_id)
        line_color = DIM_LINE

        # Vertical down
        if (row + 1, col) in perk_positions:
            ny = grid_y + (row + 1) * (NODE_H + GAP_Y)
            # Color the line if both nodes are unlocked
            other_id = perk_positions[(row + 1, col)]
            other_lvl = _get_level(hotm_perks, other_id)
            if lvl > 0 and other_lvl > 0:
                line_color = _lerp_color(DIM_LINE, ACCENT.get(ptype, DIM_LINE), 0.5)
            else:
                line_color = DIM_LINE
            draw.line([(cx, cy_bot), (cx, ny)], fill=line_color, width=2)

        # Horizontal right
        if (row, col + 1) in perk_positions:
            rx = grid_x + (col + 1) * (NODE_W + GAP_X)
            mid_y = y + NODE_H // 2
            other_id = perk_positions[(row, col + 1)]
            other_lvl = _get_level(hotm_perks, other_id)
            if lvl > 0 and other_lvl > 0:
                line_color = _lerp_color(DIM_LINE, ACCENT.get(ptype, DIM_LINE), 0.5)
            else:
                line_color = DIM_LINE
            draw.line([(x + NODE_W, mid_y), (rx, mid_y)], fill=line_color, width=2)

    # ── Tier labels on the left ──
    for row in range(GRID_ROWS):
        tier = 10 - row
        ty = grid_y + row * (NODE_H + GAP_Y) + NODE_H // 2 - 4
        tier_color = LIGHT_GREY if hotm_level >= tier else (50, 50, 60)
        draw.text((3, ty), str(tier), fill=tier_color, font=f_tier)

    # ── Draw nodes ──
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

        # Check active ability
        active = False
        if is_ability:
            possible_ids = {api_id}
            if api_id in ALT_IDS:
                possible_ids.add(ALT_IDS[api_id])
            active = selected_ability in possible_ids

        # ── Node style ──
        if not unlocked:
            fill = LOCKED_BG
            border = LOCKED_BORDER if tier_unlocked else None
            glow = False
        elif maxed:
            fill = (45, 40, 15)
            border = MAXED_GOLD
            glow = True
        elif active:
            fill = (15, 45, 25)
            border = ABILITY_GREEN
            glow = True
        else:
            # Tinted fill based on powder type
            fill = (accent[0] // 7 + 12, accent[1] // 7 + 12, accent[2] // 7 + 12)
            border = accent
            glow = False

        _draw_slot(draw, x, y, NODE_W, NODE_H, fill, border_color=border, glow=glow)

        # ── Progress bar (4px tall, inside node at bottom) ──
        if unlocked and max_lvl > 1:
            bar_x = x + 4
            bar_y = y + NODE_H - 8
            bar_w = NODE_W - 8
            bar_h = 4
            progress = min(lvl / max_lvl, 1.0)
            # Bar background
            draw.rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + bar_h], fill=BAR_BG)
            draw.rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + bar_h], outline=BAR_BORDER, width=1)
            if progress > 0:
                c = MAXED_GOLD if maxed else accent
                pw = max(1, int(bar_w * progress))
                draw.rectangle([bar_x + 1, bar_y + 1, bar_x + pw, bar_y + bar_h - 1], fill=c)

        # ── Name text ──
        lines = name.split("\n")
        name_color = WHITE if unlocked else GREY
        text_y = y + 4
        for i, line in enumerate(lines):
            _center_text(draw, line, f_name, x, text_y + i * 11, NODE_W, name_color)

        # ── Level text ──
        if is_ability:
            if active:
                lt, lc = "ACTIVE", ABILITY_GREEN
            elif unlocked:
                lt, lc = f"Lvl {lvl}", accent
            else:
                lt, lc = "Locked", GREY
        elif maxed:
            lt, lc = "MAXED", MAXED_GOLD
        elif unlocked:
            lt, lc = f"{lvl}/{max_lvl}", LIGHT_GREY
        else:
            lt, lc = "Locked", (55, 55, 65)

        lvl_y = text_y + len(lines) * 11 + 1
        _center_text(draw, lt, f_lvl, x, lvl_y, NODE_W, lc)

    # ── Footer: Powder summary ──
    fy = IMG_H - FOOTER_H
    # Separator line
    draw.line([(MARGIN, fy + 4), (IMG_W - MARGIN, fy + 4)], fill=DIM_LINE, width=1)

    powders = [
        ("Mithril", powder.get("mithril", 0), ACCENT["mithril"]),
        ("Gemstone", powder.get("gemstone", 0), ACCENT["gemstone"]),
        ("Glacite", powder.get("glacite", 0), ACCENT["glacite"]),
    ]
    sw = (IMG_W - MARGIN * 2) // 3
    for i, (label, amt, color) in enumerate(powders):
        px = MARGIN + i * sw
        # Colored dot
        dot_y = fy + 16
        draw.ellipse([px + 2, dot_y, px + 8, dot_y + 6], fill=color)
        # Label
        draw.text((px + 12, fy + 12), label, fill=color, font=f_powder_label)
        # Value
        draw.text((px + 12, fy + 28), _fmt(amt), fill=WHITE, font=f_powder_val)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf
