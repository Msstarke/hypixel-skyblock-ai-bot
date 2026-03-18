import aiohttp
import time
from typing import Optional

BAZAAR_URL = "https://api.hypixel.net/v2/skyblock/bazaar"
AUCTIONS_ENDED_URL = "https://api.hypixel.net/v2/skyblock/auctions_ended"
LOWEST_BIN_URL = "https://moulberry.codes/lowestbin.json"
MOJANG_URL = "https://api.mojang.com/users/profiles/minecraft"
PROFILES_URL = "https://api.hypixel.net/v2/skyblock/profiles"
ITEMS_URL = "https://api.hypixel.net/resources/skyblock/items"  # no API key needed
ITEMS_CACHE_TTL = 3600  # 1 hour — items rarely change

CACHE_TTL = 300  # 5 minutes
PLAYER_CACHE_TTL = 120  # 2 minutes for player data
AH_CACHE_TTL = 120    # 2 minutes for AH data

# Cumulative HotM XP required per level (source: SkyCrypt leveling.js)
# Increments: 3k, 9k, 25k, 60k, 100k, 150k, 210k, 290k, 400k
HOTM_XP = [0, 0, 3_000, 12_000, 37_000, 97_000, 197_000, 347_000, 557_000, 847_000, 1_247_000]
# XP per commission tier (tier 1 = standard Dwarven commission)
COMMISSION_XP = {1: 2_750, 2: 7_500, 3: 22_500}


class HypixelAPI:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self._cache: dict = {}

    def _cache_valid(self, key: str, ttl: int = CACHE_TTL) -> bool:
        entry = self._cache.get(key)
        return entry is not None and time.time() - entry["ts"] < ttl

    async def _get(self, url: str, cache_key: str, params: dict = None, ttl: int = CACHE_TTL) -> Optional[dict]:
        if self._cache_valid(cache_key, ttl):
            return self._cache[cache_key]["data"]
        if params is None:
            params = {"key": self.api_key} if self.api_key else {}
        elif self.api_key and "key" not in params:
            params["key"] = self.api_key
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self._cache[cache_key] = {"data": data, "ts": time.time()}
                    return data
        return None

    async def get_bazaar(self) -> Optional[dict]:
        return await self._get(BAZAAR_URL, "bazaar")

    async def get_auctions_ended(self) -> Optional[dict]:
        return await self._get(AUCTIONS_ENDED_URL, "auctions_ended", ttl=AH_CACHE_TTL)

    async def get_lowest_bin(self) -> dict:
        """Fetch lowest BIN prices from moulberry.codes (keyed by item ID)."""
        data = await self._get(LOWEST_BIN_URL, "lowest_bin", params={}, ttl=AH_CACHE_TTL)
        return data or {}

    async def search_ah(self, query: str) -> list[dict]:
        """
        Search for an item across AH sources:
        1. Lowest BIN (active listings)
        2. Recently ended auctions (last ~24h sales)
        Returns list of {source, item_id, price, name}
        """
        query_norm = query.upper().replace(" ", "_").replace("'", "")
        query_lower = query.lower().replace("'", "")
        results = []

        # 1. Lowest BIN prices
        lbin = await self.get_lowest_bin()
        lbin_matches = {k: v for k, v in lbin.items()
                        if query_norm in k or query_lower in k.lower().replace("_", " ")}
        for item_id, price in sorted(lbin_matches.items(), key=lambda x: x[1])[:5]:
            results.append({
                "source": "Lowest BIN",
                "item_id": item_id,
                "price": price,
                "name": item_id.replace("_", " ").title(),
            })

        # 2. Recently ended auctions — find recent sales for this item
        ended = await self.get_auctions_ended()
        if ended:
            auctions = ended.get("auctions", [])
            # Filter by item name match
            matches = [
                a for a in auctions
                if query_lower in a.get("item_name", "").lower() or
                   query_norm in a.get("item_lore", "")
            ]
            if matches:
                # Get median/avg price from recent sales
                prices = sorted(a["price"] for a in matches)
                median = prices[len(prices) // 2]
                results.append({
                    "source": f"Recent AH sales ({len(matches)} auctions)",
                    "item_id": query_norm,
                    "price": median,
                    "name": matches[0].get("item_name", query),
                    "low": prices[0],
                    "high": prices[-1],
                })

        return results[:6]

    async def get_bazaar_flips(self, min_margin_pct: float = 1.5, min_volume: int = 5_000, top_n: int = 15) -> list[dict]:
        """
        Find top Bazaar order-flip opportunities.
        Strategy: place buy order near instasell, sell order near instabuy.
        Profit = instabuy - instasell - 1.25% tax.
        Ranked by net_margin_pct × weekly_liquidity.
        """
        data = await self.get_bazaar()
        if not data:
            return []

        TAX = 1.25  # sell order tax %
        flips = []

        for item_id, product in data.get("products", {}).items():
            qs = product.get("quick_status", {})
            buy  = qs.get("buyPrice", 0)   # instabuy price (you pay)
            sell = qs.get("sellPrice", 0)  # instasell price (you receive)
            buy_week  = qs.get("buyMovingWeek", 0)
            sell_week = qs.get("sellMovingWeek", 0)
            buy_orders  = qs.get("buyOrders", 0)
            sell_orders = qs.get("sellOrders", 0)

            if buy <= 0 or sell <= 0 or buy <= sell:
                continue

            margin = buy - sell
            margin_pct = (margin / buy) * 100
            net_pct = margin_pct - TAX  # after 1.25% sell tax
            weekly_vol = min(buy_week, sell_week)  # liquidity = bottleneck side

            if net_pct < min_margin_pct or weekly_vol < min_volume or margin < 100:
                continue

            # Score: reward high margin AND high volume equally
            score = net_pct * (weekly_vol / 100_000)

            flips.append({
                "id": item_id,
                "name": item_id.replace("_", " ").title(),
                "buy": round(buy, 1),
                "sell": round(sell, 1),
                "margin": round(margin, 1),
                "margin_pct": round(net_pct, 2),
                "weekly_vol": int(weekly_vol),
                "buy_orders": buy_orders,
                "sell_orders": sell_orders,
                "score": score,
            })

        flips.sort(key=lambda x: x["score"], reverse=True)
        return flips[:top_n]

    async def get_ah_flips(self, min_margin_pct: float = 10.0, min_margin_coins: int = 50_000, top_n: int = 10) -> list[dict]:
        """
        Find AH BIN flip opportunities:
        Buy at lowest BIN, relist at median recently-sold price.
        Only shows items where BIN is significantly below recent median.
        """
        from collections import defaultdict

        lbin, ended = await asyncio.gather(self.get_lowest_bin(), self.get_auctions_ended())
        if not lbin or not ended:
            return []

        # Build median sale price per item ID from ended auctions
        sales: dict[str, list] = defaultdict(list)
        for auction in ended.get("auctions", []):
            item_id = auction.get("item_name", "").upper().replace(" ", "_")
            if item_id:
                sales[item_id].append(auction["price"])

        medians: dict[str, float] = {}
        for item_id, prices in sales.items():
            prices.sort()
            medians[item_id] = prices[len(prices) // 2]

        flips = []
        for item_id, bin_price in lbin.items():
            median = medians.get(item_id)
            if not median or bin_price <= 0:
                continue
            margin = median - bin_price
            margin_pct = (margin / bin_price) * 100
            if margin_pct < min_margin_pct or margin < min_margin_coins:
                continue
            flips.append({
                "id": item_id,
                "name": item_id.replace("_", " ").title(),
                "bin": round(bin_price),
                "median_sold": round(median),
                "margin": round(margin),
                "margin_pct": round(margin_pct, 1),
                "sales_count": len(sales[item_id]),
            })

        flips.sort(key=lambda x: x["margin"], reverse=True)
        return flips[:top_n]

    async def search_bazaar(self, query: str) -> list[dict]:
        data = await self.get_bazaar()
        if not data:
            return []
        query_norm = query.upper().replace(" ", "_")
        matches = []
        for item_id, product in data.get("products", {}).items():
            if query_norm in item_id:
                qs = product.get("quick_status", {})
                matches.append({
                    "id": item_id,
                    "buy": round(qs.get("buyPrice", 0), 1),
                    "sell": round(qs.get("sellPrice", 0), 1),
                    "buy_vol": qs.get("buyVolume", 0),
                    "sell_vol": qs.get("sellVolume", 0),
                })
        return matches[:15]

    async def get_bazaar_item(self, item_id: str) -> Optional[dict]:
        data = await self.get_bazaar()
        if not data:
            return None
        item_id = item_id.upper().replace(" ", "_")
        product = data.get("products", {}).get(item_id)
        if not product:
            return None
        qs = product.get("quick_status", {})
        return {
            "id": item_id,
            "buy": round(qs.get("buyPrice", 0), 1),
            "sell": round(qs.get("sellPrice", 0), 1),
            "buy_vol": qs.get("buyVolume", 0),
            "sell_vol": qs.get("sellVolume", 0),
        }

    async def get_all_items(self) -> dict[str, dict]:
        """Fetch all Skyblock items, keyed by item ID. Cached for 1 hour."""
        data = await self._get(ITEMS_URL, "all_items", params={}, ttl=ITEMS_CACHE_TTL)  # no API key
        if not data:
            return {}
        return {item["id"]: item for item in data.get("items", [])}

    async def find_item(self, query: str) -> Optional[dict]:
        """Find an item by name or ID (fuzzy match)."""
        items = await self.get_all_items()
        if not items:
            return None

        query_norm = query.upper().replace(" ", "_").replace("'", "")
        query_lower = query.lower().replace("'", "")

        # 1. Exact ID match
        if query_norm in items:
            return items[query_norm]

        # 2. Exact name match
        for item in items.values():
            if item.get("name", "").lower().replace("'", "") == query_lower:
                return item

        # 3. Partial ID match
        matches = [item for item_id, item in items.items() if query_norm in item_id]
        if matches:
            # prefer shorter ID (more specific match)
            return min(matches, key=lambda x: len(x["id"]))

        # 4. Partial name match
        matches = [item for item in items.values() if query_lower in item.get("name", "").lower()]
        if matches:
            return min(matches, key=lambda x: len(x.get("name", "")))

        return None

    def format_item_info(self, item: dict) -> str:
        """Format item data into a readable string for the AI."""
        lines = [f"**{item.get('name', item['id'])}** (ID: {item['id']})"]

        if item.get("tier"):
            lines.append(f"Rarity: {item['tier'].title()}")
        if item.get("category"):
            lines.append(f"Category: {item['category'].replace('_', ' ').title()}")
        if item.get("npc_sell_price"):
            lines.append(f"NPC sell price: {item['npc_sell_price']:,} coins")

        # Stats
        stats = item.get("stats", {})
        if stats:
            stat_str = " | ".join(f"{k.replace('_', ' ').title()}: +{v}" for k, v in stats.items())
            lines.append(f"Stats: {stat_str}")

        # Requirements
        reqs = item.get("requirements", [])
        if reqs:
            req_parts = []
            for r in reqs:
                if r.get("type") == "HEART_OF_THE_MOUNTAIN":
                    req_parts.append(f"HotM {r.get('tier', '?')}")
                elif r.get("type") == "SKILL":
                    req_parts.append(f"{r.get('skill', '').title()} {r.get('level', '?')}")
                elif r.get("type") == "SLAYER":
                    req_parts.append(f"{r.get('slayer_boss_type', '').title()} Slayer {r.get('level', '?')}")
                elif r.get("type") == "DUNGEON_SKILL":
                    req_parts.append(f"Catacombs {r.get('level', '?')}")
            if req_parts:
                lines.append(f"Requirements: {', '.join(req_parts)}")

        # Recipe (crafting table)
        recipe = item.get("recipe")
        if recipe:
            slots = []
            for row in ["A", "B", "C"]:
                for col in ["1", "2", "3"]:
                    slot = recipe.get(f"{row}{col}", "")
                    if slot:
                        item_id, count = slot.split(":") if ":" in slot else (slot, "1")
                        slots.append(f"{item_id.replace('_', ' ').title()} x{count}")
            if slots:
                lines.append(f"Recipe: {', '.join(slots)}")
        elif item.get("crafttext"):
            lines.append(f"Craft note: {item['crafttext']}")

        # Gemstone slots
        gem_slots = item.get("gemstone_slots", [])
        if gem_slots:
            slot_types = [s.get("slot_type", "").title() for s in gem_slots]
            lines.append(f"Gemstone slots: {', '.join(slot_types)}")

        return "\n".join(lines)

    async def get_uuid(self, username: str) -> Optional[str]:
        """Get Mojang UUID for a username."""
        cache_key = f"uuid_{username.lower()}"
        if self._cache_valid(cache_key, 3600):
            return self._cache[cache_key]["data"]
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{MOJANG_URL}/{username}", timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    uuid = data.get("id")
                    if uuid:
                        # Format with dashes
                        uuid = f"{uuid[:8]}-{uuid[8:12]}-{uuid[12:16]}-{uuid[16:20]}-{uuid[20:]}"
                        self._cache[cache_key] = {"data": uuid, "ts": time.time()}
                        return uuid
        return None

    async def get_profiles(self, uuid: str) -> Optional[list]:
        """Get all Skyblock profiles for a UUID."""
        cache_key = f"profiles_{uuid}"
        data = await self._get(PROFILES_URL, cache_key, {"uuid": uuid}, ttl=PLAYER_CACHE_TTL)
        if data and data.get("success"):
            return data.get("profiles", [])
        return None

    async def get_player_data(self, username: str, profile_name: str = None) -> Optional[dict]:
        """
        Fetch and parse player's Skyblock profile.
        Returns dict with 'username', 'profile_name', 'stats', and raw HotM fields.
        Optionally filter by profile_name (e.g. 'Coconut').
        """
        from player_stats import parse_member, format_for_ai

        uuid = await self.get_uuid(username)
        if not uuid:
            return None

        profiles = await self.get_profiles(uuid)
        if not profiles:
            return None

        # Pick profile by name if specified, else use selected/most recent
        if profile_name:
            active = next(
                (p for p in profiles if p.get("cute_name", "").lower() == profile_name.lower()),
                None
            )
        else:
            active = next((p for p in profiles if p.get("selected")), None)
        if not active:
            active = max(profiles, key=lambda p: p.get("last_save", 0))

        uuid_nodash = uuid.replace("-", "")
        member = active.get("members", {}).get(uuid_nodash, {})
        pname = active.get("cute_name", "Unknown")

        stats = parse_member(member)
        summary = format_for_ai(username, pname, stats)

        # Keep HotM fields at top level for backwards compat
        hotm_xp = stats["hotm_xp"]
        hotm_level = self._xp_to_hotm_level(hotm_xp)

        return {
            "username": username,
            "profile_name": pname,
            "stats": stats,
            "summary": summary,
            "hotm_xp": hotm_xp,
            "hotm_level": hotm_level,
            "xp_to_next_hotm": self._xp_to_next_hotm(hotm_xp, hotm_level),
            "xp_to_hotm_10": max(0, HOTM_XP[10] - hotm_xp),
        }

    def _xp_to_hotm_level(self, xp: float) -> int:
        level = 1
        for lvl, req in enumerate(HOTM_XP):
            if xp >= req:
                level = lvl
        return min(level, 10)

    def _xp_to_next_hotm(self, xp: float, current_level: int) -> float:
        if current_level >= 10:
            return 0
        return max(0, HOTM_XP[current_level + 1] - xp)

    @staticmethod
    def commissions_needed(xp_needed: float, tier: int = 1) -> int:
        xp_per = COMMISSION_XP.get(tier, 2_750)
        return -(-int(xp_needed) // xp_per)  # ceiling division
