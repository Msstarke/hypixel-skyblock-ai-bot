import os
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
from ai_handler import AIHandler
from bazaar_tracker import BazaarTracker, SNAPSHOT_INTERVAL
from user_links import link_user, unlink_user, get_linked_username, get_linked_uuid, update_uuid, update_username
from corrections import submit_correction, get_pending, approve_correction, reject_correction
from feedback import log_vote, log_unanswered, get_bad_responses, get_unanswered, get_feedback_stats, resolve_feedback, resolve_all_feedback
from feedback_agent import analyze_feedback, get_last_analysis, ANALYSIS_INTERVAL
import web_dashboard
from web_dashboard import start_dashboard_thread

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)
ai = AIHandler()
tracker = BazaarTracker()
ai.tracker = tracker  # share tracker with AI handler for context injection
web_dashboard._live_knowledge_base = ai.knowledge  # let dashboard reload live KB

# Optional: restrict to specific channel IDs
ALLOWED_CHANNELS = set()
raw = os.getenv("AI_CHANNELS", "")
if raw.strip():
    ALLOWED_CHANNELS = {int(c.strip()) for c in raw.split(",") if c.strip().isdigit()}


def _split_message(text: str, limit: int = 1900) -> list[str]:
    """Split a long message into chunks that fit Discord's character limit."""
    if len(text) <= limit:
        return [text]
    chunks = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        split_at = text.rfind("\n", 0, limit)
        if split_at == -1:
            split_at = text.rfind(" ", 0, limit)
        if split_at == -1:
            split_at = limit
        chunks.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    return chunks


@tasks.loop(seconds=SNAPSHOT_INTERVAL)
async def snapshot_bazaar():
    """Snapshot all Bazaar prices every 5 minutes for trend analysis."""
    try:
        data = await ai.hypixel.get_bazaar()
        if data:
            products = data.get("products", {})
            tracker.save_snapshot(products)
            print(f"[tracker] Snapshot saved — {len(products)} products")
    except Exception as e:
        print(f"[tracker] Snapshot failed: {e}")


@tasks.loop(seconds=ANALYSIS_INTERVAL)
async def auto_analyze_feedback():
    """Periodically analyze feedback to detect issues."""
    try:
        report = await analyze_feedback()
        print(f"[feedback-agent] Analysis complete ({len(report)} chars)")
    except Exception as e:
        print(f"[feedback-agent] Analysis failed: {e}")


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print(f"Serving {len(bot.guilds)} guild(s)")
    snapshot_bazaar.start()
    auto_analyze_feedback.start()
    start_dashboard_thread()


# Track recent bot responses for reaction-based feedback
# {message_id: (question, response, author_id, author_name)}
_recent_responses: dict[int, tuple[str, str, int, str]] = {}
MAX_TRACKED = 200


def _detect_tool(question: str, has_linked: bool) -> str | None:
    """Detect if the question should trigger a built-in tool instead of pure AI."""
    q = question.lower().strip()

    # HotM tree visualization
    hotm_words = ["hotm tree", "hotm", "heart of the mountain", "my hotm", "show hotm",
                  "show my hotm", "hotm perks", "my perks", "mining tree"]
    if any(w in q for w in hotm_words) and has_linked:
        return "hotm"

    # Mayor / election info
    mayor_words = ["mayor", "current mayor", "who is the mayor", "who is mayor",
                   "election", "skyblock mayor", "mayor perks", "mayor perk"]
    if any(w in q for w in mayor_words):
        return "mayor"

    # Flips / investment / money making
    flip_words = ["flip", "flips", "flipping", "what to flip", "good flip", "best flip",
                  "money making", "show flips", "flip opportunities", "bazaar flip",
                  "invest", "investment", "what to invest", "what should i invest"]
    # Long-term investment questions should go to AI, not flips tool
    long_term = any(w in q for w in ["hold", "long term", "days", "week", "month", "hold onto"])
    if any(w in q for w in flip_words) and not long_term:
        if any(w in q for w in ["ah", "auction", "bin", "snipe"]):
            return "flips_ah"
        return "flips"
    # AH snipes (standalone)
    if any(w in q for w in ["snipe", "snipes", "sniping", "ah snipe"]):
        return "flips_ah"

    # Price lookup — simple "how much is X", "price of X", "bazaar X"
    price_patterns = ["how much is", "how much does", "how much do", "price of", "price for",
                      "bazaar price", "ah price", "cost of", "what does .* cost",
                      "what does .* sell for", "what is .* worth"]
    # Direct bazaar/price queries (short questions, not complex AI questions)
    if any(w in q for w in ["bazaar ", "ah price"]):
        if len(q.split()) <= 8:
            return "price"
    import re as _re
    for pat in price_patterns:
        if _re.search(pat, q):
            return "price"

    # Recipe lookup — crafting questions
    recipe_words = ["recipe for", "recipe of", "how to craft", "how do i craft", "how do you craft",
                    "how to make", "how do i make", "how do you make", "what do i need to make",
                    "what do i need to craft", "crafting recipe", "craft recipe",
                    "ingredients for", "materials for", "what's in a", "whats in a"]
    if any(w in q for w in recipe_words):
        return "recipe"

    # MP optimizer — accessory/talisman MP questions
    mp_words = ["cheapest accessory", "cheapest accessories", "cheapest talisman", "cheapest talismans",
                "cheap mp", "cheap magical power", "maximize mp", "maximise mp", "max mp",
                "mp for lowest cost", "mp for cheapest", "best mp", "most mp per coin",
                "accessory for mp", "accessories for mp", "talisman for mp", "talismans for mp",
                "what accessories should i get", "what talismans should i get",
                "mp upgrade", "mp optimization", "mp optimisation", "increase mp",
                "raise mp", "boost mp", "more mp", "need more mp",
                "recomb or buy", "recombobulate or buy", "should i recomb"]
    if any(w in q for w in mp_words):
        return "mp_optimizer"

    # Skill calculator — XP questions
    skill_calc_patterns = [
        r"how much xp .* (?:to|for) .* \d+",
        r"xp (?:to|for|needed|required|until) .* \d+",
        r"xp .* level \d+",
        r"how many .* (?:to|for) .* \d+",
        r"(?:mining|combat|farming|foraging|fishing|enchanting|alchemy|taming|carpentry|catacombs|dungeon)\s+\d+\s+xp",
        r"\d+\s+(?:mining|combat|farming|foraging|fishing|enchanting|alchemy|taming|carpentry|catacombs)",
        r"(?:zombie|spider|wolf|enderman|blaze|vampire|revenant|tarantula|sven|voidgloom|inferno)\s+slayer\s+\d+",
        r"slayer\s+\d+",
    ]
    for pat in skill_calc_patterns:
        if _re.search(pat, q):
            return "skill_calc"

    return None


def _extract_item_name(question: str, prefixes: list[str]) -> str:
    """Extract an item name from a question by stripping known prefixes."""
    q = question.lower().strip()
    for prefix in prefixes:
        import re as _re
        m = _re.search(prefix, q)
        if m:
            item = q[m.end():].strip().rstrip("?.,! ")
            if item:
                return item
    # Fallback: return everything after removing common filler words
    for word in ["the", "a", "an", "some"]:
        q = q.replace(f" {word} ", " ")
    return q.strip().rstrip("?.,! ")


async def _run_price_tool(question: str, hypixel_api):
    """Look up price for an item from Bazaar and/or AH. Returns embed or None."""
    prefixes = ["how much (?:is|does|do) (?:a |an |the )?", "price (?:of|for) (?:a |an |the )?",
                "bazaar price (?:of|for )?", "ah price (?:of|for )?", "bazaar ",
                "cost of (?:a |an |the )?", "what (?:is|does) (?:a |an |the )?.* (?:cost|sell for|worth)"]
    item_name = _extract_item_name(question, prefixes)
    if not item_name or len(item_name) < 2:
        return None

    embed = discord.Embed(title=f"Price: {item_name.title()}", color=0x3498DB)
    found = False

    # Try Bazaar first
    baz_results = await hypixel_api.search_bazaar(item_name)
    if baz_results:
        found = True
        for r in baz_results[:5]:
            name = r['id'].replace('_', ' ').title()
            embed.add_field(
                name=f"{name} (Bazaar)",
                value=f"Buy order: **{r['buy']:,.1f}** coins\nSell offer: **{r['sell']:,.1f}** coins",
                inline=False,
            )

    # Also try AH
    ah_results = await hypixel_api.search_ah(item_name)
    if ah_results:
        found = True
        for r in ah_results[:3]:
            embed.add_field(
                name=f"{r['name']} ({r['source']})",
                value=f"Price: **{r['price']:,.0f}** coins",
                inline=False,
            )

    return embed if found else None


async def _run_recipe_tool(question: str, hypixel_api):
    """Look up crafting recipe for an item. Returns embed or None."""
    prefixes = ["recipe (?:for|of) (?:a |an |the )?", "how (?:to|do (?:i|you)) (?:craft|make) (?:a |an |the )?",
                "what do i need to (?:craft|make) (?:a |an |the )?", "crafting recipe (?:for )?",
                "craft recipe (?:for )?", "ingredients for (?:a |an |the )?",
                "materials for (?:a |an |the )?", "what'?s in (?:a |an |the )?"]
    item_name = _extract_item_name(question, prefixes)
    if not item_name or len(item_name) < 2:
        return None

    item = await hypixel_api.find_item(item_name)
    if not item:
        return None

    recipe = hypixel_api.get_recipe(item["id"])
    name = item.get("name", item["id"].replace("_", " ").title())

    embed = discord.Embed(title=f"Recipe: {name}", color=0xF1C40F)

    if item.get("tier"):
        embed.description = f"Rarity: {item['tier'].title()}"

    if recipe:
        ingredients = []
        for mat_id, count in recipe["i"].items():
            mat_name = mat_id.replace("_", " ").title()
            ingredients.append(f"**{count}x** {mat_name}")

        rtype = recipe.get("t", "craft")
        if rtype == "forge":
            dur = recipe.get("d", 0)
            dur_str = f" ({dur // 3600}h)" if dur else ""
            embed.add_field(name=f"Forge Recipe{dur_str}", value="\n".join(ingredients), inline=False)
        else:
            embed.add_field(name="Crafting Recipe", value="\n".join(ingredients), inline=False)

        output_count = recipe.get("c", 1)
        if output_count and output_count > 1:
            embed.set_footer(text=f"Produces {output_count}x per craft")
    else:
        embed.add_field(name="Recipe", value="No recipe data available for this item.", inline=False)
        if item.get("category"):
            embed.add_field(name="Category", value=item["category"].replace("_", " ").title(), inline=True)

    return embed


def _run_skill_calc_tool(question: str) -> str | None:
    """Calculate XP needed for a skill/slayer level. Returns text or None."""
    from player_stats import SKILL_XP, SKILL_MAX, SLAYER_XP
    import re as _re

    q = question.lower().strip()

    skill_aliases = {
        "mining": "Mining", "combat": "Combat", "farming": "Farming",
        "foraging": "Foraging", "fishing": "Fishing", "enchanting": "Enchanting",
        "alchemy": "Alchemy", "taming": "Taming", "carpentry": "Carpentry",
        "runecrafting": "Runecrafting", "social": "Social",
        "catacombs": "Catacombs", "dungeon": "Catacombs", "dungeons": "Catacombs",
    }
    slayer_aliases = {
        "zombie": "Revenant", "revenant": "Revenant", "rev": "Revenant",
        "spider": "Tarantula", "tarantula": "Tarantula", "tara": "Tarantula",
        "wolf": "Sven", "sven": "Sven",
        "enderman": "Voidgloom", "voidgloom": "Voidgloom", "eman": "Voidgloom",
        "blaze": "Inferno", "inferno": "Inferno",
        "vampire": "Vampire", "vamp": "Vampire",
    }

    skill_name = None
    target_level = None
    is_slayer = False

    # Check for slayer patterns first
    for alias, canonical in slayer_aliases.items():
        m = _re.search(rf'{alias}\s+slayer\s+(\d+)', q)
        if m:
            skill_name = canonical
            target_level = int(m.group(1))
            is_slayer = True
            break
        m = _re.search(rf'slayer.*{alias}\s+(\d+)', q)
        if m:
            skill_name = canonical
            target_level = int(m.group(1))
            is_slayer = True
            break

    if not skill_name:
        for alias, canonical in skill_aliases.items():
            m = _re.search(rf'{alias}\s+(?:level\s+)?(\d+)', q)
            if m:
                skill_name = canonical
                target_level = int(m.group(1))
                break
            m = _re.search(rf'(\d+)\s+{alias}', q)
            if m:
                skill_name = canonical
                target_level = int(m.group(1))
                break

    if not skill_name or target_level is None:
        return None

    if is_slayer:
        if target_level < 1 or target_level >= len(SLAYER_XP):
            return f"Slayer level {target_level} is out of range (max level {len(SLAYER_XP) - 1})."
        total_xp = SLAYER_XP[target_level]
        prev_xp = SLAYER_XP[target_level - 1] if target_level > 0 else 0
        xp_this_level = total_xp - prev_xp
        return (
            f"**{skill_name} Slayer Level {target_level}**\n"
            f"Total XP needed: **{total_xp:,}**\n"
            f"XP for this level alone: **{xp_this_level:,}**"
        )
    else:
        cap = SKILL_MAX.get(skill_name, 50) if skill_name != "Catacombs" else 50
        if target_level < 1 or target_level > cap:
            return f"{skill_name} level {target_level} is out of range (max level {cap})."
        if target_level >= len(SKILL_XP):
            return f"No XP data available for {skill_name} level {target_level}."
        total_xp = SKILL_XP[target_level]
        prev_xp = SKILL_XP[target_level - 1] if target_level > 0 else 0
        xp_this_level = total_xp - prev_xp
        return (
            f"**{skill_name} Level {target_level}**\n"
            f"Total XP needed: **{total_xp:,}**\n"
            f"XP for this level alone: **{xp_this_level:,}**\n"
            f"(Cumulative from level 0 to {target_level})"
        )


async def _run_mayor_tool():
    """Fetch current mayor and election data and return a Discord embed."""
    data = await ai.hypixel.get_current_mayor()
    if not data:
        return None

    mayor_info = data.get("mayor")
    if not mayor_info:
        return None

    embed = discord.Embed(
        title=f"Mayor: {mayor_info['name']}",
        color=0xFFD700,
    )

    # Mayor perks
    perks_text = ""
    for perk in mayor_info.get("perks", []):
        name = perk.get("name", "Unknown")
        desc = perk.get("description", "No description.")
        perks_text += f"**{name}** — {desc}\n"
    if perks_text:
        embed.add_field(name="Mayor Perks", value=perks_text.strip(), inline=False)

    # Minister info
    minister = mayor_info.get("minister")
    if minister and isinstance(minister, dict):
        minister_name = minister.get("name", "Unknown")
        minister_perk = minister.get("perk", {})
        perk_name = minister_perk.get("name", "") if isinstance(minister_perk, dict) else ""
        perk_desc = minister_perk.get("description", "") if isinstance(minister_perk, dict) else ""
        minister_text = f"**{minister_name}**"
        if perk_name:
            minister_text += f"\nPerk: **{perk_name}** — {perk_desc}"
        embed.add_field(name="Minister", value=minister_text, inline=False)

    # Year info
    year = data.get("year")
    if year:
        embed.set_footer(text=f"SkyBlock Year {year}")

    # Current election candidates
    candidates = data.get("candidates", [])
    if candidates:
        # Sort by votes descending
        candidates.sort(key=lambda c: c.get("votes", 0), reverse=True)
        cand_text = ""
        for c in candidates:
            name = c.get("name", "Unknown")
            votes = c.get("votes", 0)
            perk_names = ", ".join(p.get("name", "") for p in c.get("perks", []) if p.get("name"))
            vote_str = f" — {votes:,} votes" if votes else ""
            cand_text += f"**{name}**{vote_str}\n"
            if perk_names:
                cand_text += f"  Perks: {perk_names}\n"
        embed.add_field(name="Current Election Candidates", value=cand_text.strip(), inline=False)

    return embed


async def _run_hotm_tool(ctx, username: str, mc_uuid: str = None):
    """Run HotM tree visualization inline."""
    from hotm_render import render_hotm_tree
    from hypixel_api import HOTM_XP

    data = await ai.hypixel.get_player_data(username, uuid=mc_uuid)
    if not data:
        return None

    stats = data["stats"]
    hotm_perks = stats.get("hotm_perks", {})
    hotm_xp = stats.get("hotm_xp", 0)
    hotm_lvl = sum(1 for req in HOTM_XP[1:] if hotm_xp >= req)
    powder = {
        "mithril": stats.get("mithril_powder", 0),
        "gemstone": stats.get("gemstone_powder", 0),
        "glacite": stats.get("glacite_powder", 0),
    }
    selected = stats.get("hotm_selected_ability", "")

    buf = render_hotm_tree(hotm_perks, powder, hotm_lvl, selected, username)
    file = discord.File(buf, filename="hotm.png")

    embed = discord.Embed(title=f"{username}'s Heart of the Mountain", color=0x2E8B82)
    embed.set_image(url="attachment://hotm.png")

    mp = stats.get("mithril_powder", 0)
    gp = stats.get("gemstone_powder", 0)
    glp = stats.get("glacite_powder", 0)
    spent_m = stats.get("powder_spent_mithril", 0)
    spent_g = stats.get("powder_spent_gemstone", 0)
    spent_gl = stats.get("powder_spent_glacite", 0)
    powder_text = (
        f"Mithril: **{mp:,}** available ({spent_m:,} spent)\n"
        f"Gemstone: **{gp:,}** available ({spent_g:,} spent)\n"
        f"Glacite: **{glp:,}** available ({spent_gl:,} spent)"
    )
    embed.add_field(name="Powder", value=powder_text, inline=False)
    if selected:
        embed.add_field(name="Active Ability", value=selected.replace("_", " ").title(), inline=True)
    embed.add_field(name="HotM Tier", value=str(hotm_lvl), inline=True)

    return embed, file


def _parse_budget(question: str) -> int | None:
    """Extract a coin budget from the question, e.g. '1 billion', '500m', '10 mil'."""
    q = question.lower().replace(",", "").replace("_", "")
    import re as _re
    m = _re.search(r'(\d+(?:\.\d+)?)\s*(b(?:illion)?|m(?:il(?:lion)?)?|k)\b', q)
    if m:
        num = float(m.group(1))
        unit = m.group(2)[0]
        if unit == 'b':
            return int(num * 1_000_000_000)
        elif unit == 'm':
            return int(num * 1_000_000)
        elif unit == 'k':
            return int(num * 1_000)
    # Try bare large numbers
    m = _re.search(r'\b(\d{6,})\b', q)
    if m:
        return int(m.group(1))
    return None


async def _run_flips_tool(mode: str = "baz", budget: int | None = None):
    """Run flips lookup inline, return embed or None."""
    if mode == "ah":
        flips = await ai.hypixel.get_ah_flips()
        if not flips:
            return None
        embed = discord.Embed(title="Top AH Snipe Opportunities", color=0xE67E22)
        for f in flips[:8]:
            embed.add_field(
                name=f["name"],
                value=(
                    f"BIN: **{f['bin_price']:,.0f}** | Median: **{f['median']:,.0f}**\n"
                    f"Profit: **+{f['profit']:,.0f}** ({f['margin_pct']}%)"
                ),
                inline=False,
            )
        return embed
    else:
        if tracker and tracker.last_snapshot_age() is not None:
            flips = tracker.get_smart_flips()
        else:
            flips = await ai.hypixel.get_bazaar_flips()
        if not flips:
            return None
        title = "Top Bazaar Flip Opportunities"
        if budget:
            title += f" (Budget: {budget:,.0f} coins)"
        embed = discord.Embed(title=title, color=0x2ECC71)
        for f in flips[:8]:
            trend_icon = {"rising": "\u2191", "falling": "\u2193", "stable": "\u2192"}.get(f.get("trend", ""), "")
            buy_price = f['buy']
            # Calculate suggested volume based on budget and weekly volume
            if budget and buy_price > 0:
                # Invest up to 20% of budget per item, capped by weekly volume
                max_spend = budget * 0.2
                max_qty = int(max_spend / buy_price)
                weekly_vol = f.get('weekly_vol', 0)
                # Don't suggest more than 5% of weekly volume (to avoid moving the market)
                safe_qty = min(max_qty, int(weekly_vol * 0.05)) if weekly_vol > 0 else max_qty
                safe_qty = max(1, safe_qty)
                invest_cost = safe_qty * buy_price
                expected_profit = safe_qty * f['margin']
                vol_line = f"\nSuggested: **{safe_qty:,}x** ({invest_cost:,.0f} coins) → ~**{expected_profit:,.0f}** profit"
            else:
                vol_line = ""
            embed.add_field(
                name=f["name"],
                value=(
                    f"Buy: **{f['buy']:,.1f}** | Sell: **{f['sell']:,.1f}**\n"
                    f"Margin: **+{f['margin']:,.1f}** ({f['margin_pct']}%) | Vol: **{f['weekly_vol']:,}**/wk"
                    + (f" {trend_icon}" if trend_icon else "")
                    + vol_line
                ),
                inline=False,
            )
        if budget:
            embed.set_footer(text="Suggested volumes use ≤20% budget per item, ≤5% weekly volume. Bazaar only.")
        return embed


@bot.command(name="ai")
async def ai_command(ctx: commands.Context, *, question: str = None):
    if not question:
        await ctx.reply("Usage: `!ai <your question>` — e.g. `!ai what's the cost of 655 enchanted diamonds?`")
        return

    if ALLOWED_CHANNELS and ctx.channel.id not in ALLOWED_CHANNELS:
        return

    linked_ign = get_linked_username(ctx.author.id)
    linked_uuid = get_linked_uuid(ctx.author.id) if linked_ign else None
    tool = _detect_tool(question, has_linked=bool(linked_ign))

    async with ctx.typing():
        # --- Tool: HotM tree ---
        if tool == "hotm" and linked_ign:
            try:
                result = await _run_hotm_tool(ctx, linked_ign, mc_uuid=linked_uuid)
                if result:
                    embed, file = result
                    msg = await ctx.reply(embed=embed, file=file)
                    try:
                        await msg.add_reaction("👍")
                        await msg.add_reaction("👎")
                    except Exception as e:
                        print(f"[bot] Failed to add reactions: {e}")
                    _recent_responses[msg.id] = (question, "[HotM tree image]", ctx.author.id, str(ctx.author))
                    return
            except Exception as e:
                print(f"[bot] HotM tool failed for {linked_ign}: {e}")
                await ctx.reply("Couldn't load your HotM data right now. Let me try answering with AI instead.")
                # fall through to AI

        # --- Tool: Flips ---
        if tool in ("flips", "flips_ah"):
            try:
                mode = "ah" if tool == "flips_ah" else "baz"
                budget = _parse_budget(question)
                embed = await _run_flips_tool(mode, budget=budget)
                if embed:
                    msg = await ctx.reply(embed=embed)
                    try:
                        await msg.add_reaction("👍")
                        await msg.add_reaction("👎")
                    except Exception as e:
                        print(f"[bot] Failed to add reactions: {e}")
                    _recent_responses[msg.id] = (question, "[Flips data]", ctx.author.id, str(ctx.author))
                    return
            except Exception as e:
                print(f"[bot] Flips tool failed: {e}")
                # fall through to AI

        # --- Tool: Price lookup ---
        if tool == "price":
            try:
                embed = await _run_price_tool(question, ai.hypixel)
                if embed:
                    msg = await ctx.reply(embed=embed)
                    try:
                        await msg.add_reaction("\U0001f44d")
                        await msg.add_reaction("\U0001f44e")
                    except Exception as e:
                        print(f"[bot] Failed to add reactions: {e}")
                    _recent_responses[msg.id] = (question, "[Price lookup]", ctx.author.id, str(ctx.author))
                    return
            except Exception as e:
                print(f"[bot] Price tool failed: {e}")
                pass  # fall through to AI

        # --- Tool: Recipe lookup ---
        if tool == "recipe":
            try:
                embed = await _run_recipe_tool(question, ai.hypixel)
                if embed:
                    msg = await ctx.reply(embed=embed)
                    try:
                        await msg.add_reaction("\U0001f44d")
                        await msg.add_reaction("\U0001f44e")
                    except Exception as e:
                        print(f"[bot] Failed to add reactions: {e}")
                    _recent_responses[msg.id] = (question, "[Recipe lookup]", ctx.author.id, str(ctx.author))
                    return
            except Exception as e:
                print(f"[bot] Recipe tool failed: {e}")
                pass  # fall through to AI

        # --- Tool: Skill XP calculator ---
        if tool == "skill_calc":
            try:
                result = _run_skill_calc_tool(question)
                if result:
                    msg = await ctx.reply(result)
                    try:
                        await msg.add_reaction("\U0001f44d")
                        await msg.add_reaction("\U0001f44e")
                    except Exception as e:
                        print(f"[bot] Failed to add reactions: {e}")
                    _recent_responses[msg.id] = (question, result, ctx.author.id, str(ctx.author))
                    return
            except Exception as e:
                print(f"[bot] Skill calc tool failed: {e}")
                pass  # fall through to AI

        if tool == "mp_optimizer":
            try:
                from mp_optimizer import get_accessory_mp_rankings, format_mp_plan
                # Get player's owned accessories if linked
                owned_ids = set()
                current_mp = 0
                linked_uuid = get_linked_uuid(ctx.author.id)
                linked_name = get_linked_username(ctx.author.id)
                if linked_name:
                    pdata = await ai.hypixel.get_player_data(linked_name, uuid=linked_uuid)
                    if pdata:
                        stats = pdata["stats"]
                        current_mp = stats.get("magical_power", 0)
                        for acc in stats.get("accessories", []):
                            if acc.get("id"):
                                owned_ids.add(acc["id"])

                budget = _parse_budget(question)
                rankings = await get_accessory_mp_rankings(ai.hypixel, owned_ids=owned_ids)
                if rankings:
                    plan = format_mp_plan(
                        rankings, budget=budget,
                        current_mp=current_mp, owned_ids=owned_ids,
                        target_count=20,
                    )
                    recomb_price = rankings[0]["recomb_price"]
                    title = "Cheapest MP Upgrades"
                    if linked_name:
                        title = f"MP Upgrades for {linked_name}"

                    embed = discord.Embed(title=title, color=0x9B59B6)
                    if current_mp:
                        embed.description = f"Current MP: **{current_mp:,}**"
                    embed.set_footer(
                        text=f"Recombobulator 3000 price: {recomb_price:,.0f} coins | Prices from lowest BIN"
                    )

                    # Split plan into chunks for embed fields
                    lines = plan.split("\n")
                    summary = lines[0] if lines else ""
                    detail_lines = [l for l in lines[1:] if l.strip()]

                    if summary:
                        embed.add_field(name="Plan", value=summary, inline=False)

                    chunk = []
                    chunk_len = 0
                    field_num = 1
                    for line in detail_lines:
                        if chunk_len + len(line) + 1 > 1000:
                            embed.add_field(
                                name=f"Recommendations ({field_num})" if field_num > 1 else "Recommendations",
                                value="\n".join(chunk), inline=False
                            )
                            chunk = []
                            chunk_len = 0
                            field_num += 1
                        chunk.append(line)
                        chunk_len += len(line) + 1
                    if chunk:
                        embed.add_field(
                            name=f"Recommendations ({field_num})" if field_num > 1 else "Recommendations",
                            value="\n".join(chunk), inline=False
                        )

                    msg = await ctx.reply(embed=embed)
                    try:
                        await msg.add_reaction("\U0001f44d")
                        await msg.add_reaction("\U0001f44e")
                    except Exception as e:
                        print(f"[bot] Failed to add reactions: {e}")
                    _recent_responses[msg.id] = (question, "[MP optimizer]", ctx.author.id, str(ctx.author))
                    return
            except Exception as e:
                print(f"[bot] MP optimizer failed: {e}")
                import traceback
                traceback.print_exc()
                pass  # fall through to AI

        # --- Tool: Mayor / Election ---
        if tool == "mayor":
            try:
                embed = await _run_mayor_tool()
                if embed:
                    msg = await ctx.reply(embed=embed)
                    try:
                        await msg.add_reaction("\U0001f44d")
                        await msg.add_reaction("\U0001f44e")
                    except Exception as e:
                        print(f"[bot] Failed to add reactions: {e}")
                    _recent_responses[msg.id] = (question, "[Mayor info]", ctx.author.id, str(ctx.author))
                    return
            except Exception as e:
                print(f"[bot] Mayor tool failed: {e}")
                pass  # fall through to AI

        # --- Default: AI response ---
        response = await ai.get_response(question, discord_user_id=ctx.author.id)

    # Split long responses into multiple messages instead of truncating
    chunks = _split_message(response)
    msg = None
    for chunk in chunks:
        msg = await ctx.reply(chunk)

    # Add reaction buttons to the last message for feedback
    if msg:
        try:
            await msg.add_reaction("👍")
            await msg.add_reaction("👎")
        except Exception as e:
            print(f"[bot] Failed to add reactions: {e}")

        # Track for reaction handler
        _recent_responses[msg.id] = (question, response, ctx.author.id, str(ctx.author))
        if len(_recent_responses) > MAX_TRACKED:
            oldest = next(iter(_recent_responses))
            del _recent_responses[oldest]


@bot.command(name="hotm")
async def hotm_command(ctx: commands.Context, *, username: str = None):
    """Show a player's Heart of the Mountain tree as an image."""
    from hotm_render import render_hotm_tree
    from hypixel_api import HOTM_XP

    # Resolve username
    mc_uuid = None
    if not username:
        linked = get_linked_username(ctx.author.id)
        if linked:
            username = linked
            mc_uuid = get_linked_uuid(ctx.author.id)
        else:
            await ctx.reply("Usage: `!hotm <username>` or link your account with `!link <username>`")
            return

    async with ctx.typing():
        try:
            data = await ai.hypixel.get_player_data(username, uuid=mc_uuid)
        except Exception as e:
            await ctx.reply(f"Error fetching data: {e}")
            return

        if not data:
            await ctx.reply(f"Could not find player **{username}**.")
            return

        stats = data["stats"]
        hotm_perks = stats.get("hotm_perks", {})
        hotm_xp = stats.get("hotm_xp", 0)
        hotm_lvl = sum(1 for req in HOTM_XP[1:] if hotm_xp >= req)

        powder = {
            "mithril": stats.get("mithril_powder", 0),
            "gemstone": stats.get("gemstone_powder", 0),
            "glacite": stats.get("glacite_powder", 0),
        }
        selected = stats.get("hotm_selected_ability", "")

        buf = render_hotm_tree(hotm_perks, powder, hotm_lvl, selected, username)
        file = discord.File(buf, filename="hotm.png")

        embed = discord.Embed(
            title=f"{username}'s Heart of the Mountain",
            color=0x2E8B82,
        )
        embed.set_image(url="attachment://hotm.png")

        # Add powder summary to embed
        mp = stats.get("mithril_powder", 0)
        gp = stats.get("gemstone_powder", 0)
        glp = stats.get("glacite_powder", 0)
        spent_m = stats.get("powder_spent_mithril", 0)
        spent_g = stats.get("powder_spent_gemstone", 0)
        spent_gl = stats.get("powder_spent_glacite", 0)

        powder_text = (
            f"Mithril: **{mp:,}** available ({spent_m:,} spent)\n"
            f"Gemstone: **{gp:,}** available ({spent_g:,} spent)\n"
            f"Glacite: **{glp:,}** available ({spent_gl:,} spent)"
        )
        embed.add_field(name="Powder", value=powder_text, inline=False)

        if selected:
            embed.add_field(name="Active Ability", value=selected.replace("_", " ").title(), inline=True)
        embed.add_field(name="HotM Tier", value=str(hotm_lvl), inline=True)

        await ctx.reply(embed=embed, file=file)


@bot.command(name="mayor")
async def mayor_command(ctx: commands.Context):
    """Show the current Skyblock mayor, their perks, and active election info."""
    async with ctx.typing():
        try:
            embed = await _run_mayor_tool()
        except Exception as e:
            print(f"[bot] Mayor command failed: {e}")
            embed = None

    if embed:
        await ctx.reply(embed=embed)
    else:
        await ctx.reply("Couldn't fetch mayor/election data right now. Try again later.")


@bot.command(name="bazaar")
async def bazaar_command(ctx: commands.Context, *, item: str = None):
    """Quick bazaar price lookup without AI."""
    if not item:
        await ctx.reply("Usage: `!bazaar <item name>` — e.g. `!bazaar enchanted diamond`")
        return

    async with ctx.typing():
        results = await ai.hypixel.search_bazaar(item)

    if not results:
        await ctx.reply(f"No bazaar results found for `{item}`.")
        return

    lines = [f"**Bazaar prices for `{item}`:**"]
    for r in results[:10]:
        lines.append(f"`{r['id']}` — Buy: **{r['buy']:,.1f}** | Sell: **{r['sell']:,.1f}** coins")

    await ctx.reply("\n".join(lines))


@bot.command(name="flips")
async def flips_command(ctx: commands.Context, mode: str = "baz", *, extra: str = ""):
    """
    !flips            — Top Bazaar flips (uses historical data if available)
    !flips ah         — Top AH BIN snipe opportunities
    !flips trend <item> — Price trend for a specific item
    !flips surges     — Items with demand spikes right now
    !flips volatile   — Most price-volatile items (risky/opportunity)
    """
    if ALLOWED_CHANNELS and ctx.channel.id not in ALLOWED_CHANNELS:
        return

    mode = mode.lower()

    async with ctx.typing():
        # ── Trend lookup ──────────────────────────────────────────────────────
        if mode == "trend":
            item_id = extra.upper().replace(" ", "_") if extra else ""
            if not item_id:
                await ctx.reply("Usage: `!flips trend <item name>` e.g. `!flips trend enchanted diamond`")
                return
            history = tracker.get_history(item_id, hours=24)
            if not history:
                await ctx.reply(f"No history data for `{item_id}` yet. Data accumulates every 5 minutes.")
                return
            trend = tracker.get_trend(item_id, hours=6)
            arrow = {"rising": "📈", "falling": "📉", "stable": "➡️"}.get(trend["direction"], "❓")
            embed = discord.Embed(
                title=f"{arrow} {item_id.replace('_', ' ').title()} — Price Trend",
                color=0x3498DB,
            )
            embed.add_field(name="6h Trend", value=f"{trend['direction'].title()} ({trend['pct_change']:+.2f}%)", inline=True)
            embed.add_field(name="Avg Buy", value=f"{trend.get('avg_buy', 0):,.1f}", inline=True)
            embed.add_field(name="Avg Sell", value=f"{trend.get('avg_sell', 0):,.1f}", inline=True)
            embed.add_field(name="Data Points (24h)", value=str(len(history)), inline=True)
            history_text = tracker.format_history_for_ai(item_id, hours=24)
            if history_text:
                embed.add_field(name="Sample Snapshots", value=f"```{history_text}```", inline=False)
            await ctx.reply(embed=embed)
            return

        # ── Demand surges ─────────────────────────────────────────────────────
        if mode == "surges":
            surges = tracker.get_demand_surges(hours=3)
            if not surges:
                await ctx.reply("No significant demand surges detected in the last 3 hours. Data builds up over time.")
                return
            embed = discord.Embed(
                title="🚀 Demand Surges (Last 3h)",
                description="Items with a spike in buy order volume — potential price increase incoming.",
                color=0x9B59B6,
            )
            for s in surges[:8]:
                embed.add_field(
                    name=s["name"],
                    value=(
                        f"Surge: **+{s['surge_pct']}%** | Peak vol: **{s['peak_vol']:,}** "
                        f"(avg: {s['avg_vol']:,})\n"
                        f"Avg buy: **{s['avg_buy']:,}** | Avg sell: **{s['avg_sell']:,}**"
                    ),
                    inline=False,
                )
            embed.set_footer(text="Volume spike = players buying heavily = price may rise soon")
            await ctx.reply(embed=embed)
            return

        # ── Volatile items ────────────────────────────────────────────────────
        if mode == "volatile":
            vol_items = tracker.get_volatile_items(hours=6)
            if not vol_items:
                await ctx.reply("No volatile items detected in the last 6 hours yet. Data accumulates every 5 minutes.")
                return
            embed = discord.Embed(
                title="⚡ Most Volatile Items (6h)",
                description="High price swing = risky but can be timed for profit.",
                color=0xE74C3C,
            )
            for v in vol_items[:8]:
                embed.add_field(
                    name=v["name"],
                    value=(
                        f"Swing: **{v['swing_pct']}%** | Low: {v['min']:,} → High: {v['max']:,}\n"
                        f"Avg buy: {v['avg_buy']:,} | Avg sell: {v['avg_sell']:,}"
                    ),
                    inline=False,
                )
            await ctx.reply(embed=embed)
            return

        # ── AH flips ──────────────────────────────────────────────────────────
        if mode in ("ah", "auction"):
            flips = await ai.hypixel.get_ah_flips()
            if not flips:
                await ctx.reply("No AH flip data available right now. Try again in a moment.")
                return
            embed = discord.Embed(
                title="🏷️ Top AH BIN Flip Opportunities",
                description="Buy at lowest BIN → relist at recent median sold price.",
                color=0xE67E22,
            )
            for f in flips[:8]:
                embed.add_field(
                    name=f["name"],
                    value=(
                        f"Buy BIN: **{f['bin']:,}** | Median sold: **{f['median_sold']:,}**\n"
                        f"Profit: **+{f['margin']:,}** ({f['margin_pct']}%) | {f['sales_count']} recent sales"
                    ),
                    inline=False,
                )
            embed.set_footer(text="Data: Hypixel ended auctions + moulberry.codes BIN • Use !flips for Bazaar flips")
            await ctx.reply(embed=embed)
            return

        # ── Bazaar flips (smart if history available, else live) ──────────────
        age = tracker.last_snapshot_age()
        use_smart = age is not None and age < 1800  # have data < 30 min old

        if use_smart:
            flips = tracker.get_smart_flips()
            title = "📈 Top Bazaar Flips (Historical Analysis)"
            desc = "Ranked by margin% × liquidity × trend. Uses 6h avg prices."
            footer = f"Based on historical data ({age // 60}m old) • !flips ah | !flips surges | !flips volatile"
        else:
            flips = await ai.hypixel.get_bazaar_flips()
            title = "📈 Top Bazaar Flip Opportunities"
            desc = "Live snapshot. Historical analysis starts after ~15 min of data collection."
            footer = "Use !flips ah for AH flips | !flips surges | !flips volatile"

        if not flips:
            await ctx.reply("No Bazaar flip data available right now. Try again in a moment.")
            return

        embed = discord.Embed(title=title, description=desc, color=0x2ECC71)
        for f in flips[:10]:
            trend_icon = {"rising": "📈", "falling": "📉", "stable": "➡️"}.get(f.get("trend", ""), "")
            trend_str = f" {trend_icon} {f['trend']} ({f['trend_pct']:+.1f}%)" if f.get("trend") else ""
            embed.add_field(
                name=f["name"],
                value=(
                    f"Buy: **{f['buy']:,.1f}** | Sell: **{f['sell']:,.1f}**\n"
                    f"Margin: **+{f['margin']:,.1f}** ({f['margin_pct']}% net) | "
                    f"Vol: **{f['weekly_vol']:,}**/wk | Orders: {f['buy_orders']}B/{f['sell_orders']}S"
                    + (f"\n{trend_str}" if trend_str else "")
                ),
                inline=False,
            )
        embed.set_footer(text=footer)
        await ctx.reply(embed=embed)


@bot.command(name="skyblock", aliases=["help"])
async def help_command(ctx: commands.Context):
    embed = discord.Embed(
        title="Hypixel Skyblock AI Bot",
        color=0x5865F2
    )
    embed.add_field(
        name="!ai <question>",
        value="Ask anything about Skyblock — prices, builds, guides, personalized advice.",
        inline=False
    )
    embed.add_field(
        name="!profile [ign]",
        value="Full profile overview — networth, skills, slayers, gear, pets.",
        inline=False
    )
    embed.add_field(
        name="!skills [ign]",
        value="View all skill levels and skill average.",
        inline=False
    )
    embed.add_field(
        name="!slayer [ign]",
        value="View slayer levels and XP.",
        inline=False
    )
    embed.add_field(
        name="!dungeons [ign]",
        value="Dungeon stats — catacombs level, classes, floor completions.",
        inline=False
    )
    embed.add_field(
        name="!pets [ign]",
        value="View all pets with levels and rarities.",
        inline=False
    )
    embed.add_field(
        name="!hotm [ign]",
        value="Heart of the Mountain tree as an image.",
        inline=False
    )
    embed.add_field(
        name="!mp [ign]",
        value="Cheapest accessories to max your MP — factors in recombobulation vs buying.",
        inline=False
    )
    embed.add_field(
        name="!mayor",
        value="Current mayor, perks, and active election candidates.",
        inline=False
    )
    embed.add_field(
        name="!bazaar <item> / !flips / !flips ah",
        value="Bazaar prices, flip opportunities, and AH snipes.",
        inline=False
    )
    embed.add_field(
        name="!link <ign> / !unlink",
        value="Link your Minecraft account for personalized advice.",
        inline=False
    )
    embed.add_field(
        name="!correct <topic> | <correction>",
        value="Submit a correction if the bot gets something wrong.",
        inline=False
    )
    embed.add_field(
        name="!stats",
        value="Bot usage statistics.",
        inline=False
    )
    await ctx.send(embed=embed)


async def _get_player_or_reply(ctx, username: str = None) -> tuple:
    """Fetch player data, using linked account if no username given.
    Returns (data, username, mc_uuid) or sends error reply and returns (None, None, None).
    """
    mc_uuid = None
    if not username:
        linked_name = get_linked_username(ctx.author.id)
        if not linked_name:
            await ctx.reply("Link your account first with `!link <ign>`, or provide a username.")
            return None, None, None
        username = linked_name
        mc_uuid = get_linked_uuid(ctx.author.id)

    async with ctx.typing():
        try:
            data = await ai.hypixel.get_player_data(username, uuid=mc_uuid)
        except Exception as e:
            print(f"[bot] Player data fetch failed for {username}: {e}")
            data = None

    if not data:
        await ctx.reply(f"Couldn't find Skyblock data for **{username}**. Check spelling and make sure your API is enabled in Hypixel settings.")
        return None, None, None

    return data, data.get("username", username), mc_uuid


@bot.command(name="skills")
async def skills_command(ctx: commands.Context, *, username: str = None):
    """View skill levels for a player."""
    data, username, _ = await _get_player_or_reply(ctx, username)
    if not data:
        return

    from player_stats import _format_number, SKILL_MAX
    stats = data["stats"]
    skills = stats.get("skills", {})
    profile = data.get("profile_name", "?")

    embed = discord.Embed(
        title=f"{username}'s Skills",
        description=f"Profile: {profile}",
        color=0x3498DB,
    )

    # Calculate skill average (exclude Runecrafting, Social, Carpentry)
    avg_skills = {k: v for k, v in skills.items() if k not in ("Runecrafting", "Social", "Carpentry")}
    if avg_skills:
        sa = sum(v["level"] for v in avg_skills.values()) / len(avg_skills)
        embed.description += f" | Skill Average: **{sa:.1f}**"

    for name, info in skills.items():
        cap = SKILL_MAX.get(name, 50)
        lvl = info["level"]
        xp = info["xp"]
        bar = "█" * (lvl * 10 // cap) + "░" * (10 - lvl * 10 // cap)
        embed.add_field(
            name=f"{name} {lvl}/{cap}",
            value=f"`{bar}` {_format_number(xp)} XP",
            inline=True,
        )

    await ctx.reply(embed=embed)


@bot.command(name="slayer")
async def slayer_command(ctx: commands.Context, *, username: str = None):
    """View slayer levels for a player."""
    data, username, _ = await _get_player_or_reply(ctx, username)
    if not data:
        return

    from player_stats import _format_number
    stats = data["stats"]
    slayers = stats.get("slayer", {})
    profile = data.get("profile_name", "?")

    embed = discord.Embed(
        title=f"{username}'s Slayers",
        description=f"Profile: {profile}",
        color=0xE74C3C,
    )

    total_xp = 0
    for name, info in slayers.items():
        lvl = info["level"]
        xp = info["xp"]
        total_xp += xp
        bar = "█" * min(lvl, 9) + "░" * max(0, 9 - lvl)
        embed.add_field(
            name=f"{name} {lvl}/9",
            value=f"`{bar}` {_format_number(xp)} XP",
            inline=True,
        )

    embed.set_footer(text=f"Total Slayer XP: {total_xp:,}")
    await ctx.reply(embed=embed)


@bot.command(name="pets")
async def pets_command(ctx: commands.Context, *, username: str = None):
    """View a player's pets."""
    data, username, _ = await _get_player_or_reply(ctx, username)
    if not data:
        return

    from player_stats import _pet_level
    stats = data["stats"]
    pets = stats.get("pets", [])
    profile = data.get("profile_name", "?")

    embed = discord.Embed(
        title=f"{username}'s Pets",
        description=f"Profile: {profile} | Total: {len(pets)} pets",
        color=0xF1C40F,
    )

    tier_colors = {"COMMON": "⬜", "UNCOMMON": "🟩", "RARE": "🟦", "EPIC": "🟪", "LEGENDARY": "🟨", "MYTHIC": "🟥", "DIVINE": "🩵"}

    # Active pet first
    active = [p for p in pets if p.get("active")]
    if active:
        p = active[0]
        lvl = _pet_level(p["xp"], p["tier"])
        held = p["held_item"].replace("PET_ITEM_", "").replace("_", " ").title() if p["held_item"] else "None"
        icon = tier_colors.get(p["tier"], "⬜")
        embed.add_field(
            name=f"{icon} ACTIVE: {p['type'].replace('_', ' ').title()} (Lvl {lvl})",
            value=f"Rarity: {p['tier'].title()} | Held item: {held}",
            inline=False,
        )

    # Top pets by level (sorted by XP)
    sorted_pets = sorted(pets, key=lambda x: x["xp"], reverse=True)
    lines = []
    for p in sorted_pets[:20]:
        if p.get("active"):
            continue
        lvl = _pet_level(p["xp"], p["tier"])
        icon = tier_colors.get(p["tier"], "⬜")
        name = p["type"].replace("_", " ").title()
        lines.append(f"{icon} **{name}** — Lvl {lvl} ({p['tier'].title()})")

    if lines:
        # Split into chunks for embed field limit
        for i in range(0, len(lines), 10):
            chunk = "\n".join(lines[i:i+10])
            embed.add_field(name="Top Pets" if i == 0 else "\u200b", value=chunk, inline=False)

    await ctx.reply(embed=embed)


@bot.command(name="dungeons")
async def dungeons_command(ctx: commands.Context, *, username: str = None):
    """View dungeon stats for a player."""
    data, username, _ = await _get_player_or_reply(ctx, username)
    if not data:
        return

    from player_stats import _format_number
    stats = data["stats"]
    profile = data.get("profile_name", "?")

    cata_lvl = stats.get("catacombs_level", 0)
    cata_xp = stats.get("catacombs_xp", 0)
    sel_class = stats.get("selected_class", "None")

    embed = discord.Embed(
        title=f"{username}'s Dungeons",
        description=f"Profile: {profile} | Catacombs **{cata_lvl}** ({_format_number(cata_xp)} XP) | Class: {sel_class}",
        color=0x9B59B6,
    )

    # Classes
    classes = stats.get("dungeon_classes", {})
    if classes:
        class_lines = []
        for name, info in classes.items():
            lvl = info["level"]
            bar = "█" * (lvl * 10 // 50) + "░" * (10 - lvl * 10 // 50)
            class_lines.append(f"**{name}** {lvl} `{bar}`")
        embed.add_field(name="Classes", value="\n".join(class_lines), inline=False)

    # Floor completions
    completions = stats.get("floor_completions", {})
    if completions:
        normal = {k: v for k, v in completions.items() if k.startswith("F")}
        master = {k: v for k, v in completions.items() if k.startswith("M")}

        if normal:
            text = " | ".join(f"**{k}**: {v}" for k, v in sorted(normal.items()))
            embed.add_field(name="Normal Floors", value=text, inline=False)
        if master:
            text = " | ".join(f"**{k}**: {v}" for k, v in sorted(master.items()))
            embed.add_field(name="Master Mode", value=text, inline=False)

    await ctx.reply(embed=embed)


@bot.command(name="profile")
async def profile_command(ctx: commands.Context, *, username: str = None):
    """View a full profile overview for a player."""
    data, username, _ = await _get_player_or_reply(ctx, username)
    if not data:
        return

    from player_stats import _format_number, _pet_level, SKILL_MAX
    from hypixel_api import HOTM_XP
    stats = data["stats"]
    profile = data.get("profile_name", "?")

    embed = discord.Embed(
        title=f"{username}'s Profile",
        description=f"Profile: {profile}",
        color=0x5865F2,
    )

    # Skyblock Level
    sb_xp = stats.get("sb_xp", 0)
    if sb_xp:
        embed.description += f" | SB Level: **{int(sb_xp / 100)}**"

    # Networth
    nw = stats.get("networth")
    if nw and nw.get("total"):
        embed.add_field(
            name="Networth",
            value=f"**{_format_number(nw['total'])}** (Purse: {_format_number(nw.get('purse', 0))} | Bank: {_format_number(nw.get('bank', 0))})",
            inline=False,
        )
    else:
        purse = stats.get("purse", 0)
        bank = stats.get("bank", 0)
        embed.add_field(name="Coins", value=f"Purse: {_format_number(purse)} | Bank: {_format_number(bank)}", inline=False)

    # Skills
    skills = stats.get("skills", {})
    avg_skills = {k: v for k, v in skills.items() if k not in ("Runecrafting", "Social", "Carpentry")}
    if avg_skills:
        sa = sum(v["level"] for v in avg_skills.values()) / len(avg_skills)
        skill_text = " ".join(f"{k[:3]} {v['level']}" for k, v in skills.items() if v["level"] > 0)
        embed.add_field(name=f"Skills (SA {sa:.1f})", value=skill_text or "None", inline=False)

    # Slayers
    slayers = stats.get("slayer", {})
    slayer_parts = [f"{k} {v['level']}" for k, v in slayers.items() if v["level"] > 0]
    if slayer_parts:
        embed.add_field(name="Slayers", value=" | ".join(slayer_parts), inline=True)

    # Dungeons
    cata_lvl = stats.get("catacombs_level", 0)
    sel_class = stats.get("selected_class", "None")
    embed.add_field(name="Catacombs", value=f"Level {cata_lvl} | {sel_class}", inline=True)

    # HotM
    hotm_xp = stats.get("hotm_xp", 0)
    hotm_lvl = sum(1 for req in HOTM_XP[1:] if hotm_xp >= req)
    embed.add_field(name="HotM", value=str(hotm_lvl), inline=True)

    # Magic Power
    mp = stats.get("magical_power", 0)
    power = stats.get("selected_power", "")
    if mp:
        embed.add_field(name="Magic Power", value=f"{mp:,} ({power})" if power else f"{mp:,}", inline=True)

    # Active pet
    pets = stats.get("pets", [])
    active = [p for p in pets if p.get("active")]
    if active:
        p = active[0]
        lvl = _pet_level(p["xp"], p["tier"])
        embed.add_field(name="Active Pet", value=f"{p['type'].title()} Lvl {lvl} ({p['tier'].title()})", inline=True)

    # Fairy souls
    embed.add_field(name="Fairy Souls", value=str(stats.get("fairy_souls", 0)), inline=True)

    # Armor
    armor = [a["name"] for a in stats.get("armor", []) if a.get("name")]
    if armor:
        embed.add_field(name="Armor", value=", ".join(armor), inline=False)

    await ctx.reply(embed=embed)


@bot.command(name="mp")
async def mp_command(ctx: commands.Context, *, username: str = None):
    """Show cheapest accessories to maximize MP, factoring in recombobulation."""
    from mp_optimizer import get_accessory_mp_rankings, format_mp_plan

    data, username, _ = await _get_player_or_reply(ctx, username)
    if not data:
        return

    async with ctx.typing():
        stats = data["stats"]
        current_mp = stats.get("magical_power", 0)

        # Get owned accessory IDs
        owned_ids = set()
        for acc in stats.get("accessories", []):
            if acc.get("id"):
                owned_ids.add(acc["id"])

        rankings = await get_accessory_mp_rankings(ai.hypixel, owned_ids=owned_ids)
        if not rankings:
            await ctx.reply("Couldn't fetch accessory price data right now. Try again in a moment.")
            return

        plan = format_mp_plan(
            rankings, current_mp=current_mp,
            owned_ids=owned_ids, target_count=20,
        )
        recomb_price = rankings[0]["recomb_price"]

        embed = discord.Embed(
            title=f"MP Upgrades for {username}",
            color=0x9B59B6,
        )
        embed.description = f"Current MP: **{current_mp:,}** | Owned accessories: **{len(owned_ids)}**"
        embed.set_footer(
            text=f"Recombobulator 3000: {recomb_price:,.0f} coins | Prices: lowest BIN"
        )

        lines = plan.split("\n")
        summary = lines[0] if lines else ""
        detail_lines = [l for l in lines[1:] if l.strip()]

        if summary:
            embed.add_field(name="Plan", value=summary, inline=False)

        chunk = []
        chunk_len = 0
        field_num = 1
        for line in detail_lines:
            if chunk_len + len(line) + 1 > 1000:
                embed.add_field(
                    name=f"Recommendations ({field_num})" if field_num > 1 else "Recommendations",
                    value="\n".join(chunk), inline=False,
                )
                chunk = []
                chunk_len = 0
                field_num += 1
            chunk.append(line)
            chunk_len += len(line) + 1
        if chunk:
            embed.add_field(
                name=f"Recommendations ({field_num})" if field_num > 1 else "Recommendations",
                value="\n".join(chunk), inline=False,
            )

    await ctx.reply(embed=embed)


@bot.command(name="link")
async def link_command(ctx: commands.Context, *, username: str = None):
    """Link your Discord account to your Minecraft IGN for personalized advice."""
    if not username:
        # Check if already linked
        existing = get_linked_username(ctx.author.id)
        if existing:
            await ctx.reply(f"You're linked as **{existing}**. Use `!unlink` to remove or `!link <new_ign>` to change.")
        else:
            await ctx.reply("Usage: `!link <minecraft_ign>` — Links your account so I can give personalized advice.")
        return

    username = username.strip().split()[0]  # take first word only
    if len(username) < 3 or len(username) > 16:
        await ctx.reply("That doesn't look like a valid Minecraft username (3-16 characters).")
        return

    async with ctx.typing():
        # Verify the username exists on Hypixel
        try:
            data = await ai.hypixel.get_player_data(username)
        except Exception as e:
            print(f"[bot] Link player data fetch failed for {username}: {e}")
            data = None

    if not data:
        await ctx.reply(f"Couldn't find Hypixel Skyblock data for **{username}**. Check the spelling and make sure Skyblock API is enabled in Hypixel settings.")
        return

    # Store UUID so name changes don't break the link
    mc_uuid = None
    try:
        mc_uuid = await ai.hypixel.get_uuid(username)
    except Exception as e:
        print(f"[bot] UUID lookup failed for {username}: {e}")
    link_user(ctx.author.id, username, mc_uuid=mc_uuid)
    profile = data.get("profile_name", "?")
    await ctx.reply(f"Linked! **{username}** (profile: {profile}). I'll now use your stats for personalized advice when you use `!ai`.")


@bot.command(name="unlink")
async def unlink_command(ctx: commands.Context):
    """Unlink your Minecraft account."""
    if unlink_user(ctx.author.id):
        await ctx.reply("Unlinked. I'll no longer auto-fetch your stats.")
    else:
        await ctx.reply("You don't have a linked account. Use `!link <ign>` to link one.")


@bot.command(name="stats")
async def stats_command(ctx: commands.Context):
    """Show bot usage statistics."""
    import sqlite3
    from pathlib import Path

    data_dir = Path(__file__).parent / "data"

    # Feedback stats
    fb_db = data_dir / "feedback.db"
    total_feedback = upvotes = downvotes = unanswered = 0
    if fb_db.exists():
        con = sqlite3.connect(fb_db)
        total_feedback = con.execute("SELECT COUNT(*) FROM feedback").fetchone()[0]
        upvotes = con.execute("SELECT COUNT(*) FROM feedback WHERE vote = 'up'").fetchone()[0]
        downvotes = con.execute("SELECT COUNT(*) FROM feedback WHERE vote = 'down'").fetchone()[0]
        unanswered = con.execute("SELECT COUNT(*) FROM unanswered WHERE resolved = 0").fetchone()[0]
        con.close()

    # Upvote ratio
    total_votes = upvotes + downvotes
    if total_votes > 0:
        upvote_pct = (upvotes / total_votes) * 100
        ratio_text = f"{upvotes:,} / {downvotes:,} ({upvote_pct:.1f}% positive)"
    else:
        ratio_text = "No votes yet"

    # Linked accounts
    links_db = data_dir / "user_links.db"
    linked_accounts = 0
    if links_db.exists():
        con = sqlite3.connect(links_db)
        linked_accounts = con.execute("SELECT COUNT(*) FROM links").fetchone()[0]
        con.close()

    # Bazaar data
    baz_db = data_dir / "bazaar_history.db"
    baz_snapshots = 0
    baz_span_text = "No data yet"
    if baz_db.exists():
        con = sqlite3.connect(baz_db)
        baz_snapshots = con.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0]
        if baz_snapshots > 0:
            row = con.execute("SELECT MIN(ts), MAX(ts) FROM snapshots").fetchone()
            if row and row[0] and row[1]:
                span_seconds = row[1] - row[0]
                days = span_seconds / 86400
                if days >= 1:
                    baz_span_text = f"{days:.1f} days"
                else:
                    hours = span_seconds / 3600
                    baz_span_text = f"{hours:.1f} hours"
        con.close()

    embed = discord.Embed(title="Bot Usage Statistics", color=0x2ECC71)
    embed.add_field(name="Total Questions Answered", value=f"{total_feedback:,}", inline=False)
    embed.add_field(name="Upvotes / Downvotes", value=ratio_text, inline=False)
    embed.add_field(name="Unanswered Questions", value=f"{unanswered:,}", inline=True)
    embed.add_field(name="Linked Accounts", value=f"{linked_accounts:,}", inline=True)
    embed.add_field(
        name="Bazaar Data",
        value=f"{baz_snapshots:,} data points over {baz_span_text}",
        inline=False,
    )

    await ctx.reply(embed=embed)


@bot.command(name="reload")
@commands.is_owner()
async def reload_knowledge(ctx: commands.Context):
    """Reload knowledge files from disk (owner only)."""
    ai.knowledge.reload()
    files = ai.knowledge.list_files()
    await ctx.reply(f"Reloaded {len(files)} knowledge files: {', '.join(files)}")


@bot.command(name="correct")
async def correct_command(ctx: commands.Context, *, content: str = None):
    """Submit a correction: !correct <topic> | <correction>"""
    if not content or "|" not in content:
        await ctx.reply("Usage: `!correct <topic> | <the correct info>` — e.g. `!correct snow minion | T11 snow minion with diamond spreading makes ~1.2M/day, not 800k`")
        return

    topic, correction = content.split("|", 1)
    topic, correction = topic.strip(), correction.strip()
    if not topic or not correction:
        await ctx.reply("Both topic and correction are required. Use `|` to separate them.")
        return

    row_id = submit_correction(ctx.author.id, str(ctx.author), topic, correction)
    if row_id is None:
        await ctx.reply("You already have 3 pending corrections. Wait for them to be reviewed first.")
        return

    await ctx.reply(f"Correction submitted (#{row_id}). An admin will review it — thanks!")


@bot.command(name="corrections")
@commands.is_owner()
async def corrections_command(ctx: commands.Context):
    """List pending corrections (owner only)."""
    pending = get_pending(10)
    if not pending:
        await ctx.reply("No pending corrections.")
        return

    embed = discord.Embed(title=f"Pending Corrections ({len(pending)})", color=0xF1C40F)
    for c in pending:
        embed.add_field(
            name=f"#{c['id']} — {c['topic']}",
            value=f"{c['correction'][:200]}\n*— {c['discord_name']}*",
            inline=False,
        )
    embed.set_footer(text="!approve <id> or !reject <id>")
    await ctx.reply(embed=embed)


@bot.command(name="approve")
@commands.is_owner()
async def approve_command(ctx: commands.Context, correction_id: int = None):
    """Approve a pending correction (owner only)."""
    if correction_id is None:
        await ctx.reply("Usage: `!approve <id>`")
        return

    result = approve_correction(correction_id)
    if not result:
        await ctx.reply(f"Correction #{correction_id} not found or already reviewed.")
        return

    ai.knowledge.reload()
    await ctx.reply(f"Approved #{correction_id} (**{result['topic']}**) — added to knowledge base.")


@bot.command(name="reject")
@commands.is_owner()
async def reject_command(ctx: commands.Context, correction_id: int = None):
    """Reject a pending correction (owner only)."""
    if correction_id is None:
        await ctx.reply("Usage: `!reject <id>`")
        return

    if reject_correction(correction_id):
        await ctx.reply(f"Rejected #{correction_id}.")
    else:
        await ctx.reply(f"Correction #{correction_id} not found or already reviewed.")


@bot.event
async def on_reaction_add(reaction: discord.Reaction, user: discord.User):
    """Handle thumbs up/down reactions on bot responses."""
    if user.bot:
        return
    msg_id = reaction.message.id
    if msg_id not in _recent_responses:
        return
    emoji = str(reaction.emoji)
    if emoji not in ("👍", "👎"):
        return

    question, response, author_id, author_name = _recent_responses[msg_id]
    vote = "up" if emoji == "👍" else "down"
    log_vote(user.id, str(user), question, response, vote)


@bot.command(name="feedback")
@commands.is_owner()
async def feedback_command(ctx: commands.Context):
    """Show feedback stats and recent bad responses with IDs (owner only)."""
    stats = get_feedback_stats()
    embed = discord.Embed(title="Bot Feedback", color=0xE74C3C)
    embed.add_field(name="Votes", value=f"👍 {stats['thumbs_up']} | 👎 {stats['thumbs_down']}", inline=True)
    embed.add_field(name="Unanswered", value=str(stats['unanswered']), inline=True)

    bad = get_bad_responses(10)
    if bad:
        for b in bad:
            embed.add_field(
                name=f"#{b['id']} 👎 {b['discord_name']}",
                value=f"**Q:** {b['question'][:100]}\n**A:** {b['response'][:100]}",
                inline=False,
            )

    unans = get_unanswered(10)
    if unans:
        q_list = "\n".join(f"- **#{u['id']}** {u['question'][:80]}" for u in unans)
        embed.add_field(name="Unanswered questions", value=q_list[:1000], inline=False)

    embed.set_footer(text="!resolve <id> — mark fixed | !resolve all — clear all")
    await ctx.reply(embed=embed)


@bot.command(name="analyze")
@commands.is_owner()
async def analyze_command(ctx: commands.Context, fresh: str = None):
    """Run feedback analysis agent (owner only). Use '!analyze fresh' to force a new analysis."""
    if fresh and fresh.lower() == "fresh":
        await ctx.reply("Running fresh feedback analysis... this may take a moment.")
        try:
            report = await analyze_feedback()
        except Exception as e:
            await ctx.reply(f"Analysis failed: {e}")
            return
    else:
        report = get_last_analysis()
        if not report:
            await ctx.reply("No previous analysis found. Running fresh analysis...")
            try:
                report = await analyze_feedback()
            except Exception as e:
                await ctx.reply(f"Analysis failed: {e}")
                return

    # Split into chunks for Discord's 2000 char limit
    chunks = []
    while report:
        if len(report) <= 1900:
            chunks.append(report)
            break
        split_at = report.rfind("\n", 0, 1900)
        if split_at == -1:
            split_at = 1900
        chunks.append(report[:split_at])
        report = report[split_at:].lstrip("\n")

    for chunk in chunks:
        await ctx.reply(chunk)


@bot.command(name="resolve")
@commands.is_owner()
async def resolve_command(ctx: commands.Context, target: str = None):
    """Mark feedback as resolved (owner only). Use '!resolve all' or '!resolve <id>'."""
    if not target:
        await ctx.reply("Usage: `!resolve all` or `!resolve <id>`")
        return

    if target.lower() == "all":
        count = resolve_all_feedback()
        await ctx.reply(f"Resolved {count} feedback entries. `!analyze fresh` will now only show new issues.")
    elif target.isdigit():
        if resolve_feedback(int(target)):
            await ctx.reply(f"Resolved feedback #{target}.")
        else:
            await ctx.reply(f"Feedback #{target} not found or already resolved.")
    else:
        await ctx.reply("Usage: `!resolve all` or `!resolve <id>`")


@bot.event
async def on_command_error(ctx: commands.Context, error):
    if isinstance(error, commands.CommandNotFound):
        return  # ignore unknown commands
    raise error


bot.run(os.getenv("DISCORD_TOKEN"))
