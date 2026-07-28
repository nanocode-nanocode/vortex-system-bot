"""
Custom Commands Cog — إنشاء أوامر مخصصة
Users with admin can create custom text commands that the bot responds to.
"""
import discord
from discord.ext import commands
from discord import app_commands
import json, datetime
from pathlib import Path

BASE = Path(__file__).parent.parent
DATA_FILE = BASE / "data" / "custom_commands.json"

def load_data():
    if DATA_FILE.exists():
        try:
            return json.loads(DATA_FILE.read_text())
        except:
            pass
    return {}

def save_data(data):
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))

class CustomCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data = load_data()

    def get_guild_cmds(self, guild_id):
        gid = str(guild_id)
        if gid not in self.data:
            self.data[gid] = {}
        return self.data[gid]

    custom_group = app_commands.Group(
        name="commands",
        description="إدارة الأوامر المخصصة",
        default_permissions=discord.Permissions(administrator=True),
    )

    @custom_group.command(name="add", description="إضافة أمر مخصص جديد")
    @app_commands.describe(
        trigger="كلمة الأمر (بدون prefix)",
        response="الرد الذي سيرسله البوت"
    )
    async def cc_add(self, interaction: discord.Interaction, trigger: str, response: str):
        """إضافة أمر مخصص"""
        gcmds = self.get_guild_cmds(interaction.guild_id)
        trigger_lower = trigger.lower().strip()
        
        if not trigger_lower:
            await interaction.response.send_message("❌ | كلمة الأمر لا يمكن أن تكون فارغة!", ephemeral=True)
            return
        
        gcmds[trigger_lower] = {
            "response": response,
            "author_id": interaction.user.id,
            "created_at": datetime.datetime.utcnow().isoformat()
        }
        save_data(self.data)
        
        embed = discord.Embed(
            title="✅ أمر مخصص مضاف",
            description=f"**الأمر:** `!{trigger_lower}`\n**الرد:** {response[:500]}",
            color=discord.Color.green()
        )
        embed.set_footer(text=f"بواسطة {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed, ephemeral=False)

    @custom_group.command(name="remove", description="حذف أمر مخصص")
    @app_commands.describe(trigger="كلمة الأمر للحذف")
    async def cc_remove(self, interaction: discord.Interaction, trigger: str):
        """حذف أمر مخصص"""
        gcmds = self.get_guild_cmds(interaction.guild_id)
        trigger_lower = trigger.lower().strip()
        
        if trigger_lower in gcmds:
            del gcmds[trigger_lower]
            save_data(self.data)
            await interaction.response.send_message(f"✅ | تم حذف الأمر `!{trigger_lower}`", ephemeral=False)
        else:
            await interaction.response.send_message(f"❌ | الأمر `!{trigger_lower}` غير موجود!", ephemeral=True)

    @custom_group.command(name="list", description="عرض جميع الأوامر المخصصة")
    async def cc_list(self, interaction: discord.Interaction):
        """عرض قائمة الأوامر المخصصة"""
        gcmds = self.get_guild_cmds(interaction.guild_id)
        
        if not gcmds:
            await interaction.response.send_message("📭 | لا توجد أوامر مخصصة في هذا السيرفر.", ephemeral=False)
            return
        
        embed = discord.Embed(
            title="📋 الأوامر المخصصة",
            description="\n".join(f"`!{k}`" for k in sorted(gcmds.keys())),
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"المجموع: {len(gcmds)} أمر")
        await interaction.response.send_message(embed=embed, ephemeral=False)

    @commands.Cog.listener()
    async def on_message(self, message):
        """معالجة الأوامر المخصصة"""
        if message.author.bot or not message.guild:
            return
        
        # Prefix command processing
        prefix = "!"
        if not message.content.startswith(prefix):
            return
        
        trigger = message.content[len(prefix):].strip().lower()
        gcmds = self.get_guild_cmds(message.guild.id)
        
        if trigger in gcmds:
            cmd_data = gcmds[trigger]
            response = cmd_data.get("response", "")
            # Replace placeholders
            response = response.replace("{user}", message.author.mention)
            response = response.replace("{username}", message.author.display_name)
            response = response.replace("{server}", message.guild.name)
            
            await message.reply(response, mention_author=False)

async def setup(bot):
    await bot.add_cog(CustomCommands(bot))
