import discord
from discord.ext import commands
from discord import app_commands
import json, datetime
from pathlib import Path

BASE = Path(__file__).parent.parent
with open(BASE / "config.json") as f:
    CONFIG = json.load(f)

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    admin_group = app_commands.Group(name="admin", description="⚙️ أوامر إدارية")
    
    @admin_group.command(name="say", description="💬 إرسال رسالة عن طريق البوت")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(message="الرسالة")
    async def say_slash(self, interaction: discord.Interaction, message: str):
        await interaction.response.send_message("✅", ephemeral=True)
        await interaction.channel.send(message)
    
    @admin_group.command(name="embed", description="📦 إرسال امبد")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(title="العنوان", description="الوصف")
    async def embed_slash(self, interaction: discord.Interaction, title: str, description: str):
        embed = discord.Embed(title=title, description=description, color=CONFIG.get("color", 0x5865F2))
        embed.set_footer(text=f"VØRTΞX • {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed)
    
    @admin_group.command(name="dm", description="✉️ إرسال رسالة خاصة لعضو")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(member="العضو", message="الرسالة")
    async def dm_slash(self, interaction: discord.Interaction, member: discord.Member, message: str):
        try:
            embed = discord.Embed(title=f"📬 | رسالة من إدارة {interaction.guild.name}", description=message, color=CONFIG.get("color", 0x5865F2))
            embed.set_footer(text=f"بواسطة {interaction.user}")
            await member.send(embed=embed)
            await interaction.response.send_message(f"✅ | تم إرسال الرسالة لـ {member.mention}")
        except:
            await interaction.response.send_message(f"❌ | ما قدرت أرسل لـ {member.mention}")
    
    @admin_group.command(name="roleall", description="🎖️ إضافة رتبة لكل الأعضاء")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(role="الرتبة")
    async def roleall_slash(self, interaction: discord.Interaction, role: discord.Role):
        await interaction.response.defer()
        count = 0
        for member in interaction.guild.members:
            if role not in member.roles:
                try:
                    await member.add_roles(role)
                    count += 1
                except:
                    pass
        await interaction.followup.send(f"✅ | تم إضافة {role.name} لـ {count} عضو")
    
    @admin_group.command(name="clean", description="🧹 مسح رسائل البوت فقط")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(limit="عدد الرسائل")
    async def clean_slash(self, interaction: discord.Interaction, limit: int = 50):
        await interaction.response.defer()
        def is_bot(msg):
            return msg.author.bot
        deleted = await interaction.channel.purge(limit=limit, check=is_bot)
        await interaction.followup.send(f"🧹 | تم مسح {len(deleted)} رسالة بوت", ephemeral=True)
    
    @admin_group.command(name="slowmode", description="🐌 ضبط الوضع البطيء")
    @app_commands.default_permissions(manage_channels=True)
    @app_commands.describe(seconds="المدة بالثواني (0 للإلغاء)")
    async def slowmode_slash(self, interaction: discord.Interaction, seconds: int = 0):
        if seconds < 0 or seconds > 21600:
            return await interaction.response.send_message("❌ | المدة: 0-21600 ثانية", ephemeral=True)
        await interaction.channel.edit(slowmode_delay=seconds)
        if seconds == 0:
            await interaction.response.send_message("✅ | تم إلغاء الوضع البطيء")
        else:
            await interaction.response.send_message(f"✅ | تم ضبط الوضع البطيء: {seconds} ثانية")
    
    @admin_group.command(name="reload", description="🔄 إعادة تحميل الأنظمة (المالك فقط)")
    @commands.is_owner()
    async def reload_slash(self, interaction: discord.Interaction):
        await interaction.response.defer()
        cogs_dir = BASE / "cogs"
        loaded = 0
        for file in sorted(cogs_dir.glob("*.py")):
            if file.name.startswith("_"):
                continue
            cog_name = f"cogs.{file.stem}"
            try:
                await self.bot.reload_extension(cog_name)
                loaded += 1
            except commands.ExtensionNotLoaded:
                await self.bot.load_extension(cog_name)
                loaded += 1
        await interaction.followup.send(f"✅ | تم تحديث {loaded} نظام")
    
    # ── Prefix fallbacks ──────────────────────────────────────────────
    
    @commands.command(name="say")
    @commands.has_permissions(administrator=True)
    async def say_prefix(self, ctx, *, message):
        await ctx.message.delete()
        await ctx.send(message)
    
    @commands.command(name="embed")
    @commands.has_permissions(administrator=True)
    async def embed_prefix(self, ctx, *, text):
        await ctx.message.delete()
        embed = discord.Embed(description=text, color=CONFIG.get("color", 0x5865F2))
        embed.set_footer(text=f"VØRTΞX • {ctx.author.display_name}")
        await ctx.send(embed=embed)
    
    @commands.command(name="dm")
    @commands.has_permissions(administrator=True)
    async def dm_prefix(self, ctx, member: discord.Member, *, message):
        try:
            embed = discord.Embed(title=f"📬 | رسالة من إدارة {ctx.guild.name}", description=message, color=CONFIG.get("color", 0x5865F2))
            embed.set_footer(text=f"بواسطة {ctx.author}")
            await member.send(embed=embed)
            await ctx.send(f"✅ | تم إرسال الرسالة لـ {member.mention}")
        except:
            await ctx.send(f"❌ | ما قدرت أرسل لـ {member.mention}")
    
    @commands.command(name="roleall")
    @commands.has_permissions(administrator=True)
    async def roleall_prefix(self, ctx, role: discord.Role):
        await ctx.send(f"⏳ | جاري إضافة {role.name} للكل...")
        count = 0
        for member in ctx.guild.members:
            if role not in member.roles:
                try:
                    await member.add_roles(role)
                    count += 1
                except:
                    pass
        await ctx.send(f"✅ | تم إضافة {role.name} لـ {count} عضو")
    
    @commands.command(name="clean")
    @commands.has_permissions(administrator=True)
    async def clean_prefix(self, ctx, limit: int = 50):
        def is_bot(msg):
            return msg.author.bot
        deleted = await ctx.channel.purge(limit=limit, check=is_bot)
        await ctx.send(f"🧹 | تم مسح {len(deleted)} رسالة بوت", delete_after=3)
    
    @commands.command(name="slowmode")
    @commands.has_permissions(manage_channels=True)
    async def slowmode_prefix(self, ctx, seconds: int = 0):
        if seconds < 0 or seconds > 21600:
            return await ctx.send("❌ | المدة: 0-21600 ثانية")
        await ctx.channel.edit(slowmode_delay=seconds)
        if seconds == 0:
            await ctx.send("✅ | تم إلغاء الوضع البطيء")
        else:
            await ctx.send(f"✅ | تم ضبط الوضع البطيء: {seconds} ثانية")
    
    @commands.command(name="reload")
    @commands.is_owner()
    async def reload_prefix(self, ctx):
        await ctx.send("⏳ | جاري تحديث الأنظمة...")
        cogs_dir = BASE / "cogs"
        for file in sorted(cogs_dir.glob("*.py")):
            if file.name.startswith("_"):
                continue
            cog_name = f"cogs.{file.stem}"
            try:
                await self.bot.reload_extension(cog_name)
            except commands.ExtensionNotLoaded:
                await self.bot.load_extension(cog_name)
        await ctx.send("✅ | تم تحديث جميع الأنظمة!")

async def setup(bot):
    await bot.add_cog(Admin(bot))
