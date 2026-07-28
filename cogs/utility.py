#!/usr/bin/env python3
"""
VØRTΞX System Bot — Utility (DB)
Server info, bot stats, user info — all DB-backed with defer.
"""
import discord
from discord.ext import commands
from discord import app_commands
import json, time
from pathlib import Path

BASE = Path(__file__).parent.parent
with open(BASE / "config.json") as f:
    CONFIG = json.load(f)

from db import get_all_stats, get_stat, get_guild_config

class Utility(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="serverinfo", description="ℹ️ معلومات السيرفر")
    async def serverinfo(self, interaction: discord.Interaction):
        await interaction.response.defer()
        g = interaction.guild
        embed = discord.Embed(title=f"ℹ️ {g.name}", color=CONFIG.get("color", 5793266))
        embed.set_thumbnail(url=g.icon.url if g.icon else None)
        embed.add_field(name="🆔", value=g.id, inline=True)
        embed.add_field(name="👑 Owner", value=g.owner.mention if g.owner else "—", inline=True)
        embed.add_field(name="👥 الأعضاء", value=g.member_count, inline=True)
        embed.add_field(name="💬 القنوات", value=len(g.channels), inline=True)
        embed.add_field(name="🎭 الرولات", value=len(g.roles), inline=True)
        embed.add_field(name="📅 أنشئ", value=g.created_at.strftime("%Y-%m-%d"), inline=True)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="botstats", description="📊 إحصائيات البوت")
    async def botstats(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            stats = get_all_stats()
        except:
            stats = {}
        embed = discord.Embed(title="📊 VØRTΞX Bot Stats", color=CONFIG.get("color", 5793266))
        embed.add_field(name="🖥️ السيرفرات", value=stats.get("total_guilds", "—"), inline=True)
        embed.add_field(name="👥 المستخدمين", value=stats.get("total_users", "—"), inline=True)
        embed.add_field(name="⌨️ الأوامر", value=stats.get("total_commands", "—"), inline=True)
        embed.add_field(name="📦 شاردات", value=self.bot.shard_count or 1, inline=True)
        embed.add_field(name="⚡ بنق", value=f"{round(self.bot.latency * 1000)}ms", inline=True)
        start = stats.get("bot_started", 0)
        if start:
            uptime = time.time() - int(start)
            h, r = divmod(int(uptime), 3600)
            m, s = divmod(r, 60)
            embed.add_field(name="⏱️ أوبتايم", value=f"{h}h {m}m {s}s", inline=True)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="userinfo", description="👤 معلومات عضو")
    @app_commands.describe(member="العضو (اختياري)")
    async def userinfo(self, interaction: discord.Interaction, member: discord.Member = None):
        await interaction.response.defer()
        target = member or interaction.user
        embed = discord.Embed(title=f"👤 {target}", color=target.color if target.color.value else CONFIG.get("color", 5793266))
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="🆔", value=target.id, inline=True)
        embed.add_field(name="📛 العرض", value=target.display_name, inline=True)
        embed.add_field(name="📅 انضم", value=target.joined_at.strftime("%Y-%m-%d") if target.joined_at else "—", inline=True)
        embed.add_field(name="📅 سجل", value=target.created_at.strftime("%Y-%m-%d"), inline=True)
        embed.add_field(name="🎭 الرولات", value=len(target.roles) - 1, inline=True)
        embed.add_field(name="🤖 بوت", value="نعم" if target.bot else "لا", inline=True)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="ping", description="🏓 اختبار سرعة البوت")
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await interaction.followup.send(f"🏓 **Pong!** `{round(self.bot.latency * 1000)}ms`")

    @app_commands.command(name="help", description="📖 قائمة الأوامر")
    async def help_cmd(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        embed = discord.Embed(
            title="📖 VØRTΞX Bot v4",
            description="**24 أمر سلاش** — كلها متزامنة",
            color=CONFIG.get("color", 5793266)
        )
        embed.add_field(name="🛡️ حماية", value="`/antiraid` `/lock` `/unlock`", inline=True)
        embed.add_field(name="⚙️ إعدادات", value="`/setup` `/config`", inline=True)
        embed.add_field(name="🎮 تسلية", value="`/rank` `/levelup` `/leaderboard` `/avatar`", inline=True)
        embed.add_field(name="📢 إعلانات", value="`/broadcast`", inline=True)
        embed.add_field(name="🎫 تذاكر", value="`/ticket` `/close`", inline=True)
        embed.add_field(name="📋 أوامر", value="`/commands` `/addcommand` `/delcommand`", inline=True)
        embed.add_field(name="🎭 رولات", value="`/reactionrole`", inline=True)
        embed.add_field(name="👋 ترحيب", value="`/welcome`", inline=True)
        embed.add_field(name="ℹ️ أخرى", value="`/ping` `/serverinfo` `/userinfo` `/botstats`", inline=True)
        embed.set_footer(text="⚡ VØRTΞX HOST")
        await interaction.followup.send(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Utility(bot))
