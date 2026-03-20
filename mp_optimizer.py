"""
Magical Power optimizer — finds the cheapest accessories to maximize MP.
Factors in recombobulation costs vs buying higher-tier accessories.
"""

# MP per rarity tier
RARITY_MP = {
    "COMMON": 3,
    "UNCOMMON": 5,
    "RARE": 8,
    "EPIC": 12,
    "LEGENDARY": 16,
    "MYTHIC": 22,
    "SPECIAL": 3,
    "VERY_SPECIAL": 5,
    "SUPREME": 22,
    "DIVINE": 22,
}

# Rarity upgrade order for recombobulation
RARITY_ORDER = ["COMMON", "UNCOMMON", "RARE", "EPIC", "LEGENDARY", "MYTHIC"]

RECOMB_ITEM_ID = "RECOMBOBULATOR_3000"

# Accessory families — only highest tier in a family counts for MP
# We group by shared prefix/suffix patterns


def _get_rarity_mp(tier: str) -> int:
    return RARITY_MP.get(tier, 0)


def _next_rarity(tier: str) -> str | None:
    """Return the next rarity tier, or None if already max."""
    try:
        idx = RARITY_ORDER.index(tier)
        if idx + 1 < len(RARITY_ORDER):
            return RARITY_ORDER[idx + 1]
    except ValueError:
        pass
    return None


async def get_accessory_mp_rankings(hypixel_api, owned_ids: set = None) -> list[dict]:
    """
    Get all accessories ranked by cost-per-MP.

    Returns list of dicts:
    {
        'id': str, 'name': str, 'tier': str, 'mp': int,
        'price': float, 'cost_per_mp': float,
        'recomb_price': float, 'recomb_cost_per_mp': float,
        'recomb_better': bool, 'soulbound': bool,
    }
    """
    import asyncio

    # Fetch items and prices in parallel
    items_task = hypixel_api.get_all_items()
    lbin_task = hypixel_api.get_lowest_bin()
    baz_task = hypixel_api.get_bazaar()
    items, lbin, baz = await asyncio.gather(items_task, lbin_task, baz_task)

    if not items:
        return []

    # Get recombobulator price from bazaar
    recomb_price = 0
    if baz:
        recomb_product = baz.get("products", {}).get(RECOMB_ITEM_ID, {})
        recomb_qs = recomb_product.get("quick_status", {})
        recomb_price = recomb_qs.get("buyPrice", 0)
    if not recomb_price and lbin:
        recomb_price = lbin.get(RECOMB_ITEM_ID, 0)
    if not recomb_price:
        recomb_price = 5_000_000  # fallback estimate

    # Filter to accessories only
    accessories = [
        item for item in items.values()
        if item.get("category") == "ACCESSORY"
        and item.get("tier") in RARITY_MP
    ]

    owned_ids = owned_ids or set()
    results = []

    for acc in accessories:
        item_id = acc["id"]
        name = acc.get("name", item_id.replace("_", " ").title())
        tier = acc.get("tier", "COMMON")
        mp = _get_rarity_mp(tier)
        soulbound = bool(acc.get("soulbound"))

        if mp == 0:
            continue

        # Get price from lowest BIN
        price = lbin.get(item_id, 0)

        # Skip items with no price data (unobtainable/untradeable)
        if price <= 0 and not soulbound:
            continue
        if soulbound:
            price = 0  # free if obtainable

        # Already owned — skip for buying recommendations but note it
        already_owned = item_id in owned_ids

        # Cost per MP (buying this accessory)
        cost_per_mp = price / mp if mp > 0 and price > 0 else float("inf")

        # Recombobulation math: can we recomb this for cheaper cost-per-MP?
        next_tier = _next_rarity(tier)
        recomb_mp_gain = 0
        recomb_total = 0
        recomb_cost_per_mp = float("inf")
        recomb_better = False

        if next_tier and price > 0:
            recomb_mp_gain = _get_rarity_mp(next_tier) - mp
            if recomb_mp_gain > 0:
                recomb_total = recomb_price  # cost of recomb only (already own the item)
                recomb_cost_per_mp = recomb_total / recomb_mp_gain

        results.append({
            "id": item_id,
            "name": name,
            "tier": tier,
            "mp": mp,
            "price": price,
            "cost_per_mp": cost_per_mp,
            "recomb_price": recomb_price if next_tier else 0,
            "recomb_mp_gain": recomb_mp_gain,
            "recomb_cost_per_mp": recomb_cost_per_mp,
            "recomb_better": False,  # calculated below
            "soulbound": soulbound,
            "owned": already_owned,
        })

    # Sort by cost per MP
    results.sort(key=lambda x: x["cost_per_mp"])

    return results


def format_mp_plan(rankings: list[dict], budget: int = None,
                   current_mp: int = 0, owned_ids: set = None,
                   target_count: int = 25) -> str:
    """
    Build a buying plan: cheapest accessories to buy + when to recomb instead.

    Returns formatted text for Discord embed.
    """
    owned_ids = owned_ids or set()
    recomb_price = rankings[0]["recomb_price"] if rankings else 5_000_000

    # Split into buyable (not owned) and owned (recomb candidates)
    buyable = [r for r in rankings if not r["owned"] and not r["soulbound"] and r["price"] > 0]
    owned = [r for r in rankings if r["owned"]]

    # Build recomb options for owned accessories
    recomb_options = []
    for acc in owned:
        if acc["recomb_mp_gain"] > 0:
            recomb_options.append({
                "name": acc["name"],
                "id": acc["id"],
                "tier": acc["tier"],
                "mp_gain": acc["recomb_mp_gain"],
                "cost": recomb_price,
                "cost_per_mp": recomb_price / acc["recomb_mp_gain"],
                "type": "recomb",
            })

    # Build buy options
    buy_options = []
    for acc in buyable:
        buy_options.append({
            "name": acc["name"],
            "id": acc["id"],
            "tier": acc["tier"],
            "mp_gain": acc["mp"],
            "cost": acc["price"],
            "cost_per_mp": acc["cost_per_mp"],
            "type": "buy",
        })

    # Merge and sort all options by cost per MP
    all_options = buy_options + recomb_options
    all_options.sort(key=lambda x: x["cost_per_mp"])

    # Build the plan
    lines = []
    total_cost = 0
    total_mp_gain = 0
    seen_ids = set()

    for i, opt in enumerate(all_options[:target_count]):
        if opt["id"] in seen_ids:
            continue
        seen_ids.add(opt["id"])

        if budget and total_cost + opt["cost"] > budget:
            break

        total_cost += opt["cost"]
        total_mp_gain += opt["mp_gain"]

        cost_str = _format_coins(opt["cost"])
        cpm_str = _format_coins(opt["cost_per_mp"])

        if opt["type"] == "recomb":
            lines.append(
                f"**{i+1}.** Recomb **{opt['name']}** ({opt['tier'].title()}) "
                f"— +{opt['mp_gain']} MP for {cost_str} ({cpm_str}/MP)"
            )
        else:
            lines.append(
                f"**{i+1}.** Buy **{opt['name']}** ({opt['tier'].title()}) "
                f"— +{opt['mp_gain']} MP for {cost_str} ({cpm_str}/MP)"
            )

    summary = f"**Total: +{total_mp_gain} MP for {_format_coins(total_cost)}**"
    if current_mp:
        summary += f" (MP: {current_mp:,} → {current_mp + total_mp_gain:,})"

    return summary + "\n\n" + "\n".join(lines) if lines else "No recommendations available."


def _format_coins(n: float) -> str:
    if n >= 1_000_000_000:
        return f"{n / 1_000_000_000:.1f}B"
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return f"{n:,.0f}"
