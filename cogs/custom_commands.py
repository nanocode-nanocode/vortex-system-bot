#!/usr/bin/env python3
"""
VØRTΞX System Bot — Custom Commands (DB)
Database-backed custom commands per guild.
"""
import discord
from discord.ext import commands
from discord import app_commands
import json
from pathlib import Path

BASE = Path(__file__).parent.parent
with open(BASE / "config.json") as f:
    CONFIG = json.load(f)

# ── DB ────────────────────────────────────────────────────────────────
from db import set_custom_command, del_custom_command, get_custom_command, list_custom_commands

class CustomCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="addcommand", description="➕ أضف أمر مخصص للسيرفر")
    @app_commands.describe(name="اسم الأمر", response="الرد")
    @app_commands.checks.has_permissions(administrator=True)
    async def add_command(self, interaction: discord.Interaction, name: str, response: str):
        await interaction.response.defer(ephemeral=True)
        set_custom_command(interaction.guild_id, name, response, interaction.user.id)
        await interaction.followup.send(f"✅ تم إضافة الأمر `{name}` بنجاح!", ephemeral=True)

    @app_commands.command(name="delcommand", description="🗑️ احذف أمر مخصص")
    @app_commands.describe(name="اسم الأمر")
    @app_commands.checks.has_permissions(administrator=True)
    async def del_command(self, interaction: discord.Interaction, name: str):
        await interaction.response.defer(ephemeral=True)
        if del_custom_command(interaction.guild_id, name):
            await interaction.followup.send(f"✅ تم حذف الأمر `{name}`!", ephemeral=True)
        else:
            await interaction.followup.send(f"❌ الأمر `{name}` غير موجود!", ephemeral=True)

    @app_commands.command(name="commands", description="📋 قائمة الأوامر المخصصة")
    async def list_commands(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        cmds = list_custom_commands(interaction.guild_id)
        if not cmds:
            await interaction.followup.send("📭 لا توجد أوامر مخصصة!", ephemeral=True)
            return
        embed = discord.Embed(
            title="📋 الأوامر المخصصة",
            description="\n".join(f"`{c['name']}` → {c['response'][:50]}" for c in cmds),
            color=CONFIG.get("color", 5793266)
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return
        prefix = CONFIG.get("prefix", "!")
        if not message.content.startswith(prefix):
            return
        cmd_name = message.content[len(prefix):].split()[0].lower()
        response = get_custom_command(message.guild.id, cmd_name)
        if response:
            await message.channel.send(response)

async def setup(bot):
    await bot.add_cog(CustomCommands(bot))
