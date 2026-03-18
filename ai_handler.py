import os
import re
import asyncio
from groq import AsyncGroq
from hypixel_api import HypixelAPI, HOTM_XP
from knowledge_base import KnowledgeBase
from reforges import pick_reforge, normalize_stat, STAT_ALIASES

PRICE_KEYWORDS = [
    "cost", "price", "worth", "buy", "sell", "bazaar", "coins",
    "how much", "profit", "flip", "instabuy", "instasell",
    "cheapest", "cheap", "expensive", "auction", " ah ", "on ah",
    "lowest", "highest", "median", "average",
]

MAX_DISCORD_LEN = 1900

# Matches patterns like "24 enchanted melon", "x655 diamond", "655x enchanted diamond"
QTY_PATTERN = re.compile(
    r"\bx?(\d+)x?\s+([a-z][a-z\s]{2,40}?)(?:\s*\?|$|,|\band\b)",
    re.IGNORECASE
)


class AIHandler:
    def __init__(self):
        self.client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))
        self.model = "openai/gpt-oss-120b"
        self.hypixel = HypixelAPI(os.getenv("HYPIXEL_API_KEY", ""))
        self.knowledge = KnowledgeBase()
        self.semaphore = asyncio.Semaphore(5)
        self.tracker = None

    def _extract_cata_level(self, question: str) -> int | None:
        """Extract stated Catacombs level from e.g. 'cata 0', 'cata level 5', 'im cata 12'."""
        m = re.search(r'cata(?:combs)?\s*(?:level\s*)?(\d+)', question, re.IGNORECASE)
        return int(m.group(1)) if m else None

    def _extract_username(self, question: str) -> str | None:
        """Extract a Minecraft username only from explicit patterns like 'my account is X', 'ign X'."""
        patterns = [
            r"(?:my\s+)?(?:account|ign|username)\s+(?:is\s+)?([A-Za-z0-9_]{3,16})",
            r"\bcheck\s+(?:player\s+)?([A-Za-z0-9_]{3,16})\b",
            r"\bfor\s+player\s+([A-Za-z0-9_]{3,16})\b",
        ]
        for pat in patterns:
            m = re.search(pat, question, re.IGNORECASE)
            if m:
                return m.group(1)
        return None

    def _extract_profile_name(self, question: str) -> str | None:
        """Extract profile name from question, e.g. 'on my Coconut profile'."""
        m = re.search(r'\b(?:on\s+(?:my\s+)?|profile\s+)([A-Za-z]+)\b', question, re.IGNORECASE)
        if m:
            candidate = m.group(1)
            # Common Skyblock profile names
            profile_names = {
                "apple", "banana", "blueberry", "coconut", "cucumber", "grapes",
                "kiwi", "lemon", "lime", "mango", "orange", "papaya", "peach",
                "pear", "pineapple", "pomegranate", "raspberry", "strawberry",
                "tomato", "watermelon", "zucchini",
            }
            if candidate.lower() in profile_names:
                return candidate
        return None

    async def _handle_player_question(self, question: str, username: str) -> str | None:
        """
        Handle any question about a specific player.
        Fetches full profile, injects as AI context, lets AI answer.
        For HotM commission calculations, handles directly in code.
        """
        q = question.lower()
        profile_name = self._extract_profile_name(question)

        data = await self.hypixel.get_player_data(username, profile_name)
        if not data:
            return f"Couldn't find player **{username}** — check the spelling."

        # ── HotM commission calc (code path, no AI needed) ─────────────────
        if "hotm" in q or "heart of the mountain" in q:
            if "commission" in q or "how many" in q or "till" in q or "to" in q:
                lvl = data["hotm_level"]
                xp = data["hotm_xp"]
                profile = data["profile_name"]

                if lvl >= 10:
                    return f"**{username}** ({profile}) is already **HotM 10**! ({xp:,.0f} XP)"

                target_match = re.search(r"hotm\s*(\d+)", q)
                target = int(target_match.group(1)) if target_match else 10
                target = min(max(target, lvl + 1), 10)

                xp_needed = max(0, HOTM_XP[target] - xp)
                tier = 2 if ("tier 2" in q or "t2" in q) else 3 if ("tier 3" in q or "t3" in q) else 1
                commissions = self.hypixel.commissions_needed(xp_needed, tier)
                from hypixel_api import COMMISSION_XP
                xp_per = COMMISSION_XP[tier]

                return (
                    f"**{username}** ({profile}) — HotM **{lvl}** → **{target}**\n"
                    f"XP needed: **{xp_needed:,.0f}** ({xp:,.0f} / {HOTM_XP[target]:,.0f})\n"
                    f"Tier {tier} commissions: **{commissions:,}** ({xp_per:,} XP each)"
                )

        # ── General player question — inject stats as AI context ────────────
        summary = data.get("summary", "No data available.")
        system = (
            "You are a Hypixel Skyblock assistant. Answer ONLY using the player stats and knowledge base below.\n"
            "Do NOT invent stats, items, or advice not present in the provided data. Be concise (1-3 lines).\n\n"
            f"PLAYER STATS:\n{summary}\n\n"
            f"KNOWLEDGE BASE:\n{self.knowledge.get_relevant_knowledge(question)}"
        )
        try:
            resp = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": question},
                ],
                max_tokens=400,
                temperature=0.0,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            return f"AI error: {e}"

    def _needs_live_data(self, question: str) -> bool:
        q = question.lower()
        return any(kw in q for kw in PRICE_KEYWORDS)

    def _needs_ah_data(self, question: str) -> bool:
        q = question.lower()
        budget_kws = ["budget", "afford", "for x", "for 1", "for 2", "for 3", "for 4",
                      "for 5", "for 6", "for 7", "for 8", "for 9", "million", " mil",
                      "cheapest", "cheap", "how much is", "how much does", "ah price",
                      "auction price", "bin price", "lowest bin",
                      "best reforge", "reforge for", "reforge stone",
                      "best mining", "best armor", "best weapon", "best sword",
                      "best setup", "best pet", "best dungeon", "best mage",
                      "best berserk", "best archer", "best tank", "best healer",
                      "whats the best", "what is the best", "recommend"]
        return self._needs_live_data(q) or any(kw in q for kw in budget_kws)

    def _extract_qty_item(self, question: str) -> tuple[int, str] | None:
        """Try to extract a quantity + item name from the question."""
        m = QTY_PATTERN.search(question)
        if m:
            qty = int(m.group(1))
            item = m.group(2).strip()
            return qty, item
        return None

    def _extract_search_phrases(self, question: str) -> list[str]:
        stopwords = {
            "what", "is", "the", "a", "an", "of", "for", "how", "much",
            "does", "do", "cost", "price", "worth", "buy", "sell", "total",
            "many", "coins", "get", "me", "i", "to", "in", "and", "or",
            "bazaar", "profit", "per", "each", "are", "can", "you", "if",
            "whats", "would", "be", "x", "my", "have"
        }
        words = re.sub(r"[^\w\s]", "", question.lower()).split()
        cleaned = [w.rstrip("s") if len(w) > 4 else w for w in words if w not in stopwords]

        phrases = set()
        for i in range(len(cleaned)):
            for j in range(i + 1, min(i + 4, len(cleaned) + 1)):
                phrase = " ".join(cleaned[i:j])
                if len(phrase) >= 3:
                    phrases.add(phrase)
        return list(phrases)

    async def _find_best_bazaar_match(self, item_name: str) -> dict | None:
        """Search bazaar and return the closest matching item."""
        # Try exact match first, then partial
        norm = item_name.upper().replace(" ", "_")
        exact = await self.hypixel.get_bazaar_item(norm)
        if exact:
            return exact

        # Try stripping trailing S (plurals)
        results = await self.hypixel.search_bazaar(item_name)
        if results:
            # Prefer the result whose ID most closely matches the query
            norm_query = norm.rstrip("S")
            for r in results:
                if r["id"].rstrip("S") == norm_query:
                    return r
            return results[0]  # fallback to first match

        return None

    async def _build_item_context(self, question: str) -> str:
        """Search the Hypixel items API for items mentioned in the question."""
        stopwords = {"what", "is", "the", "a", "an", "recipe", "for", "craft", "how", "to",
                     "make", "ingredients", "of", "get", "whats", "me", "tell", "about",
                     "stats", "item", "info", "and", "or", "in"}
        words = re.sub(r"[^\w\s']", "", question.lower()).split()
        candidates = set()

        # Try multi-word phrases (up to 4 words)
        for i in range(len(words)):
            for j in range(i + 1, min(i + 5, len(words) + 1)):
                phrase = " ".join(words[i:j])
                if not all(w in stopwords for w in phrase.split()) and len(phrase) > 3:
                    candidates.add(phrase)

        found = {}
        for phrase in sorted(candidates, key=len, reverse=True):  # try longer phrases first
            item = await self.hypixel.find_item(phrase)
            if item and item["id"] not in found:
                found[item["id"]] = item
            if len(found) >= 3:
                break

        if not found:
            return ""

        lines = ["Item data from Hypixel API:"]
        for item in found.values():
            lines.append(self.hypixel.format_item_info(item))
        return "\n".join(lines)

    async def _build_live_context(self, question: str) -> str:
        if not os.getenv("HYPIXEL_API_KEY"):
            return ""

        phrases = self._extract_search_phrases(question)
        results = {}

        for phrase in phrases:
            try:
                matches = await self.hypixel.search_bazaar(phrase)
                for m in matches:
                    results[m["id"]] = m
            except Exception:
                pass

        if not results:
            return ""

        # Only keep the top 5 closest matches by ID length similarity
        def match_score(item):
            q = question.lower().replace(" ", "_")
            return len(set(item["id"].lower().split("_")) & set(q.split("_")))

        top = sorted(results.values(), key=match_score, reverse=True)[:5]
        lines = ["Current Bazaar prices (live):"]
        for item in top:
            lines.append(
                f"  {item['id']}: instabuy {item['buy']:,.1f} | instasell {item['sell']:,.1f} coins"
            )
        return "\n".join(lines)

    # Known items with their AH item IDs and gemstone slot counts
    # Maps item name aliases → Hypixel item ID (gem slots fetched live from API)
    ITEM_UPGRADE_MAP = {
        "divan helmet":       "ARMOR_OF_DIVAN_HELMET",
        "divan chestplate":   "ARMOR_OF_DIVAN_CHESTPLATE",
        "divan leggings":     "ARMOR_OF_DIVAN_LEGGINGS",
        "divan boots":        "ARMOR_OF_DIVAN_BOOTS",
        "glacite helmet":     "GLACITE_HELMET",
        "glacite chestplate": "GLACITE_CHESTPLATE",
        "glacite leggings":   "GLACITE_LEGGINGS",
        "glacite boots":      "GLACITE_BOOTS",
        "hyperion":           "HYPERION",
        "terminator":         "TERMINATOR",
        "livid dagger":       "LIVID_DAGGER",
        "necron helmet":      "NECRONS_HELMET",
        "necron chestplate":  "NECRONS_CHESTPLATE",
        "necron leggings":    "NECRONS_LEGGINGS",
        "necron boots":       "NECRONS_BOOTS",
        "storm helmet":       "STORM_HELMET",
        "storm chestplate":   "STORM_CHESTPLATE",
        "storm leggings":     "STORM_LEGGINGS",
        "storm boots":        "STORM_BOOTS",
        "aurora helmet":      "AURORA_HELMET",
        "aurora chestplate":  "AURORA_CHESTPLATE",
        "aurora leggings":    "AURORA_LEGGINGS",
        "aurora boots":       "AURORA_BOOTS",
        "terror helmet":      "TERROR_HELMET",
        "terror chestplate":  "TERROR_CHESTPLATE",
        "terror leggings":    "TERROR_LEGGINGS",
        "terror boots":       "TERROR_BOOTS",
    }

    async def _handle_hypermax_question(self, question: str) -> str | None:
        """Detect hypermaxed/maxed item questions and return full upgrade cost breakdown."""
        q = question.lower()
        hypermax_kws = ["hypermaxed", "hypermax", "hyper max", "maxed out", "fully maxed",
                        "max out", "fully upgraded", "max price", "max cost"]
        if not any(kw in q for kw in hypermax_kws):
            return None

        # Normalize query: remove apostrophes/punctuation for matching
        # Tokenize question — strip possessives so "divans" → "divan"
        q_tokens = re.sub(r"'s?\b", "", q)
        q_tokens = re.sub(r"[^a-z0-9\s]", "", q_tokens).split()

        for name, item_id in self.ITEM_UPGRADE_MAP.items():
            name_words = name.split()
            # All words in the item name must appear in the question (prefix match for plurals)
            if all(any(qt.startswith(nw) for qt in q_tokens) for nw in name_words):
                # ── Dynamic reforge selection ────────────────────────────────
                desired_stat = self._detect_desired_stat(question)

                # Fetch lbin for item price, coflnet for stone prices
                lbin = await self.hypixel.get_lowest_bin()
                item_price = lbin.get(item_id, 0)

                # Batch-fetch all stone prices from coflnet in parallel
                from reforges import REFORGES
                stone_ids = list({d["stone"] for d in REFORGES.values() if d.get("stone")})
                prices_list = await asyncio.gather(
                    *[self.hypixel.get_reforge_stone_price(sid) for sid in stone_ids]
                )
                stone_prices = dict(zip(stone_ids, prices_list))

                reforge = pick_reforge(
                    item_id,
                    desired_stat=desired_stat,
                    item_price=item_price,
                    stone_prices=stone_prices,
                )
                stone_id    = reforge["stone"]    if reforge else None
                reforge_name = reforge["name"]    if reforge else None

                result = await self.hypixel.get_hypermaxed_price(item_id, reforge_stone_id=stone_id)
                if not result:
                    return "Couldn't fetch upgrade prices right now, try again."

                # Parse exclusions: "without hot potato", "no recomb", "without jaded", etc.
                exclude_map = {
                    "hot potato":       "hot_potato_books",
                    "hpb":              "hot_potato_books",
                    "fuming potato":    "fuming_potato_books",
                    "fuming":           "fuming_potato_books",
                    "fhpb":             "fuming_potato_books",
                    "recomb":           "recombobulator_3000",
                    "recombobulator":   "recombobulator_3000",
                    "art of peace":     "art_of_peace",
                    "aop":              "art_of_peace",
                    "reforge":          "reforge_stone",
                    "slot unlock":      "slot_unlocking",
                    "unlocking":        "slot_unlocking",
                    "unlock":           "slot_unlocking",
                    "gemstone chamber": "slot_unlocking",
                }
                if reforge_name:
                    exclude_map[reforge_name] = "reforge_stone"

                excluded = set()
                for phrase, key in exclude_map.items():
                    if phrase in q:
                        excluded.add(key)

                total = sum(
                    v["total"] for k, v in result["breakdown"].items()
                    if k not in excluded
                )

                base_price = result["breakdown"]["base_item"]["total"]
                base_note  = f"{base_price:,.0f} (lowest BIN)" if base_price > 0 else "price unavailable — bid-only AH item, add manually"
                excl_note  = f" *(excl. {', '.join(e.replace('_', ' ') for e in excluded)})*" if excluded else ""

                # Reforge header note
                if reforge and "reforge_stone" not in excluded:
                    stat_str = ", ".join(f"+{v} {k.replace('_', ' ').title()}" for k, v in reforge["stats"].items())
                    afford_warn = " ⚠️ expensive relative to item" if not reforge["affordable"] else ""
                    reforge_label = f" + **{reforge_name.title()}** reforge ({stat_str}){afford_warn}"
                else:
                    reforge_label = ""

                lines = [
                    f"**Hypermaxed {name.title()}**{reforge_label}{excl_note} — Total: **{total:,.0f} coins**\n",
                    f"  Base item: {base_note}",
                ]
                free = result.get("free_slots", 0)
                for label, data in result["breakdown"].items():
                    if label == "base_item" or data["total"] == 0 or label in excluded:
                        continue
                    if label == "reforge_stone" and reforge_name:
                        label_fmt = f"{reforge_name.title()} Reforge Stone"
                    elif label == "slot_unlocking":
                        slot_note = f" ({free} free)" if free else ""
                        label_fmt = f"Gem Slot Unlocking ×{data['qty']}{slot_note}"
                        # Append detail breakdown as sub-line
                        lines.append(f"  {label_fmt}: {data['total']:,.0f}")
                        for detail in data.get("details", []):
                            lines.append(f"    ↳ {detail}")
                        continue
                    else:
                        label_fmt = label.replace("_", " ").title()
                    if data["qty"] > 1:
                        lines.append(f"  {label_fmt} ×{data['qty']}: {data['total']:,.0f} ({data['unit']:,.0f} each)")
                    else:
                        lines.append(f"  {label_fmt}: {data['total']:,.0f}")
                return "\n".join(lines)

        # Hypermax keywords were present but no item in ITEM_UPGRADE_MAP matched
        return "I don't recognize that item for a hypermax calculation. Supported items: Divan armor, Glacite armor, Necron armor, Storm armor, Aurora armor, Terror armor, Hyperion, Terminator, Livid Dagger."

    def _detect_desired_stat(self, question: str) -> str | None:
        """Extract a desired stat from phrases like 'with more intelligence', 'for mage', 'i want str'."""
        q = question.lower()
        # Explicit stat patterns: "with X", "for X", "want X", "more X", "extra X"
        patterns = [
            r"(?:with|for|want|more|extra|need|give me|maximize)\s+([a-z][a-z _]{2,30}?)(?:\s+(?:stat|reforge|build|setup)|$|\?)",
            r"(?:focused on|optimized for|best for)\s+([a-z][a-z _]{2,30}?)(?:\s|$|\?)",
        ]
        for pat in patterns:
            m = re.search(pat, q)
            if m:
                candidate = m.group(1).strip()
                normed = normalize_stat(candidate)
                if normed:
                    return normed
        # Build shortcuts: "mage build" → intelligence, "mining build" → mining_fortune
        build_map = {
            "mage":    "intelligence",
            "wizard":  "intelligence",
            "archer":  "crit_chance",
            "berserker": "crit_damage",
            "tank":    "defense",
            "mining":  "mining_fortune",
        }
        for keyword, stat in build_map.items():
            if keyword in q:
                return stat
        return None

    # Known armor set ID prefixes
    ARMOR_SETS = {
        "armor of divan": "ARMOR_OF_DIVAN",
        "glacite": "GLACITE",
        "mineral": "MINERAL",
        "aurora": "AURORA",
        "terror": "TERROR",
        "fervor": "FERVOR",
        "crimson": "CRIMSON",
        "necron": "NECRONS",
        "wither": "WITHER",
        "shadow assassin": "SHADOW_ASSASSIN",
        "superior dragon": "SUPERIOR_DRAGON",
        "strong dragon": "STRONG_DRAGON",
        "young dragon": "YOUNG_DRAGON",
        "old dragon": "OLD_DRAGON",
        "unstable dragon": "UNSTABLE_DRAGON",
        "holy dragon": "HOLY_DRAGON",
        "wise dragon": "WISE_DRAGON",
        "protector dragon": "PROTECTOR_DRAGON",
        "tarantula": "TARANTULA",
        "revenant": "REVENANT",
        "mastiff": "MASTIFF",
        "berserker": "BERSERKER",
        "hollow": "HOLLOW",
        "goldor": "GOLDOR",
        "storm": "STORM",
        "maxor": "MAXOR",
    }

    async def _build_armor_set_context(self, question: str, kb_text: str = "") -> str:
        """Fetch full set prices for armor sets mentioned in the question OR knowledge base."""
        search_text = question.lower() + " " + kb_text.lower()
        lines = []
        checked = set()
        for name, prefix in self.ARMOR_SETS.items():
            if name in search_text and prefix not in checked:
                checked.add(prefix)
                try:
                    prices = await self.hypixel.get_armor_set_prices(prefix)
                    if prices:
                        total = prices.pop("total")
                        pieces = " | ".join(
                            f"{slot}: {data['price']:,.0f}" for slot, data in prices.items()
                        )
                        lines.append(f"{name.title()} full set: {total:,.0f} coins ({pieces})")
                except Exception:
                    pass
            if len(checked) >= 8:  # cap to avoid too many API calls
                break
        return ("Current AH set prices:\n" + "\n".join(lines)) if lines else ""

    async def _build_ah_context(self, question: str, extra_ids: list[str] = None) -> str:
        """Search AH (lowest BIN + ended auctions) for items mentioned in the question."""
        phrases = self._extract_search_phrases(question)
        # Also search any explicit item IDs passed in (e.g. from knowledge base)
        if extra_ids:
            phrases = list(extra_ids) + phrases
        seen_ids: set = set()
        lines = []

        for phrase in phrases:
            try:
                results = await self.hypixel.search_ah(phrase)
                for r in results:
                    item_id = r["item_id"]
                    if item_id in seen_ids:
                        continue
                    seen_ids.add(item_id)
                    if r["source"].startswith("Lowest BIN"):
                        lines.append(f"  {r['name']} (BIN): {r['price']:,.1f} coins")
                    else:
                        low = r.get("low", r["price"])
                        high = r.get("high", r["price"])
                        src = r["source"]
                        lines.append(
                            f"  {r['name']} (AH {src}): "
                            f"median {r['price']:,.1f} | low {low:,.1f} | high {high:,.1f} coins"
                        )
            except Exception:
                pass
            if len(seen_ids) >= 6:
                break

        if not lines:
            return ""
        return "Auction House prices (live):\n" + "\n".join(lines)

    async def get_response(self, question: str) -> str:
        async with self.semaphore:
            price_question = self._needs_live_data(question)

            # --- Player data path ---
            username = self._extract_username(question)
            if username:
                try:
                    result = await self._handle_player_question(question, username)
                    if result:
                        return result
                except Exception as e:
                    return f"Error fetching player data: {e}"

            # --- Hypermax price calculator ---
            try:
                hypermax = await self._handle_hypermax_question(question)
                if hypermax:
                    return hypermax
            except Exception as e:
                print(f"[hypermax error] {e}")

            # --- Fast path: quantity × item calculation, bypass AI entirely ---
            if price_question and os.getenv("HYPIXEL_API_KEY"):
                parsed = self._extract_qty_item(question)
                if parsed:
                    qty, item_name = parsed
                    try:
                        match = await self._find_best_bazaar_match(item_name)
                        if match:
                            use_sell = any(w in question.lower() for w in ["sell", "instasell"])
                            price = match["sell"] if use_sell else match["buy"]
                            total = price * qty
                            label = "instasell" if use_sell else "instabuy"
                            return (
                                f"**{qty}x {match['id'].replace('_', ' ').title()}** = "
                                f"**{total:,.1f} coins** ({label} @ {price:,.1f} each)"
                            )
                    except Exception:
                        pass  # fall through to AI

            # --- Normal AI path ---
            live_ctx = ""
            ah_ctx = ""
            item_ctx = ""

            # Item/recipe lookup from Hypixel items API
            item_keywords = ["what is", "stats", "item info"]
            if any(kw in question.lower() for kw in item_keywords):
                try:
                    item_ctx = await self._build_item_context(question)
                except Exception:
                    pass

            if price_question:
                try:
                    live_ctx = await self._build_live_context(question)
                except Exception as e:
                    live_ctx = f"(Live price fetch failed: {e})"

            static_ctx = self.knowledge.get_relevant_knowledge(question)

            if self._needs_ah_data(question):
                try:
                    # Only extract IDs from curated "Item IDs for price lookups:" lines
                    # to avoid flooding with false positives from large wiki dump files
                    kb_ids = []
                    for line in static_ctx.splitlines():
                        if "item ids for price lookups" in line.lower():
                            kb_ids.extend(re.findall(r'\b[A-Z][A-Z0-9_]{4,}\b', line))
                    kb_ids = list(dict.fromkeys(kb_ids))[:20]
                    ah_ctx = await self._build_ah_context(question, extra_ids=kb_ids)
                except Exception:
                    pass
                try:
                    set_ctx = await self._build_armor_set_context(question, kb_text=static_ctx)
                    if set_ctx:
                        ah_ctx = (ah_ctx + "\n\n" + set_ctx).strip()
                except Exception:
                    pass

            # Inject historical trend data if tracker has data and question involves a specific item
            hist_ctx = ""
            if self.tracker and price_question:
                try:
                    phrases = self._extract_search_phrases(question)
                    for phrase in phrases[:3]:
                        item_id = phrase.upper().replace(" ", "_")
                        history = self.tracker.format_history_for_ai(item_id, hours=24)
                        if history:
                            hist_ctx += history + "\n"
                            break
                except Exception:
                    pass
            # Warn if knowledge base came back empty AND no live data — high hallucination risk
            kb_empty = len(static_ctx.strip()) < 100 and not live_ctx and not ah_ctx and not item_ctx
            cata_level = self._extract_cata_level(question)
            cata_note = (
                f"- The user has stated their Catacombs level is {cata_level}. "
                f"ONLY recommend items/content they can use or access at Cata {cata_level}. "
                f"If an item requires a higher Cata level, skip it.\n"
            ) if cata_level is not None else ""
            system = (
                "You are a Hypixel Skyblock assistant. Answer ONLY using the knowledge base and live price data provided below.\n\n"
                "STRICT RULES:\n"
                "- FORBIDDEN: Do NOT invent, guess, or assume any item names, set names, stats, drop sources, or recipes. "
                "If an item or fact is not explicitly written in the knowledge base below, say 'I don't have that info in my knowledge base yet.' "
                "Invented items like 'Wither Armor', 'Ember Ash Armor', 'Squire Armor', 'Diamante Handle', 'Refined Mineral' are examples of hallucination — never do this.\n"
                "- Before writing any item name, verify it appears word-for-word in the KNOWLEDGE BASE section below. If it doesn't, do not mention it.\n"
                + ("- WARNING: Knowledge base has little relevant content for this question. Say: "
                   "'I don't have enough info on that in my knowledge base yet.' Do not guess.\n"
                   if kb_empty else "")
                + cata_note
                + "- PRICES: Ignore ALL coin amounts in the knowledge base — they are outdated. "
                "Use ONLY the live data in 'LIVE AH PRICES' / 'LIVE BAZAAR PRICES' sections. If no live price exists, say 'price unavailable'.\n"
                "- For budget questions: only list items whose live price fits within budget. Sort cheapest first.\n"
                "- Format: 'Item Name — key stats — X,XXX,XXX coins (live)'\n"
                "- If not about Hypixel Skyblock, reply: 'I only answer Hypixel Skyblock questions.'\n"
                "- No intro, no filler. Direct answer only.\n\n"
                f"KNOWLEDGE BASE:\n{static_ctx}"
            )

            if item_ctx:
                system += f"\n\n{item_ctx}"
            if live_ctx:
                system += f"\n\nLIVE BAZAAR PRICES:\n{live_ctx}"
            if ah_ctx:
                system += f"\n\nLIVE AH PRICES:\n{ah_ctx}"
            if hist_ctx:
                system += f"\n\nHistorical price data:\n{hist_ctx}"
            if price_question and not live_ctx and not ah_ctx:
                system += "\n\nNo live price data found. Do NOT guess prices."

            try:
                resp = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": question},
                    ],
                    max_tokens=1200,
                    temperature=0.0,
                )
                text = resp.choices[0].message.content.strip()
                # deepseek-r1 wraps its reasoning in <think>...</think> — strip it
                text = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.IGNORECASE).strip()
                if len(text) > MAX_DISCORD_LEN:
                    text = text[:MAX_DISCORD_LEN] + "…"
                return text
            except Exception as e:
                return f"AI error: {e}"
