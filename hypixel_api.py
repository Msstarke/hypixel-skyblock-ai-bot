import aiohttp
import time
from typing import Optional

BAZAAR_URL = "https://api.hypixel.net/v2/skyblock/bazaar"
AUCTIONS_ENDED_URL = "https://api.hypixel.net/v2/skyblock/auctions_ended"
ITEMS_URL = "https://api.hypixel.net/v2/skyblock/items"

CACHE_TTL = 300  # 5 minutes


class HypixelAPI:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self._cache: dict = {}

    def _cache_valid(self, key: str) -> bool:
        entry = self._cache.get(key)
        return entry is not None and time.time() - entry["ts"] < CACHE_TTL

    async def _get(self, url: str, cache_key: str) -> Optional[dict]:
        if self._cache_valid(cache_key):
            return self._cache[cache_key]["data"]
        params = {"key": self.api_key} if self.api_key else {}
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
        """Search bazaar by partial item name. Returns up to 15 matches."""
        data = await self.get_bazaar()
        if not data:
            return []

        query_norm = query.upper().replace(" ", "_")
        products = data.get("products", {})
        matches = []

        for item_id, product in products.items():
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
        """Exact lookup by item ID."""
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

    async def get_all_bazaar_items(self) -> list[str]:
        """Return list of all bazaar item IDs."""
        data = await self.get_bazaar()
        if not data:
            return []
        return list(data.get("products", {}).keys())
