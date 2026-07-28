#!/usr/bin/env python3
"""
VØRTΞX System Bot — Tickets Cog (PostgreSQL)
Uses db.py for all persistent storage.
"""

import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button
import asyncio, json, re
from pathlib import Path

from db import (
    create_ticket,
    close_ticket,
    get_user_ticket,
    get_guild_config,
    set_guild_config,
    add_audit,
)

BASE = Path(__file__).parent.parent
with open(BASE / "config.json") as f:
    CONFIG = json.load(f)


# ── Ticket Panel View ──────────────────────────────────────────────────

class TicketView(View):
    """Persistent view: ticket-open button placed in the setup channel."""

    def __init__(self, guild_id: int):
        super().__init__(timeout=None)
        self.guild_id = guild_id

    @discord.ui.button(
        label="🎫 | فتح تذكرة",
        style=discord.ButtonStyle.primary,
        custom_id="ticket_open",
    )
    async def create_ticket(self, interaction: discord.Interaction, button: Button):
        if interaction.guild_id != self.guild_id:
            return

        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        gcfg = get_guild_config(guild.id)

        ticket_name = f"ticket-{interaction.user.name.lower().replace(' ', '-')}"

        # ── Check PostgreSQL for existing open ticket ──
        existing_ticket = get_user_ticket(guild.id, interaction.user.id)
        if existing_ticket:
            existing_ch = discord.utils.get(guild.text_channels, name=ticket_name)
            if existing_ch:
                return await interaction.followup.send(
                    f"❌ | عندك تذكرة مفتوحة: {existing_ch.mention}",
                    ephemeral=True,
                )

        # ── Resolve category ──
        category_name = gcfg.get("ticket_category", " 🎫 Tickets")
        category = discord.utils.get(guild.categories, name=category_name)
        if not category:
            category = await guild.create_category(category_name)

        # ── Resolve support roles ──
        raw_roles = gcfg.get(
            "ticket_support_roles",
            CONFIG.get("mod_roles", ["Mod", "Admin"]),
        )
        if isinstance(raw_roles, str):
            raw_roles = [r.strip() for r in raw_roles.replace("{", "").replace("}", "").split(",")]

        support_roles = []
        for rn in raw_roles:
            role = discord.utils.get(guild.roles, name=rn)
            if role:
                support_roles.append(role)

        # ── Permission overwrites ──
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(
                read_messages=True, send_messages=True, attach_files=True
            ),
            guild.me: discord.PermissionOverwrite(
                read_messages=True, send_messages=True, manage_channels=True
            ),
        }
        for role in support_roles:
            overwrites[role] = discord.PermissionOverwrite(
                read_messages=True, send_messages=True
            )

        # ── Create channel ──
        channel = await guild.create_text_channel(
            name=ticket_name,
            category=category,
            overwrites=overwrites,
            topic=f"Ticket for {interaction.user} (ID: {interaction.user.id})",
        )

        # ── Persist to PostgreSQL ──
        try:
            create_ticket(guild.id, interaction.user.id, category_name)
        except Exception:
            pass  # Non-fatal — channel is already created

        # ── Welcome embed ──
        embed_color = gcfg.get("embed_color", CONFIG.get("color", 0x5865F2))
        embed = discord.Embed(
            title="🎫 | تذكرتك",
            description=(
                f"مرحباً {interaction.user.mention}!\n"
                "الرجاء شرح مشكلتك بالتفصيل.\n\n"
                "فريق الدعم سيصل قريباً."
            ),
            color=embed_color,
        )
        embed.add_field(
            name="📌 | نصائح",
            value="• اشرح المشكلة بالتفصيل\n• أرفق صور إذا لزم الأمر\n• كن محترماً",
            inline=False,
        )
        embed.set_footer(text="VØRTΞX System • Support Team")

        close_view = TicketCloseView()
        await channel.send(embed=embed, view=close_view)
        await channel.send(
            f"{interaction.user.mention} {' '.join(r.mention for r in support_roles)}",
            delete_after=1,
        )

        # ── Audit log ──
        add_audit(
            "ticket_create",
            f"Channel: {channel.name} | Category: {category_name}",
            guild.id,
            interaction.user.id,
        )

        # ── Log channel notification ──
        log_channel_id = gcfg.get("ticket_log_channel")
        if log_channel_id:
            try:
                log_ch = guild.get_channel(int(log_channel_id))
                if log_ch:
                    await log_ch.send(
                        f"🎫 | تذكرة جديدة: {channel.mention}\n👤 | {interaction.user}"
                    )
            except Exception:
                pass

        await interaction.followup.send(
            f"✅ | تم فتح تذكرتك: {channel.mention}",
            ephemeral=True,
        )


# ── Close-Button View ──────────────────────────────────────────────────

class TicketCloseView(View):
    """Persistent view: close button sent inside every ticket channel."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="🔒 | إغلاق",
        style=discord.ButtonStyle.danger,
        custom_id="ticket_close",
    )
    async def close_ticket(self, interaction: discord.Interaction, button: Button):
        if "ticket-" not in interaction.channel.name:
            await interaction.response.defer(ephemeral=True)
            return await interaction.followup.send(
                "❌ | هذه القناة ليست تذكرة!", ephemeral=True
            )

        await interaction.response.defer()
        confirm_view = TicketConfirmClose()
        await interaction.followup.send(
            "🔒 | تأكيد إغلاق التذكرة؟", view=confirm_view
        )


# ── Confirm-Close View ─────────────────────────────────────────────────

class TicketConfirmClose(View):
    """Ephemeral confirmation view with a 30-second timeout."""

    def __init__(self):
        super().__init__(timeout=30)

    @discord.ui.button(label="✅ | تأكيد الإغلاق", style=discord.ButtonStyle.danger)
    async def confirm_close(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        channel = interaction.channel

        # ── Extract ticket owner from channel topic ──
        ticket_user_id = None
        if channel.topic:
            m = re.search(r"ID:\s*(\d+)", channel.topic)
            if m:
                ticket_user_id = int(m.group(1))

        # ── Update the confirmation message ──
        progress_embed = discord.Embed(
            title="🔒 | جاري إغلاق التذكرة...",
            description="سيتم حذف القناة بعد 5 ثواني",
            color=0xED4245,
        )
        await interaction.edit_original_response(embed=progress_embed, view=None)

        # ── Save transcript ──
        messages = []
        async for msg in channel.history(limit=100):
            messages.append(f"[{msg.created_at}] {msg.author}: {msg.content}")

        transcript_path = BASE / "data" / "transcripts" / f"{channel.name}.txt"
        transcript_path.parent.mkdir(parents=True, exist_ok=True)
        transcript_path.write_text("\n".join(reversed(messages)))

        # ── Close in PostgreSQL ──
        try:
            if ticket_user_id:
                ticket = get_user_ticket(channel.guild.id, ticket_user_id)
                if ticket:
                    close_ticket(ticket["id"], interaction.user.id)
        except Exception:
            pass

        # ── Audit ──
        add_audit(
            "ticket_close",
            f"Channel: {channel.name} | Transcript: {transcript_path.name}",
            channel.guild.id,
            interaction.user.id,
        )

        await asyncio.sleep(5)
        await channel.delete()

    @discord.ui.button(label="❌ | إلغاء", style=discord.ButtonStyle.grey)
    async def cancel_close(self, interaction: discord.Interaction, button: Button):
        await interaction.response.defer()
        await interaction.edit_original_response(
            content="✅ | تم إلغاء الإغلاق", view=None
        )


# ── Main Cog ───────────────────────────────────────────────────────────

class Ticket(commands.Cog):
    """Slash + prefix commands for the ticket system."""

    def __init__(self, bot):
        self.bot = bot

    ticket_group = app_commands.Group(name="ticket", description="🎫 نظام التذاكر")

    # ── /ticket setup ───────────────────────────────────────────────────

    @ticket_group.command(
        name="setup", description="🎫 نصب لوحة التذاكر في هذه القناة"
    )
    @app_commands.default_permissions(administrator=True)
    async def ticket_setup(self, interaction: discord.Interaction):
        await interaction.response.defer()

        embed_color = CONFIG.get("color", 0x5865F2)
        embed = discord.Embed(
            title="🎫 | نظام التذاكر",
            description=(
                "اضغط الزر أدناه لفتح تذكرة دعم فني\n"
                "سيتم إنشاء قناة خاصة بك"
            ),
            color=embed_color,
        )
        embed.add_field(
            name="✅",
            value="فريق الدعم سيرد عليك في أقرب وقت",
            inline=True,
        )
        embed.add_field(
            name="🔒",
            value="اضغط لإغلاق التذكرة بعد الانتهاء",
            inline=True,
        )
        embed.set_footer(text="VØRTΞX HOST • 24/7 Support")
        if interaction.guild.icon:
            embed.set_thumbnail(url=interaction.guild.icon.url)

        view = TicketView(interaction.guild.id)
        await interaction.followup.send(embed=embed, view=view)

    # ── /ticket config ──────────────────────────────────────────────────

    @ticket_group.command(
        name="config",
        description="⚙️ إعدادات التذاكر (category / support-roles / log)",
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        setting="الإعداد: category | support-roles | log-channel",
        value="القيمة الجديدة",
    )
    async def ticket_config(
        self,
        interaction: discord.Interaction,
        setting: str,
        value: str,
    ):
        await interaction.response.defer(ephemeral=True)

        gid = interaction.guild.id
        setting_map = {
            "category": "ticket_category",
            "support-roles": "ticket_support_roles",
            "log-channel": "ticket_log_channel",
            "log_channel": "ticket_log_channel",
            "support_roles": "ticket_support_roles",
        }

        key = setting_map.get(setting)
        if not key:
            return await interaction.followup.send(
                "❌ | الإعدادات: `category`, `support-roles`, `log-channel`",
                ephemeral=True,
            )

        if key == "ticket_log_channel":
            try:
                ch_id = int(value.strip("<#>"))
                set_guild_config(gid, **{key: ch_id})
                await interaction.followup.send(
                    f"✅ | تم ضبط قناة السجلات: <#{ch_id}>"
                )
            except (ValueError, Exception):
                return await interaction.followup.send(
                    "❌ | منشن القناة: #channel",
                    ephemeral=True,
                )
        elif key == "ticket_support_roles":
            roles_str = ",".join(r.strip() for r in value.split(","))
            set_guild_config(gid, **{key: roles_str})
            await interaction.followup.send(f"✅ | تم ضبط رتب الدعم: {value}")
        else:
            set_guild_config(gid, **{key: value})
            await interaction.followup.send(f"✅ | تم ضبط {setting}: {value}")

        add_audit(
            "ticket_config",
            f"{setting} → {value}",
            gid,
            interaction.user.id,
        )

    # ── /ticket add ─────────────────────────────────────────────────────

    @ticket_group.command(
        name="add", description="➕ إضافة عضو للتذكرة"
    )
    @app_commands.default_permissions(manage_channels=True)
    @app_commands.describe(member="العضو")
    async def ticket_add(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
    ):
        await interaction.response.defer()

        if "ticket-" not in interaction.channel.name:
            return await interaction.followup.send(
                "❌ | هذه القناة ليست تذكرة!",
                ephemeral=True,
            )

        await interaction.channel.set_permissions(
            member, read_messages=True, send_messages=True
        )
        await interaction.followup.send(
            f"✅ | تم إضافة {member.mention} للتذكرة"
        )

    # ── /ticket remove ──────────────────────────────────────────────────

    @ticket_group.command(
        name="remove", description="➖ إزالة عضو من التذكرة"
    )
    @app_commands.default_permissions(manage_channels=True)
    @app_commands.describe(member="العضو")
    async def ticket_remove(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
    ):
        await interaction.response.defer()

        if "ticket-" not in interaction.channel.name:
            return await interaction.followup.send(
                "❌ | هذه القناة ليست تذكرة!",
                ephemeral=True,
            )

        await interaction.channel.set_permissions(member, overwrite=None)
        await interaction.followup.send(
            f"✅ | تم إزالة {member.mention} من التذكرة"
        )

    # ── /ticket close ───────────────────────────────────────────────────

    @ticket_group.command(
        name="close", description="🔒 إغلاق التذكرة"
    )
    async def ticket_close(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        if "ticket-" not in interaction.channel.name:
            return await interaction.followup.send(
                "❌ | هذه القناة ليست تذكرة!",
                ephemeral=True,
            )

        confirm = TicketConfirmClose()
        await interaction.followup.send(
            "🔒 | تأكيد إغلاق التذكرة؟",
            view=confirm,
            ephemeral=True,
        )

    # ── Prefix Fallback Commands ────────────────────────────────────────

    @commands.command(name="ticket-setup")
    @commands.has_permissions(administrator=True)
    async def ticket_setup_prefix(self, ctx):
        embed_color = CONFIG.get("color", 0x5865F2)
        embed = discord.Embed(
            title="🎫 | نظام التذاكر",
            description="اضغط الزر لفتح تذكرة",
            color=embed_color,
        )
        view = TicketView(ctx.guild.id)
        await ctx.send(embed=embed, view=view)
        try:
            await ctx.message.delete()
        except Exception:
            pass

    @commands.command(name="adduser")
    @commands.has_permissions(manage_channels=True)
    async def adduser_prefix(self, ctx, member: discord.Member):
        if "ticket-" not in ctx.channel.name:
            return await ctx.send("❌ | هذه القناة ليست تذكرة!")
        await ctx.channel.set_permissions(
            member, read_messages=True, send_messages=True
        )
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
