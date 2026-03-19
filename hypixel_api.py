import asyncio
import aiohttp
import time
from typing import Optional

BAZAAR_URL = "https://api.hypixel.net/v2/skyblock/bazaar"
AUCTIONS_ENDED_URL = "https://api.hypixel.net/v2/skyblock/auctions_ended"
ACTIVE_AUCTIONS_URL = "https://api.hypixel.net/v2/skyblock/auctions"
LOWEST_BIN_URL = "https://moulberry.codes/lowestbin.json"
COFLNET_PRICE_URL = "https://sky.coflnet.com/api/item/price/{item_id}/current"
COFLNET_HISTORY_URL = "https://sky.coflnet.com/api/item/price/{item_id}/history/day"
MOJANG_URL = "https://api.mojang.com/users/profiles/minecraft"
PROFILES_URL = "https://api.hypixel.net/v2/skyblock/profiles"
ITEMS_URL = "https://api.hypixel.net/resources/skyblock/items"  # no API key needed
ITEMS_CACHE_TTL = 3600  # 1 hour — items rarely change

CACHE_TTL = 300  # 5 minutes
PLAYER_CACHE_TTL = 120  # 2 minutes for player data
AH_CACHE_TTL = 120    # 2 minutes for AH data
ACTIVE_AH_CACHE_TTL = 900  # 15 minutes — bid-only item scan

# Search terms for bid-only items in the active AH (item_name substring matches)
# Used when no BIN or coflnet price is found
BID_ONLY_SEARCH_TERMS: dict[str, list[str]] = {
    "NECRONS_HELMET":      ["necron", "helmet"],
    "NECRONS_CHESTPLATE":  ["necron", "chestplate"],
    "NECRONS_LEGGINGS":    ["necron", "leggings"],
    "NECRONS_BOOTS":       ["necron", "boots"],
    "STORM_HELMET":        ["storm", "helmet"],
    "STORM_CHESTPLATE":    ["storm", "chestplate"],
    "STORM_LEGGINGS":      ["storm", "leggings"],
    "STORM_BOOTS":         ["storm", "boots"],
    "MAXOR_HELMET":        ["maxor", "helmet"],
    "MAXOR_CHESTPLATE":    ["maxor", "chestplate"],
    "MAXOR_LEGGINGS":      ["maxor", "leggings"],
    "MAXOR_BOOTS":         ["maxor", "boots"],
    "GOLDOR_HELMET":       ["goldor", "helmet"],
    "GOLDOR_CHESTPLATE":   ["goldor", "chestplate"],
    "GOLDOR_LEGGINGS":     ["goldor", "leggings"],
    "GOLDOR_BOOTS":        ["goldor", "boots"],
}

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

    async def get_auction_averages(self) -> dict:
        """Stub — moulberry auction averages URLs are dead (404). Returns empty dict."""
        return {}

    async def get_reforge_stone_price(self, stone_id: str) -> float:
        """
        Fetch AH price for a reforge stone via coflnet.
        Reforge stones are regular AH items (not BIN), so they're not in lowestbin.
        Returns the buy price (what you'd pay), or 0 if not found.
        """
        cache_key = f"coflnet_{stone_id}"
        if self._cache_valid(cache_key, AH_CACHE_TTL):
            return self._cache[cache_key]["data"]
        url = COFLNET_PRICE_URL.format(item_id=stone_id)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        # coflnet returns buy/sell for bazaar items, lbin/median for AH items
                        price = (data.get("buy") or data.get("sell") or
                                 data.get("lbin") or data.get("median") or
                                 data.get("min") or 0)
                        self._cache[cache_key] = {"data": price, "ts": time.time()}
                        return price
        except Exception:
            pass
        return 0

    async def _coflnet_history_price(self, item_id: str) -> float:
        """
        Fetch the most recent sold price from CoflNet's 24h history endpoint.
        Useful for bid-only items where /current returns 0 but sales happened recently.
        """
        cache_key = f"coflnet_hist_{item_id}"
        if self._cache_valid(cache_key, AH_CACHE_TTL):
            return self._cache[cache_key]["data"]
        url = COFLNET_HISTORY_URL.format(item_id=item_id)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                    if resp.status == 200:
                        history = await resp.json()
                        if isinstance(history, list) and history:
                            # Most recent entry is last; pick avg of last 3 to smooth noise
                            recent = history[-3:]
                            prices = [e.get("avg") or e.get("median") or e.get("min") or 0
                                      for e in recent if e.get("avg") or e.get("median") or e.get("min")]
                            price = sum(prices) / len(prices) if prices else 0
                            self._cache[cache_key] = {"data": price, "ts": time.time()}
                            return price
        except Exception:
            pass
        self._cache[cache_key] = {"data": 0, "ts": time.time()}
        return 0

    def _derive_search_terms(self, item_id: str) -> list[str]:
        """
        Derive auction search terms from an item ID for bid-only auction scanning.
        e.g. NECRONS_CHESTPLATE → ["necron", "chestplate"]
             SHADOW_ASSASSIN_CHESTPLATE → ["shadow assassin", "chestplate"]
        """
        SLOT_TYPES = {"HELMET", "CHESTPLATE", "LEGGINGS", "BOOTS", "SWORD", "BOW",
                      "WAND", "GAUNTLET", "NECKLACE", "CLOAK", "BELT", "GLOVES"}
        parts = item_id.upper().split("_")
        # Find last slot-type word
        slot = None
        prefix_parts = parts
        for i in range(len(parts) - 1, -1, -1):
            if parts[i] in SLOT_TYPES:
                slot = parts[i].lower()
                prefix_parts = parts[:i]
                break
        if not prefix_parts:
            return []
        # Join prefix words, strip trailing 'S' on the last word (e.g. NECRONS → necron)
        name_words = [p.lower() for p in prefix_parts]
        if name_words and name_words[-1].endswith("s") and len(name_words[-1]) > 4:
            name_words[-1] = name_words[-1].rstrip("s")
        name_phrase = " ".join(name_words)
        terms = [name_phrase]
        if slot:
            terms.append(slot)
        return terms

    async def get_item_price(self, item_id: str) -> float:
        """
        Unified price lookup for any Skyblock item. Tries all sources in order:
        1. Lowest BIN (moulberry) — fastest, most common items
        2. CoflNet /current — covers non-BIN AH items, bid-only dungeon drops
        3. CoflNet /current with items-API ID remapping (e.g. ARMOR_OF_DIVAN → DIVAN)
        4. CoflNet 24h history — catches items with no current BIN but recent sales
        5. Dynamic bid auction scan — last resort, scans all active auctions live
        """
        # 1. Lowest BIN
        lbin = await self.get_lowest_bin()
        price = lbin.get(item_id, 0)
        if price:
            return price

        # 2. CoflNet /current with raw ID
        price = await self.get_reforge_stone_price(item_id)
        if price:
            return price

        # 3. CoflNet /current with remapped items-API ID
        mapped_id = self._ITEMS_API_ID_MAP.get(item_id)
        if mapped_id and mapped_id != item_id:
            price = await self.get_reforge_stone_price(mapped_id)
            if price:
                return price

        # 4. CoflNet 24h history (catches bid-only items that sold recently)
        price = await self._coflnet_history_price(item_id)
        if price:
            return price
        if mapped_id and mapped_id != item_id:
            price = await self._coflnet_history_price(mapped_id)
            if price:
                return price

        # 5. Bid auction scan — use hardcoded terms if known, else derive from ID
        terms = BID_ONLY_SEARCH_TERMS.get(item_id) or self._derive_search_terms(item_id)
        if terms:
            price = await self.scan_bid_auctions(terms)
        return price

    async def search_ah(self, query: str) -> list[dict]:
        """
        Search for an item across AH sources:
        1. Lowest BIN (active listings)
        2. Auction averages (covers dungeon/bid auction items)
        3. Recently ended auctions (last ~60s)
        Returns list of {source, item_id, price, name}
        """
        query_norm = query.upper().replace(" ", "_").replace("'", "")
        query_lower = query.lower().replace("'", "")
        results = []
        seen_ids: set = set()

        # 1. Lowest BIN prices
        lbin = await self.get_lowest_bin()
        lbin_matches = {k: v for k, v in lbin.items()
                        if query_norm in k or query_lower in k.lower().replace("_", " ")}
        for item_id, price in sorted(lbin_matches.items(), key=lambda x: x[1])[:5]:
            seen_ids.add(item_id)
            results.append({
                "source": "Lowest BIN",
                "item_id": item_id,
                "price": price,
                "name": item_id.replace("_", " ").title(),
            })

        # 2. Auction averages — catches dungeon items and bid-only auctions
        if len(results) < 3:
            avg = await self.get_auction_averages()
            avg_matches = {k: v for k, v in avg.items()
                           if (query_norm in k or query_lower in k.lower().replace("_", " "))
                           and k not in seen_ids}
            for item_id, price in sorted(avg_matches.items(), key=lambda x: x[1])[:3]:
                seen_ids.add(item_id)
                results.append({
                    "source": "AH average",
                    "item_id": item_id,
                    "price": price,
                    "name": item_id.replace("_", " ").title(),
                })

        # 3. Recently ended auctions (last ~60s from Hypixel API)
        # Use spaced version too: "storm_chestplate" → "storm chestplate" to match item names
        query_spaced = query_lower.replace("_", " ")
        ended = await self.get_auctions_ended()
        if ended:
            auctions = ended.get("auctions", [])
            matches = [
                a for a in auctions
                if query_spaced in a.get("item_name", "").lower() or
                   query_lower in a.get("item_name", "").lower() or
                   query_norm in a.get("item_lore", "")
            ]
            if matches:
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

        # 4. Coflnet fallback — catches AH items not in lowestbin (gems, stones, etc.)
        if not results:
            price = await self.get_reforge_stone_price(query_norm)
            if price:
                results.append({
                    "source": "AH (coflnet)",
                    "item_id": query_norm,
                    "price": price,
                    "name": query_norm.replace("_", " ").title(),
                })

        return results[:6]

    # Map from AH item IDs (used for price lookups) to the Hypixel items API IDs
    # (some items like Armor of Divan use different IDs in each system)
    _ITEMS_API_ID_MAP = {
        "ARMOR_OF_DIVAN_HELMET":      "DIVAN_HELMET",
        "ARMOR_OF_DIVAN_CHESTPLATE":  "DIVAN_CHESTPLATE",
        "ARMOR_OF_DIVAN_LEGGINGS":    "DIVAN_LEGGINGS",
        "ARMOR_OF_DIVAN_BOOTS":       "DIVAN_BOOTS",
    }

    async def get_item_gem_slots(self, item_id: str) -> list[dict]:
        """
        Fetch full gemstone slot data for an item from the Hypixel items API.
        Returns list of slot dicts: [{slot_type, costs: [{type, item_id/coins, amount}]}]
        slot_type may be a specific gem type (AMBER, JADE) or UNIVERSAL/COMBAT/etc.
        """
        api_id = self._ITEMS_API_ID_MAP.get(item_id, item_id)
        items_data = await self.get_all_items()
        item = items_data.get(api_id, {})
        return item.get("gemstone_slots", [])

    async def scan_bid_auctions(self, search_terms: list[str]) -> float:
        """
        Scan ALL active Hypixel auction pages in parallel to find bid-only auctions
        matching the given keywords (checked against item_name, case-insensitive).
        Returns the median highest_bid_amount of matched auctions, or 0 if none found.
        Cached for 15 minutes to avoid repeated expensive scans.
        """
        cache_key = "bid_scan_" + "_".join(sorted(search_terms))
        cached = self._cache.get(cache_key)
        if cached and time.time() - cached["ts"] < ACTIVE_AH_CACHE_TTL:
            return cached["price"]

        terms = [t.lower() for t in search_terms]
        all_auctions: list[dict] = []

        try:
            timeout = aiohttp.ClientTimeout(total=15)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                # Page 0 first to get totalPages
                async with session.get(f"{ACTIVE_AUCTIONS_URL}?page=0") as r:
                    page0 = await r.json()
                total_pages = min(page0.get("totalPages", 1), 60)
                all_auctions.extend(page0.get("auctions", []))

                # Fetch remaining pages in parallel
                async def fetch_page(p: int) -> list[dict]:
                    try:
                        async with session.get(f"{ACTIVE_AUCTIONS_URL}?page={p}") as r:
                            d = await r.json()
                            return d.get("auctions", [])
                    except Exception:
                        return []

                pages_data = await asyncio.gather(*[fetch_page(p) for p in range(1, total_pages)])
                for page_auctions in pages_data:
                    all_auctions.extend(page_auctions)
        except Exception:
            self._cache[cache_key] = {"ts": time.time(), "price": 0}
            return 0

        # Find non-BIN auctions that have at least one bid and match all terms
        matches = [
            a for a in all_auctions
            if not a.get("bin", False)
            and a.get("highest_bid_amount", 0) > 0
            and all(t in a.get("item_name", "").lower() for t in terms)
        ]

        if not matches:
            self._cache[cache_key] = {"ts": time.time(), "price": 0}
            return 0

        prices = sorted(a["highest_bid_amount"] for a in matches)
        median = prices[len(prices) // 2]
        self._cache[cache_key] = {"ts": time.time(), "price": median}
        return median

    async def _price_unlock_costs(self, slots: list[dict], baz: dict) -> tuple[float, list[str]]:
        """
        Calculate total cost to unlock all gem slots.
        Returns (total_coins, list_of_detail_strings).
        Items not on Bazaar are fetched from coflnet.
        """
        def baz_price(bid: str) -> float:
            p = baz.get("products", {}).get(bid, {})
            return p.get("quick_status", {}).get("buyPrice", 0)

        total = 0.0
        details = []
        # Track items needed across all slots
        coin_costs: float = 0.0
        item_costs: dict[str, int] = {}  # item_id -> total count needed

        for slot in slots:
            for cost in slot.get("costs", []):
                if cost.get("type") == "COINS":
                    coin_costs += cost.get("coins", 0)
                elif cost.get("type") == "ITEM":
                    iid = cost["item_id"]
                    amt = cost.get("amount", 1)
                    item_costs[iid] = item_costs.get(iid, 0) + amt

        if coin_costs:
            total += coin_costs
            details.append(f"coins: {coin_costs:,.0f}")

        for iid, count in item_costs.items():
            price = baz_price(iid)
            if not price:
                price = await self.get_reforge_stone_price(iid)  # coflnet fallback
            cost_total = price * count
            total += cost_total
            name = iid.replace("_", " ").title()
            details.append(f"{name} ×{count}: {cost_total:,.0f}")

        return total, details

    async def get_hypermaxed_price(self, item_id: str, reforge_stone_id: str = None) -> dict | None:
        """
        Calculate total cost of a hypermaxed item using live prices:
        - Base item (lowest BIN from AH)
        - 10x Hot Potato Books
        - 5x Fuming Potato Books
        - 1x Recombobulator 3000
        - 1x Art of Peace
        - Gemstone slot unlock costs (coins + required items per slot)
        - Perfect gemstones for each slot
        - Reforge stone (optional)
        Returns itemised cost dict.
        """
        lbin, avg, baz, raw_slots = await asyncio.gather(
            self.get_lowest_bin(),
            self.get_auction_averages(),
            self.get_bazaar(),
            self.get_item_gem_slots(item_id),
        )
        if not baz:
            return None

        def baz_price(bid: str) -> float:
            p = baz.get("products", {}).get(bid, {})
            return p.get("quick_status", {}).get("buyPrice", 0)

        # Base item — unified price lookup (lbin → coflnet → history → bid scan)
        base = await self.get_item_price(item_id)

        hpb_price  = baz_price("HOT_POTATO_BOOK")
        fhpb_price = baz_price("FUMING_POTATO_BOOK")
        recomb     = baz_price("RECOMBOBULATOR_3000")
        aop        = baz_price("ART_OF_PEACE")

        breakdown = {
            "base_item":           {"qty": 1,  "unit": base,       "total": base},
            "hot_potato_books":    {"qty": 10, "unit": hpb_price,  "total": hpb_price * 10},
            "fuming_potato_books": {"qty": 5,  "unit": fhpb_price, "total": fhpb_price * 5},
            "recombobulator_3000": {"qty": 1,  "unit": recomb,     "total": recomb},
            "art_of_peace":        {"qty": 1,  "unit": aop,        "total": aop},
        }

        # ── Gemstone slot unlock costs ────────────────────────────────────────
        # Slots with no costs list (or empty costs) are free to unlock
        locked_slots = [s for s in raw_slots if s.get("costs")]
        free_slots   = [s for s in raw_slots if not s.get("costs")]

        if locked_slots:
            unlock_total, unlock_details = await self._price_unlock_costs(locked_slots, baz)
            if unlock_total > 0:
                breakdown["slot_unlocking"] = {
                    "qty":     len(locked_slots),
                    "unit":    unlock_total / len(locked_slots),
                    "total":   unlock_total,
                    "details": unlock_details,  # extra info for display
                }

        # ── Perfect gem costs ─────────────────────────────────────────────────
        # Count typed gem slots (skip UNIVERSAL/COMBAT/etc which need a decision)
        GENERIC_TYPES = {"UNIVERSAL", "COMBAT", "DEFENSIVE", "MINING", "SPEED"}
        gem_counts: dict[str, int] = {}
        for slot in raw_slots:
            t = slot.get("slot_type", "")
            if t and t not in GENERIC_TYPES:
                gem_counts[t] = gem_counts.get(t, 0) + 1

        for gem_type, count in gem_counts.items():
            gem_id = f"PERFECT_{gem_type}_GEM"
            price = baz_price(gem_id)
            if price > 0:
                breakdown[f"perfect_{gem_type.lower()}_gems"] = {
                    "qty": count, "unit": price, "total": price * count
                }

        # ── Reforge stone ─────────────────────────────────────────────────────
        if reforge_stone_id:
            stone_price = await self.get_reforge_stone_price(reforge_stone_id)
            breakdown["reforge_stone"] = {"qty": 1, "unit": stone_price, "total": stone_price}

        total = sum(v["total"] for v in breakdown.values())
        return {
            "item_id":    item_id,
            "gem_counts": gem_counts,
            "free_slots": len(free_slots),
            "breakdown":  breakdown,
            "total":      total,
        }

    async def get_armor_set_prices(self, set_id_prefix: str) -> dict | None:
        """
        Fetch lowest BIN price for each piece of an armor set.
        set_id_prefix: e.g. 'ARMOR_OF_DIVAN', 'GLACITE', 'MINERAL'
        Returns {helmet, chestplate, leggings, boots, total} or None.
        """
        lbin = await self.get_lowest_bin()
        slots = {
            "helmet":     [f"{set_id_prefix}_HELMET"],
            "chestplate": [f"{set_id_prefix}_CHESTPLATE"],
            "leggings":   [f"{set_id_prefix}_LEGGINGS"],
            "boots":      [f"{set_id_prefix}_BOOTS"],
        }
        result = {}
        for slot, ids in slots.items():
            for item_id in ids:
                if item_id in lbin:
                    result[slot] = {"id": item_id, "price": lbin[item_id]}
                    break
        if not result:
            return None
        result["total"] = sum(v["price"] for v in result.values())
        return result

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

        # Recipe — Hypixel items API does NOT provide recipe data. Flag it so the AI doesn't guess.
        lines.append("Recipe: NOT AVAILABLE in items API — do not guess the recipe")

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
