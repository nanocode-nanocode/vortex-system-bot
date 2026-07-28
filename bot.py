#!/usr/bin/env python3
"""
VØRTΞX System Bot v4 — Enterprise (PostgreSQL)
All-in-one: Moderation, Tickets, Levels, Welcome, Broadcast,
Reaction Roles, Anti-Raid, AutoMod, Custom Commands, Utility.

Database-backed • Auto-sharding • Auto-reconnect
"""
import discord
from discord.ext import commands
import json, os, sys, asyncio, signal
from pathlib import Path

BASE = Path(__file__).parent

# ── Config ─────────────────────────────────────────────────────────────
config_path = BASE / "config.json"
if config_path.exists():
    with open(config_path) as f:
        CONFIG = json.load(f)
else:
    CONFIG = {}

# ── Database ──────────────────────────────────────────────────────────
sys.path.insert(0, str(BASE))
try:
    from db import (
        close as db_close, incr_stat,
        add_audit, set_guild_config, init_defaults
    )
    HAS_DB = True
    init_defaults()
    print("✅ Database: PostgreSQL connected")
except Exception as e:
    HAS_DB = False
    print(f"⚠️ Database not available: {e}")

# ── Intents ────────────────────────────────────────────────────────────
intents = discord.Intents.all()

# ── Bot (with auto-sharding) ──────────────────────────────────────────
bot = commands.Bot(
    command_prefix=CONFIG.get("prefix", "!"),
    intents=intents,
    case_insensitive=True,
    help_command=None,
    # Auto-sharding — discord.py handles this automatically
    # Set shard_count=None for auto, or explicit for control
    shard_count=None,
    # Reconnect settings
    max_ratelimit_timeout=120,
)

# ── Cog loader ─────────────────────────────────────────────────────────
async def load_cogs():
    cogs_dir = BASE / "cogs"
    if not cogs_dir.exists():
        print("⚠️ No cogs directory found")
        return
    loaded = 0
    failed = 0
    for file in sorted(cogs_dir.glob("*.py")):
        if file.name.startswith("_"):
            continue
        cog_name = f"cogs.{file.stem}"
        try:
            await bot.load_extension(cog_name)
            print(f"✅ Loaded: {cog_name}")
            loaded += 1
        except Exception as e:
            print(f"❌ Failed {cog_name}: {e}")
            failed += 1
    print(f"\n📦 Cogs: {loaded} loaded, {failed} failed")

# ── Events ─────────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    if HAS_DB:
        from db import set_stat
        set_stat("total_guilds", len(bot.guilds))
        set_stat("total_users", sum(g.member_count or 0 for g in bot.guilds))
        add_audit("bot_start", f"Bot started with {len(bot.guilds)} guilds, {bot.shard_count or 1} shards")

    print(f"\n{'='*50}")
    print("  VØRTΞX System Bot v4 — Enterprise (DB)")
    print(f"  User: {bot.user} (ID: {bot.user.id})")
    print(f"  Guilds: {len(bot.guilds)}")
    print(f"  Users: {sum(g.member_count or 0 for g in bot.guilds):,}")
    print(f"  Shards: {bot.shard_count or 1}")
    print(f"  DB: {'✅ PostgreSQL' if HAS_DB else '⚠️ Local JSON'}")
    
    # Sync slash commands
    try:
        synced = await bot.tree.sync()
        print(f"  Synced: {len(synced)} slash commands")
    except Exception as e:
        print(f"  ⚠️ Sync error: {e}")
    
    print(f"{'='*50}\n")
    
    status_text = CONFIG.get("status", "⚡ VØRTΞX HOST")
    activity = discord.Activity(type=discord.ActivityType.watching, name=status_text)
    await bot.change_presence(activity=activity, status=discord.Status.dnd)

@bot.event
async def on_shard_ready(shard_id):
    print(f"🟢 Shard {shard_id} ready")

@bot.event
async def on_disconnect():
    print("⚠️ Bot disconnected — waiting for reconnect...")

@bot.event
async def on_resumed():
    print("🔄 Bot reconnected to Discord")

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    await bot.process_commands(message)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send(f"❌ | {ctx.author.mention} ما عندك صلاحية!", delete_after=5)
    elif isinstance(error, commands.BotMissingPermissions):
        await ctx.send("❌ | البوت ما عنده صلاحية!", delete_after=5)
    else:
        await ctx.send(f"⚠️ | خطأ: `{str(error)[:100]}`", delete_after=10)
        if not isinstance(error, (commands.CommandOnCooldown, commands.MaxConcurrencyReached)):
            print(f"⚠️ Command error: {error}")
            # Don't raise to avoid traceback spam

@bot.event
async def on_app_command_completion(interaction, command):
    """Track command usage"""
    if HAS_DB:
        incr_stat("total_commands")
        add_audit("command", f"/{command.name} used by {interaction.user} in {interaction.guild}", 
                   guild_id=interaction.guild_id, user_id=interaction.user.id)

@bot.event
async def on_guild_join(guild):
    if HAS_DB:
        incr_stat("total_guilds")
        incr_stat("total_users", guild.member_count or 0)
        add_audit("guild_join", f"Joined {guild.name} (ID: {guild.id}) — Now {len(bot.guilds)} servers")
        set_guild_config(guild.id)
    print(f"📥 Joined guild: {guild.name} (ID: {guild.id}) — Now at {len(bot.guilds)} servers")

@bot.event
async def on_guild_remove(guild):
    if HAS_DB:
        incr_stat("total_guilds", -1)
        add_audit("guild_leave", f"Left {guild.name} (ID: {guild.id}) — Now {len(bot.guilds)} servers")
    print(f"📤 Left guild: {guild.name} (ID: {guild.id}) — Now at {len(bot.guilds)} servers")

# ── Graceful shutdown ─────────────────────────────────────────────────
async def shutdown():
    print("\n🛑 Shutting down gracefully...")
    if HAS_DB:
        add_audit("bot_stop", "Bot shutting down")
        db_close()
    await bot.close()

def handle_signal(sig, frame):
    print(f"Received signal {sig}, shutting down...")
    asyncio.create_task(shutdown())

# ── Main ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)
    
    asyncio.run(load_cogs())
    
    token = os.getenv("DISCORD_TOKEN") or CONFIG.get("token")
    if not token:
        print("❌ No token found! Set DISCORD_TOKEN env var")
        sys.exit(1)
    
    try:
        bot.run(
            token,
            reconnect=True,
            log_handler=None,  # Avoid duplicate logs
        )
    except KeyboardInterrupt:
        asyncio.run(shutdown())
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)
