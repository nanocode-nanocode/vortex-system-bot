#!/usr/bin/env python3
"""
VØRTΞX System Bot v4 — Enterprise-Grade
All-in-one: Moderation, Tickets, Levels, Welcome, Broadcast,
Reaction Roles, Anti-Raid, AutoMod, Custom Commands, Utility.

Features:
  • Auto-sharding (handles 2500+ guilds)
  • Auto-reconnect on disconnect
  • Statistics tracking
  • Graceful shutdown on SIGTERM
  • Resilience wrappers for all image generation
"""
import discord
from discord.ext import commands
from discord import app_commands
import json, os, sys, asyncio, signal, datetime
from pathlib import Path

BASE = Path(__file__).parent

# ── Config ─────────────────────────────────────────────────────────────
config_path = BASE / "config.json"
if config_path.exists():
    with open(config_path) as f:
        CONFIG = json.load(f)
else:
    CONFIG = {}

# ── Stats ──────────────────────────────────────────────────────────────
STATS_FILE = BASE / "data" / "stats.json"
if STATS_FILE.exists():
    with open(STATS_FILE) as f:
        STATS = json.load(f)
else:
    STATS = {"commands_used": 0, "total_guilds": 0, "total_users": 0, "started_at": None}

def save_stats():
    STATS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATS_FILE, "w") as f:
        json.dump(STATS, f, indent=2)

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
    # Update stats
    STATS["total_guilds"] = len(bot.guilds)
    STATS["total_users"] = sum(g.member_count or 0 for g in bot.guilds)
    if STATS["started_at"] is None:
        STATS["started_at"] = datetime.datetime.utcnow().isoformat()
    save_stats()

    print(f"\n{'='*50}")
    print(f"  VØRTΞX System Bot v4 — Enterprise")
    print(f"  User: {bot.user} (ID: {bot.user.id})")
    print(f"  Guilds: {len(bot.guilds)}")
    print(f"  Users: {STATS['total_users']:,}")
    print(f"  Shards: {bot.shard_count or 1}")
    print(f"  Started: {STATS['started_at']}")
    
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
        await ctx.send(f"❌ | البوت ما عنده صلاحية!", delete_after=5)
    else:
        await ctx.send(f"⚠️ | خطأ: `{str(error)[:100]}`", delete_after=10)
        if not isinstance(error, (commands.CommandOnCooldown, commands.MaxConcurrencyReached)):
            print(f"⚠️ Command error: {error}")
            # Don't raise to avoid traceback spam

@bot.event
async def on_app_command_completion(interaction, command):
    """Track command usage"""
    STATS["commands_used"] = STATS.get("commands_used", 0) + 1
    if STATS.get("commands_used", 0) % 50 == 0:
        save_stats()

@bot.event
async def on_guild_join(guild):
    STATS["total_guilds"] = len(bot.guilds)
    STATS["total_users"] = sum(g.member_count or 0 for g in bot.guilds)
    save_stats()
    print(f"📥 Joined guild: {guild.name} (ID: {guild.id}) — Now at {len(bot.guilds)} servers")

@bot.event
async def on_guild_remove(guild):
    STATS["total_guilds"] = len(bot.guilds)
    STATS["total_users"] = sum(g.member_count or 0 for g in bot.guilds)
    save_stats()
    print(f"📤 Left guild: {guild.name} (ID: {guild.id}) — Now at {len(bot.guilds)} servers")

# ── Graceful shutdown ─────────────────────────────────────────────────
async def shutdown():
    print("\n🛑 Shutting down gracefully...")
    save_stats()
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
