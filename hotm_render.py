"""
Render a Heart of the Mountain (HotM) tree visualization.
Dark, compact, game-styled — not corporate dashboard slop.
"""
import io
from PIL import Image, ImageDraw, ImageFont

# --- Perk definitions ---
# (node_id, display_name, max_level, tier, column, powder_type, is_ability)
HOTM_PERKS = {
    "mining_speed":        {"name": "Mining Speed",        "max": 50,  "tier": 1,  "col": 2, "powder": "mithril"},
    "mining_speed_boost":  {"name": "Speed Boost",         "max": 3,   "tier": 2,  "col": 1, "powder": "token", "ability": True},
    "precision_mining":    {"name": "Precision Mining",    "max": 1,   "tier": 2,  "col": 2, "powder": "token"},
    "pickobulus":          {"name": "Pickobulus",          "max": 3,   "tier": 2,  "col": 3, "powder": "token", "ability": True},
    "efficient_miner":     {"name": "Efficient Miner",    "max": 100, "tier": 3,  "col": 0, "powder": "mithril"},
    "mining_fortune":      {"name": "Mining Fortune",     "max": 50,  "tier": 3,  "col": 1, "powder": "mithril"},
    "quick_forge":         {"name": "Quick Forge",        "max": 20,  "tier": 3,  "col": 2, "powder": "mithril"},
    "mole":                {"name": "Mole",               "max": 200, "tier": 3,  "col": 3, "powder": "mithril"},
    "seasoned_mineman":    {"name": "Seasoned Mineman",   "max": 100, "tier": 3,  "col": 4, "powder": "mithril"},
    "gem_lover":           {"name": "Gem Lover",          "max": 20,  "tier": 4,  "col": 0, "powder": "gemstone"},
    "old_school":          {"name": "Old School",         "max": 20,  "tier": 4,  "col": 1, "powder": "mithril"},
    "professional":        {"name": "Professional",       "max": 140, "tier": 4,  "col": 2, "powder": "gemstone"},
    "lonesome_miner":      {"name": "Lonesome Miner",     "max": 45,  "tier": 4,  "col": 3, "powder": "gemstone"},
    "blockhead":           {"name": "Blockhead",          "max": 20,  "tier": 4,  "col": 4, "powder": "mithril"},
    "daily_powder":        {"name": "Daily Powder",       "max": 100, "tier": 5,  "col": 0, "powder": "gemstone"},
    "fortunate_mineman":   {"name": "Fortunate Mineman",  "max": 50,  "tier": 5,  "col": 1, "powder": "gemstone"},
    "great_explorer":      {"name": "Great Explorer",     "max": 20,  "tier": 5,  "col": 2, "powder": "gemstone"},
    "speedy_mineman":      {"name": "Speedy Mineman",     "max": 50,  "tier": 5,  "col": 3, "powder": "gemstone"},
    "powder_buff":         {"name": "Powder Buff",        "max": 50,  "tier": 5,  "col": 4, "powder": "gemstone"},
    "tunnel_vision":       {"name": "Tunnel Vision",      "max": 3,   "tier": 6,  "col": 1, "powder": "token", "ability": True},
    "warm_hearted":        {"name": "Warm Hearted",       "max": 50,  "tier": 6,  "col": 2, "powder": "glacite"},
    "maniac_miner":        {"name": "Maniac Miner",       "max": 3,   "tier": 6,  "col": 3, "powder": "token", "ability": True},
    "titanium_insanium":   {"name": "Titanium Insanium",  "max": 50,  "tier": 7,  "col": 1, "powder": "mithril"},
    "keep_it_cool":        {"name": "Keep It Cool",       "max": 50,  "tier": 7,  "col": 2, "powder": "glacite"},
    "subterranean_fisher": {"name": "Subterranean Fisher", "max": 40, "tier": 7,  "col": 3, "powder": "glacite"},
    "front_loaded":        {"name": "Front Loaded",       "max": 1,   "tier": 8,  "col": 2, "powder": "token"},
    "no_stone_unturned":   {"name": "No Stone Unturned",  "max": 50,  "tier": 9,  "col": 1, "powder": "glacite"},
    "surveyor":            {"name": "Surveyor",           "max": 20,  "tier": 9,  "col": 3, "powder": "glacite"},
    "gemstone_infusion":   {"name": "Gemstone Infusion",  "max": 3,   "tier": 10, "col": 1, "powder": "token", "ability": True},
    "core_of_the_mountain": {"name": "COTM",              "max": 10,  "tier": 10, "col": 2, "powder": "all"},
    "sheer_force":         {"name": "Sheer Force",        "max": 3,   "tier": 10, "col": 3, "powder": "token", "ability": True},
}

# --- Colors ---
BG = (20, 20, 30)
NODE_LOCKED = (35, 35, 48)
NODE_LOCKED_BORDER = (50, 50, 65)

# Powder type accent colors
ACCENT = {
    "mithril":  (0, 200, 180),
    "gemstone": (200, 60, 200),
    "glacite":  (70, 180, 240),
    "token":    (240, 200, 60),
    "all":      (240, 150, 50),
}

MAXED_GOLD = (255, 215, 0)
ABILITY_GREEN = (50, 230, 100)
WHITE = (240, 240, 245)
GREY = (90, 90, 110)
DIM = (55, 55, 70)
BAR_BG = (25, 25, 38)
PROGRESS_BG = (40, 40, 55)

# --- Short display names (fit in small nodes) ---
SHORT_NAMES = {
    "mining_speed": "M. Speed",
    "mining_speed_boost": "Spd Boost",
    "precision_mining": "Precision",
    "efficient_miner": "Efficient",
    "mining_fortune": "M. Fortune",
    "quick_forge": "Q. Forge",
    "seasoned_mineman": "Seasoned",
    "gem_lover": "Gem Lover",
    "old_school": "Old School",
    "professional": "Professnl",
    "lonesome_miner": "Lonesome",
    "daily_powder": "Daily Pwr",
    "fortunate_mineman": "Fortunate",
    "great_explorer": "Explorer",
    "speedy_mineman": "Speedy",
    "powder_buff": "Pwr Buff",
    "tunnel_vision": "Tunnel V.",
    "warm_hearted": "Warm Heart",
    "maniac_miner": "Maniac",
    "titanium_insanium": "Titanium",
    "keep_it_cool": "Keep Cool",
    "subterranean_fisher": "Sub Fisher",
    "front_loaded": "Front Load",
    "no_stone_unturned": "No Stone",
    "gemstone_infusion": "Gem Infuse",
    "core_of_the_mountain": "COTM",
    "sheer_force": "Sheer Frce",
}

# --- Layout ---
NODE_W = 62
NODE_H = 50
GAP = 5
COLS = 5
ROWS = 10
MARGIN = 24
TIER_LABEL_W = 20
HEADER_H = 34
FOOTER_H = 48

GRID_W = TIER_LABEL_W + COLS * NODE_W + (COLS - 1) * GAP
IMG_W = MARGIN * 2 + GRID_W
IMG_H = HEADER_H + MARGIN + ROWS * NODE_H + (ROWS - 1) * GAP + MARGIN + FOOTER_H


def _fmt(n: int) -> str:
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.0f}K"
    return str(n)


def _font(size: int):
    for p in [
        "C:/Windows/Fonts/consola.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]:
        try:
            return ImageFont.truetype(p, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def _center_text(draw, text, font, x, y, w, h, fill):
    """Draw text centered in a bounding box."""
    bb = draw.textbbox((0, 0), text, font=font)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    draw.text((x + (w - tw) / 2, y + (h - th) / 2 - 1), text, fill=fill, font=font)


def render_hotm_tree(hotm_perks: dict, powder: dict, hotm_level: int,
                     selected_ability: str = "", username: str = "") -> io.BytesIO:
    img = Image.new("RGB", (IMG_W, IMG_H), BG)
    draw = ImageDraw.Draw(img)

    f_title = _font(14)
    f_small = _font(9)
    f_tiny = _font(8)
    f_powder = _font(11)

    # Header
    title = f"{username}  |  HotM {hotm_level}" if username else f"HotM {hotm_level}"
    bb = draw.textbbox((0, 0), title, font=f_title)
    draw.text(((IMG_W - (bb[2] - bb[0])) / 2, 10), title, fill=WHITE, font=f_title)

    # Thin separator
    draw.line([(MARGIN, HEADER_H), (IMG_W - MARGIN, HEADER_H)], fill=DIM, width=1)

    grid_x = MARGIN + TIER_LABEL_W
    grid_y = HEADER_H + MARGIN

    # Draw connection lines between tiers (subtle vertical lines)
    for tier in range(1, 10):
        row = 9 - tier
        row_above = row - 1
        y_bot = grid_y + row * (NODE_H + GAP) + NODE_H
        y_top = grid_y + row_above * (NODE_H + GAP)

        cols_this = [info["col"] for info in HOTM_PERKS.values() if info["tier"] == tier]
        cols_above = [info["col"] for info in HOTM_PERKS.values() if info["tier"] == tier + 1]

        for c in set(cols_this) & set(cols_above):
            cx = grid_x + c * (NODE_W + GAP) + NODE_W // 2
            draw.line([(cx, y_bot), (cx, y_top)], fill=DIM, width=1)

    # Draw nodes
    for node_id, info in HOTM_PERKS.items():
        tier = info["tier"]
        col = info["col"]
        max_lvl = info["max"]
        is_ability = info.get("ability", False)
        ptype = info["powder"]

        row = 9 - (tier - 1)
        x = grid_x + col * (NODE_W + GAP)
        y = grid_y + row * (NODE_H + GAP)

        lvl = hotm_perks.get(node_id, 0)
        unlocked = lvl > 0
        maxed = lvl >= max_lvl
        active_ability = is_ability and node_id == selected_ability
        tier_unlocked = hotm_level >= tier

        accent = ACCENT.get(ptype, ACCENT["mithril"])

        # Background + border
        if not unlocked:
            fill = NODE_LOCKED
            border = NODE_LOCKED_BORDER if tier_unlocked else (30, 30, 40)
        elif maxed:
            fill = (40, 38, 18)
            border = MAXED_GOLD
        elif active_ability:
            fill = (18, 45, 25)
            border = ABILITY_GREEN
        else:
            fill = (accent[0] // 6, accent[1] // 6, accent[2] // 6)
            border = accent

        draw.rectangle([x, y, x + NODE_W - 1, y + NODE_H - 1], fill=fill, outline=border, width=1)

        # Progress bar at bottom of node (3px tall)
        if unlocked and max_lvl > 1:
            bar_y = y + NODE_H - 5
            bar_w = NODE_W - 6
            progress = min(lvl / max_lvl, 1.0)
            draw.rectangle([x + 3, bar_y, x + 3 + bar_w, bar_y + 3], fill=PROGRESS_BG)
            if progress > 0:
                bar_color = MAXED_GOLD if maxed else accent
                draw.rectangle([x + 3, bar_y, x + 3 + int(bar_w * progress), bar_y + 3], fill=bar_color)

        # Perk name (top of node)
        name = SHORT_NAMES.get(node_id, info["name"])
        name_color = WHITE if unlocked else GREY
        bb = draw.textbbox((0, 0), name, font=f_tiny)
        tw = bb[2] - bb[0]
        draw.text((x + (NODE_W - tw) / 2, y + 4), name, fill=name_color, font=f_tiny)

        # Level text (middle)
        if is_ability:
            if active_ability:
                lvl_text = "ACTIVE"
                lvl_color = ABILITY_GREEN
            elif unlocked:
                lvl_text = f"Lvl {lvl}"
                lvl_color = accent
            else:
                lvl_text = "--"
                lvl_color = DIM
        elif maxed:
            lvl_text = "MAX"
            lvl_color = MAXED_GOLD
        elif unlocked:
            lvl_text = f"{lvl}/{max_lvl}"
            lvl_color = WHITE
        else:
            lvl_text = "--"
            lvl_color = DIM

        bb = draw.textbbox((0, 0), lvl_text, font=f_small)
        tw = bb[2] - bb[0]
        draw.text((x + (NODE_W - tw) / 2, y + 20), lvl_text, fill=lvl_color, font=f_small)

    # Tier labels
    for tier in range(1, 11):
        row = 9 - (tier - 1)
        y = grid_y + row * (NODE_SIZE + GAP)
        color = WHITE if hotm_level >= tier else DIM
        draw.text((MARGIN + 2, y + NODE_SIZE // 2 - 5), str(tier), fill=color, font=f_small)

    # Footer — powder amounts
    fy = IMG_H - FOOTER_H
    draw.line([(MARGIN, fy), (IMG_W - MARGIN, fy)], fill=DIM, width=1)

    powders = [
        ("Mithril", powder.get("mithril", 0), ACCENT["mithril"]),
        ("Gemstone", powder.get("gemstone", 0), ACCENT["gemstone"]),
        ("Glacite", powder.get("glacite", 0), ACCENT["glacite"]),
    ]
    section_w = (IMG_W - MARGIN * 2) // 3
    for i, (label, amt, color) in enumerate(powders):
        px = MARGIN + i * section_w
        draw.text((px + 4, fy + 8), label, fill=color, font=f_tiny)
        draw.text((px + 4, fy + 22), _fmt(amt), fill=WHITE, font=f_powder)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf
