#!/usr/bin/env python3
"""
VØRTΞX System Bot — Language Cog (i18n)
/language command with guild-based switching between العربية and English.
"""
import discord
from discord.ext import commands
from discord import app_commands
import json
from pathlib import Path

BASE = Path(__file__).parent.parent
with open(BASE / "config.json") as f:
    CONFIG = json.load(f)

from db import set_guild_config, get_guild_config

class LanguageCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="language", description="🌐 تغيير لغة البوت / Change bot language")
    @app_commands.describe(lang="اختر اللغة / Select language")
    @app_commands.choices(lang=[
        app_commands.Choice(name="🇸🇦 العربية", value="ar"),
        app_commands.Choice(name="🇬🇧 English", value="en"),
    ])
    @app_commands.checks.has_permissions(administrator=True)
    async def language(self, interaction: discord.Interaction, lang: str):
        await interaction.response.defer(ephemeral=True)
        if lang not in ("ar", "en"):
            return await interaction.followup.send("❌ لغة غير مدعومة / Unsupported language!", ephemeral=True)
        
        try:
            set_guild_config(interaction.guild_id, language=lang)
        except:
            # Fallback when DB is down - store in local JSON
            lang_file = BASE / "data" / "guild_lang.json"
            langs = {}
            if lang_file.exists():
                import json
                langs = json.loads(lang_file.read_text())
            langs[str(interaction.guild_id)] = lang
            lang_file.write_text(json.dumps(langs, indent=2))
        
        if lang == "ar":
            await interaction.followup.send("✅ تم ضبط اللغة على **العربية**!", ephemeral=True)
        else:
            await interaction.followup.send("✅ Language set to **English**!", ephemeral=True)

def get_guild_lang(guild_id: int) -> str:
    """Get guild language setting"""
    try:
        cfg = get_guild_config(guild_id)
        if cfg and cfg.get("language"):
            return cfg["language"]
    except:
        pass
    # Fallback to local file
    lang_file = BASE / "data" / "guild_lang.json"
    if lang_file.exists():
        try:
            langs = json.loads(lang_file.read_text())
            return langs.get(str(guild_id), "ar")
        except:
            pass
    return "ar"

async def setup(bot):
    await bot.add_cog(LanguageCog(bot))
