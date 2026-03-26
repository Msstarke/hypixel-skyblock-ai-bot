import os
import re
import asyncio
from groq import AsyncGroq
from hypixel_api import HypixelAPI, HOTM_XP
from knowledge_base import KnowledgeBase
from reforges import pick_reforge, normalize_stat, STAT_ALIASES
from user_links import get_linked_username, get_linked_uuid
from wiki_lookup import wiki_context
from feedback import log_unanswered
from learned_facts import find_fact, save_fact

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
        self.model = "meta-llama/llama-4-scout-17b-16e-instruct"
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
            return (
                f"Couldn't find player **{username}**. A few things to check:\n"
                f"- Double-check the spelling of the username\n"
                f"- Make sure API access is enabled in your Hypixel settings (main menu > Settings > API)\n"
                f"- Use their current username, not an old one"
            )

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
        corrections = self.knowledge.get_corrections()
        system = (
            "You are a Hypixel Skyblock assistant. Answer ONLY using the player stats, community corrections, and knowledge base below.\n"
            "CRITICAL: Do NOT invent stats, items, prices, perk effects, or advice not present in the provided data.\n"
            "If information is not in the data below, say 'I don't have that info' — do NOT guess or make something up.\n"
            "HotM PERKS: ALWAYS use the perk names and max levels from COMMUNITY CORRECTIONS. Mining Fortune max level is 50 (NOT 100). Do NOT invent perk levels.\n"
            "Do NOT recommend removed perks (Mining Madness, Star Powder, Vein Seeker, Goblin Killer, Orbiter, Crystallized).\n"
            "Do NOT recommend fake items (Spelunker reforge, Divan's Drill, HotMines menu).\n"
            "Be concise and accurate. When unsure, say so.\n\n"
            f"PLAYER STATS:\n{summary}\n\n"
            f"KNOWLEDGE BASE:\n{self.knowledge.get_relevant_knowledge(question)}"
        )
        if corrections:
            system += f"\n\nCOMMUNITY CORRECTIONS (verified facts — these override general knowledge):\n{corrections}"
        try:
            resp = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": question},
                ],
                max_tokens=2000,
                temperature=0.0,
            )
            text = resp.choices[0].message.content.strip()
            text = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.IGNORECASE).strip()
            return self._filter_hallucinations(text)
        except Exception as e:
            print(f"[ai] Player question AI error: {e}")
            err_name = type(e).__name__.lower()
            err_str = str(e).lower()
            if "rate" in err_name or "rate" in err_str or "429" in err_str:
                return "I'm getting too many questions right now, try again in a moment."
            if any(w in err_name for w in ("timeout", "connect", "connection")) or any(w in err_str for w in ("timeout", "connect")):
                return "Couldn't reach the AI service, try again in a moment."
            return "Something went wrong, try again."

    # Known fake items/terms the AI likes to hallucinate
    _FAKE_TERMS = [
        "spelunker reforge", "spelunker ix", "spelunker i ", "spelunker ii", "spelunker tier",
        "hotmines", "hot mines menu",
        "refined mineral", "mineral armor upgrade",
        "mithril powder boost",
        "divan's drill", "divans drill", "divan drill",
        "very lucky reforge",
        "abiphone flip", "wither bow",
        "sniper helmet", "sniper bow",
        "fortune iii",  # should be Fortune IV in skyblock
        "sharpness v",  # not a mining enchant on pickaxes
        "smite v",  # not a mining enchant
        "mining madness",  # removed perk
        "star powder",  # removed perk
        "vein seeker",  # removed perk
        "goblin killer",  # removed perk
        "crystallized",  # removed perk
        "orbiter",  # removed perk
        "miner's blessing",
        "gemstone infusion",
        "crystal hollows pass",
        "mining xp boost enchant",
        "fortune v",
    ]

    # Patterns that indicate the AI is fabricating specific numbers
    _HALLUCINATION_PATTERNS = [
        # Fake specific coin amounts with no live data context
        (re.compile(r"costs?\s+(?:around\s+|about\s+|~)?(\d{1,3}(?:,\d{3})*)\s+coins", re.IGNORECASE), None),
    ]

    def _filter_hallucinations(self, text: str) -> str:
        """Flag known hallucinated terms in AI responses."""
        lower = text.lower()
        found = [t for t in self._FAKE_TERMS if t in lower]
        # Check for Auspicious on armor (common hallucination)
        if "auspicious" in lower and any(w in lower for w in ["helmet", "chestplate", "leggings", "boots", "armor piece"]):
            found.append("auspicious on armor")
        if found:
            warning = "\n\n⚠️ *This response may contain inaccurate information. Please verify in-game or on the wiki.*"
            text += warning
        return text

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
            "whats", "would", "be", "x", "my", "have",
            # Dungeon class names — not item names, produce garbage AH results
            "berserk", "berserker", "mage", "archer", "healer", "tank",
            # Generic adjectives that are not item names
            "best", "good", "great", "cheap", "budget", "early", "late", "mid",
            "setup", "build", "guide", "class", "use",
            # Generic item categories — too broad for AH search, armor set context handles them
            "armor", "weapon", "item", "gear", "piece", "set",
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

        is_craft_q = any(w in question.lower() for w in ["craft", "recipe", "cost", "make", "ingredients"])

        lines = ["Item data from Hypixel API:"]
        for item in found.values():
            lines.append(self.hypixel.format_item_info(item))

            # If craft question, price up recipe materials from recipe DB
            if is_craft_q:
                recipe = self.hypixel.get_recipe(item["id"])
                if recipe:
                    total_craft = 0
                    mat_lines = []
                    for mat_id, count in recipe["i"].items():
                        try:
                            baz = await self.hypixel.search_bazaar(mat_id.replace("_", " "))
                            if baz:
                                price = baz[0]["buy"]
                                subtotal = price * count
                                total_craft += subtotal
                                mat_lines.append(f"  {count}x {mat_id}: {price:,.1f} each = {subtotal:,.1f} coins")
                            else:
                                p, src = await self.hypixel.get_item_price(mat_id, allow_auction=True)
                                if p:
                                    subtotal = p * count
                                    total_craft += subtotal
                                    mat_lines.append(f"  {count}x {mat_id}: {p:,.1f} each = {subtotal:,.1f} coins ({src})")
                                else:
                                    mat_lines.append(f"  {count}x {mat_id}: price unavailable")
                        except Exception:
                            mat_lines.append(f"  {count}x {mat_id}: price fetch failed")

                    if mat_lines:
                        lines.append("Craft cost breakdown (live prices):")
                        lines.extend(mat_lines)
                        if total_craft > 0:
                            lines.append(f"  TOTAL craft cost: {total_craft:,.1f} coins")

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
        # ── Mining ──
        "divan helmet":              "ARMOR_OF_DIVAN_HELMET",
        "divan chestplate":          "ARMOR_OF_DIVAN_CHESTPLATE",
        "divan leggings":            "ARMOR_OF_DIVAN_LEGGINGS",
        "divan boots":               "ARMOR_OF_DIVAN_BOOTS",
        "glacite helmet":            "GLACITE_HELMET",
        "glacite chestplate":        "GLACITE_CHESTPLATE",
        "glacite leggings":          "GLACITE_LEGGINGS",
        "glacite boots":             "GLACITE_BOOTS",
        "mineral helmet":            "MINERAL_HELMET",
        "mineral chestplate":        "MINERAL_CHESTPLATE",
        "mineral leggings":          "MINERAL_LEGGINGS",
        "mineral boots":             "MINERAL_BOOTS",
        "glossy mineral helmet":     "GLOSSY_MINERAL_HELMET",
        "glossy mineral chestplate": "GLOSSY_MINERAL_CHESTPLATE",
        "glossy mineral leggings":   "GLOSSY_MINERAL_LEGGINGS",
        "glossy mineral boots":      "GLOSSY_MINERAL_BOOTS",
        # ── Dungeons — Wither ──
        "necron helmet":             "POWER_WITHER_HELMET",
        "necron chestplate":         "POWER_WITHER_CHESTPLATE",
        "necron leggings":           "POWER_WITHER_LEGGINGS",
        "necron boots":              "POWER_WITHER_BOOTS",
        "storm helmet":              "WISE_WITHER_HELMET",
        "storm chestplate":          "WISE_WITHER_CHESTPLATE",
        "storm leggings":            "WISE_WITHER_LEGGINGS",
        "storm boots":               "WISE_WITHER_BOOTS",
        "aurora helmet":             "AURORA_HELMET",
        "aurora chestplate":         "AURORA_CHESTPLATE",
        "aurora leggings":           "AURORA_LEGGINGS",
        "aurora boots":              "AURORA_BOOTS",
        "terror helmet":             "TERROR_HELMET",
        "terror chestplate":         "TERROR_CHESTPLATE",
        "terror leggings":           "TERROR_LEGGINGS",
        "terror boots":              "TERROR_BOOTS",
        "maxor helmet":              "SPEED_WITHER_HELMET",
        "maxor chestplate":          "SPEED_WITHER_CHESTPLATE",
        "maxor leggings":            "SPEED_WITHER_LEGGINGS",
        "maxor boots":               "SPEED_WITHER_BOOTS",
        "goldor helmet":             "TANK_WITHER_HELMET",
        "goldor chestplate":         "TANK_WITHER_CHESTPLATE",
        "goldor leggings":           "TANK_WITHER_LEGGINGS",
        "goldor boots":              "TANK_WITHER_BOOTS",
        # ── Dungeons — other ──
        "shadow assassin helmet":    "SHADOW_ASSASSIN_HELMET",
        "shadow assassin chestplate":"SHADOW_ASSASSIN_CHESTPLATE",
        "shadow assassin leggings":  "SHADOW_ASSASSIN_LEGGINGS",
        "shadow assassin boots":     "SHADOW_ASSASSIN_BOOTS",
        "holy dragon helmet":        "HOLY_DRAGON_HELMET",
        "holy dragon chestplate":    "HOLY_DRAGON_CHESTPLATE",
        "holy dragon leggings":      "HOLY_DRAGON_LEGGINGS",
        "holy dragon boots":         "HOLY_DRAGON_BOOTS",
        # ── Dragon armor ──
        "superior dragon helmet":    "SUPERIOR_DRAGON_HELMET",
        "superior dragon chestplate":"SUPERIOR_DRAGON_CHESTPLATE",
        "superior dragon leggings":  "SUPERIOR_DRAGON_LEGGINGS",
        "superior dragon boots":     "SUPERIOR_DRAGON_BOOTS",
        "strong dragon helmet":      "STRONG_DRAGON_HELMET",
        "strong dragon chestplate":  "STRONG_DRAGON_CHESTPLATE",
        "strong dragon leggings":    "STRONG_DRAGON_LEGGINGS",
        "strong dragon boots":       "STRONG_DRAGON_BOOTS",
        "young dragon helmet":       "YOUNG_DRAGON_HELMET",
        "young dragon chestplate":   "YOUNG_DRAGON_CHESTPLATE",
        "young dragon leggings":     "YOUNG_DRAGON_LEGGINGS",
        "young dragon boots":        "YOUNG_DRAGON_BOOTS",
        "old dragon helmet":         "OLD_DRAGON_HELMET",
        "old dragon chestplate":     "OLD_DRAGON_CHESTPLATE",
        "old dragon leggings":       "OLD_DRAGON_LEGGINGS",
        "old dragon boots":          "OLD_DRAGON_BOOTS",
        "unstable dragon helmet":    "UNSTABLE_DRAGON_HELMET",
        "unstable dragon chestplate":"UNSTABLE_DRAGON_CHESTPLATE",
        "unstable dragon leggings":  "UNSTABLE_DRAGON_LEGGINGS",
        "unstable dragon boots":     "UNSTABLE_DRAGON_BOOTS",
        "wise dragon helmet":        "WISE_DRAGON_HELMET",
        "wise dragon chestplate":    "WISE_DRAGON_CHESTPLATE",
        "wise dragon leggings":      "WISE_DRAGON_LEGGINGS",
        "wise dragon boots":         "WISE_DRAGON_BOOTS",
        "protector dragon helmet":   "PROTECTOR_DRAGON_HELMET",
        "protector dragon chestplate":"PROTECTOR_DRAGON_CHESTPLATE",
        "protector dragon leggings": "PROTECTOR_DRAGON_LEGGINGS",
        "protector dragon boots":    "PROTECTOR_DRAGON_BOOTS",
        # ── Slayer / combat ──
        "mastiff helmet":            "MASTIFF_HELMET",
        "mastiff chestplate":        "MASTIFF_CHESTPLATE",
        "mastiff leggings":          "MASTIFF_LEGGINGS",
        "mastiff boots":             "MASTIFF_BOOTS",
        "tarantula helmet":          "TARANTULA_HELMET",
        "tarantula chestplate":      "TARANTULA_CHESTPLATE",
        "tarantula leggings":        "TARANTULA_LEGGINGS",
        "tarantula boots":           "TARANTULA_BOOTS",
        "hollow helmet":             "HOLLOW_HELMET",
        "hollow chestplate":         "HOLLOW_CHESTPLATE",
        "hollow leggings":           "HOLLOW_LEGGINGS",
        "hollow boots":              "HOLLOW_BOOTS",
        "fervor helmet":             "FERVOR_HELMET",
        "fervor chestplate":         "FERVOR_CHESTPLATE",
        "fervor leggings":           "FERVOR_LEGGINGS",
        "fervor boots":              "FERVOR_BOOTS",
        # ── Weapons ──
        "hyperion":                  "HYPERION",
        "terminator":                "TERMINATOR",
        "livid dagger":              "LIVID_DAGGER",
        "juju shortbow":             "JUJU_SHORTBOW",
        "aspect of the end":         "ASPECT_OF_THE_END",
        "aspect of the void":        "ASPECT_OF_THE_VOID",
        "aote":                      "ASPECT_OF_THE_END",
        "aotv":                      "ASPECT_OF_THE_VOID",
        "midas sword":               "MIDAS_SWORD",
        "midas staff":               "MIDAS_STAFF",
        "giants sword":              "GIANTS_SWORD",
        "flower of truth":           "FLOWER_OF_TRUTH",
        "valkyrie":                  "VALKYRIE",
        "shadow fury":               "SHADOW_FURY",
        "bonzo staff":               "BONZO_STAFF",
        "spirit sceptre":            "SPIRIT_SCEPTRE",
        "last breath":               "LAST_BREATH",
        "necron blade":              "NECRON_BLADE",
        "astraea":                   "ASTRAEA",
        "scylla":                    "SCYLLA",
        # ── Drills ──
        "titanium drill 655":        "TITANIUM_DRILL_4",
        "titanium drill 555":        "TITANIUM_DRILL_3",
        "titanium drill 455":        "TITANIUM_DRILL_2",
        "titanium drill 355":        "TITANIUM_DRILL_1",
        "mithril drill 326":         "MITHRIL_DRILL_2",
        "mithril drill 226":         "MITHRIL_DRILL_1",
        "gemstone drill":            "GEMSTONE_DRILL_4",
        "divans drill":              "DIVAN_DRILL",
        "divan drill":               "DIVAN_DRILL",
        # ── Pickaxes ──
        "pickonimbus":               "PICKONIMBUS",
        "gemstone gauntlet":         "GEMSTONE_GAUNTLET",
    }

    # Full armor set aliases — matched when user says "mineral set" / "necron armor" etc.
    # Token → (display name, [helmet_id, chestplate_id, leggings_id, boots_id])
    ITEM_SET_MAP = {
        # ── Mining ──
        "divan":     ("Divan Armor Set",            ["ARMOR_OF_DIVAN_HELMET",     "ARMOR_OF_DIVAN_CHESTPLATE",     "ARMOR_OF_DIVAN_LEGGINGS",     "ARMOR_OF_DIVAN_BOOTS"]),
        "glacite":   ("Glacite Armor Set",          ["GLACITE_HELMET",            "GLACITE_CHESTPLATE",            "GLACITE_LEGGINGS",            "GLACITE_BOOTS"]),
        "mineral":        ("Mineral Armor Set",          ["MINERAL_HELMET",         "MINERAL_CHESTPLATE",        "MINERAL_LEGGINGS",        "MINERAL_BOOTS"]),
        "glossy mineral": ("Glossy Mineral Armor Set", ["GLOSSY_MINERAL_HELMET",   "GLOSSY_MINERAL_CHESTPLATE", "GLOSSY_MINERAL_LEGGINGS", "GLOSSY_MINERAL_BOOTS"]),
        # ── Dungeons — Wither ──
        "necron":    ("Necron Armor Set",           ["POWER_WITHER_HELMET",       "POWER_WITHER_CHESTPLATE",       "POWER_WITHER_LEGGINGS",       "POWER_WITHER_BOOTS"]),
        "storm":     ("Storm Armor Set",            ["WISE_WITHER_HELMET",        "WISE_WITHER_CHESTPLATE",        "WISE_WITHER_LEGGINGS",        "WISE_WITHER_BOOTS"]),
        "aurora":    ("Aurora Armor Set",           ["AURORA_HELMET",             "AURORA_CHESTPLATE",             "AURORA_LEGGINGS",             "AURORA_BOOTS"]),
        "terror":    ("Terror Armor Set",           ["TERROR_HELMET",             "TERROR_CHESTPLATE",             "TERROR_LEGGINGS",             "TERROR_BOOTS"]),
        "maxor":     ("Maxor Armor Set",            ["SPEED_WITHER_HELMET",       "SPEED_WITHER_CHESTPLATE",       "SPEED_WITHER_LEGGINGS",       "SPEED_WITHER_BOOTS"]),
        "goldor":    ("Goldor Armor Set",           ["TANK_WITHER_HELMET",        "TANK_WITHER_CHESTPLATE",        "TANK_WITHER_LEGGINGS",        "TANK_WITHER_BOOTS"]),
        # ── Dungeons — other ──
        "shadow":    ("Shadow Assassin Armor Set",  ["SHADOW_ASSASSIN_HELMET",    "SHADOW_ASSASSIN_CHESTPLATE",    "SHADOW_ASSASSIN_LEGGINGS",    "SHADOW_ASSASSIN_BOOTS"]),
        "holy":      ("Holy Dragon Armor Set",      ["HOLY_DRAGON_HELMET",        "HOLY_DRAGON_CHESTPLATE",        "HOLY_DRAGON_LEGGINGS",        "HOLY_DRAGON_BOOTS"]),
        # ── Dragon armor ──
        "superior":  ("Superior Dragon Armor Set",  ["SUPERIOR_DRAGON_HELMET",    "SUPERIOR_DRAGON_CHESTPLATE",   "SUPERIOR_DRAGON_LEGGINGS",    "SUPERIOR_DRAGON_BOOTS"]),
        "strong":    ("Strong Dragon Armor Set",    ["STRONG_DRAGON_HELMET",      "STRONG_DRAGON_CHESTPLATE",     "STRONG_DRAGON_LEGGINGS",      "STRONG_DRAGON_BOOTS"]),
        "young":     ("Young Dragon Armor Set",     ["YOUNG_DRAGON_HELMET",       "YOUNG_DRAGON_CHESTPLATE",      "YOUNG_DRAGON_LEGGINGS",       "YOUNG_DRAGON_BOOTS"]),
        "old":       ("Old Dragon Armor Set",       ["OLD_DRAGON_HELMET",         "OLD_DRAGON_CHESTPLATE",        "OLD_DRAGON_LEGGINGS",         "OLD_DRAGON_BOOTS"]),
        "unstable":  ("Unstable Dragon Armor Set",  ["UNSTABLE_DRAGON_HELMET",    "UNSTABLE_DRAGON_CHESTPLATE",   "UNSTABLE_DRAGON_LEGGINGS",    "UNSTABLE_DRAGON_BOOTS"]),
        "wise":      ("Wise Dragon Armor Set",      ["WISE_DRAGON_HELMET",        "WISE_DRAGON_CHESTPLATE",       "WISE_DRAGON_LEGGINGS",        "WISE_DRAGON_BOOTS"]),
        "protector": ("Protector Dragon Armor Set", ["PROTECTOR_DRAGON_HELMET",   "PROTECTOR_DRAGON_CHESTPLATE",  "PROTECTOR_DRAGON_LEGGINGS",   "PROTECTOR_DRAGON_BOOTS"]),
        # ── Slayer / combat ──
        "mastiff":   ("Mastiff Armor Set",          ["MASTIFF_HELMET",            "MASTIFF_CHESTPLATE",           "MASTIFF_LEGGINGS",            "MASTIFF_BOOTS"]),
        "tarantula": ("Tarantula Armor Set",        ["TARANTULA_HELMET",          "TARANTULA_CHESTPLATE",         "TARANTULA_LEGGINGS",          "TARANTULA_BOOTS"]),
        "hollow":    ("Hollow Armor Set",           ["HOLLOW_HELMET",             "HOLLOW_CHESTPLATE",            "HOLLOW_LEGGINGS",             "HOLLOW_BOOTS"]),
        "fervor":    ("Fervor Armor Set",           ["FERVOR_HELMET",             "FERVOR_CHESTPLATE",            "FERVOR_LEGGINGS",             "FERVOR_BOOTS"]),
    }
    # Piece-type tokens — if any of these appear, it's a single-piece request, not a full set
    _PIECE_TOKENS = {"helmet", "chestplate", "leggings", "boots"}

    async def _handle_hypermax_question(self, question: str) -> str | None:
        """Detect hypermaxed/maxed item questions and return full upgrade cost breakdown."""
        q = question.lower()
        hypermax_kws = ["hypermaxed", "hypermax", "hyper max", "maxed out", "fully maxed",
                        "max out", "fully upgraded", "max price", "max cost"]
        if not any(kw in q for kw in hypermax_kws):
            return None

        # Normalize query: remove apostrophes/punctuation for matching
        # Tokenize question — strip possessives so "divan's" → "divan"
        q_tokens = re.sub(r"'s?\b", "", q)
        q_tokens = re.sub(r"[^a-z0-9\s]", "", q_tokens).split()
        # Normalised set for set/piece token matching — strip trailing 's' so "divans" matches "divan"
        q_tokens_norm = {t.rstrip("s") if len(t) > 4 else t for t in q_tokens}

        # ── Mixed 3/4 set — check FIRST so it isn't swallowed by single-piece match ──
        if re.search(r'3\s*/\s*4', q):
            # Split at "with" so we only look for the base set BEFORE "with"
            # and the replacement piece AFTER "with"
            split_parts = re.split(r'\bwith\b', q, maxsplit=1)
            q_before = split_parts[0]
            q_after  = split_parts[1] if len(split_parts) > 1 else ""

            tokens_before = re.sub(r"[^a-z0-9\s]", "", re.sub(r"'s?\b", "", q_before)).split()
            tokens_before_norm = {t.rstrip("s") if len(t) > 4 else t for t in tokens_before}
            tokens_after = re.sub(r"[^a-z0-9\s]", "", re.sub(r"'s?\b", "", q_after)).split()

            base_set_name  = None
            base_piece_ids = None
            # Sort by token length descending so "glossy mineral" matches before "mineral"
            for st, (sn, ids) in sorted(self.ITEM_SET_MAP.items(), key=lambda x: -len(x[0])):
                if all(w in tokens_before_norm for w in st.split()):
                    base_set_name  = sn
                    base_piece_ids = list(ids)
                    break

            rep_id   = None
            rep_slot = None
            SLOT_IDX = {"helmet": 0, "chestplate": 1, "leggings": 2, "boots": 3}
            if base_piece_ids:
                for iname, iid in self.ITEM_UPGRADE_MAP.items():
                    iname_words = iname.split()
                    if (iid not in base_piece_ids
                            and all(any(t.startswith(nw) for t in tokens_after) for nw in iname_words)):
                        rep_id = iid
                        for slot_word, idx in SLOT_IDX.items():
                            if slot_word in iname:
                                rep_slot = idx
                                break
                        if rep_slot is None:
                            rep_slot = 0
                        break

            if base_piece_ids and rep_id is not None and rep_slot is not None:
                pieces = list(base_piece_ids)
                pieces[rep_slot] = rep_id
                slot_labels = ["Helmet", "Chestplate", "Leggings", "Boots"]

                lbin = await self.hypixel.get_lowest_bin()
                item_price = lbin.get(rep_id, 0) or lbin.get(pieces[0], 0)
                reforge, stone_prices = await self._resolve_reforge(question, rep_id, item_price)
                stone_id     = reforge["stone"] if reforge else None
                reforge_name = reforge["name"]  if reforge else None

                results = await asyncio.gather(*[
                    self.hypixel.get_hypermaxed_price(pid, reforge_stone_id=stone_id)
                    for pid in pieces
                ])
                excluded = self._build_excluded(q, reforge_name)
                rep_display  = next((n.title() for n, i in self.ITEM_UPGRADE_MAP.items() if i == rep_id), rep_id.replace("_", " ").title())
                base_display = base_set_name.replace(" Armor Set", "")
                title = f"3/4 {base_display} + {rep_display}"
                lines, grand_total = self._format_set_hypermax(
                    results, pieces, excluded, title, reforge, reforge_name
                )
                return "\n".join(lines)

        for name, item_id in sorted(self.ITEM_UPGRADE_MAP.items(), key=lambda x: -len(x[0])):
            name_words = name.split()
            # All words in the item name must appear in the question (prefix match for plurals)
            if all(any(qt.startswith(nw) for qt in q_tokens) for nw in name_words):
                # ── Reforge selection (explicit name wins over scoring) ──────
                lbin = await self.hypixel.get_lowest_bin()
                item_price = lbin.get(item_id, 0)
                reforge, stone_prices = await self._resolve_reforge(question, item_id, item_price)
                stone_id     = reforge["stone"] if reforge else None
                reforge_name = reforge["name"]  if reforge else None

                result = await self.hypixel.get_hypermaxed_price(item_id, reforge_stone_id=stone_id)
                if not result:
                    return "Couldn't fetch upgrade prices right now, try again."

                excluded = self._build_excluded(q, reforge_name)

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
                        lines.append(f"  {label_fmt}: {data['total']:,.0f}")
                        for detail in data.get("details", []):
                            lines.append(f"    ↳ {detail}")
                        continue
                    elif label == "essence_stars":
                        etype = data.get("essence_type", "?")
                        per_star = data.get("per_star", [])
                        star_detail = " + ".join(str(a) for a in per_star)
                        label_fmt = f"5 Stars ({etype.title()} Essence ×{data['qty']})"
                        lines.append(f"  {label_fmt}: {data['total']:,.0f} ({data['unit']:,.0f}/essence)")
                        lines.append(f"    ↳ Per star: {star_detail}")
                        continue
                    elif label == "master_stars":
                        ms_prices = data.get("prices", [])
                        lines.append(f"  Master Stars (×5): {data['total']:,.0f}")
                        ms_names = ["1st", "2nd", "3rd", "4th", "5th"]
                        for mn, mp in zip(ms_names, ms_prices):
                            lines.append(f"    ↳ {mn}: {mp:,.0f}")
                        continue
                    elif label == "enchantments":
                        lines.append(f"  Enchantments (×{data['qty']}): {data['total']:,.0f}")
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

        # ── Full armor set match ─────────────────────────────────────────────
        # If no individual piece matched, check if a set name is in the question
        # and no piece-type word (helmet/chestplate/etc.) was specified
        if not any(pt in q_tokens_norm for pt in self._PIECE_TOKENS):
            for set_token, (set_name, piece_ids) in sorted(self.ITEM_SET_MAP.items(), key=lambda x: -len(x[0])):
                if all(w in q_tokens_norm for w in set_token.split()):
                    # Use first piece (helmet) to pick reforge — same reforge applies to all
                    lbin = await self.hypixel.get_lowest_bin()
                    item_price = lbin.get(piece_ids[0], 0)
                    reforge, stone_prices = await self._resolve_reforge(question, piece_ids[0], item_price)
                    stone_id     = reforge["stone"] if reforge else None
                    reforge_name = reforge["name"]  if reforge else None

                    # Calculate all 4 pieces in parallel
                    results = await asyncio.gather(*[
                        self.hypixel.get_hypermaxed_price(pid, reforge_stone_id=stone_id)
                        for pid in piece_ids
                    ])

                    excluded = self._build_excluded(q, reforge_name)
                    lines, grand_total = self._format_set_hypermax(
                        results, piece_ids, excluded, set_name, reforge, reforge_name
                    )
                    return "\n".join(lines)

        # ── Dynamic item lookup — any item in the game ───────────────────────
        # Strip hypermax keywords and try to find any Hypixel item in the question
        q_stripped = q
        for kw in ["hypermaxed", "hypermax", "hyper max", "maxed out", "fully maxed",
                   "max out", "fully upgraded", "max price", "max cost"]:
            q_stripped = q_stripped.replace(kw, "")
        dyn_stopwords = {"what", "is", "the", "a", "an", "of", "for", "how", "much",
                         "does", "cost", "price", "worth", "my", "i", "to", "and", "or",
                         "armor", "weapon", "item", "gear", "set", "piece"}
        dyn_words = [w for w in re.sub(r"[^\w\s]", "", q_stripped).split()
                     if w not in dyn_stopwords and len(w) > 2]

        found_item = None
        # Try longest phrases first; single words require 5+ chars to avoid false matches
        for length in range(min(4, len(dyn_words)), 0, -1):
            for i in range(len(dyn_words) - length + 1):
                phrase = " ".join(dyn_words[i:i + length])
                if length == 1 and len(phrase) < 5:
                    continue
                try:
                    item = await self.hypixel.find_item(phrase)
                    if item:
                        found_item = item
                        break
                except Exception:
                    pass
            if found_item:
                break

        if found_item:
            dyn_id   = found_item["id"]
            dyn_name = found_item.get("name", dyn_id.replace("_", " ").title())

            lbin = await self.hypixel.get_lowest_bin()
            item_price = lbin.get(dyn_id, 0)
            reforge, stone_prices = await self._resolve_reforge(question, dyn_id, item_price)
            stone_id     = reforge["stone"] if reforge else None
            reforge_name = reforge["name"]  if reforge else None

            result = await self.hypixel.get_hypermaxed_price(dyn_id, reforge_stone_id=stone_id)
            if result:
                excluded = self._build_excluded(q, reforge_name)

                total = sum(v["total"] for k, v in result["breakdown"].items() if k not in excluded)
                base_price = result["breakdown"]["base_item"]["total"]
                base_note  = f"{base_price:,.0f} (lowest BIN)" if base_price > 0 else "price unavailable — bid-only AH item, add manually"
                excl_note  = f" *(excl. {', '.join(e.replace('_',' ') for e in excluded)})*" if excluded else ""

                if reforge and "reforge_stone" not in excluded:
                    stat_str = ", ".join(f"+{v} {k.replace('_',' ').title()}" for k, v in reforge["stats"].items())
                    afford_warn = " ⚠️ expensive relative to item" if not reforge["affordable"] else ""
                    reforge_label = f" + **{reforge_name.title()}** reforge ({stat_str}){afford_warn}"
                else:
                    reforge_label = ""

                lines = [
                    f"**Hypermaxed {dyn_name}**{reforge_label}{excl_note} — Total: **{total:,.0f} coins**\n",
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

        # Hypermax keywords were present but no item matched
        return "I don't recognize that item for a hypermax calculation. Try specifying a piece or set name (e.g. 'hypermax divan helmet', 'hypermax necron armor')."

    def _format_set_hypermax(
        self, results: list, piece_ids: list, excluded: set,
        title: str, reforge: dict | None, reforge_name: str | None,
    ) -> tuple[list[str], int]:
        """Format a multi-piece hypermax result with per-piece AND aggregated cost breakdown."""
        piece_names = ["Helmet", "Chestplate", "Leggings", "Boots"]

        # Aggregate costs across all pieces by category
        agg: dict[str, float] = {}
        grand_total = 0
        piece_totals = []
        for r, pname in zip(results, piece_names):
            if not r:
                piece_totals.append((pname, 0))
                continue
            ptotal = 0
            for k, v in r["breakdown"].items():
                if k in excluded:
                    continue
                ptotal += v["total"]
                agg[k] = agg.get(k, 0) + v["total"]
            grand_total += ptotal
            piece_totals.append((pname, ptotal))

        # Header
        if reforge and "reforge_stone" not in excluded:
            stat_str = ", ".join(f"+{v} {k.replace('_',' ').title()}" for k, v in reforge["stats"].items())
            afford_warn = " ⚠️ expensive relative to item" if not reforge["affordable"] else ""
            reforge_label = f" + **{reforge_name.title()}** reforge (×4, {stat_str}){afford_warn}"
        else:
            reforge_label = ""
        excl_note = f" *(excl. {', '.join(e.replace('_',' ') for e in excluded)})*" if excluded else ""
        lines = [f"**Hypermaxed {title}**{reforge_label}{excl_note} — Total: **{grand_total:,.0f} coins**\n"]

        # Per-piece totals
        for pname, ptotal in piece_totals:
            lines.append(f"  {pname}: {ptotal:,.0f}")

        # Aggregated cost breakdown
        num_pieces = sum(1 for _, pt in piece_totals if pt > 0)
        lines.append("")
        lines.append("**Cost Breakdown (all pieces combined):**")
        # Friendly labels and ordering
        LABEL_ORDER = ["base_item", "hot_potato_books", "fuming_potato_books", "recombobulator_3000",
                       "art_of_peace", "essence_stars", "master_stars", "enchantments",
                       "slot_unlocking", "reforge_stone"]
        seen = set()
        # Find essence type from any result that has it
        essence_type = None
        for r in results:
            if r and "essence_stars" in r.get("breakdown", {}):
                essence_type = r["breakdown"]["essence_stars"].get("essence_type")
                break
        for key in LABEL_ORDER:
            if key in agg and agg[key] > 0 and key not in excluded:
                seen.add(key)
                label = key.replace("_", " ").title()
                if key == "reforge_stone" and reforge_name:
                    label = f"{reforge_name.title()} Reforge Stone ×{num_pieces}"
                elif key in ("hot_potato_books", "fuming_potato_books"):
                    label = f"{label} ×{num_pieces * (10 if 'hot' in key else 5)}"
                elif key == "recombobulator_3000":
                    label = f"{label} ×{num_pieces}"
                elif key == "base_item":
                    label = f"Base Items (×{num_pieces})"
                elif key == "essence_stars":
                    etype = (essence_type or "?").title()
                    label = f"5 Stars ({etype} Essence) ×{num_pieces}"
                elif key == "master_stars":
                    label = f"Master Stars (×5) ×{num_pieces}"
                elif key == "enchantments":
                    label = f"Enchantments ×{num_pieces}"
                lines.append(f"  {label}: {agg[key]:,.0f}")
        # Any remaining keys (gem types, etc.)
        for key, val in agg.items():
            if key not in seen and val > 0 and key not in excluded:
                label = key.replace("_", " ").title()
                lines.append(f"  {label}: {val:,.0f}")

        return lines, grand_total

    def _build_excluded(self, q: str, reforge_name: str | None = None) -> set[str]:
        """Parse exclusion keywords from the question. Returns set of breakdown keys to skip."""
        excluded: set[str] = set()
        # "no books" / "without books" → exclude both HPB and FHPB
        if re.search(r'\bno\s+books?\b|\bwithout\s+books?\b|\bno\s+(hpb|potato books?)\b', q):
            excluded |= {"hot_potato_books", "fuming_potato_books"}
        single = {
            "hot potato":       "hot_potato_books",
            "hpb":              "hot_potato_books",
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
            "stars":            "essence_stars",
            "essence":          "essence_stars",
            "master star":      "master_stars",
            "enchant":          "enchantments",
            "enchants":         "enchantments",
            "enchantment":      "enchantments",
        }
        # "no stars" excludes both essence stars and master stars
        if re.search(r'\bno\s+stars?\b|\bwithout\s+stars?\b', q):
            excluded |= {"essence_stars", "master_stars"}
        for phrase, key in single.items():
            if phrase in q:
                excluded.add(key)
        if reforge_name and reforge_name in q:
            excluded.add("reforge_stone")
        return excluded

    async def _resolve_reforge(self, question: str, item_id: str, item_price: float) -> tuple[dict | None, dict]:
        """
        Resolve the best reforge for an item, respecting explicit user requests.
        Returns (reforge_dict | None, stone_prices_dict).
        Explicit reforge names in the question always win over pick_reforge scoring.
        """
        from reforges import REFORGES
        stone_ids = list({d["stone"] for d in REFORGES.values() if d.get("stone")})
        prices_list = await asyncio.gather(
            *[self.hypixel.get_reforge_stone_price(sid) for sid in stone_ids]
        )
        stone_prices = dict(zip(stone_ids, prices_list))

        # Explicit reforge name in question overrides scoring
        explicit = self._detect_explicit_reforge(question)
        if explicit:
            if explicit["stone"]:
                explicit["stone_price"] = stone_prices.get(explicit["stone"], 0)
            return explicit, stone_prices

        desired_stat = self._detect_desired_stat(question)
        reforge = pick_reforge(item_id, desired_stat=desired_stat,
                               item_price=item_price, stone_prices=stone_prices)
        return reforge, stone_prices

    def _detect_explicit_reforge(self, question: str) -> dict | None:
        """
        Detect if the user explicitly names a reforge (e.g. 'with jaded', 'use withered').
        Returns the full reforge dict if found, None otherwise.
        Explicit requests bypass the affordability penalty entirely.
        """
        from reforges import REFORGES
        q = question.lower()
        TRIGGER_WORDS = r"(?:with|use|using|apply|applying|want|reforge(?:d)?\s+(?:with|to|as)?)"
        for key, data in REFORGES.items():
            clean = key.replace("_weapon", "")
            # Match "with jaded", "use jaded", "jaded reforge", "reforge with jaded"
            if re.search(rf"(?:{TRIGGER_WORDS}\s+{re.escape(clean)}|{re.escape(clean)}\s+reforge)", q):
                return {
                    "name":        clean,
                    "stone":       data["stone"],
                    "stone_price": 0,  # filled in by caller once stone prices are fetched
                    "stats":       data["stats"],
                    "note":        data["note"],
                    "affordable":  True,   # user explicitly chose it — skip affordability check
                    "score":       999,
                }
        return None

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

    # ── Fast path: best reforge question ──────────────────────────────────────
    async def _handle_reforge_question(self, question: str) -> str | None:
        """Detect 'best reforge for X' and return directly without AI."""
        q = question.lower()
        # Must contain "reforge" and either "best" or "what" or item name
        if "reforge" not in q:
            return None
        # Must be asking for a recommendation, not a general question about reforging
        if not any(w in q for w in ["best", "what", "which", "recommend", "should", "for"]):
            return None

        # Find the item they're asking about
        matched_id = None
        matched_name = None
        for iname, iid in sorted(self.ITEM_UPGRADE_MAP.items(), key=lambda x: -len(x[0])):
            iname_words = iname.split()
            q_words = re.sub(r"[^a-z0-9\s]", "", q).split()
            q_norm = {w.rstrip("s") if len(w) > 4 else w for w in q_words}
            if all(any(qt.startswith(nw) for qt in q_norm) for nw in iname_words):
                matched_id = iid
                matched_name = iname.title()
                break

        if not matched_id:
            return None

        try:
            lbin = await self.hypixel.get_lowest_bin()
            item_price = lbin.get(matched_id, 0)
            reforge, stone_prices = await self._resolve_reforge(question, matched_id, item_price)
            if not reforge:
                return f"No suitable reforge found for **{matched_name}**."

            stat_str = ", ".join(f"+{v} {k.replace('_', ' ').title()}" for k, v in reforge["stats"].items())
            stone_note = ""
            if reforge.get("stone"):
                sp = reforge.get("stone_price", 0)
                stone_name = reforge["stone"].replace("_", " ").title()
                stone_note = f"\n- Reforge stone: **{stone_name}** (~{sp:,.0f} coins)" if sp else f"\n- Reforge stone: **{stone_name}**"
            afford = "" if reforge["affordable"] else "\n- ⚠️ Stone is expensive relative to item value"

            return (
                f"**Best reforge for {matched_name}: {reforge['name'].title()}**\n"
                f"- Stats: {stat_str}"
                f"{stone_note}{afford}\n"
                f"- {reforge.get('note', '')}"
            )
        except Exception as e:
            print(f"[reforge fast path error] {e}")
            return None

    # ── Fast path: recipe/craft cost ──────────────────────────────────────────
    async def _handle_recipe_question(self, question: str) -> str | None:
        """Detect recipe/craft questions and return cost breakdown without AI."""
        q = question.lower()
        if not any(w in q for w in ["recipe", "craft", "how to make", "ingredients", "cost to craft"]):
            return None
        # Don't match if it's a vague question like "what should I craft"
        if any(w in q for w in ["should", "best", "what to", "recommend"]):
            return None

        # Find item
        item = None
        stopwords = {"what", "is", "the", "a", "an", "recipe", "for", "craft", "how", "to",
                     "make", "ingredients", "of", "get", "whats", "me", "tell", "about", "cost"}
        words = re.sub(r"[^\w\s']", "", q).split()
        candidates = set()
        for i in range(len(words)):
            for j in range(i + 1, min(i + 5, len(words) + 1)):
                phrase = " ".join(words[i:j])
                if not all(w in stopwords for w in phrase.split()) and len(phrase) > 3:
                    candidates.add(phrase)

        for phrase in sorted(candidates, key=len, reverse=True):
            found = await self.hypixel.find_item(phrase)
            if found:
                item = found
                break

        if not item:
            return None

        recipe = self.hypixel.get_recipe(item["id"])
        if not recipe:
            return None

        try:
            item_name = item.get("name", item["id"].replace("_", " ").title())
            lines = [f"**{item_name}** — Craft Cost"]

            total_craft = 0
            for mat_id, count in recipe["i"].items():
                baz = await self.hypixel.search_bazaar(mat_id.replace("_", " "))
                if baz:
                    price = baz[0]["buy"]
                    subtotal = price * count
                    total_craft += subtotal
                    mat_name = mat_id.replace("_", " ").title()
                    lines.append(f"- {count}x **{mat_name}**: {subtotal:,.0f} coins ({price:,.0f} each)")
                else:
                    p, src = await self.hypixel.get_item_price(mat_id, allow_auction=True)
                    if p:
                        subtotal = p * count
                        total_craft += subtotal
                        mat_name = mat_id.replace("_", " ").title()
                        lines.append(f"- {count}x **{mat_name}**: {subtotal:,.0f} coins ({src})")
                    else:
                        mat_name = mat_id.replace("_", " ").title()
                        lines.append(f"- {count}x **{mat_name}**: price unavailable")

            if total_craft > 0:
                lines.append(f"\n**Total craft cost: {total_craft:,.0f} coins**")

                # Compare to buy price
                buy_p, buy_src = await self.hypixel.get_item_price(item["id"], allow_auction=True)
                if buy_p:
                    diff = buy_p - total_craft
                    if diff > 0:
                        lines.append(f"Buy price: {buy_p:,.0f} ({buy_src}) — crafting saves **{diff:,.0f}** coins")
                    else:
                        lines.append(f"Buy price: {buy_p:,.0f} ({buy_src}) — buying is **{abs(diff):,.0f}** cheaper")

            return "\n".join(lines)
        except Exception as e:
            print(f"[recipe fast path error] {e}")
            return None

    # ── Fast path: simple player stat lookup ──────────────────────────────────
    def _handle_simple_stat_question(self, question: str, summary: str) -> str | None:
        """Answer simple stat questions from linked player data without AI."""
        q = question.lower().strip()

        # Patterns: "what's my X", "what is my X", "my X level", "whats my X"
        stat_match = re.search(
            r"(?:what(?:'?s| is) my |my |show (?:me )?my )([a-z\s]+?)(?:\s*level|\s*lvl|\s*xp|\?|$)",
            q
        )
        if not stat_match:
            return None

        stat_name = stat_match.group(1).strip()

        # Map user terms to what appears in the summary
        STAT_MAP = {
            "cata": "Catacombs", "catacombs": "Catacombs", "dungeon": "Catacombs",
            "mining": "Mining", "farming": "Farming", "combat": "Combat",
            "foraging": "Foraging", "fishing": "Fishing", "enchanting": "Enchanting",
            "alchemy": "Alchemy", "taming": "Taming", "carpentry": "Carpentry",
            "social": "Social", "runecrafting": "Runecrafting",
            "hotm": "HotM", "heart of the mountain": "HotM",
            "skill average": "Skill avg", "sa": "Skill avg",
            "skyblock": "Skyblock Level", "sb": "Skyblock Level",
            "slayer": "Slayer",
            "magic power": "Magic Power", "mp": "Magic Power",
            "networth": "Networth", "nw": "Networth",
        }

        search_key = STAT_MAP.get(stat_name)
        if not search_key:
            return None

        # Search through the summary for the matching line
        for line in summary.split("\n"):
            if search_key.lower() in line.lower():
                # For skills line, extract just the relevant skill
                if search_key in ("Mining", "Farming", "Combat", "Foraging", "Fishing",
                                   "Enchanting", "Alchemy", "Taming", "Carpentry",
                                   "Social", "Runecrafting") and "Skills:" in line:
                    # Extract "Mining 45" from "Skills: Mining 45 | Combat 38 | ..."
                    skill_match = re.search(rf'{search_key}\s+(\d+)', line)
                    if skill_match:
                        return f"Your **{search_key}** level is **{skill_match.group(1)}**"
                    return None

                # For other stats, return the whole line cleaned up
                clean_line = line.strip()
                if clean_line.startswith("==="): continue  # skip header
                return f"**{clean_line}**"

        return None

    # Known armor set ID prefixes
    ARMOR_SETS = {
        "armor of divan": "ARMOR_OF_DIVAN",
        "glacite": "GLACITE",
        "glossy mineral": "GLOSSY_MINERAL",
        "mineral": "MINERAL",
        "aurora": "AURORA",
        "terror": "TERROR",
        "fervor": "FERVOR",
        "crimson": "CRIMSON",
        "necron": "POWER_WITHER",
        "necrons": "POWER_WITHER",
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
        "hollow": "HOLLOW",
        "goldor": "TANK_WITHER",
        "storm": "WISE_WITHER",
        "maxor": "SPEED_WITHER",
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
                        prices.pop("has_auction", False)
                        total = prices.pop("total")
                        pieces = " | ".join(
                            f"{slot}: {data['price']:,.0f}" for slot, data in prices.items()
                            if isinstance(data, dict)
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

    async def get_response(self, question: str, discord_user_id: int = None, ingame: bool = False, mc_ign: str = None) -> str:
        async with self.semaphore:
            price_question = self._needs_live_data(question)

            # --- Linked player context (auto-fetch if linked) ---
            linked_summary = ""

            # In-game: use mc_ign directly
            if mc_ign:
                try:
                    pdata = await self.hypixel.get_player_data(mc_ign)
                    if pdata and pdata.get("summary"):
                        linked_summary = pdata["summary"]
                except Exception:
                    pass

            # Discord: use discord_user_id to look up linked account
            elif discord_user_id:
                linked_ign = get_linked_username(discord_user_id)
                if linked_ign:
                    try:
                        linked_uuid = get_linked_uuid(discord_user_id)
                        pdata = await self.hypixel.get_player_data(linked_ign, uuid=linked_uuid)
                        if pdata and pdata.get("summary"):
                            linked_summary = pdata["summary"]
                            # Update cached username if it changed (name change)
                            if pdata.get("username") and pdata["username"].lower() != linked_ign.lower():
                                from user_links import update_username
                                update_username(discord_user_id, pdata["username"])
                    except Exception:
                        pass  # silently skip if fetch fails

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

            # --- Fast path: bare item name lookup (e.g. "!ai enchanted diamond") ---
            # Triggered when the question is 1-5 words with no verb/question structure
            if os.getenv("HYPIXEL_API_KEY"):
                _NON_ITEM_WORDS = {"what", "why", "how", "when", "where", "who", "is", "are",
                                   "can", "do", "does", "should", "would", "best", "guide",
                                   "tell", "explain", "help", "tips", "i", "my", "the",
                                   "hi", "hello", "hey", "sup", "yo", "test", "testing",
                                   "thanks", "thank", "ty", "thx", "ok", "okay", "lol",
                                   "lmao", "bruh", "nice", "cool", "yes", "no", "yeah",
                                   "nah", "please", "pls", "stop", "start", "go", "bye",
                                   "good", "bad", "idk", "wdym", "huh", "hmm", "oh",
                                   "ping", "work", "working", "works", "broken", "fix"}
                q_words = re.sub(r"[^\w\s]", "", question.lower()).split()
                if 1 <= len(q_words) <= 5 and not any(w in _NON_ITEM_WORDS for w in q_words):
                    item_phrase = " ".join(q_words)
                    try:
                        # Normalize q_words: strip trailing 's' from 5+ char words
                        # so "necrons" matches "necron", "divans" matches "divan", etc.
                        q_words_norm = {w.rstrip("s") if len(w) > 4 else w for w in q_words}

                        def _format_set_prices(aname, prices):
                            """Format set price result for display."""
                            if not prices:
                                return f"**{aname.title()} Set** — no price data available"
                            has_auction = prices.pop("has_auction", False)
                            total = prices.pop("total")
                            pieces = " | ".join(
                                f"{slot}: {data['price']:,.0f}" for slot, data in prices.items()
                                if isinstance(data, dict)
                            )
                            label = "AH estimate" if has_auction else "BIN"
                            return f"**{aname.title()} Set** — Total: **{total:,.0f}** coins ({label})\n  {pieces}"

                        # "X set" → armor set price lookup
                        if "set" in q_words:
                            set_words = [w for w in q_words_norm if w != "set" and w != "armor"]
                            for aname, prefix in sorted(self.ARMOR_SETS.items(), key=lambda x: -len(x[0])):
                                if all(w in set_words for w in aname.split()):
                                    prices = await self.hypixel.get_armor_set_prices(prefix)
                                    return _format_set_prices(aname, prices)

                        # If query matches a known armor set name and has NO piece-type word,
                        # treat it as an implicit set query (e.g. "glossy mineral" → full set)
                        _PIECE_WORDS = {"helmet", "chestplate", "leggings", "boots", "helm", "chest", "legs", "boot"}
                        if not any(w in _PIECE_WORDS for w in q_words):
                            for aname, prefix in sorted(self.ARMOR_SETS.items(), key=lambda x: -len(x[0])):
                                aname_words = aname.split()
                                if all(w in q_words_norm for w in aname_words):
                                    prices = await self.hypixel.get_armor_set_prices(prefix)
                                    return _format_set_prices(aname, prices)

                        # Check ITEM_UPGRADE_MAP — exact known item IDs, no fuzzy guessing
                        matched_iid = None
                        matched_display = None
                        for iname, iid in sorted(self.ITEM_UPGRADE_MAP.items(), key=lambda x: -len(x[0])):
                            iname_words = iname.split()
                            if all(nw in q_words_norm for nw in iname_words):
                                matched_iid = iid
                                matched_display = iname.title()
                                break
                        if matched_iid:
                            p, src = await self.hypixel.get_item_price(matched_iid, allow_auction=True)
                            if p:
                                label = "lowest BIN" if src == "bin" else "AH estimate"
                                return f"**{matched_display}** — **{p:,.0f}** coins ({label})"
                            else:
                                return f"**{matched_display}** — no price data available"

                        # Try bazaar first (fast), then AH
                        baz_match = await self._find_best_bazaar_match(item_phrase)
                        if baz_match:
                            return (f"**{baz_match['id'].replace('_', ' ').title()}** — "
                                    f"instabuy **{baz_match['buy']:,.1f}** | instasell **{baz_match['sell']:,.1f}** coins")
                        ah_results = await self.hypixel.search_ah(item_phrase)
                        if ah_results:
                            r = ah_results[0]
                            if r["source"].startswith("Lowest BIN"):
                                return f"**{r['name']}** — **{r['price']:,.0f}** coins (lowest BIN)"
                            return (f"**{r['name']}** — median **{r['price']:,.0f}** | "
                                    f"low **{r.get('low', r['price']):,.0f}** | high **{r.get('high', r['price']):,.0f}** coins (AH)")
                        # Try unified price lookup via item ID
                        found = await self.hypixel.find_item(item_phrase)
                        if found:
                            p = await self.hypixel.get_item_price(found["id"])
                            if p:
                                return f"**{found.get('name', found['id'])}** — **{p:,.0f}** coins"
                    except Exception:
                        pass  # fall through to AI

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

            # --- Fast path: "best reforge for X" — direct code, no AI ---
            if os.getenv("HYPIXEL_API_KEY"):
                reforge_result = await self._handle_reforge_question(question)
                if reforge_result:
                    return reforge_result

            # --- Fast path: recipe/craft cost — direct code, no AI ---
            if os.getenv("HYPIXEL_API_KEY"):
                recipe_result = await self._handle_recipe_question(question)
                if recipe_result:
                    return recipe_result

            # --- Fast path: simple player stat lookup for linked users ---
            if linked_summary:
                stat_result = self._handle_simple_stat_question(question, linked_summary)
                if stat_result:
                    return stat_result

            # --- Fast path: SkyBlock year / zodiac cycle ---
            q = question.lower()
            if any(kw in q for kw in ["current year", "currant year", "skyblock year", "what year", "whats the year", "sb year", "next year"]):
                import time as _time
                # SkyBlock epoch: June 11, 2019 at 4:55 PM UTC. Each year = 124 hours (446400 seconds).
                sb_epoch = 1560275700
                sb_year = int((_time.time() - sb_epoch) / 446400) + 1
                year_start = sb_epoch + (sb_year - 1) * 446400
                year_end = year_start + 446400
                import datetime
                time_left = year_end - _time.time()
                hours_left = max(0, int(time_left / 3600))
                days_left = hours_left // 24
                hrs_rem = hours_left % 24
                if "next year" in q or "next skyblock" in q:
                    return f"The current SkyBlock year is **Year {sb_year}**. **Year {sb_year + 1}** starts in ~**{days_left}d {hrs_rem}h**."
                return f"The current SkyBlock year is **Year {sb_year}**. Year {sb_year + 1} starts in ~{days_left}d {hrs_rem}h."

            # Known SkyBlock yearly event cycle: use known anchor points to calculate
            # Known: Year 476 = Witch, cycle is 12 years
            _YEARLY_EVENTS = {
                "pig": 0, "seal": 1, "witch": 2,
                # Remaining 9 slots in the 12-year cycle are TBA/unknown
            }
            # Year 476 = Witch (offset 2), so Year 474 = Pig (offset 0) in this cycle
            _CYCLE_BASE = 474  # Year where offset 0 (Pig) falls
            _CYCLE_LEN = 12
            zodiac_match = None
            for name in _YEARLY_EVENTS:
                if f"year of the {name}" in q or f"year of {name}" in q:
                    zodiac_match = name
                    break
            if zodiac_match:
                import time as _time
                sb_epoch = 1560275700
                sb_year = int((_time.time() - sb_epoch) / 446400) + 1
                offset = _YEARLY_EVENTS[zodiac_match]
                # Find next year >= sb_year where (year - _CYCLE_BASE) % _CYCLE_LEN == offset
                current_pos = (sb_year - _CYCLE_BASE) % _CYCLE_LEN
                diff = (offset - current_pos) % _CYCLE_LEN
                next_year = sb_year + diff if diff > 0 else sb_year + _CYCLE_LEN
                if diff == 0:
                    return f"It is currently the **Year of the {zodiac_match.title()}** (Year {sb_year})! The next one will be Year {sb_year + _CYCLE_LEN}."
                else:
                    return f"The next **Year of the {zodiac_match.title()}** is **Year {next_year}** ({diff} SkyBlock years from now, ~{int(diff * 124 / 24)} real days)."

            # --- Fast path: Jerry's Workshop / Season of Jerry timing ---
            if any(kw in q for kw in ["jerry workshop", "jerrys workshop", "jerry's workshop",
                                       "season of jerry", "next jerry", "when jerry"]):
                import time as _time, datetime
                sb_epoch = 1560275700
                now = _time.time()
                sb_year = int((now - sb_epoch) / 446400) + 1
                year_start = sb_epoch + (sb_year - 1) * 446400
                # Late Winter = month 12 (last month). Day 24 = Season of Jerry start.
                # Late Winter day 1 = SB day (11*31)+1 = 342. Each SB day = 1200s.
                jerry_offset = (341 + 23) * 1200  # Late Winter 24th (day 364, 0-indexed 363)
                next_jerry = year_start + jerry_offset
                if next_jerry < now:
                    next_jerry += 446400  # next year
                time_left = next_jerry - now
                hours_left = max(0, int(time_left / 3600))
                days_left = hours_left // 24
                hrs_rem = hours_left % 24
                return (
                    f"**Jerry's Workshop** opens during Late Winter (last month of the SkyBlock year).\n"
                    f"**Season of Jerry** (defense event): Late Winter 24-26.\n"
                    f"Next one: ~**{days_left}d {hrs_rem}h** from now.\n"
                    f"- Workshop is in the Jerry's Island portal (Hub)\n"
                    f"- Contains: White/Green Gifts, Jerry NPC, unique items\n"
                    f"- Jerry mayor's Jerrypocalypse is a separate thing (special mayor perk)"
                )

            # --- Fast path: Shen's Auction timing ---
            if any(kw in q for kw in ["shen auction", "shens auction", "shen's auction", "next shen"]):
                import time as _time
                sb_epoch = 1560275700
                now = _time.time()
                sb_year = int((now - sb_epoch) / 446400) + 1
                # Each SB year = 446400 seconds. Late Spring 1st is roughly 25% through the year.
                year_start = sb_epoch + (sb_year - 1) * 446400
                # Late Spring 1st ≈ day 93 of 124 days. Each SB day = 1200s real. Late Spring = month 10 of 12.
                # SB months: Early Spring(1-3), Spring(4-6), Late Spring(7-9), Early Summer(10-12)...
                # Actually: 12 months, 31 days each = 372 SB days per year. Late Spring = month 6.
                # Late Spring day 1 = SB day (5*31)+1 = 156. Each SB day = 20 min real = 1200s.
                shen_offset = 155 * 1200  # Late Spring 1st (day 156, 0-indexed 155)
                next_shen = year_start + shen_offset
                if next_shen < now:
                    # Already passed this year, next year
                    next_shen += 446400
                import datetime
                shen_dt = datetime.datetime.fromtimestamp(next_shen, tz=datetime.timezone.utc)
                time_left = next_shen - now
                hours_left = int(time_left / 3600)
                days_left = hours_left // 24
                hrs_rem = hours_left % 24
                return (
                    f"**Shen's Auction** happens once per SkyBlock year on Late Spring 1st.\n"
                    f"Next one: ~**{days_left}d {hrs_rem}h** from now ({shen_dt.strftime('%b %d, %H:%M UTC')}).\n"
                    f"- Requires Museum Milestone 10 (regular) or 20 (Shen's Special)\n"
                    f"- Items: Artifact of Control (10/yr), Pandora's Box (20/yr), Shen's Regalia (40/yr)\n"
                    f"- Diaz mayor doubles available quantities"
                )

            # --- Fast path: Diana profit question — direct answer, no AI ---
            diana_profit_kws = ["diana profit", "diana coins", "diana money", "diana per hour",
                                "mythological profit", "mythological money", "mythological coins",
                                "1h of diana", "hour of diana", "diana making", "diana earn",
                                "diana income", "diana grind", "how much diana"]
            if any(kw in q for kw in diana_profit_kws) or ("diana" in q and any(w in q for w in ["profit", "money", "coins", "hour", "earn", "making", "income"])):
                return (
                    "**Diana Mythological Ritual Profit Rates:**\n"
                    "- **Common Griffin:** ~12M coins/hour (mostly Griffin Feathers)\n"
                    "- **Legendary Griffin (max setup):** 70-100M+ coins/hour\n"
                    "  - Main income: Chimera books (~100-200M each, 1/81 Inquisitor spawn, ~1% drop)\n"
                    "  - Daedalus Sticks (~2M each), Minos Relic (~50-60M), Ancient Claws, coin bags\n"
                    "- **Key factors:** Burrows/hour, Griffin rarity, Magic Find %, spade tier\n"
                    "- **Max setup:** Legendary/Mythic Griffin + Four-Eyed Fish, Daedalus Blade + Chimera V, "
                    "Deific Spade + Erudite reforge, Sorrow Armor, SkyHanni mod\n"
                    "- SkyHanni mod is practically mandatory (~80% efficiency boost from burrow tracking)"
                )

            # --- Fast path: live mayor/election data ---
            mayor_ctx = ""
            mayor_keywords = ["mayor", "current mayor", "election", "mayor perk",
                              "who is mayor", "whos mayor", "which mayor"]
            if any(kw in question.lower() for kw in mayor_keywords):
                try:
                    mayor_data = await self.hypixel.get_current_mayor()
                    if mayor_data:
                        lines = []
                        m = mayor_data.get("mayor")
                        if m:
                            lines.append(f"CURRENT MAYOR: {m['name']}")
                            for p in m.get("perks", []):
                                lines.append(f"  Perk: {p['name']} — {p['description']}")
                            minister = m.get("minister")
                            if minister:
                                mname = minister.get("name", "Unknown")
                                mperk = minister.get("perk", {})
                                mperk_name = mperk.get("name", "") if isinstance(mperk, dict) else ""
                                mperk_desc = mperk.get("description", "") if isinstance(mperk, dict) else ""
                                lines.append(f"  Minister: {mname} — {mperk_name}: {mperk_desc}")
                        candidates = mayor_data.get("candidates", [])
                        if candidates:
                            lines.append("\nCURRENT ELECTION CANDIDATES:")
                            for c in sorted(candidates, key=lambda x: x.get("votes", 0), reverse=True):
                                votes = c.get("votes", 0)
                                lines.append(f"  {c['name']}: {votes:,} votes")
                                for p in c.get("perks", []):
                                    lines.append(f"    - {p['name']}: {p['description']}")
                        mayor_ctx = "\n".join(lines)
                except Exception as e:
                    print(f"[mayor_ctx error] {e}")

            # --- Normal AI path ---
            live_ctx = ""
            ah_ctx = ""
            item_ctx = ""

            # Item/recipe lookup from Hypixel items API
            item_keywords = ["what is", "stats", "item info", "craft", "recipe", "how to make", "ingredients"]
            if any(kw in question.lower() for kw in item_keywords):
                try:
                    item_ctx = await self._build_item_context(question)
                except Exception as e:
                    print(f"[item_ctx error] {e}")

            if price_question:
                try:
                    live_ctx = await self._build_live_context(question)
                except Exception as e:
                    live_ctx = f"(Live price fetch failed: {e})"

            static_ctx = self.knowledge.get_relevant_knowledge(
                question, is_price_question=price_question
            )

            # --- Inject cached learned facts ---
            learned_ctx = ""
            try:
                facts = find_fact(question)
                if facts:
                    parts = []
                    for f in facts:
                        parts.append(f"Q: {f['question']}\nA: {f['answer']}")
                    learned_ctx = "\n\n".join(parts)
            except Exception:
                pass

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

            # Inject historical trend data if tracker has data
            hist_ctx = ""
            market_ctx = ""
            if self.tracker and price_question:
                # For investment/flip questions, inject full market analysis
                invest_words = ["invest", "investment", "flip", "money making", "hold", "profit",
                                "what to buy", "market", "trending"]
                if any(w in question.lower() for w in invest_words):
                    try:
                        market_ctx = self.tracker.format_market_analysis_for_ai()
                    except Exception:
                        pass
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
            # Live wiki fetch — always search for non-price questions to supplement KB
            wiki_ctx = ""
            if not price_question:
                try:
                    wiki_ctx = await wiki_context(question, max_chars=4000)
                except Exception as e:
                    print(f"[wiki error] {e}")
            cata_level = self._extract_cata_level(question)
            cata_note = (
                f"- The user has stated their Catacombs level is {cata_level}. "
                f"ONLY recommend items/content they can use or access at Cata {cata_level}. "
                f"If an item requires a higher Cata level, skip it.\n"
            ) if cata_level is not None else ""
            system = (
                "You are a Hypixel Skyblock assistant in a Discord server.\n"
                "RESPONSE FORMAT:\n"
                "- Simple fact questions (what is X, how much is X): 1-3 sentences, no lists.\n"
                "- Progression/improvement questions (how to improve, what to upgrade, review my profile): "
                "Give SPECIFIC, ACTIONABLE steps as a numbered list (max 5-6 steps). Reference the player's ACTUAL "
                "gear/stats/levels and name exact items, exact upgrades, exact costs where possible. "
                "Don't say 'get better armor' — say 'replace your [current piece] with [specific item] "
                "(costs ~X coins on AH)'. Prioritize upgrades by impact.\n"
                "- NEVER use markdown tables — they render poorly in Discord and waste space.\n"
                "- Keep responses concise. No filler, no repeating what the player already knows.\n\n"
                "DATA PRIORITY (highest wins):\n"
                "1. COMMUNITY CORRECTIONS — verified player-submitted facts, always trust these\n"
                "2. LIVE DATA — real-time bazaar/AH prices and player stats\n"
                "3. WIKI DATA — live game wiki content\n"
                "4. KNOWLEDGE BASE — static reference guides\n"
                "5. General Skyblock knowledge — OK for advice, NOT for specific numbers\n\n"
                "HARD RULES — FOLLOW STRICTLY:\n"
                "- ONLY use information from the data sections below (KNOWLEDGE BASE, COMMUNITY CORRECTIONS, LIVE DATA, WIKI DATA, PLAYER STATS). If information is NOT in any of these sections, say 'I don't have that info — check the wiki' instead of guessing.\n"
                "- Do NOT invent specific numbers: no fake prices, stat values, collection tiers, XP amounts, recipe details, milestone rewards, or perk effects. If you don't know the exact number, say 'check the wiki for exact values'.\n"
                "- Do NOT invent items, enchantments, reforges, abilities, perks, or game mechanics that aren't mentioned in the data below.\n"
                "- REFORGES: Auspicious is a TOOL reforge (pickaxes/drills), NOT an armor reforge. Do NOT recommend Auspicious on armor pieces.\n"
                "- FLIPS: NEVER suggest specific flip items unless you have LIVE BAZAAR/AH PRICES below. If no live data is provided, say 'I don't have live price data right now' — do NOT make up item names or prices.\n"
                "- HotM PERKS: ALWAYS use the perk names and max levels from COMMUNITY CORRECTIONS. Mining Fortune max level is 50 (NOT 100). Do NOT invent perk levels or rewards.\n"
                "- MINING TOOLS: Auspicious reforge gives Mining FORTUNE (not Mining Speed). Fortune IV (not III) is the correct enchant. Sharpness/Smite do NOT go on pickaxes/drills.\n"
                "- INVESTMENTS: NEVER create specific investment portfolios with item quantities and prices. Only recommend BAZAAR investments, NEVER AH items.\n"
                "- FAKE ITEMS: Spelunker reforge, Divan's Drill (as separate from regular drills), Mining Madness perk — these do NOT exist.\n"
                "- PRICES: Use ONLY live price data provided below. Never guess or estimate prices.\n"
                "- If the user has linked their account, reference their actual stats/gear.\n"
                "- When unsure, say 'I'm not sure about that — check the wiki' rather than making something up.\n"
                + cata_note
                + "- Budget questions: only list items whose live price fits the budget.\n"
                "- Off-topic: say you only help with Skyblock.\n\n"
                f"KNOWLEDGE BASE:\n{static_ctx}"
            )

            corrections = self.knowledge.get_corrections()
            if corrections:
                system += f"\n\nCOMMUNITY CORRECTIONS (verified facts — these override general knowledge):\n{corrections}"

            if item_ctx:
                system += f"\n\n{item_ctx}"
            if live_ctx:
                system += f"\n\nLIVE BAZAAR PRICES:\n{live_ctx}"
            if ah_ctx:
                system += f"\n\nLIVE AH PRICES:\n{ah_ctx}"
            if hist_ctx:
                system += f"\n\nHistorical price data:\n{hist_ctx}"
            if market_ctx:
                system += f"\n\n{market_ctx}\nUse this real market data to make investment recommendations. Only recommend BAZAAR items. Reference specific items, their trends, and volumes from this data."
            if wiki_ctx:
                system += f"\n\nWIKI DATA (live from Hypixel Skyblock wiki):\n{wiki_ctx}"
            if learned_ctx:
                system += f"\n\nPREVIOUSLY LEARNED FACTS (verified from past web searches):\n{learned_ctx}"
            if mayor_ctx:
                system += f"\n\nLIVE MAYOR/ELECTION DATA (real-time from Hypixel API):\n{mayor_ctx}\nIMPORTANT: Use this live data for mayor questions. This is the CURRENT mayor and election state."
            if price_question and not live_ctx and not ah_ctx:
                system += "\n\nNo live price data found. Do NOT guess prices."
            if linked_summary:
                system += (
                    "\n\nLINKED PLAYER STATS (this user's actual Skyblock profile):\n"
                    + linked_summary
                    + "\nIMPORTANT: This user has linked their account. Rules for personalized responses:"
                    "\n1. ALWAYS reference their actual stats. Say 'your Mining 45' not 'your mining level'."
                    "\n2. For upgrades, look at what they CURRENTLY have and recommend the NEXT step up."
                    "   Name exact items, enchants, gems, reforges, and HotM perks."
                    "\n3. Prioritize by impact: what single change gives them the biggest boost?"
                    "\n4. If they have low skill average, suggest which skill to grind and where."
                    "\n5. If their Magic Power is low for their progression, flag it."
                    "\n6. If they have unspent powder, tell them exactly which HotM perks to level."
                    "\n7. Compare their gear to what's appropriate for their level — if undergeared, say so."
                    "\n8. If their slayers are behind their combat level, suggest which to do."
                    "\n9. Give coin estimates when possible (e.g. 'upgrade to X for ~5M')."
                    "\n10. Never give generic advice that ignores their stats."
                )

            if ingame:
                system += (
                    "\n\nIN-GAME MODE: You are responding inside a Minecraft overlay. "
                    "Give complete, helpful answers in 5-15 lines. Do NOT cut yourself short — finish your answer fully. "
                    "Use **bold** for item names, numbers, and key terms. "
                    "Use bullet points (- ) for lists. Use numbered steps (1. 2. 3.) for guides. "
                    "Be direct but thorough. No filler phrases like 'I recommend' or 'you could try'. "
                    "Example format:\n"
                    "**Jungle Axe** — ~40k on AH\n"
                    "- Best early Foraging tool\n"
                    "- Instantly breaks wood in a 3x3 area\n"
                    "- Upgrade to **Treecapitator** later (~5M)\n"
                )

            try:
                resp = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": question},
                    ],
                    max_tokens=1000 if ingame else 2000,
                    temperature=0.0,
                )
                text = resp.choices[0].message.content.strip()
                # deepseek-r1 wraps its reasoning in <think>...</think> — strip it
                text = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.IGNORECASE).strip()

                # Post-processing: catch known hallucinated items/terms
                text = self._filter_hallucinations(text)

                # Auto-search retry: if AI doesn't know, search web and try again
                _NO_INFO = ["don't have that info", "don't have enough info",
                            "i'm not sure", "not in my knowledge", "don't have info",
                            "check the wiki"]
                if any(phrase in text.lower() for phrase in _NO_INFO):
                    try:
                        # Search wiki + web for the answer
                        search_ctx = await wiki_context(question, max_chars=5000)
                        if search_ctx and len(search_ctx.strip()) > 100:
                            retry_system = system + f"\n\nADDITIONAL WEB SEARCH RESULTS:\n{search_ctx}\nYou now have web search data. Use it to answer the question. Do NOT say you don't have the info."
                            retry_resp = await self.client.chat.completions.create(
                                model=self.model,
                                messages=[
                                    {"role": "system", "content": retry_system},
                                    {"role": "user", "content": question},
                                ],
                                max_tokens=1000 if ingame else 2000,
                                temperature=0.0,
                            )
                            retry_text = retry_resp.choices[0].message.content.strip()
                            retry_text = re.sub(r"<think>[\s\S]*?</think>", "", retry_text, flags=re.IGNORECASE).strip()
                            retry_text = self._filter_hallucinations(retry_text)

                            # If the retry actually answered it, cache the fact
                            if not any(p in retry_text.lower() for p in _NO_INFO):
                                keywords = re.sub(r"[^\w\s]", "", question.lower())
                                try:
                                    save_fact(question, keywords, retry_text, source="wiki_search")
                                except Exception:
                                    pass
                                return retry_text
                    except Exception as e:
                        print(f"[ai] Auto-search retry error: {e}")

                    # Still couldn't answer — log it
                    try:
                        log_unanswered(question, discord_user_id)
                    except Exception:
                        pass
                else:
                    # Good answer — cache it for questions with thin KB coverage
                    if len(static_ctx.strip()) < 500 and len(text) > 50:
                        keywords = re.sub(r"[^\w\s]", "", question.lower())
                        try:
                            save_fact(question, keywords, text, source="ai_response")
                        except Exception:
                            pass

                return text
            except Exception as e:
                print(f"[ai] Main AI error: {e}")
                err_name = type(e).__name__.lower()
                err_str = str(e).lower()
                if "rate" in err_name or "rate" in err_str or "429" in err_str:
                    return "I'm getting too many questions right now, try again in a moment."
                if any(w in err_name for w in ("timeout", "connect", "connection")) or any(w in err_str for w in ("timeout", "connect")):
                    return "Couldn't reach the AI service, try again in a moment."
                return "Something went wrong, try again."
