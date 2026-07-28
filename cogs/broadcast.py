import discord
from discord.ext import commands
from discord import app_commands
import json, datetime, asyncio, re
from pathlib import Path

BASE = Path(__file__).parent.parent
with open(BASE / "config.json") as f:
    CONFIG = json.load(f)

HISTORY_FILE = BASE / "data" / "broadcast_history.json"


class Broadcast(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        HISTORY_FILE.parent.mkdir(exist_ok=True)
        if not HISTORY_FILE.exists():
            HISTORY_FILE.write_text("{}")

    # ── Storage helpers ────────────────────────────────────────────────

    def load_history(self):
        return json.loads(HISTORY_FILE.read_text())

    def save_history(self, data):
        HISTORY_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    def build_embed(self, title, description):
        embed = discord.Embed(
            title=title,
            description=description,
            color=CONFIG.get("color", 0x5865F2),
            timestamp=datetime.datetime.now(),
        )
        return embed

    # ── Slash command group ────────────────────────────────────────────

    broadcast = app_commands.Group(name="broadcast", description="📢 أوامر الإعلانات (للمشرفين فقط)")

    @broadcast.command(name="send", description="📢 إرسال إعلان إلى قناة واحدة")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(channel="القناة المستهدفة", title="عنوان الإعلان", message="نص الإعلان")
    async def broadcast_send(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        title: str,
        message: str,
    ):
        """إرسال إعلان إلى قناة محددة."""
        embed = self.build_embed(title, message)
        embed.set_footer(text=f"بواسطة {interaction.user.display_name}")
        await channel.send(embed=embed)

        # ── Save history ──
        history = self.load_history()
        gid = str(interaction.guild_id)
        history.setdefault(gid, []).append({
            "type": "send",
            "channel": channel.id,
            "title": title,
            "message": message,
            "by": str(interaction.user),
            "time": datetime.datetime.now().isoformat(),
        })
        self.save_history(history)

        await interaction.response.send_message(
            f"✅ | تم إرسال الإعلان إلى {channel.mention}", ephemeral=True
        )

    @broadcast.command(name="all", description="📢 إرسال إعلان إلى عدة قنوات في وقت واحد")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        channels="معرفات القنوات أو منشناتها مفصولة بمسافة (مثال: #عام #إعلانات)",
        title="عنوان الإعلان",
        message="نص الإعلان",
    )
    async def broadcast_all(
        self,
        interaction: discord.Interaction,
        channels: str,
        title: str,
        message: str,
    ):
        """إرسال إعلان إلى عدة قنوات مرة واحدة."""
        await interaction.response.defer()

        # Extract channel IDs from mentions / raw numbers
        ids = re.findall(r"\d+", channels)
        targets = []
        errors = []

        for cid in ids:
            ch = interaction.guild.get_channel(int(cid))
            if ch and isinstance(ch, discord.TextChannel):
                targets.append(ch)
            else:
                errors.append(cid)

        if not targets:
            return await interaction.followup.send(
                "❌ | لم أجد أي قناة صالحة!", ephemeral=True
            )

        embed = self.build_embed(title, message)
        embed.set_footer(text=f"بواسطة {interaction.user.display_name} • إعلان عام")

        sent = 0
        for ch in targets:
            try:
                await ch.send(embed=embed)
                sent += 1
            except discord.Forbidden:
                errors.append(str(ch.id))

        # ── Save history ──
        history = self.load_history()
        gid = str(interaction.guild_id)
        history.setdefault(gid, []).append({
            "type": "all",
            "channels": [ch.id for ch in targets],
            "sent": sent,
            "title": title,
            "message": message,
            "by": str(interaction.user),
            "time": datetime.datetime.now().isoformat(),
        })
        self.save_history(history)

        msg = f"✅ | تم إرسال الإعلان إلى **{sent}** قناة"
        if errors:
            msg += f"\n⚠️ | فشل في: {', '.join(str(e) for e in errors)}"
        await interaction.followup.send(msg)

    @broadcast.command(name="dm", description="✉️ إرسال إعلان خاص لعضو محدد")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(member="العضو المستهدف", title="عنوان الإعلان", message="نص الإعلان")
    async def broadcast_dm(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        title: str,
        message: str,
    ):
        """إرسال إعلان خاص عبر DM لعضو."""
        embed = self.build_embed(title, message)
        embed.set_footer(text=f"رسالة من إدارة {interaction.guild.name}")

        try:
            await member.send(embed=embed)
        except discord.Forbidden:
            return await interaction.response.send_message(
                f"❌ | ما قدرت أرسل لـ {member.mention} (الخاص مقفل)", ephemeral=True
            )
        except discord.HTTPException:
            return await interaction.response.send_message(
                f"❌ | حدث خطأ أثناء الإرسال لـ {member.mention}", ephemeral=True
            )

        # ── Save history ──
        history = self.load_history()
        gid = str(interaction.guild_id)
        history.setdefault(gid, []).append({
            "type": "dm",
            "target": member.id,
            "title": title,
            "message": message,
            "by": str(interaction.user),
            "time": datetime.datetime.now().isoformat(),
        })
        self.save_history(history)

        await interaction.response.send_message(
            f"✅ | تم إرسال الإعلان الخاص إلى {member.mention}", ephemeral=True
        )

    @broadcast.command(name="role", description="👥 إرسال إعلان لجميع أعضاء رتبة محددة")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(role="الرتبة المستهدفة", title="عنوان الإعلان", message="نص الإعلان")
    async def broadcast_role(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
        title: str,
        message: str,
    ):
        """إرسال إعلان خاص لكل أعضاء رتبة معينة مع تباعد لتجنب limit."""
        await interaction.response.defer()

        embed = self.build_embed(title, message)
        embed.set_footer(text=f"رسالة من إدارة {interaction.guild.name}")

        members = [m for m in role.members if not m.bot]
        sent = 0
        failed = 0

        for member in members:
            try:
                await member.send(embed=embed)
                sent += 1
                await asyncio.sleep(1)  # Cooldown to avoid rate limits
            except (discord.Forbidden, discord.HTTPException):
                failed += 1

        # ── Save history ──
        history = self.load_history()
        gid = str(interaction.guild_id)
        history.setdefault(gid, []).append({
            "type": "role",
            "role": role.id,
            "target_count": len(members),
            "sent": sent,
            "failed": failed,
            "title": title,
            "message": message,
            "by": str(interaction.user),
            "time": datetime.datetime.now().isoformat(),
        })
        self.save_history(history)

        await interaction.followup.send(
            f"✅ | تم إرسال الإعلان إلى **{sent}** عضو من رتبة {role.mention}\n"
            f"❌ | فشل إرسال إلى **{failed}** عضو (خاص مقفل / خطأ)"
        )

    # ── History ────────────────────────────────────────────────────────

    @broadcast.command(name="history", description="📜 عرض آخر 10 إعلانات سابقة")
    @app_commands.default_permissions(administrator=True)
    async def broadcast_history(self, interaction: discord.Interaction):
        """عرض تاريخ الإعلانات المرسلة في السيرفر."""
        history = self.load_history()
        gid = str(interaction.guild_id)
        entries = history.get(gid, [])

        if not entries:
            return await interaction.response.send_message(
                "📜 | لا يوجد إعلانات سابقة في هذا السيرفر", ephemeral=True
            )

        embed = discord.Embed(
            title="📜 | تاريخ الإعلانات",
            description=f"إجمالي الإعلانات: **{len(entries)}**",
            color=CONFIG.get("color", 0x5865F2),
        )

        emoji_map = {"send": "📢", "all": "📢", "dm": "✉️", "role": "👥"}

        for entry in reversed(entries[-10:]):
            e_type = entry.get("type", "?")
            emoji = emoji_map.get(e_type, "📌")
            entry_title = entry.get("title", "بدون عنوان")
            timestamp = entry.get("time", "")[:16]
            by = entry.get("by", "غير معروف")

            embed.add_field(
                name=f"{emoji} {entry_title}",
                value=f"النوع: `{e_type}` | {timestamp}\nبواسطة: {by}",
                inline=False,
            )

        embed.set_footer(text="آخر 10 إعلانات")
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(Broadcast(bot))
