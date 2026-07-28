import discord
from discord.ext import commands
from discord import app_commands
import json, datetime, asyncio
from pathlib import Path

BASE = Path(__file__).parent.parent
with open(BASE / "config.json") as f:
    CONFIG = json.load(f)

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.warns_file = BASE / "data" / "warns.json"
        self.warns_file.parent.mkdir(exist_ok=True)
        if not self.warns_file.exists():
            self.warns_file.write_text("{}")
    
    def load_warns(self):
        return json.loads(self.warns_file.read_text())
    
    def save_warns(self, data):
        self.warns_file.write_text(json.dumps(data, indent=2))
    
    # ── Slash Commands ────────────────────────────────────────────────
    
    @app_commands.command(name="ban", description="🔨 حظر عضو من السيرفر")
    @app_commands.default_permissions(ban_members=True)
    @app_commands.describe(member="العضو المراد حظره", reason="السبب")
    async def ban_slash(self, interaction: discord.Interaction, member: discord.Member, reason: str = "لا يوجد سبب"):
        if member.top_role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
            return await interaction.response.send_message("❌ | ما تقدر تحظر عضو صلاحيته أعلى منك!", ephemeral=True)
        await member.ban(reason=f"[{interaction.user}] {reason}")
        embed = discord.Embed(title="🔨 | تم الحظر", description=f"**العضو:** {member} ({member.id})", color=CONFIG.get("color", 0x5865F2))
        embed.add_field(name="السبب", value=reason, inline=False)
        embed.add_field(name="بواسطة", value=interaction.user.mention, inline=False)
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="kick", description="👢 طرد عضو من السيرفر")
    @app_commands.default_permissions(kick_members=True)
    @app_commands.describe(member="العضو المراد طرده", reason="السبب")
    async def kick_slash(self, interaction: discord.Interaction, member: discord.Member, reason: str = "لا يوجد سبب"):
        if member.top_role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
            return await interaction.response.send_message("❌ | ما تقدر تطرد عضو صلاحيته أعلى منك!", ephemeral=True)
        await member.kick(reason=f"[{interaction.user}] {reason}")
        embed = discord.Embed(title="👢 | تم الطرد", description=f"**العضو:** {member} ({member.id})", color=CONFIG.get("color", 0x5865F2))
        embed.add_field(name="السبب", value=reason, inline=False)
        embed.add_field(name="بواسطة", value=interaction.user.mention, inline=False)
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="warn", description="⚠️ تحذير عضو")
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.describe(member="العضو", reason="سبب التحذير")
    async def warn_slash(self, interaction: discord.Interaction, member: discord.Member, reason: str = "لا يوجد سبب"):
        warns = self.load_warns()
        mid = str(member.id)
        if mid not in warns:
            warns[mid] = []
        warns[mid].append({"reason": reason, "by": str(interaction.user), "time": datetime.datetime.now().isoformat()})
        self.save_warns(warns)
        embed = discord.Embed(title="⚠️ | تحذير", description=f"**العضو:** {member.mention}\n**عدد التحذيرات:** {len(warns[mid])}", color=0xFEE75C)
        embed.add_field(name="السبب", value=reason, inline=False)
        embed.add_field(name="بواسطة", value=interaction.user.mention, inline=False)
        await interaction.response.send_message(embed=embed)
        try:
            await member.send(f"⚠️ تم تحذيرك في **{interaction.guild.name}**\nالسبب: {reason}\nعدد التحذيرات: {len(warns[mid])}")
        except:
            pass
        if len(warns[mid]) >= 3:
            await member.ban(reason=f"⚠️ 3 تحذيرات - {reason}")
            await interaction.followup.send(f"🔨 | {member} تم حظره تلقائياً لوصول 3 تحذيرات!")
    
    @app_commands.command(name="warnings", description="⚠️ عرض تحذيرات عضو")
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.describe(member="العضو")
    async def warnings_slash(self, interaction: discord.Interaction, member: discord.Member):
        warns = self.load_warns()
        mid = str(member.id)
        if mid not in warns or not warns[mid]:
            return await interaction.response.send_message(f"✅ | {member.mention} ما عنده تحذيرات!")
        embed = discord.Embed(title=f"⚠️ تحذيرات {member.display_name}", color=0xFEE75C)
        for i, w in enumerate(warns[mid], 1):
            embed.add_field(name=f"#{i} — {w['time'][:10]}", value=f"السبب: {w['reason']}\nبواسطة: {w['by']}", inline=False)
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="clearwarn", description="🧹 مسح تحذيرات عضو")
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.describe(member="العضو")
    async def clearwarn_slash(self, interaction: discord.Interaction, member: discord.Member):
        warns = self.load_warns()
        mid = str(member.id)
        if mid in warns:
            warns[mid] = []
            self.save_warns(warns)
        await interaction.response.send_message(f"✅ | تم مسح جميع تحذيرات {member.mention}")
    
    @app_commands.command(name="purge", description="🧹 مسح رسائل من القناة")
    @app_commands.default_permissions(manage_messages=True)
    @app_commands.describe(amount="عدد الرسائل (1-100)")
    async def purge_slash(self, interaction: discord.Interaction, amount: int):
        if amount < 1 or amount > 100:
            return await interaction.response.send_message("❌ | حد مسح الرسائل: 1-100", ephemeral=True)
        await interaction.response.defer()
        deleted = await interaction.channel.purge(limit=amount)
        await interaction.followup.send(f"🧹 | تم مسح {len(deleted)} رسالة", ephemeral=True)
    
    @app_commands.command(name="timeout", description="🔇 كتم عضو مؤقت")
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.describe(member="العضو", minutes="المدة بالدقائق", reason="السبب")
    async def timeout_slash(self, interaction: discord.Interaction, member: discord.Member, minutes: int = 10, reason: str = "لا يوجد سبب"):
        if member.top_role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
            return await interaction.response.send_message("❌ | ما تقدر تكتم عضو صلاحيته أعلى منك!", ephemeral=True)
        duration = datetime.timedelta(minutes=minutes)
        await member.timeout(duration, reason=f"[{interaction.user}] {reason}")
        embed = discord.Embed(title="🔇 | تم الكتم", description=f"**العضو:** {member.mention}\n**المدة:** {minutes} دقيقة\n**السبب:** {reason}", color=CONFIG.get("color", 0x5865F2))
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="untimeout", description="🔊 إلغاء كتم عضو")
    @app_commands.default_permissions(moderate_members=True)
    @app_commands.describe(member="العضو")
    async def untimeout_slash(self, interaction: discord.Interaction, member: discord.Member):
        await member.timeout(None)
        await interaction.response.send_message(f"🔊 | تم إلغاء الكتم عن {member.mention}")
    
    @app_commands.command(name="lock", description="🔒 قفل القناة")
    @app_commands.default_permissions(manage_channels=True)
    @app_commands.describe(channel="القناة (اختياري)")
    async def lock_slash(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        channel = channel or interaction.channel
        await channel.set_permissions(interaction.guild.default_role, send_messages=False)
        await interaction.response.send_message(f"🔒 | تم قفل {channel.mention}")
    
    @app_commands.command(name="unlock", description="🔓 فتح القناة")
    @app_commands.default_permissions(manage_channels=True)
    @app_commands.describe(channel="القناة (اختياري)")
    async def unlock_slash(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        channel = channel or interaction.channel
        await channel.set_permissions(interaction.guild.default_role, send_messages=True)
        await interaction.response.send_message(f"🔓 | تم فتح {channel.mention}")

async def setup(bot):
    await bot.add_cog(Moderation(bot))
