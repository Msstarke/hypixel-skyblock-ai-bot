import aiohttp
import time
from typing import Optional

BAZAAR_URL = "https://api.hypixel.net/v2/skyblock/bazaar"
AUCTIONS_ENDED_URL = "https://api.hypixel.net/v2/skyblock/auctions_ended"
MOJANG_URL = "https://api.mojang.com/users/profiles/minecraft"
PROFILES_URL = "https://api.hypixel.net/v2/skyblock/profiles"
ITEMS_URL = "https://api.hypixel.net/resources/skyblock/items"  # no API key needed
ITEMS_CACHE_TTL = 3600  # 1 hour — items rarely change

CACHE_TTL = 300  # 5 minutes
PLAYER_CACHE_TTL = 120  # 2 minutes for player data

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
        return await self._get(AUCTIONS_ENDED_URL, "auctions_ended")

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

        recipe = item.get("recipe")
        if recipe:
            # Recipe is a 3x3 grid: A1-C3
            slots = []
            for row in ["A", "B", "C"]:
                for col in ["1", "2", "3"]:
                    slot = recipe.get(f"{row}{col}", "")
                    if slot:
                        item_id, count = slot.split(":") if ":" in slot else (slot, "1")
                        name = item_id.replace("_", " ").title()
                        slots.append(f"{name} x{count}")
            if slots:
                lines.append(f"Recipe: {', '.join(slots)}")
        elif item.get("crafttext"):
            lines.append(f"Craft info: {item['crafttext']}")

        if item.get("museum"):
            lines.append("Museum: Yes")

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
