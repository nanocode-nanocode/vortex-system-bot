#!/usr/bin/env python3
"""
VØRTΞX System Bot — Events & Giveaways (DB)
Polls, Giveaways, Reminders, Counting, Suggestions
"""
import discord
from discord.ext import commands
from discord import app_commands
import json, asyncio, random, datetime
from pathlib import Path

BASE = Path(__file__).parent.parent
with open(BASE / "config.json") as f:
    CONFIG = json.load(f)

from db import add_audit, get_guild_config
from i18n import t
from cogs.language import get_guild_lang

class Events(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_giveaways = {}

    async def cog_load(self):
        """Called when the cog is loaded."""
        pass  # Giveaways placeholder — will be implemented when needed

    async def _init_giveaways(self):
        await self.bot.wait_until_ready()
        # Load saved giveaways from DB would go here

    @app_commands.command(name="poll", description="📊 أنشئ استفتاء / Create a poll")
    @app_commands.describe(question="السؤال / Question", option1="خيار 1 / Option 1", option2="خيار 2 / Option 2")
    @app_commands.checks.has_permissions(administrator=True)
    async def poll(self, interaction: discord.Interaction, question: str, option1: str, option2: str):
        await interaction.response.defer()
        embed = discord.Embed(title="📊 " + question, color=CONFIG.get("color", 5793266))
        embed.add_field(name="1️⃣", value=option1, inline=True)
        embed.add_field(name="2️⃣", value=option2, inline=True)
        embed.set_footer(text=f"من {interaction.user.name}")
        msg = await interaction.followup.send(embed=embed)
        await msg.add_reaction("1️⃣")
        await msg.add_reaction("2️⃣")
        add_audit("poll", f"Poll created by {interaction.user}", interaction.guild_id, interaction.user.id)

    @app_commands.command(name="quickpoll", description="📊 استفتاء سريع (نعم/لا) / Quick yes/no poll")
    @app_commands.describe(question="السؤال / Question")
    async def quickpoll(self, interaction: discord.Interaction, question: str):
        await interaction.response.defer()
        embed = discord.Embed(title="📊 " + question, color=CONFIG.get("color", 5793266))
        embed.set_footer(text=f"من {interaction.user.name}")
        msg = await interaction.followup.send(embed=embed)
        for emoji in ["✅", "❌"]:
            await msg.add_reaction(emoji)

    @app_commands.command(name="say", description="💬 يجيب البوت رسالتك / Make the bot say something")
    @app_commands.describe(message="الرسالة / Message", channel="الروم (اختياري) / Channel (optional)")
    @app_commands.checks.has_permissions(administrator=True)
    async def say(self, interaction: discord.Interaction, message: str, channel: discord.TextChannel = None):
        await interaction.response.defer(ephemeral=True)
        ch = channel or interaction.channel
        await ch.send(message)
        await interaction.followup.send(f"✅ تم الإرسال إلى {ch.mention}", ephemeral=True)

    @app_commands.command(name="embed", description="📝 أرسل إمبد / Send an embed message")
    @app_commands.describe(title="العنوان / Title", description="الوصف / Description", color="اللون / Color hex")
    @app_commands.checks.has_permissions(administrator=True)
    async def embed_cmd(self, interaction: discord.Interaction, title: str, description: str, color: str = None):
        await interaction.response.defer(ephemeral=True)
        embed_color = int(color.replace("#", ""), 16) if color else CONFIG.get("color", 5793266)
        embed = discord.Embed(title=title, description=description, color=embed_color)
        await interaction.channel.send(embed=embed)
        await interaction.followup.send("✅ تم!", ephemeral=True)

    @app_commands.command(name="announce", description="📢 إعلان مهم / Important announcement")
    @app_commands.describe(title="العنوان / Title", message="الرسالة / Message", ping="@everyone or @here")
    @app_commands.checks.has_permissions(administrator=True)
    async def announce(self, interaction: discord.Interaction, title: str, message: str, ping: str = ""):
        await interaction.response.defer(ephemeral=True)
        embed = discord.Embed(title=f"📢 {title}", description=message, color=0xED4245)
        embed.set_footer(text=interaction.guild.name, icon_url=interaction.guild.icon.url if interaction.guild.icon else None)
        content = ""
        if ping.lower() in ("@everyone", "everyone"):
            content = "@everyone"
        elif ping.lower() in ("@here", "here"):
            content = "@here"
        await interaction.channel.send(content=content, embed=embed)
        await interaction.followup.send("✅ تم الإعلان!", ephemeral=True)

    @app_commands.command(name="suggest", description="💡 اقتراح / Suggest something")
    @app_commands.describe(suggestion="الاقتراح / Your suggestion")
    async def suggest(self, interaction: discord.Interaction, suggestion: str):
        await interaction.response.defer()
        embed = discord.Embed(title="💡 اقتراح", description=suggestion, color=0xFEE75C)
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        msg = await interaction.followup.send(embed=embed)
        for emoji in ["👍", "👎"]:
            await msg.add_reaction(emoji)

    @app_commands.command(name="timer", description="⏰ مؤقت / Set a timer")
    @app_commands.describe(seconds="الوقت بالثواني / Time in seconds", reminder="تذكير (اختياري) / Reminder (optional)")
    async def timer(self, interaction: discord.Interaction, seconds: int, reminder: str = "⏰ الوقت انتهى!"):
        await interaction.response.defer(ephemeral=True)
        if seconds < 5 or seconds > 86400:
            return await interaction.followup.send("⚠️ الوقت بين 5 ثواني و 24 ساعة", ephemeral=True)
        await interaction.followup.send(f"⏰ تم ضبط مؤقت لمدة {seconds} ثانية!", ephemeral=True)
        await asyncio.sleep(seconds)
        try:
            await interaction.user.send(f"{reminder}\nتم ضبطه منذ {seconds} ثانية")
        except:
            await interaction.channel.send(f"{interaction.user.mention} {reminder}")

    @app_commands.command(name="avatar", description="🖼️ عرض صورة البروفايل / Show profile picture")
    @app_commands.describe(member="العضو / Member (optional)")
    async def avatar_cmd(self, interaction: discord.Interaction, member: discord.Member = None):
        await interaction.response.defer()
        target = member or interaction.user
        embed = discord.Embed(title=f"🖼️ {target.display_name}", color=target.color if target.color.value else CONFIG.get("color", 5793266))
        embed.set_image(url=target.display_avatar.url)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="serveravatar", description="🖼️ صورة السيرفر / Server icon")
    async def server_avatar(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if not interaction.guild.icon:
            return await interaction.followup.send("❌ السيرفر ما عنده صورة!")
        embed = discord.Embed(title=f"🖼️ {interaction.guild.name}", color=CONFIG.get("color", 5793266))
        embed.set_image(url=interaction.guild.icon.url)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="roleinfo", description="🎭 معلومات رول / Role info")
    @app_commands.describe(role="الرول / Role")
    async def role_info(self, interaction: discord.Interaction, role: discord.Role):
        await interaction.response.defer()
        embed = discord.Embed(title=f"🎭 {role.name}", color=role.color if role.color.value else CONFIG.get("color", 5793266))
        embed.add_field(name="🆔", value=role.id, inline=True)
        embed.add_field(name="👥 الأعضاء", value=len(role.members), inline=True)
        embed.add_field(name="🎨 اللون", value=str(role.color), inline=True)
        embed.add_field(name="📅 أنشئ", value=role.created_at.strftime("%Y-%m-%d"), inline=True)
        embed.add_field(name="📍 منشن", value="✅" if role.mentionable else "❌", inline=True)
        embed.add_field(name="👁️ منفصل", value="✅" if role.hoist else "❌", inline=True)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="channelinfo", description="💬 معلومات الروم / Channel info")
    @app_commands.describe(channel="الروم / Channel (optional)")
    async def channel_info(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        await interaction.response.defer()
        ch = channel or interaction.channel
        embed = discord.Embed(title=f"💬 #{ch.name}", color=CONFIG.get("color", 5793266))
        embed.add_field(name="🆔", value=ch.id, inline=True)
        embed.add_field(name="📅 أنشئ", value=ch.created_at.strftime("%Y-%m-%d"), inline=True)
        embed.add_field(name="📌 الموضوع", value=(ch.topic or "—")[:100], inline=False)
        embed.add_field(name="🐌 سرعة بطيئة", value=f"{ch.slowmode_delay}ث" if ch.slowmode_delay else "مفعلة", inline=True)
        if ch.category:
            embed.add_field(name="📂 القسم", value=ch.category.name, inline=True)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="invite", description="🔗 رابط دعوة البوت / Bot invite link")
    async def invite(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        embed = discord.Embed(title="🔗 VØRTΞX Bot", 
            description="[إضافة البوت لسيرفرك](https://discord.com/api/oauth2/authorize?client_id=1527818267455000847&permissions=8&scope=bot%20applications.commands)",
            color=CONFIG.get("color", 5793266))
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="botinfo", description="🤖 معلومات البوت / Bot information")
    async def botinfo_cmd(self, interaction: discord.Interaction):
        await interaction.response.defer()
        embed = discord.Embed(title="🤖 VØRTΞX Bot v4", 
            description="Enterprise Discord Bot — PostgreSQL powered\nالمطور: VØRTΞX HOST",
            color=CONFIG.get("color", 5793266))
        embed.add_field(name="📦 كوجز", value="10", inline=True)
        embed.add_field(name="⌨️ أوامر", value="50+", inline=True)
        embed.add_field(name="🖥️ سيرفرات", value=len(self.bot.guilds), inline=True)
        embed.add_field(name="⚡ بنق", value=f"{round(self.bot.latency * 1000)}ms", inline=True)
        embed.add_field(name="🗣️ لغات", value="🇸🇦 العربية / 🇬🇧 English", inline=True)
        embed.add_field(name="💾 DB", value="PostgreSQL 🐘", inline=True)
        await interaction.followup.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Events(bot))
