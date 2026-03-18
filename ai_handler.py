import os
import re
import asyncio
from groq import AsyncGroq
from hypixel_api import HypixelAPI, HOTM_XP
from knowledge_base import KnowledgeBase

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
        self.model = "llama-3.3-70b-versatile"
        self.hypixel = HypixelAPI(os.getenv("HYPIXEL_API_KEY", ""))
        self.knowledge = KnowledgeBase()
        self.semaphore = asyncio.Semaphore(5)
        self.tracker = None

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
                      "for 5", "for 6", "for 7", "for 8", "for 9", "million", "mil ",
                      "cheapest", "cheap", "how much is", "how much does", "ah price",
                      "auction price", "bin price", "lowest bin"]
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
    ITEM_UPGRADE_MAP = {
        "divan helmet":        ("ARMOR_OF_DIVAN_HELMET",     5, "JASPER"),
        "divan chestplate":    ("ARMOR_OF_DIVAN_CHESTPLATE", 5, "JASPER"),
        "divan leggings":      ("ARMOR_OF_DIVAN_LEGGINGS",   5, "JASPER"),
        "divan boots":         ("ARMOR_OF_DIVAN_BOOTS",      5, "JASPER"),
        "glacite helmet":      ("GLACITE_HELMET",            0, "JASPER"),
        "glacite chestplate":  ("GLACITE_CHESTPLATE",        0, "JASPER"),
        "glacite leggings":    ("GLACITE_LEGGINGS",          0, "JASPER"),
        "glacite boots":       ("GLACITE_BOOTS",             0, "JASPER"),
        "hyperion":            ("HYPERION",                  3, "JASPER"),
        "terminator":          ("TERMINATOR",                3, "JASPER"),
        "necron helmet":       ("NECRONS_HELMET",            3, "JASPER"),
        "necron chestplate":   ("NECRONS_CHESTPLATE",        3, "JASPER"),
        "necron leggings":     ("NECRONS_LEGGINGS",          3, "JASPER"),
        "necron boots":        ("NECRONS_BOOTS",             3, "JASPER"),
        "storm helmet":        ("STORM_HELMET",              3, "JASPER"),
        "storm chestplate":    ("STORM_CHESTPLATE",          3, "JASPER"),
        "storm leggings":      ("STORM_LEGGINGS",            3, "JASPER"),
        "storm boots":         ("STORM_BOOTS",               3, "JASPER"),
    }

    async def _handle_hypermax_question(self, question: str) -> str | None:
        """Detect hypermaxed/maxed item questions and return full upgrade cost breakdown."""
        q = question.lower()
        hypermax_kws = ["hypermaxed", "hypermax", "maxed out", "fully maxed", "max out", "fully upgraded", "max price"]
        if not any(kw in q for kw in hypermax_kws):
            return None

        # Normalize query: remove apostrophes/punctuation for matching
        q_norm = re.sub(r"['\s]+", " ", q).strip()

        for name, (item_id, gem_slots, gem_type) in self.ITEM_UPGRADE_MAP.items():
            name_norm = re.sub(r"['\s]+", " ", name).strip()
            # Also try without trailing 's' (divans -> divan)
            if (name_norm in q_norm
                    or name_norm.rstrip("s") in q_norm
                    or name_norm in q_norm.replace("divans", "divan")):
                result = await self.hypixel.get_hypermaxed_price(item_id, gem_slots, gem_type)
                if not result:
                    return f"Couldn't fetch upgrade prices right now, try again."

                base_price = result["breakdown"]["base_item"]["total"]
                base_note = f"{base_price:,.0f} (lowest BIN)" if base_price > 0 else "not found on AH"
                lines = [f"**Hypermaxed {name.title()}** — Total: **{result['total']:,.0f} coins**\n",
                         f"  Base item: {base_note}"]
                for label, data in result["breakdown"].items():
                    if data["total"] == 0:
                        continue
                    label_fmt = label.replace("_", " ").title()
                    if data["qty"] > 1:
                        lines.append(f"  {label_fmt} ×{data['qty']}: {data['total']:,.0f} ({data['unit']:,.0f} each)")
                    else:
                        lines.append(f"  {label_fmt}: {data['total']:,.0f}")
                return "\n".join(lines)

        return None

    # Known armor set ID prefixes
    ARMOR_SETS = {
        "armor of divan": "ARMOR_OF_DIVAN",
        "divan": "ARMOR_OF_DIVAN",
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

    async def _build_armor_set_context(self, question: str) -> str:
        """Fetch full set prices for any armor sets mentioned in the question."""
        q = question.lower()
        lines = []
        checked = set()
        for name, prefix in self.ARMOR_SETS.items():
            if name in q and prefix not in checked:
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
            except Exception:
                pass

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
            item_keywords = ["recipe", "craft", "how to make", "ingredients", "what is", "stats", "item info"]
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

            if self._needs_ah_data(question):
                try:
                    kb_ids = re.findall(r'\b[A-Z][A-Z0-9_]{3,}\b', static_ctx)
                    kb_ids = list(dict.fromkeys(kb_ids))[:10]
                    ah_ctx = await self._build_ah_context(question, extra_ids=kb_ids)
                except Exception:
                    pass
                try:
                    set_ctx = await self._build_armor_set_context(question)
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

            static_ctx = self.knowledge.get_relevant_knowledge(question)
            system = (
                "You are a Hypixel Skyblock assistant. Answer ONLY using the knowledge base provided below.\n\n"
                "STRICT RULES:\n"
                "- ONLY reference items, mechanics, setups, and numbers that appear in the knowledge base below.\n"
                "- Do NOT use your general training knowledge. If it is not in the knowledge base, do not say it.\n"
                "- If the question is not about Hypixel Skyblock, reply ONLY: 'I only answer Hypixel Skyblock questions.'\n"
                "- For price questions: one line only, use live data provided. Never guess prices.\n"
                "- For budget questions (e.g. 'best X for 5M'): use the live AH/Bazaar prices provided to recommend what fits the budget. Show item name, key stats, and current price.\n"
                "- If the exact item is not found in the live data, say 'I couldn't find [item] on the Bazaar/AH.' Do NOT list similar items.\n"
                "- Be extremely concise. No intro, no filler, no 'great question', no explanations unless asked.\n"
                "- For 'best X' questions: just list the item name + key stats. Example: 'Armor of Divan — +150 Mining Fortune, +1800 Mining Speed'\n"
                "- Never say 'In Hypixel Skyblock...' or 'The best option is...' — just give the answer directly.\n"
                "- Format coin amounts with commas.\n\n"
                f"KNOWLEDGE BASE:\n{static_ctx}"
            )

            if item_ctx:
                system += f"\n\n{item_ctx}"
            if live_ctx:
                system += f"\n\n{live_ctx}"
            if ah_ctx:
                system += f"\n\n{ah_ctx}"
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
                    max_tokens=400,
                    temperature=0.0,
                )
                text = resp.choices[0].message.content.strip()
                if len(text) > MAX_DISCORD_LEN:
                    text = text[:MAX_DISCORD_LEN] + "…"
                return text
            except Exception as e:
                return f"AI error: {e}"
