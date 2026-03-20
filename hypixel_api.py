import asyncio
import aiohttp
import json
import time
from pathlib import Path
from typing import Optional

BAZAAR_URL = "https://api.hypixel.net/v2/skyblock/bazaar"
AUCTIONS_ENDED_URL = "https://api.hypixel.net/v2/skyblock/auctions_ended"
ACTIVE_AUCTIONS_URL = "https://api.hypixel.net/v2/skyblock/auctions"
LOWEST_BIN_URL = "https://moulberry.codes/lowestbin.json"
SKYHELPER_PRICES_URL = "https://raw.githubusercontent.com/SkyHelperBot/Prices/main/pricesV2.json"
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


# Reforge name → reforge stone item ID (from SkyHelper-Networth-Go)
_REFORGE_TO_STONE: dict[str, str] = {
    "STIFF": "HARDENED_WOOD", "TRASHY": "OVERFLOWING_TRASH_CAN", "SALTY": "SALT_CUBE",
    "AOTE_STONE": "AOTE_STONE", "BLAZING": "BLAZEN_SPHERE", "WAXED": "BLAZE_WAX",
    "ROOTED": "BURROWING_SPORES", "CALCIFIED": "CALCIFIED_HEART", "CANDIED": "CANDY_CORN",
    "PERFECT": "DIAMOND_ATOM", "FLEET": "DIAMONITE", "FABLED": "DRAGON_CLAW",
    "SPIKED": "DRAGON_SCALE", "ROYAL": "DWARVEN_TREASURE", "HYPER": "ENDSTONE_GEODE",
    "COLDFUSION": "ENTROPY_SUPPRESSOR", "BLOOMING": "FLOWERING_BOUQUET",
    "FANGED": "FULL_JAW_FANGING_KIT", "JADED": "JADERALD", "JERRY": "JERRY_STONE",
    "MAGNETIC": "LAPIS_CRYSTAL", "EARTHY": "LARGE_WALNUT", "GROOVY": "MANGROVE_GEM",
    "FORTIFIED": "METEOR_SHARD", "GILDED": "MIDAS_JEWEL", "MOONGLADE": "MOONGLADE_JEWEL",
    "CUBIC": "MOLTEN_CUBE", "NECROTIC": "NECROMANCER_BROOCH", "FRUITFUL": "ONYX",
    "PRECISE": "OPTICAL_LENS", "MOSSY": "OVERGROWN_GRASS", "PITCHIN": "PITCHIN_KOI",
    "UNDEAD": "PREMIUM_FLESH", "BLOOD_SOAKED": "PRESUMED_GALLON_OF_RED_PAINT",
    "MITHRAIC": "PURE_MITHRIL", "REINFORCED": "RARE_DIAMOND", "RIDICULOUS": "RED_NOSE",
    "LOVING": "RED_SCARF", "AUSPICIOUS": "ROCK_GEMSTONE", "TREACHEROUS": "RUSTY_ANCHOR",
    "HEADSTRONG": "SALMON_OPAL", "STRENGTHENED": "SEARING_STONE", "GLISTENING": "SHINY_PRISM",
    "BUSTLING": "SKYMART_BROCHURE", "SPIRITUAL": "SPIRIT_DECOY", "SQUEAKY": "SQUEAKY_TOY",
    "SUSPICIOUS": "SUSPICIOUS_VIAL", "SNOWY": "TERRY_SNOWGLOBE",
    "DIMENSIONAL": "TITANIUM_TESSERACT", "AMBERED": "AMBER_MATERIAL", "BEADY": "BEADY_EYES",
    "BLESSED": "BLESSED_FRUIT", "BULKY": "BULKY_STONE", "BUZZING": "CLIPPED_WINGS",
    "SUBMERGED": "DEEP_SEA_ORB", "RENOWNED": "DRAGON_HORN", "FESTIVE": "FROZEN_BAUBLE",
    "GIANT": "GIANT_TOOTH", "LUSTROUS": "GLEAMING_CRYSTAL", "BOUNTIFUL": "GOLDEN_BALL",
    "CHOMP": "KUUDRA_MANDIBLE", "LUCKY": "LUCKY_DICE", "STELLAR": "PETRIFIED_STARFALL",
    "SCRAPED": "POCKET_ICEBERG", "ANCIENT": "PRECURSOR_GEAR", "REFINED": "REFINED_AMBER",
    "EMPOWERED": "SADAN_BROOCH", "WITHERED": "WITHER_BLOOD", "GLACIAL": "FRIGID_HUSK",
    "HEATED": "HOT_STUFF", "DIRTY": "DIRT_BOTTLE", "MOIL": "MOIL_LOG", "TOIL": "TOIL_LOG",
    "GREATER_SPOOK": "BOO_STONE", "WISE": "WISE_DRAGON_FRAGMENT",
}


class HypixelAPI:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self._cache: dict = {}
        self._recipes = self._load_recipes()

    def _load_recipes(self) -> dict:
        """Load pre-extracted recipe database from data/recipes.json."""
        path = Path(__file__).parent / "data" / "recipes.json"
        if path.exists():
            try:
                with open(path) as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def get_recipe(self, item_id: str) -> dict | None:
        """Get recipe for an item. Returns {'i': {mat_id: count, ...}, 'c': output_count} or None."""
        return self._recipes.get(item_id)

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
                    data = await resp.json(content_type=None)
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

    async def get_skyhelper_prices(self) -> dict:
        """Fetch SkyHelper prices (13k+ items incl enchantments, reforges, pets)."""
        # Use params={} to avoid appending the Hypixel API key to a GitHub URL
        if self._cache_valid("skyhelper_prices", CACHE_TTL):
            return self._cache["skyhelper_prices"]["data"]
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(SKYHELPER_PRICES_URL, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status == 200:
                        data = await resp.json(content_type=None)
                        self._cache["skyhelper_prices"] = {"data": data, "ts": time.time()}
                        return data
        except Exception:
            pass
        return {}

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

    @staticmethod
    def _item_id_variants(item_id: str) -> list[str]:
        """
        Generate lookup variants for an item ID to handle apostrophe differences.
        Some items appear in lowestbin/coflnet with 'S_ instead of S_:
        NECRONS_CHESTPLATE → also try NECRON'S_CHESTPLATE
        STORMS_CHESTPLATE  → also try STORM'S_CHESTPLATE
        """
        import re as _re
        variants = [item_id]
        # Insert apostrophe before trailing S on each word segment: NECRONS_ → NECRON'S_
        apos = _re.sub(r"([A-Z]+)S_", r"\1'S_", item_id)
        if apos != item_id:
            variants.append(apos)
        # Also try without apostrophe (strip any existing apostrophes)
        stripped = item_id.replace("'", "")
        if stripped != item_id and stripped not in variants:
            variants.append(stripped)
        return variants

    async def get_item_price(self, item_id: str, allow_auction: bool = False) -> tuple[float, str] | float:
        """
        Price lookup for an item. Returns price (float) by default.
        If allow_auction=True, returns (price, source_tag) where source_tag is
        "bin" or "auction" so callers can label the price correctly.

        Lookup chain:
        1. Lowest BIN (moulberry lowestbin.json)
        2. CoflNet lbin field
        3. (if allow_auction) CoflNet median field — covers bid-only AH items
        """
        lbin = await self.get_lowest_bin()

        # 1. Moulberry lowest BIN — try all ID variants
        mapped_id = self._ITEMS_API_ID_MAP.get(item_id)
        all_ids = list(dict.fromkeys(
            self._item_id_variants(item_id)
            + (self._item_id_variants(mapped_id) if mapped_id and mapped_id != item_id else [])
        ))
        for vid in all_ids:
            price = lbin.get(vid, 0)
            if price:
                return (price, "bin") if allow_auction else price

        # 2. CoflNet lbin field — actual BIN price
        coflnet_median = 0
        for vid in all_ids:
            try:
                url = COFLNET_PRICE_URL.format(item_id=vid)
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            p = data.get("lbin") or 0
                            if p:
                                return (p, "bin") if allow_auction else p
                            # Stash median for fallback
                            if not coflnet_median:
                                coflnet_median = data.get("median") or data.get("sell") or 0
            except Exception:
                pass

        # 3. CoflNet median — bid-only auction price (only if caller opted in)
        if allow_auction and coflnet_median:
            return (coflnet_median, "auction")

        return (0, "none") if allow_auction else 0

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

    async def get_item_star_costs(self, item_id: str) -> dict | None:
        """
        Fetch star upgrade costs for a dungeon item from the Hypixel items API.
        Returns {essence_type, essence_amounts: [star1..star5], is_dungeon: bool} or None.
        """
        items_data = await self.get_all_items()
        api_id = self._ITEMS_API_ID_MAP.get(item_id, item_id)
        item = items_data.get(api_id) or items_data.get(item_id) or {}

        if not item.get("dungeon_item") or not item.get("upgrade_costs"):
            return None

        upgrade_costs = item["upgrade_costs"]
        # Each star level is a list of cost dicts; we sum essence amounts
        essence_type = None
        essence_amounts = []
        for star_costs in upgrade_costs:
            star_essence = 0
            for cost in star_costs:
                if cost.get("type") == "ESSENCE":
                    essence_type = cost.get("essence_type", essence_type)
                    star_essence += cost.get("amount", 0)
            essence_amounts.append(star_essence)

        if not essence_type:
            return None

        return {
            "essence_type": essence_type,
            "essence_amounts": essence_amounts,  # [star1, star2, star3, star4, star5]
            "is_dungeon": True,
        }

    # Master star item IDs in order (1st through 5th)
    MASTER_STAR_IDS = [
        "FIRST_MASTER_STAR",
        "SECOND_MASTER_STAR",
        "THIRD_MASTER_STAR",
        "FOURTH_MASTER_STAR",
        "FIFTH_MASTER_STAR",
    ]

    async def get_item_gem_slots(self, item_id: str) -> list[dict]:
        """
        Fetch full gemstone slot data for an item from the Hypixel items API.
        Returns list of slot dicts: [{slot_type, costs: [{type, item_id/coins, amount}]}]
        slot_type may be a specific gem type (AMBER, JADE) or UNIVERSAL/COMBAT/etc.
        Tries: explicit ID map → raw ID → strip known prefixes (ARMOR_OF_, etc.)
        """
        items_data = await self.get_all_items()

        # 1. Explicit map (e.g. ARMOR_OF_DIVAN_HELMET → DIVAN_HELMET)
        api_id = self._ITEMS_API_ID_MAP.get(item_id, item_id)
        item = items_data.get(api_id, {})
        if item.get("gemstone_slots"):
            return item["gemstone_slots"]

        # 2. Raw ID
        item = items_data.get(item_id, {})
        if item.get("gemstone_slots"):
            return item["gemstone_slots"]

        # 3. Strip known AH-only prefixes (e.g. ARMOR_OF_ prefix on some items)
        for prefix in ("ARMOR_OF_", "NECRONS_"):
            if item_id.startswith(prefix):
                stripped = item_id[len(prefix):]
                item = items_data.get(stripped, {})
                if item.get("gemstone_slots"):
                    return item["gemstone_slots"]

        return []

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

        # Find non-BIN auctions matching all terms with a meaningful bid (> 10k to filter trolls)
        matches = [
            a for a in all_auctions
            if not a.get("bin", False)
            and a.get("highest_bid_amount", 0) > 10_000
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
                price = await self.get_item_price(iid)  # full fallback chain
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
        - Enchantments (based on item type and use case)
        - Reforge stone (optional)
        Returns itemised cost dict.
        """
        from enchants import pick_enchants
        baz, raw_slots, star_info = await asyncio.gather(
            self.get_bazaar(),
            self.get_item_gem_slots(item_id),
            self.get_item_star_costs(item_id),
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

        # ── Stars (essence) ──────────────────────────────────────────────────
        if star_info:
            essence_type = star_info["essence_type"]
            essence_amounts = star_info["essence_amounts"]  # [star1..star5]
            total_essence = sum(essence_amounts)
            essence_baz_id = f"ESSENCE_{essence_type}"
            essence_unit = baz_price(essence_baz_id)
            essence_cost = essence_unit * total_essence
            breakdown["essence_stars"] = {
                "qty": total_essence,
                "unit": essence_unit,
                "total": essence_cost,
                "essence_type": essence_type,
                "per_star": essence_amounts,
            }

            # Master stars (5 items, each applied once)
            ms_total = 0
            ms_prices = []
            for ms_id in self.MASTER_STAR_IDS:
                # Master stars are bid-only AH items — use allow_auction
                p, src = await self.get_item_price(ms_id, allow_auction=True)
                ms_prices.append(p)
                ms_total += p
            if ms_total > 0:
                breakdown["master_stars"] = {
                    "qty": 5,
                    "unit": ms_total / 5,
                    "total": ms_total,
                    "prices": ms_prices,  # individual prices for display
                }

        # ── Enchantments ─────────────────────────────────────────────────────
        enchant_list = pick_enchants(item_id)
        if enchant_list:
            enchant_total = 0
            enchant_details = []
            for e in enchant_list:
                price = baz_price(e["bazaar_id"])
                # Some enchants (Chimera etc) aren't on bazaar — try AH
                if price <= 0:
                    p, _src = await self.get_item_price(e["bazaar_id"], allow_auction=True)
                    price = p
                if price > 0:
                    enchant_total += price
                    ult_tag = " (ULT)" if e.get("ultimate") else ""
                    enchant_details.append(f"{e['name']}{ult_tag}: {price:,.0f}")
            if enchant_total > 0:
                breakdown["enchantments"] = {
                    "qty": len(enchant_details),
                    "unit": enchant_total / len(enchant_details),
                    "total": enchant_total,
                    "details": enchant_details,
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
        Fetch price for each piece of an armor set using the full fallback chain
        (lowestbin → coflnet → history → bid auction scan).
        set_id_prefix: e.g. 'ARMOR_OF_DIVAN', 'GLACITE', 'NECRONS'
        Returns {helmet, chestplate, leggings, boots, total} or None.
        """
        piece_ids = {
            "helmet":     f"{set_id_prefix}_HELMET",
            "chestplate": f"{set_id_prefix}_CHESTPLATE",
            "leggings":   f"{set_id_prefix}_LEGGINGS",
            "boots":      f"{set_id_prefix}_BOOTS",
        }
        price_results = await asyncio.gather(*[
            self.get_item_price(pid, allow_auction=True) for pid in piece_ids.values()
        ])
        result = {}
        has_auction = False
        for (slot, item_id), (price, source) in zip(piece_ids.items(), price_results):
            if price:
                result[slot] = {"id": item_id, "price": price, "source": source}
                if source == "auction":
                    has_auction = True
        if not result:
            return None
        result["total"] = sum(v["price"] for v in result.values() if isinstance(v, dict))
        result["has_auction"] = has_auction
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

        # 5. Word-based match — all query words appear somewhere in item name
        # Handles "titanium drill 655" matching "Titanium Drill DR-X655"
        import re as _re
        q_words = _re.findall(r'[a-z0-9]+', query_lower)
        if len(q_words) >= 2:
            best = None
            best_len = 999
            for item in items.values():
                name = item.get("name", "").lower()
                # Check each query word is found somewhere in the name string
                if all(w in name for w in q_words) and len(name) < best_len:
                    best = item
                    best_len = len(name)
            if best:
                return best

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

        # Recipe from local database
        recipe = self.get_recipe(item["id"])
        if recipe:
            recipe_parts = []
            for mat_id, count in recipe["i"].items():
                name = mat_id.replace("_", " ").title()
                recipe_parts.append(f"{count}x {name}")
            rtype = recipe.get("t", "craft")
            if rtype == "forge":
                dur = recipe.get("d", 0)
                dur_str = f" ({dur // 3600}h)" if dur else ""
                lines.append(f"Recipe (Forge{dur_str}): {', '.join(recipe_parts)}")
            else:
                lines.append(f"Recipe: {', '.join(recipe_parts)}")

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

        # Inject profile-level bank balance into member data for parsing
        bank_balance = active.get("banking", {}).get("balance", 0)
        member["_bank_balance"] = bank_balance

        stats = parse_member(member)

        # Calculate networth
        try:
            networth = await self.calculate_networth(stats)
            stats["networth"] = networth
        except Exception:
            stats["networth"] = None

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

    async def calculate_networth(self, stats: dict) -> dict:
        """
        Calculate networth using SkyHelper prices (same source as SkyCrypt).
        Accounts for base item price + enchantments, reforges, recombobulator,
        hot potato books, stars, drill parts, art of war, wood singularity, etherwarp.
        """
        prices = await self.get_skyhelper_prices()
        if not prices:
            # Fallback to lowestbin + bazaar
            lbin = await self.get_lowest_bin()
            baz = await self.get_bazaar()
            prices = dict(lbin)
            for k, v in baz.items():
                if k not in prices:
                    prices[k] = v.get("buy", 0)

        # Application worth multipliers (match SkyHelper-Networth-Go)
        APP_WORTH = {
            "enchantments": 0.85,
            "reforge": 0.55,
            "recombobulator": 1.0,
            "hot_potato_book": 1.0,
            "fuming_potato_book": 1.0,
            "stars": 0.8,
            "drill_part": 1.0,
            "art_of_war": 1.0,
            "wood_singularity": 1.0,
            "etherwarp": 1.0,
            "silex": 0.8,
        }

        # Essence cost per star tier (cumulative essence for upgrade_level)
        # Varies by item type but we use the essence price directly
        ESSENCE_PER_STAR = [0, 10, 20, 40, 80, 160]  # Stars 1-5
        MASTER_STAR_ITEMS = [
            "FIRST_MASTER_STAR", "SECOND_MASTER_STAR", "THIRD_MASTER_STAR",
            "FOURTH_MASTER_STAR", "FIFTH_MASTER_STAR",
        ]

        STACKING_ENCHANTS = {
            "CHAMPION", "CULTIVATING", "COMPACT", "EXPERTISE", "HECATOMB",
            "TOXOPHILITE", "COUNTER_STRIKE",
        }

        def price_of(item_id: str) -> float:
            return prices.get(item_id, 0)

        def price_item_full(item: dict) -> float:
            """Price a single item including all modifiers."""
            item_id = item.get("id", "")
            if not item_id:
                return 0
            count = item.get("count", 1)

            # Check for skinned variant
            skin = item.get("skin", "")
            if skin:
                skinned_id = f"{item_id}_SKINNED_{skin}"
                if price_of(skinned_id) > price_of(item_id):
                    item_id = skinned_id

            # Starred dungeon items
            if item_id.startswith("STARRED_") and price_of(item_id) == 0:
                base_id = item_id.replace("STARRED_", "", 1)
                if price_of(base_id) > 0:
                    item_id = base_id

            base = price_of(item_id) * count
            modifier_value = 0

            # Enchantments
            for ench_name, ench_level in item.get("enchantments", {}).items():
                upper = ench_name.upper()
                if upper in STACKING_ENCHANTS:
                    ench_level = 1
                ench_key = f"ENCHANTMENT_{upper}_{ench_level}"
                ep = price_of(ench_key)
                if ep > 0:
                    modifier_value += ep * APP_WORTH["enchantments"]
                # Silex (efficiency above 5)
                if upper == "EFFICIENCY" and ench_level > 5:
                    silex_count = ench_level - 5
                    modifier_value += price_of("SIL_EX") * silex_count * APP_WORTH["silex"]

            # Reforge
            reforge = item.get("reforge", "")
            if reforge:
                stone_id = _REFORGE_TO_STONE.get(reforge.upper(), "")
                if stone_id:
                    modifier_value += price_of(stone_id) * APP_WORTH["reforge"]

            # Recombobulator
            if item.get("recombobulated"):
                modifier_value += price_of("RECOMBOBULATOR_3000") * APP_WORTH["recombobulator"]

            # Hot potato books
            hpb = item.get("hot_potato_count", 0)
            if hpb > 0:
                normal = min(hpb, 10)
                fuming = max(0, hpb - 10)
                modifier_value += price_of("HOT_POTATO_BOOK") * normal * APP_WORTH["hot_potato_book"]
                modifier_value += price_of("FUMING_POTATO_BOOK") * fuming * APP_WORTH["fuming_potato_book"]

            # Stars (essence stars 1-5 + master stars 6-10)
            stars = item.get("stars", 0)
            if stars > 0:
                # Master stars (6-10)
                master = max(0, stars - 5)
                for i in range(min(master, 5)):
                    modifier_value += price_of(MASTER_STAR_ITEMS[i]) * APP_WORTH["stars"]

            # Drill parts
            for part_key in ("drill_part_fuel_tank", "drill_part_engine", "drill_part_upgrade_module"):
                part_id = item.get(part_key, "")
                if part_id:
                    modifier_value += price_of(part_id) * APP_WORTH["drill_part"]

            # Art of War
            if item.get("art_of_war"):
                modifier_value += price_of("THE_ART_OF_WAR") * APP_WORTH["art_of_war"]

            # Wood Singularity
            if item.get("wood_singularity"):
                modifier_value += price_of("WOOD_SINGULARITY") * APP_WORTH["wood_singularity"]

            # Etherwarp
            if item.get("etherwarp"):
                modifier_value += price_of("ETHERWARP_CONDUIT") * APP_WORTH["etherwarp"]
                modifier_value += price_of("ETHERWARP_MERGER") * APP_WORTH["etherwarp"]

            # Gemstones
            gems = item.get("gems", {})
            if gems:
                # Gem slots: JADE_0, JADE_1, AMBER_0, etc.
                # Value is the quality (PERFECT, FLAWLESS, etc.)
                # Also handle _gem suffix keys for universal slots
                GEMSTONE_TYPES = {"JADE", "AMBER", "TOPAZ", "SAPPHIRE", "AMETHYST",
                                  "RUBY", "JASPER", "OPAL", "AQUAMARINE", "CITRINE",
                                  "ONYX", "PERIDOT"}
                for gem_key, gem_val in gems.items():
                    if gem_key == "unlocked_slots" or gem_key.endswith("_gem"):
                        continue
                    # Determine gem type and quality
                    quality = gem_val if isinstance(gem_val, str) else ""
                    if not quality or quality.startswith("[") or quality.startswith("{"):
                        continue
                    # Extract gem type from key (e.g., JADE_0 -> JADE)
                    parts = gem_key.rsplit("_", 1)
                    slot_type = parts[0] if len(parts) == 2 and parts[1].isdigit() else gem_key
                    # For universal slots, check the _gem key
                    if slot_type.upper() not in GEMSTONE_TYPES:
                        gem_type = gems.get(f"{gem_key}_gem", slot_type)
                    else:
                        gem_type = slot_type
                    gem_id = f"{quality.upper()}_{gem_type.upper()}_GEM"
                    gp = price_of(gem_id)
                    if gp > 0:
                        modifier_value += gp * 0.9  # gemstone application worth

            return base + modifier_value

        def price_items(items: list[dict]) -> tuple[float, list[tuple[str, float]]]:
            total = 0
            breakdown = []
            for item in items:
                p = price_item_full(item)
                if p > 0:
                    total += p
                    breakdown.append((item.get("name", item.get("id", "?")), p))
            return total, breakdown

        # Price all item categories (same as SkyCrypt)
        all_bd = []
        categories = {}
        for cat in ("armor", "equipment", "inventory", "wardrobe", "ender_chest",
                     "personal_vault", "accessories", "fishing_bag", "potion_bag",
                     "sacks_bag", "quiver", "storage"):
            val, bd = price_items(stats.get(cat, []))
            categories[cat] = val
            all_bd.extend(bd)

        # Pet values — SkyHelper format: LVL_100_<TIER>_<TYPE>
        # Interpolate based on XP between LVL_1 and LVL_100 prices
        pet_total = 0
        for pet in stats.get("pets", []):
            ptype = pet.get("type", "").upper()
            ptier = pet.get("tier", "").upper()
            pet_xp = pet.get("xp", 0)
            base_id = f"{ptier}_{ptype}"
            p1 = price_of(f"LVL_1_{base_id}")
            p100 = price_of(f"LVL_100_{base_id}")
            p200 = price_of(f"LVL_200_{base_id}")
            # Estimate pet level from XP using our _pet_level helper
            from player_stats import _pet_level, PET_XP_LEGENDARY
            est_level = _pet_level(pet_xp, ptier)
            if p200 and est_level >= 100:
                # Golden dragon / special 200-level pets
                p = p100 + (p200 - p100) * min((est_level - 100), 100) / 100
            elif p100 and p1 and est_level < 100:
                # Linear interpolation: fraction of XP toward max
                # XP-to-max varies by tier but approximate with level ratio
                frac = max(0, min(1, (est_level - 1) / 99))
                p = p1 + (p100 - p1) * frac
            elif p100:
                p = p100
            elif p1:
                p = p1
            else:
                p = 0
            # Held item value
            held = pet.get("held_item", "")
            held_p = price_of(held) if held else 0
            val = p + held_p
            if val > 0:
                pet_total += val
                name = f"{ptype.title()} ({ptier[0] if ptier else '?'})"
                all_bd.append((name, val))
        categories["pets"] = pet_total

        # Sacks (raw materials)
        sack_total = 0
        for item_id, count in stats.get("sacks", {}).items():
            p = price_of(item_id)
            if p > 0:
                sack_total += p * count
        categories["sacks"] = sack_total

        # Essence
        essence_total = 0
        for etype, count in stats.get("essence_counts", {}).items():
            if count > 0:
                p = price_of(f"ESSENCE_{etype}")
                if p > 0:
                    essence_total += p * count
        categories["essence"] = essence_total

        purse = stats.get("purse", 0)
        bank = stats.get("bank", 0)

        items_total = sum(categories.values())
        total = purse + bank + items_total

        return {
            "total": total,
            "purse": purse,
            "bank": bank,
            "items_total": items_total,
            "categories": {k: v for k, v in categories.items() if v > 0},
            "top_items": sorted(all_bd, key=lambda x: x[1], reverse=True)[:10],
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
