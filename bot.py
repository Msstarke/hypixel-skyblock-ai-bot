import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
from ai_handler import AIHandler

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)
ai = AIHandler()

# Optional: restrict to specific channel IDs
ALLOWED_CHANNELS = set()
raw = os.getenv("AI_CHANNELS", "")
if raw.strip():
    ALLOWED_CHANNELS = {int(c.strip()) for c in raw.split(",") if c.strip().isdigit()}


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print(f"Serving {len(bot.guilds)} guild(s)")


@bot.command(name="ai")
async def ai_command(ctx: commands.Context, *, question: str = None):
    if not question:
        await ctx.reply("Usage: `!ai <your question>` — e.g. `!ai what's the cost of 655 enchanted diamonds?`")
        return

    if ALLOWED_CHANNELS and ctx.channel.id not in ALLOWED_CHANNELS:
        return  # silently ignore if channel-restricted

    async with ctx.typing():
        response = await ai.get_response(question)

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
        name="Examples",
        value=(
            "`!ai what's the total cost of 655 enchanted diamonds?`\n"
            "`!ai how much profit per hour does a t11 wheat minion make?`\n"
            "`!ai what's the best reforge for berserker armor?`\n"
            "`!bazaar enchanted diamond`"
        ),
        inline=False
    )
    await ctx.send(embed=embed)


@bot.event
async def on_command_error(ctx: commands.Context, error):
    if isinstance(error, commands.CommandNotFound):
        return  # ignore unknown commands
    raise error


bot.run(os.getenv("DISCORD_TOKEN"))
