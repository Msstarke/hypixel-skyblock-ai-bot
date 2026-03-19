import os
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
from ai_handler import AIHandler
from bazaar_tracker import BazaarTracker, SNAPSHOT_INTERVAL
from user_links import link_user, unlink_user, get_linked_username

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)
ai = AIHandler()
tracker = BazaarTracker()
ai.tracker = tracker  # share tracker with AI handler for context injection

# Optional: restrict to specific channel IDs
ALLOWED_CHANNELS = set()
raw = os.getenv("AI_CHANNELS", "")
if raw.strip():
    ALLOWED_CHANNELS = {int(c.strip()) for c in raw.split(",") if c.strip().isdigit()}


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


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print(f"Serving {len(bot.guilds)} guild(s)")
    snapshot_bazaar.start()


@bot.command(name="ai")
async def ai_command(ctx: commands.Context, *, question: str = None):
    if not question:
        await ctx.reply("Usage: `!ai <your question>` — e.g. `!ai what's the cost of 655 enchanted diamonds?`")
        return

    if ALLOWED_CHANNELS and ctx.channel.id not in ALLOWED_CHANNELS:
        return  # silently ignore if channel-restricted

    async with ctx.typing():
        response = await ai.get_response(question, discord_user_id=ctx.author.id)

    await ctx.reply(response)


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


@bot.command(name="skyblock")
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
        name="Examples",
        value=(
            "`!ai what's the total cost of 655 enchanted diamonds?`\n"
            "`!ai how much profit per hour does a t11 wheat minion make?`\n"
            "`!ai what's the best reforge for berserker armor?`\n"
            "`!bazaar enchanted diamond`\n"
            "`!flips` / `!flips ah`"
        ),
        inline=False
    )
    await ctx.send(embed=embed)


@bot.command(name="reload")
@commands.is_owner()
async def reload_knowledge(ctx: commands.Context):
    """Reload knowledge files from disk (owner only)."""
    ai.knowledge.reload()
    files = ai.knowledge.list_files()
    await ctx.reply(f"Reloaded {len(files)} knowledge files: {', '.join(files)}")


@bot.event
async def on_command_error(ctx: commands.Context, error):
    if isinstance(error, commands.CommandNotFound):
        return  # ignore unknown commands
    raise error


bot.run(os.getenv("DISCORD_TOKEN"))
