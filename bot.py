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

    return None


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
        value="Ask anything about Skyblock. Fetches live Bazaar prices when relevant.",
        inline=False
    )
    embed.add_field(
        name="!bazaar <item>",
        value="Quick Bazaar price lookup by item name.",
        inline=False
    )
    embed.add_field(
        name="!flips",
        value="Top Bazaar flip opportunities ranked by margin × liquidity.",
        inline=False
    )
    embed.add_field(
        name="!flips ah",
        value="Top AH BIN snipe opportunities (buy cheap, relist at median).",
        inline=False
    )
    embed.add_field(
        name="!hotm [username]",
        value="View a player's Heart of the Mountain tree as an image. Uses linked account if no name given.",
        inline=False
    )
    embed.add_field(
        name="!link <ign>",
        value="Link your Minecraft account for personalized advice, networth, and stats.",
        inline=False
    )
    embed.add_field(
        name="!correct <topic> | <correction>",
        value="Submit a correction if the bot gets something wrong. Reviewed by admins.",
        inline=False
    )
    embed.add_field(
        name="!stats",
        value="Show bot usage statistics — questions answered, vote ratios, linked accounts, and bazaar data.",
        inline=False
    )
    embed.add_field(
        name="Examples",
        value=(
            "`!ai whats my networth` (requires !link)\n"
            "`!ai hypermax divan helmet`\n"
            "`!ai whats the craft cost for glossy mineral helmet`\n"
            "`!bazaar enchanted diamond`\n"
            "`!flips` / `!flips ah`\n"
            "`!correct minions | T11 snow minion makes ~1.2M/day with diamond spreading`"
        ),
        inline=False
    )
    await ctx.send(embed=embed)


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
        except Exception:
            data = None

    if not data:
        await ctx.reply(f"Couldn't find Hypixel Skyblock data for **{username}**. Check the spelling and make sure Skyblock API is enabled in Hypixel settings.")
        return

    # Store UUID so name changes don't break the link
    mc_uuid = None
    try:
        mc_uuid = await ai.hypixel.get_uuid(username)
    except Exception:
        pass
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
