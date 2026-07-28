import discord
from discord.ext import commands
from discord import app_commands
import json, datetime
from pathlib import Path
from db import get_warns, add_warn, clear_warns, add_audit

BASE = Path(__file__).parent.parent
with open(BASE / "config.json") as f:
    CONFIG = json.load(f)

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="warn", description="⚠️ تحذير عضو")
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.describe(member="العضو", reason="سبب التحذير")
    async def warn_slash(self, interaction: discord.Interaction, member: discord.Member, reason: str = "لا يوجد سبب"):
        await interaction.response.defer()
        add_warn(interaction.guild_id, member.id, interaction.user.id, reason)
        add_audit("warn", f"{member} ({member.id}): {reason}", interaction.guild_id, interaction.user.id)
        warns = get_warns(interaction.guild_id, member.id)
        warn_count = len(warns)
        embed = discord.Embed(title="⚠️ | تحذير", description=f"**العضو:** {member.mention}\n**عدد التحذيرات:** {warn_count}", color=0xFEE75C)
        embed.add_field(name="السبب", value=reason, inline=False)
        embed.add_field(name="بواسطة", value=interaction.user.mention, inline=False)
        await interaction.followup.send(embed=embed)
        try:
            await member.send(f"⚠️ تم تحذيرك في **{interaction.guild.name}**\nالسبب: {reason}\nعدد التحذيرات: {warn_count}")
        except:
            pass
        if warn_count >= 3:
            await member.ban(reason=f"⚠️ 3 تحذيرات - {reason}")
            await interaction.followup.send(f"🔨 | {member} تم حظره تلقائياً لوصول 3 تحذيرات!")

    @app_commands.command(name="warnings", description="⚠️ عرض تحذيرات عضو")
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.describe(member="العضو")
    async def warnings_slash(self, interaction: discord.Interaction, member: discord.Member):
        await interaction.response.defer()
        warns = get_warns(interaction.guild_id, member.id)
        if not warns:
            return await interaction.followup.send(f"✅ | {member.mention} ما عنده تحذيرات!")
        embed = discord.Embed(title=f"⚠️ تحذيرات {member.display_name}", color=0xFEE75C)
        for i, w in enumerate(warns, 1):
            embed.add_field(name=f"#{i} — {w['time'][:10] if isinstance(w['time'], str) else str(w['time'])[:10]}", 
                           value=f"السبب: {w['reason']}\nبواسطة: <@{w['moderator_id']}>", inline=False)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="clearwarn", description="🧹 مسح تحذيرات عضو")
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.describe(member="العضو")
    async def clearwarn_slash(self, interaction: discord.Interaction, member: discord.Member):
        await interaction.response.defer()
        clear_warns(interaction.guild_id, member.id)
        add_audit("clear_warns", f"{member} ({member.id})", interaction.guild_id, interaction.user.id)
        await interaction.followup.send(f"✅ | تم مسح جميع تحذيرات {member.mention}")

    @app_commands.command(name="timeout", description="🔇 كتم عضو مؤقت")
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.describe(member="العضو", minutes="المدة بالدقائق", reason="السبب")
    async def timeout_slash(self, interaction: discord.Interaction, member: discord.Member, minutes: int = 10, reason: str = "لا يوجد سبب"):
        await interaction.response.defer()
        if member.top_role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
            return await interaction.followup.send("❌ | ما تقدر تكتم عضو صلاحيته أعلى منك!", ephemeral=True)
        duration = datetime.timedelta(minutes=minutes)
        await member.timeout(duration, reason=f"[{interaction.user}] {reason}")
        add_audit("timeout", f"{member} ({member.id}): {minutes}min {reason}", interaction.guild_id, interaction.user.id)
        embed = discord.Embed(title="🔇 | تم الكتم", description=f"**العضو:** {member.mention}\n**المدة:** {minutes} دقيقة\n**السبب:** {reason}", color=CONFIG.get("color", 0x5865F2))
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="untimeout", description="🔊 إلغاء كتم عضو")
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.describe(member="العضو")
    async def untimeout_slash(self, interaction: discord.Interaction, member: discord.Member):
        await interaction.response.defer()
        await member.timeout(None)
        add_audit("untimeout", f"{member} ({member.id})", interaction.guild_id, interaction.user.id)
        await interaction.followup.send(f"🔊 | تم إلغاء الكتم عن {member.mention}")

async def setup(bot):
    await bot.add_cog(Moderation(bot))
