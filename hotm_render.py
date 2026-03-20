"""
Render a Heart of the Mountain (HotM) tree visualization as an image.
Matches the in-game layout with tiers 1-10 from bottom to top.
"""
import io
from PIL import Image, ImageDraw, ImageFont

# --- HotM tree layout ---
# Each perk: (node_id, display_name, max_level, powder_type, is_ability)
# Tiers go 1 (bottom) to 10 (top). Each tier has perks in columns.
# Grid positions: (col, row) where row 0 = tier 10 (top), row 9 = tier 1 (bottom)

HOTM_PERKS = {
    # Tier 1
    "mining_speed":       {"name": "Mining Speed",       "max": 50,  "tier": 1, "col": 2, "powder": "mithril"},
    # Tier 2
    "mining_speed_boost": {"name": "Mining Speed\nBoost", "max": 3,   "tier": 2, "col": 1, "powder": "token", "ability": True},
    "precision_mining":   {"name": "Precision\nMining",   "max": 1,   "tier": 2, "col": 2, "powder": "token"},
    "pickobulus":         {"name": "Pickobulus",          "max": 3,   "tier": 2, "col": 3, "powder": "token", "ability": True},
    # Tier 3
    "efficient_miner":    {"name": "Efficient\nMiner",    "max": 100, "tier": 3, "col": 0, "powder": "mithril"},
    "mining_fortune":     {"name": "Mining\nFortune",     "max": 50,  "tier": 3, "col": 1, "powder": "mithril"},
    "quick_forge":        {"name": "Quick Forge",         "max": 20,  "tier": 3, "col": 2, "powder": "mithril"},
    "mole":               {"name": "Mole",                "max": 200, "tier": 3, "col": 3, "powder": "mithril"},
    "seasoned_mineman":   {"name": "Seasoned\nMineman",   "max": 100, "tier": 3, "col": 4, "powder": "mithril"},
    # Tier 4
    "gem_lover":          {"name": "Gem Lover",           "max": 20,  "tier": 4, "col": 0, "powder": "gemstone"},
    "old_school":         {"name": "Old School",          "max": 20,  "tier": 4, "col": 1, "powder": "mithril"},
    "professional":       {"name": "Professional",        "max": 140, "tier": 4, "col": 2, "powder": "gemstone"},
    "lonesome_miner":     {"name": "Lonesome\nMiner",     "max": 45,  "tier": 4, "col": 3, "powder": "gemstone"},
    "blockhead":          {"name": "Blockhead",           "max": 20,  "tier": 4, "col": 4, "powder": "mithril"},
    # Tier 5
    "daily_powder":       {"name": "Daily\nPowder",       "max": 100, "tier": 5, "col": 0, "powder": "gemstone"},
    "fortunate_mineman":  {"name": "Fortunate\nMineman",  "max": 50,  "tier": 5, "col": 1, "powder": "gemstone"},
    "great_explorer":     {"name": "Great\nExplorer",     "max": 20,  "tier": 5, "col": 2, "powder": "gemstone"},
    "speedy_mineman":     {"name": "Speedy\nMineman",     "max": 50,  "tier": 5, "col": 3, "powder": "gemstone"},
    "powder_buff":        {"name": "Powder\nBuff",        "max": 50,  "tier": 5, "col": 4, "powder": "gemstone"},
    # Tier 6
    "tunnel_vision":      {"name": "Tunnel\nVision",      "max": 3,   "tier": 6, "col": 1, "powder": "token", "ability": True},
    "warm_hearted":       {"name": "Warm\nHearted",       "max": 50,  "tier": 6, "col": 2, "powder": "glacite"},
    "maniac_miner":       {"name": "Maniac\nMiner",       "max": 3,   "tier": 6, "col": 3, "powder": "token", "ability": True},
    # Tier 7
    "titanium_insanium":  {"name": "Titanium\nInsanium",  "max": 50,  "tier": 7, "col": 1, "powder": "mithril"},
    "keep_it_cool":       {"name": "Keep It\nCool",       "max": 50,  "tier": 7, "col": 2, "powder": "glacite"},
    "subterranean_fisher": {"name": "Subterranean\nFisher", "max": 40, "tier": 7, "col": 3, "powder": "glacite"},
    # Tier 8
    "front_loaded":       {"name": "Front\nLoaded",       "max": 1,   "tier": 8, "col": 2, "powder": "token"},
    # Tier 9
    "no_stone_unturned":  {"name": "No Stone\nUnturned",  "max": 50,  "tier": 9, "col": 1, "powder": "glacite"},
    "surveyor":           {"name": "Surveyor",            "max": 20,  "tier": 9, "col": 3, "powder": "glacite"},
    # Tier 10
    "gemstone_infusion":  {"name": "Gemstone\nInfusion",  "max": 3,   "tier": 10, "col": 1, "powder": "token", "ability": True},
    "core_of_the_mountain": {"name": "Core of the\nMountain", "max": 10, "tier": 10, "col": 2, "powder": "all"},
    "sheer_force":        {"name": "Sheer\nForce",        "max": 3,   "tier": 10, "col": 3, "powder": "token", "ability": True},
}

# Colors
BG_COLOR = (30, 30, 46)
CARD_BG = (40, 42, 60)
LOCKED_COLOR = (80, 80, 100)
LOCKED_BORDER = (60, 60, 80)
MITHRIL_COLOR = (46, 139, 130)
GEMSTONE_COLOR = (170, 60, 160)
GLACITE_COLOR = (80, 160, 210)
TOKEN_COLOR = (200, 170, 50)
ALL_COLOR = (220, 120, 50)
MAXED_COLOR = (255, 200, 50)
ABILITY_ACTIVE = (80, 220, 120)
TEXT_COLOR = (230, 230, 240)
DIM_TEXT = (140, 140, 160)
TIER_TEXT = (100, 100, 120)

POWDER_COLORS = {
    "mithril": MITHRIL_COLOR,
    "gemstone": GEMSTONE_COLOR,
    "glacite": GLACITE_COLOR,
    "token": TOKEN_COLOR,
    "all": ALL_COLOR,
}

# Layout constants
NODE_W = 110
NODE_H = 64
COL_GAP = 12
ROW_GAP = 14
COLS = 5
ROWS = 10
MARGIN_X = 50
MARGIN_TOP = 80
MARGIN_BOTTOM = 30
POWDER_BAR_H = 60

IMG_W = MARGIN_X * 2 + COLS * NODE_W + (COLS - 1) * COL_GAP
IMG_H = MARGIN_TOP + ROWS * NODE_H + (ROWS - 1) * ROW_GAP + MARGIN_BOTTOM + POWDER_BAR_H


def _fmt_num(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def _get_font(size: int):
    """Try to load a decent font, fall back to default."""
    import platform
    paths = []
    if platform.system() == "Windows":
        paths = [
            "C:/Windows/Fonts/segoeui.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/calibri.ttf",
        ]
    else:
        paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/TTF/DejaVuSans.ttf",
        ]
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def render_hotm_tree(hotm_perks: dict, powder: dict, hotm_level: int,
                     selected_ability: str = "", username: str = "") -> io.BytesIO:
    """
    Render a HotM tree image.

    Args:
        hotm_perks: dict of {node_id: level} from player data
        powder: dict with keys mithril, gemstone, glacite (available amounts)
        hotm_level: int, HotM tier 1-10
        selected_ability: str, active ability node_id
        username: str, player name for the title

    Returns:
        BytesIO containing the PNG image
    """
    img = Image.new("RGB", (IMG_W, IMG_H), BG_COLOR)
    draw = ImageDraw.Draw(img)

    font_name = _get_font(11)
    font_level = _get_font(10)
    font_title = _get_font(18)
    font_tier = _get_font(12)
    font_powder = _get_font(13)

    # Title
    title = f"{username}'s HotM Tree" if username else "Heart of the Mountain"
    title += f"  (Tier {hotm_level})"
    bbox = draw.textbbox((0, 0), title, font=font_title)
    tw = bbox[2] - bbox[0]
    draw.text(((IMG_W - tw) / 2, 20), title, fill=TEXT_COLOR, font=font_title)

    # Draw tier labels and nodes
    for node_id, info in HOTM_PERKS.items():
        tier = info["tier"]
        col = info["col"]
        max_lvl = info["max"]
        is_ability = info.get("ability", False)
        powder_type = info["powder"]

        # Position: tier 10 at top (row 0), tier 1 at bottom (row 9)
        row = 10 - tier
        x = MARGIN_X + col * (NODE_W + COL_GAP)
        y = MARGIN_TOP + row * (NODE_H + ROW_GAP)

        player_level = hotm_perks.get(node_id, 0)
        unlocked = player_level > 0
        is_maxed = player_level >= max_lvl
        is_active_ability = is_ability and node_id == selected_ability

        # Node background
        if not unlocked:
            bg = LOCKED_COLOR
            border = LOCKED_BORDER
        elif is_maxed:
            bg = (60, 55, 20)
            border = MAXED_COLOR
        elif is_active_ability:
            bg = (25, 60, 35)
            border = ABILITY_ACTIVE
        else:
            base = POWDER_COLORS.get(powder_type, MITHRIL_COLOR)
            bg = (base[0] // 3, base[1] // 3, base[2] // 3)
            border = base

        # Draw rounded rectangle
        draw.rounded_rectangle([x, y, x + NODE_W, y + NODE_H], radius=6, fill=bg, outline=border, width=2)

        # Perk name (centered, multi-line)
        name = info["name"]
        lines = name.split("\n")
        line_h = 13
        total_text_h = len(lines) * line_h
        start_y = y + 6

        for i, line in enumerate(lines):
            bbox = draw.textbbox((0, 0), line, font=font_name)
            lw = bbox[2] - bbox[0]
            lx = x + (NODE_W - lw) / 2
            color = TEXT_COLOR if unlocked else DIM_TEXT
            draw.text((lx, start_y + i * line_h), line, fill=color, font=font_name)

        # Level text at bottom of node
        if is_ability:
            if is_active_ability:
                lvl_text = "ACTIVE"
                lvl_color = ABILITY_ACTIVE
            elif unlocked:
                lvl_text = f"Lvl {player_level}"
                lvl_color = TEXT_COLOR
            else:
                lvl_text = "Locked"
                lvl_color = DIM_TEXT
        elif unlocked:
            if is_maxed:
                lvl_text = f"MAX ({max_lvl})"
                lvl_color = MAXED_COLOR
            else:
                lvl_text = f"{player_level}/{max_lvl}"
                lvl_color = TEXT_COLOR
        else:
            lvl_text = "Locked"
            lvl_color = DIM_TEXT

        bbox = draw.textbbox((0, 0), lvl_text, font=font_level)
        lw = bbox[2] - bbox[0]
        draw.text((x + (NODE_W - lw) / 2, y + NODE_H - 16), lvl_text, fill=lvl_color, font=font_level)

    # Tier labels on the left
    for tier in range(1, 11):
        row = 10 - tier
        y = MARGIN_TOP + row * (NODE_H + ROW_GAP) + NODE_H / 2 - 6
        # Check if player has this tier
        has_tier = hotm_level >= tier
        color = TEXT_COLOR if has_tier else TIER_TEXT
        draw.text((8, y), f"T{tier}", fill=color, font=font_tier)

    # Powder bar at bottom
    powder_y = IMG_H - POWDER_BAR_H - 10
    draw.rounded_rectangle([MARGIN_X, powder_y, IMG_W - MARGIN_X, powder_y + POWDER_BAR_H],
                           radius=8, fill=CARD_BG)

    powder_items = [
        ("Mithril", powder.get("mithril", 0), MITHRIL_COLOR),
        ("Gemstone", powder.get("gemstone", 0), GEMSTONE_COLOR),
        ("Glacite", powder.get("glacite", 0), GLACITE_COLOR),
    ]
    section_w = (IMG_W - MARGIN_X * 2) / 3
    for i, (label, amount, color) in enumerate(powder_items):
        px = MARGIN_X + i * section_w + section_w / 2
        draw.text((px - 30, powder_y + 10), label, fill=color, font=font_powder)
        amt_text = _fmt_num(amount)
        draw.text((px - 20, powder_y + 30), amt_text, fill=TEXT_COLOR, font=font_powder)

    # Save to BytesIO
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf
