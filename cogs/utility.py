import discord
from discord.ext import commands
from discord import app_commands
import datetime
from pathlib import Path

BASE = Path(__file__).parent.parent
import json
with open(BASE / "config.json") as f:
    CONFIG = json.load(f)

class Utility(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.start_time = datetime.datetime.now()
    
    util_group = app_commands.Group(name="util", description="ℹ️ أوامر خدماتية")
    
    @util_group.command(name="ping", description="🏓 قياس سرعة البوت")
    async def ping_slash(self, interaction: discord.Interaction):
        latency = round(self.bot.latency * 1000)
        embed = discord.Embed(title="🏓 | Pong!", description=f"📶 **{latency}ms**", color=CONFIG.get("color", 0x5865F2))
        await interaction.response.send_message(embed=embed)
    
    @util_group.command(name="uptime", description="⏱ مدة تشغيل البوت")
    async def uptime_slash(self, interaction: discord.Interaction):
        delta = datetime.datetime.now() - self.start_time
        days, rem = divmod(delta.days * 86400 + delta.seconds, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, seconds = divmod(rem, 60)
        embed = discord.Embed(title="⏱ | وقت التشغيل", description=f"**{days}** يوم **{hours}** ساعة **{minutes}** دقيقة **{seconds}** ثانية", color=CONFIG.get("color", 0x5865F2))
        await interaction.response.send_message(embed=embed)
    
    @util_group.command(name="userinfo", description="👤 معلومات عن عضو")
    @app_commands.describe(member="العضو (اختياري)")
    async def userinfo_slash(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        roles = [r.mention for r in member.roles if r != interaction.guild.default_role]
        embed = discord.Embed(title=f"👤 | معلومات {member.display_name}", color=member.color if member.color != discord.Color.default() else CONFIG.get("color", 0x5865F2))
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="👤 | الاسم", value=member.name, inline=True)
        embed.add_field(name="🆔 | ID", value=member.id, inline=True)
        embed.add_field(name="🤖 | بوت", value="✅" if member.bot else "❌", inline=True)
        embed.add_field(name="📅 | الانضمام", value=member.joined_at.strftime("%Y-%m-%d") if member.joined_at else "غير معروف", inline=True)
        embed.add_field(name="📅 | الحساب", value=member.created_at.strftime("%Y-%m-%d"), inline=True)
        embed.add_field(name="🏆 | الرتب", value=", ".join(roles[:5]) if roles else "لا يوجد", inline=False)
        embed.set_footer(text=f"طلب: {interaction.user}")
        await interaction.response.send_message(embed=embed)
    
    @util_group.command(name="serverinfo", description="📊 معلومات السيرفر")
    async def serverinfo_slash(self, interaction: discord.Interaction):
        g = interaction.guild
        embed = discord.Embed(title=f"📊 | معلومات {g.name}", color=CONFIG.get("color", 0x5865F2))
        if g.icon:
            embed.set_thumbnail(url=g.icon.url)
        embed.add_field(name="👑 | المالك", value=g.owner.mention, inline=True)
        embed.add_field(name="🆔 | ID", value=g.id, inline=True)
        embed.add_field(name="👥 | الأعضاء", value=g.member_count, inline=True)
        embed.add_field(name="💬 | الشنلز", value=f"{len(g.text_channels)} Text / {len(g.voice_channels)} Voice", inline=True)
        embed.add_field(name="🏆 | الرتب", value=len(g.roles), inline=True)
        embed.add_field(name="📅 | الإنشاء", value=g.created_at.strftime("%Y-%m-%d"), inline=True)
        embed.add_field(name="🚀 | البوستات", value=g.premium_subscription_count or 0, inline=True)
        embed.add_field(name="✅ | البوتات", value=sum(1 for m in g.members if m.bot), inline=True)
        embed.add_field(name="👤 | الأعضاء الحقيقيين", value=sum(1 for m in g.members if not m.bot), inline=True)
        await interaction.response.send_message(embed=embed)

    @util_group.command(name="stats", description="📈 إحصائيات البوت")
    async def stats_slash(self, interaction: discord.Interaction):
        """📈 Bot statistics — guilds, users, commands used"""
        STATS_FILE = BASE / "data" / "stats.json"
        if STATS_FILE.exists():
            try:
                with open(STATS_FILE) as f:
                    s = json.load(f)
            except:
                s = {}
        else:
            s = {}
        
        embed = discord.Embed(
            title="📈 | إحصائيات VØRTΞX Bot",
            color=CONFIG.get("color", 0x5865F2)
        )
        embed.add_field(name="🖥️ | السيرفرات", value=f"**{s.get('total_guilds', len(self.bot.guilds))}**", inline=True)
        embed.add_field(name="👥 | المستخدمين", value=f"**{s.get('total_users', 0):,}**", inline=True)
        embed.add_field(name="⚡ | الأوامر المنفذة", value=f"**{s.get('commands_used', 0):,}**", inline=True)
        embed.add_field(name="📦 | الكوجز", value=f"**{len(self.bot.cogs)}**", inline=True)
        embed.add_field(name="⏱ | سرعة الاتصال", value=f"**{round(self.bot.latency * 1000)}ms**", inline=True)
        embed.add_field(name="🆔 | الشارد", value=f"**{getattr(self.bot, 'shard_count', 1) or 1}**", inline=True)
        
        started = s.get("started_at")
        if started:
            try:
                from datetime import datetime
                st = datetime.fromisoformat(started)
                delta = datetime.utcnow() - st
                days = delta.days
                hours = delta.seconds // 3600
                embed.set_footer(text=f"🟢 شغال منذ {days} يوم {hours} ساعة")
            except:
                pass
        
        await interaction.response.send_message(embed=embed)

    @util_group.command(name="avatar", description="🖼 صورة العضو")
    @app_commands.describe(member="العضو (اختياري)")
    async def avatar_slash(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        embed = discord.Embed(title=f"🖼 | صورة {member.display_name}", color=CONFIG.get("color", 0x5865F2), url=member.display_avatar.url)
        embed.set_image(url=member.display_avatar.url)
        await interaction.response.send_message(embed=embed)
    
    @util_group.command(name="banner", description="🖼 بانر العضو")
    @app_commands.describe(member="العضو (اختياري)")
    async def banner_slash(self, interaction: discord.Interaction, member: discord.Member = None):
        member = member or interaction.user
        user = await self.bot.fetch_user(member.id)
        if user.banner:
            embed = discord.Embed(title=f"🖼 | بانر {member.display_name}", color=CONFIG.get("color", 0x5865F2))
            embed.set_image(url=user.banner.url)
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message(f"❌ | {member.mention} ما عنده بانر!")
    
    @util_group.command(name="roleinfo", description="🏆 معلومات عن رتبة")
    @app_commands.describe(role="الرتبة")
    async def roleinfo_slash(self, interaction: discord.Interaction, role: discord.Role):
        embed = discord.Embed(title=f"🏆 | رتبة: {role.name}", color=role.color if role.color != discord.Color.default() else CONFIG.get("color", 0x5865F2))
        embed.add_field(name="🆔 | ID", value=role.id, inline=True)
        embed.add_field(name="🎨 | لون", value=str(role.color), inline=True)
        embed.add_field(name="👥 | الأعضاء", value=len(role.members), inline=True)
        embed.add_field(name="📅 | الإنشاء", value=role.created_at.strftime("%Y-%m-%d"), inline=True)
        embed.add_field(name="📌 | منشور", value="✅" if role.mentionable else "❌", inline=True)
        embed.add_field(name="🛡️ | الترتيب", value=role.position, inline=True)
        await interaction.response.send_message(embed=embed)
    
    @util_group.command(name="poll", description="📊 إنشاء تصويت")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(question="السؤال")
    async def poll_slash(self, interaction: discord.Interaction, question: str):
        embed = discord.Embed(title="📊 | تصويت", description=question, color=CONFIG.get("color", 0x5865F2))
        embed.set_footer(text=f"بواسطة {interaction.user}")
        await interaction.response.send_message(embed=embed)
        msg = await interaction.original_response()
        await msg.add_reaction("✅")
        await msg.add_reaction("❌")
    
    # ── Prefix fallbacks ──────────────────────────────────────────────
    
    @commands.command(name="ping")
    async def ping_prefix(self, ctx):
        latency = round(self.bot.latency * 1000)
        embed = discord.Embed(title="🏓 | Pong!", description=f"📶 **{latency}ms**", color=CONFIG.get("color", 0x5865F2))
        await ctx.send(embed=embed)
    
    @commands.command(name="uptime")
    async def uptime_prefix(self, ctx):
        delta = datetime.datetime.now() - self.start_time
        days, rem = divmod(delta.days * 86400 + delta.seconds, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, seconds = divmod(rem, 60)
        embed = discord.Embed(title="⏱ | وقت التشغيل", description=f"{days} يوم, {hours} ساعة, {minutes} دقيقة, {seconds} ثانية", color=CONFIG.get("color", 0x5865F2))
        await ctx.send(embed=embed)
    
    @commands.command(name="userinfo")
    async def userinfo_prefix(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        roles = [r.mention for r in member.roles if r != ctx.guild.default_role]
        embed = discord.Embed(title=f"👤 | معلومات {member.display_name}", color=member.color if member.color != discord.Color.default() else CONFIG.get("color", 0x5865F2))
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="👤 | اسم", value=member.name, inline=True)
        embed.add_field(name="🆔 | ID", value=member.id, inline=True)
        embed.add_field(name="🤖 | بوت", value="✅" if member.bot else "❌", inline=True)
        embed.add_field(name="📅 | انضم للسيرفر", value=member.joined_at.strftime("%Y-%m-%d") if member.joined_at else "غير معروف", inline=True)
        embed.add_field(name="📅 | أنشأ الحساب", value=member.created_at.strftime("%Y-%m-%d"), inline=True)
        embed.add_field(name="🏆 | الرتب", value=", ".join(roles[:5]) if roles else "لا يوجد", inline=False)
        embed.set_footer(text=f"طلب: {ctx.author}")
        await ctx.send(embed=embed)
    
    @commands.command(name="serverinfo")
    async def serverinfo_prefix(self, ctx):
        g = ctx.guild
        embed = discord.Embed(title=f"📊 | معلومات {g.name}", color=CONFIG.get("color", 0x5865F2))
        if g.icon:
            embed.set_thumbnail(url=g.icon.url)
        embed.add_field(name="👑 | المالك", value=g.owner.mention, inline=True)
        embed.add_field(name="🆔 | ID", value=g.id, inline=True)
        embed.add_field(name="👥 | الأعضاء", value=g.member_count, inline=True)
        embed.add_field(name="💬 | الشنلز", value=f"{len(g.text_channels)} Text / {len(g.voice_channels)} Voice", inline=True)
        embed.add_field(name="🏆 | الرتب", value=len(g.roles), inline=True)
        embed.add_field(name="📅 | أنشئ", value=g.created_at.strftime("%Y-%m-%d"), inline=True)
        embed.add_field(name="🚀 | البوستات", value=g.premium_subscription_count or 0, inline=True)
        embed.add_field(name="✅ | البوتات", value=sum(1 for m in g.members if m.bot), inline=True)
        await ctx.send(embed=embed)
    
    @commands.command(name="avatar")
    async def avatar_prefix(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        embed = discord.Embed(title=f"🖼 | صورة {member.display_name}", color=CONFIG.get("color", 0x5865F2), url=member.display_avatar.url)
        embed.set_image(url=member.display_avatar.url)
        await ctx.send(embed=embed)
    
    @commands.command(name="banner")
    async def banner_prefix(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        user = await self.bot.fetch_user(member.id)
        if user.banner:
            embed = discord.Embed(title=f"🖼 | بانر {member.display_name}", color=CONFIG.get("color", 0x5865F2))
            embed.set_image(url=user.banner.url)
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"❌ | {member.mention} ما عنده بانر!")
    
    @commands.command(name="roleinfo")
    async def roleinfo_prefix(self, ctx, role: discord.Role):
        embed = discord.Embed(title=f"🏆 | رتبة: {role.name}", color=role.color if role.color != discord.Color.default() else CONFIG.get("color", 0x5865F2))
        embed.add_field(name="🆔 | ID", value=role.id, inline=True)
        embed.add_field(name="🎨 | لون", value=str(role.color), inline=True)
        embed.add_field(name="👥 | الأعضاء", value=len(role.members), inline=True)
        embed.add_field(name="📅 | أنشئت", value=role.created_at.strftime("%Y-%m-%d"), inline=True)
        embed.add_field(name="📌 | ذكر منفصل", value="✅" if role.mentionable else "❌", inline=True)
        embed.add_field(name="🛡️ | الترتيب", value=role.position, inline=True)
        await ctx.send(embed=embed)
    
    @commands.command(name="poll")
    @commands.has_permissions(administrator=True)
    async def poll_prefix(self, ctx, *, question):
        embed = discord.Embed(title="📊 | تصويت", description=question, color=CONFIG.get("color", 0x5865F2))
        embed.set_footer(text=f"بواسطة {ctx.author}")
        msg = await ctx.send(embed=embed)
        await msg.add_reaction("✅")
        await msg.add_reaction("❌")
        await ctx.message.delete()
    
    # ── Help ──────────────────────────────────────────────────────────
    
    @app_commands.command(name="help", description="📖 عرض كل أوامر البوت")
    async def help_slash(self, interaction: discord.Interaction):
        embed = discord.Embed(title="📖 | أوامر VØRTΞX System Bot v2", description="**Slash Commands /** متوفرة", color=CONFIG.get("color", 0x5865F2))
        
        embed.add_field(name="🛡️ | الإشراف `/ban /kick /warn /warnings /clearwarn /timeout /untimeout /purge /lock /unlock`", value="أوامر الإشراف", inline=False)
        embed.add_field(name="🎫 | التذاكر `/ticket setup /ticket config /ticket add /ticket remove /ticket close`", value="نظام التذاكر", inline=False)
        embed.add_field(name="🎉 | الترحيب `/welcome status /welcome channel /welcome message /welcome toggle /welcome dm-toggle /welcome autorole`", value="نظام الترحيب", inline=False)
        embed.add_field(name="⚙️ | الإدارة `/admin say /admin embed /admin dm /admin roleall /admin clean /admin slowmode /admin reload`", value="أوامر إدارية", inline=False)
        embed.add_field(name="ℹ️ | الخدمات `/util ping /util uptime /util userinfo /util serverinfo /util avatar /util banner /util roleinfo /util poll`", value="أوامر خدماتية", inline=False)
        embed.add_field(name="🏆 | المستويات `/rank /leaderboard /level`", value="نظام الليفل", inline=False)
        
        embed.set_footer(text="VØRTΞX System Bot v2 • كامل شامل")
        await interaction.response.send_message(embed=embed)
    
    # Prefix help fallback
    @commands.command(name="help")
    async def help_prefix(self, ctx):
        embed = discord.Embed(title="📖 | أوامر VØRTΞX System Bot v2", color=CONFIG.get("color", 0x5865F2))
        embed.add_field(name="🛡️ | الإشراف", value="`ban` `kick` `warn` `warnings` `purge` `timeout` `untimeout` `lock` `unlock`", inline=False)
        embed.add_field(name="🎫 | التذاكر", value="`ticket-setup` `adduser` `removeuser`", inline=False)
        embed.add_field(name="🎉 | الترحيب", value="`welcome`", inline=False)
        embed.add_field(name="⚙️ | الإدارة", value="`say` `embed` `dm` `roleall` `clean` `slowmode` `reload` `poll`", inline=False)
        embed.add_field(name="ℹ️ | الخدمات", value="`ping` `uptime` `userinfo` `serverinfo` `avatar` `banner` `roleinfo`", inline=False)
        embed.add_field(name="🏆 | المستويات", value="`rank` `leaderboard` `level`", inline=False)
        embed.set_footer(text="VØRTΞX System Bot v2 • استخدم /help لرؤية الأوامر الجديدة")
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Utility(bot))
