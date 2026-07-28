import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button, Select
import json, datetime, asyncio
from pathlib import Path

BASE = Path(__file__).parent.parent
with open(BASE / "config.json") as f:
    CONFIG = json.load(f)

TICKET_CONFIG_FILE = BASE / "data" / "ticket_config.json"

def load_ticket_config():
    if TICKET_CONFIG_FILE.exists():
        return json.loads(TICKET_CONFIG_FILE.read_text())
    return {}

def save_ticket_config(data):
    TICKET_CONFIG_FILE.parent.mkdir(exist_ok=True)
    TICKET_CONFIG_FILE.write_text(json.dumps(data, indent=2))

class TicketView(View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=None)
        self.guild_id = guild_id
    
    @discord.ui.button(label="🎫 | فتح تذكرة", style=discord.ButtonStyle.primary, custom_id="ticket_open")
    async def create_ticket(self, interaction: discord.Interaction, button: Button):
        if interaction.guild_id != self.guild_id:
            return
        guild = interaction.guild
        config = load_ticket_config()
        gcfg = config.get(str(guild.id), {})
        
        ticket_name = f"ticket-{interaction.user.name.lower().replace(' ', '-')}"
        existing = discord.utils.get(guild.text_channels, name=ticket_name)
        if existing:
            return await interaction.response.send_message(f"❌ | عندك تذكرة مفتوحة: {existing.mention}", ephemeral=True)
        
        category_name = gcfg.get("category", " 🎫 Tickets")
        category = discord.utils.get(guild.categories, name=category_name)
        if not category:
            category = await guild.create_category(category_name)
        
        support_roles = []
        for rn in gcfg.get("support_roles", CONFIG.get("mod_roles", ["Mod", "Admin"])):
            role = discord.utils.get(guild.roles, name=rn)
            if role:
                support_roles.append(role)
        
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True),
        }
        for role in support_roles:
            overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        
        channel = await guild.create_text_channel(
            name=ticket_name,
            category=category,
            overwrites=overwrites,
            topic=f"Ticket for {interaction.user} (ID: {interaction.user.id})"
        )
        
        embed = discord.Embed(
            title="🎫 | تذكرتك",
            description=f"مرحباً {interaction.user.mention}!\nالرجاء شرح مشكلتك بالتفصيل.\n\nفريق الدعم سيصل قريباً.",
            color=CONFIG.get("color", 0x5865F2)
        )
        embed.add_field(name="📌 | نصائح", value="• اشرح المشكلة بالتفصيل\n• أرفق صور إذا لزم الأمر\n• كن محترماً", inline=False)
        embed.set_footer(text="VØRTΞX System • Support Team")
        
        close_view = TicketCloseView()
        await channel.send(embed=embed, view=close_view)
        await channel.send(f"{interaction.user.mention} {' '.join(r.mention for r in support_roles)}", delete_after=1)
        
        # Log
        log_channel_id = gcfg.get("log_channel")
        if log_channel_id:
            log_ch = guild.get_channel(log_channel_id)
            if log_ch:
                await log_ch.send(f"🎫 | تذكرة جديدة: {channel.mention}\n👤 | {interaction.user}")
        
        await interaction.response.send_message(f"✅ | تم فتح تذكرتك: {channel.mention}", ephemeral=True)

class TicketCloseView(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="🔒 | إغلاق", style=discord.ButtonStyle.danger, custom_id="ticket_close")
    async def close_ticket(self, interaction: discord.Interaction, button: Button):
        if "ticket-" not in interaction.channel.name:
            return await interaction.response.send_message("❌ | هذه القناة ليست تذكرة!", ephemeral=True)
        
        confirm_view = TicketConfirmClose()
        await interaction.response.send_message("🔒 | تأكيد إغلاق التذكرة؟", view=confirm_view)

class TicketConfirmClose(View):
    def __init__(self):
        super().__init__(timeout=30)
    
    @discord.ui.button(label="✅ | تأكيد الإغلاق", style=discord.ButtonStyle.danger)
    async def confirm_close(self, interaction: discord.Interaction, button: Button):
        channel = interaction.channel
        embed = discord.Embed(title="🔒 | جاري إغلاق التذكرة...", description="سيتم حذف القناة بعد 5 ثواني", color=0xED4245)
        await interaction.response.edit_message(embed=embed, view=None)
        
        # Save transcript
        messages = []
        async for msg in channel.history(limit=100):
            messages.append(f"[{msg.created_at}] {msg.author}: {msg.content}")
        transcript_path = BASE / "data" / "transcripts" / f"{channel.name}.txt"
        transcript_path.parent.mkdir(exist_ok=True)
        transcript_path.write_text("\n".join(reversed(messages)))
        
        await asyncio.sleep(5)
        await channel.delete()
    
    @discord.ui.button(label="❌ | إلغاء", style=discord.ButtonStyle.grey)
    async def cancel_close(self, interaction: discord.Interaction, button: Button):
        await interaction.response.edit_message(content="✅ | تم إلغاء الإغلاق", view=None)

class Ticket(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    ticket_group = app_commands.Group(name="ticket", description="🎫 نظام التذاكر")
    
    @ticket_group.command(name="setup", description="🎫 نصب لوحة التذاكر في هذه القناة")
    @app_commands.default_permissions(administrator=True)
    async def ticket_setup(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🎫 | نظام التذاكر",
            description="اضغط الزر أدناه لفتح تذكرة دعم فني\nسيتم إنشاء قناة خاصة بك",
            color=CONFIG.get("color", 0x5865F2),
        )
        embed.add_field(name="✅", value="فريق الدعم سيرد عليك في أقرب وقت", inline=True)
        embed.add_field(name="🔒", value="اضغط لإغلاق التذكرة بعد الانتهاء", inline=True)
        embed.set_footer(text="VØRTΞX HOST • 24/7 Support")
        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)
        
        view = TicketView(interaction.guild.id)
        await interaction.response.send_message(embed=embed, view=view)
    
    @ticket_group.command(name="config", description="⚙️ إعدادات التذاكر (category / support-roles / log)")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        setting="الإعداد: category | support-roles | log-channel",
        value="القيمة الجديدة"
    )
    async def ticket_config(self, interaction: discord.Interaction, setting: str, value: str):
        config = load_ticket_config()
        gid = str(interaction.guild.id)
        if gid not in config:
            config[gid] = {}
        
        setting_map = {
            "category": "category",
            "support-roles": "support_roles",
            "log-channel": "log_channel",
            "log_channel": "log_channel",
            "support_roles": "support_roles"
        }
        
        key = setting_map.get(setting)
        if not key:
            return await interaction.response.send_message("❌ | الإعدادات: `category`, `support-roles`, `log-channel`", ephemeral=True)
        
        if key == "log_channel":
            try:
                ch_id = int(value.strip("<#>"))
                config[gid][key] = ch_id
                save_ticket_config(config)
                await interaction.response.send_message(f"✅ | تم ضبط قناة السجلات: <#{ch_id}>")
            except:
                await interaction.response.send_message("❌ | منشن القناة: #channel", ephemeral=True)
        elif key == "support_roles":
            config[gid][key] = [r.strip() for r in value.split(",")]
            save_ticket_config(config)
            await interaction.response.send_message(f"✅ | تم ضبط رتب الدعم: {value}")
        else:
            config[gid][key] = value
            save_ticket_config(config)
            await interaction.response.send_message(f"✅ | تم ضبط {key}: {value}")
    
    @ticket_group.command(name="add", description="➕ إضافة عضو للتذكرة")
    @app_commands.default_permissions(manage_channels=True)
    @app_commands.describe(member="العضو")
    async def ticket_add(self, interaction: discord.Interaction, member: discord.Member):
        if "ticket-" not in interaction.channel.name:
            return await interaction.response.send_message("❌ | هذه القناة ليست تذكرة!", ephemeral=True)
        await interaction.channel.set_permissions(member, read_messages=True, send_messages=True)
        await interaction.response.send_message(f"✅ | تم إضافة {member.mention} للتذكرة")
    
    @ticket_group.command(name="remove", description="➖ إزالة عضو من التذكرة")
    @app_commands.default_permissions(manage_channels=True)
    @app_commands.describe(member="العضو")
    async def ticket_remove(self, interaction: discord.Interaction, member: discord.Member):
        if "ticket-" not in interaction.channel.name:
            return await interaction.response.send_message("❌ | هذه القناة ليست تذكرة!", ephemeral=True)
        await interaction.channel.set_permissions(member, overwrite=None)
        await interaction.response.send_message(f"✅ | تم إزالة {member.mention} من التذكرة")
    
    @ticket_group.command(name="close", description="🔒 إغلاق التذكرة")
    async def ticket_close(self, interaction: discord.Interaction):
        if "ticket-" not in interaction.channel.name:
            return await interaction.response.send_message("❌ | هذه القناة ليست تذكرة!", ephemeral=True)
        confirm = TicketConfirmClose()
        await interaction.response.send_message("🔒 | تأكيد إغلاق التذكرة؟", view=confirm)
    
    # Prefix fallback
    @commands.command(name="ticket-setup")
    @commands.has_permissions(administrator=True)
    async def ticket_setup_prefix(self, ctx):
        embed = discord.Embed(title="🎫 | نظام التذاكر", description="اضغط الزر لفتح تذكرة", color=CONFIG.get("color", 0x5865F2))
        view = TicketView(ctx.guild.id)
        await ctx.send(embed=embed, view=view)
        await ctx.message.delete()
    
    @commands.command(name="adduser")
    @commands.has_permissions(manage_channels=True)
    async def adduser_prefix(self, ctx, member: discord.Member):
        if "ticket-" not in ctx.channel.name:
            return await ctx.send("❌ | هذه القناة ليست تذكرة!")
        await ctx.channel.set_permissions(member, read_messages=True, send_messages=True)
        await ctx.send(f"✅ | تم إضافة {member.mention} للتذكرة")
    
    @commands.command(name="removeuser")
    @commands.has_permissions(manage_channels=True)
    async def removeuser_prefix(self, ctx, member: discord.Member):
        if "ticket-" not in ctx.channel.name:
            return await ctx.send("❌ | هذه القناة ليست تذكرة!")
        await ctx.channel.set_permissions(member, overwrite=None)
        await ctx.send(f"✅ | تم إزالة {member.mention} من التذكرة")

async def setup(bot):
    await bot.add_cog(Ticket(bot))
