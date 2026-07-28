#!/usr/bin/env python3
"""
VØRTΞX System Bot — Admin Cog (Expanded)
Full administration suite with 30 commands: moderation, channels, roles,
emoji management, voice moderation, server backups, and welcome config.
"""
import discord
from discord.ext import commands
from discord import app_commands
import json
import time
import asyncio
from pathlib import Path

BASE = Path(__file__).parent.parent
with open(BASE / "config.json") as f:
    CONFIG = json.load(f)

from db import set_guild_config, get_guild_config, add_audit
from i18n import t

BACKUP_DIR = BASE / "backups"
BACKUP_DIR.mkdir(exist_ok=True)


def get_lang(guild_id: int) -> str:
    """Get the guild's configured language (ar/en), defaulting to Arabic."""
    return get_guild_config(guild_id).get("language", "ar")


async def log_to_mod_log(guild, message: str):
    """Send a log message to the guild's mod-log channel if configured."""
    try:
        cfg = get_guild_config(guild.id)
        ch_id = cfg.get("mod_log_channel")
        if ch_id:
            ch = guild.get_channel(ch_id)
            if ch:
                await ch.send(message)
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════
#  COG
# ═══════════════════════════════════════════════════════════════════════

class Admin(commands.Cog):
    """Admin & moderation commands for server managers."""

    def __init__(self, bot):
        self.bot = bot

    # ───────────────────────────────────────────────────────────────────
    #  EXISTING COMMANDS
    # ───────────────────────────────────────────────────────────────────

    @app_commands.command(name="setup", description="⚙️ الإعدادات الأساسية للبوت / Basic bot setup")
    @app_commands.describe(
        welcome_channel="روم الترحيب / Welcome channel",
        ticket_category="قسم التذاكر / Ticket category",
        admin_role="رول الأدمن / Admin role",
        mod_role="رول المشرف / Mod role",
        mod_log_channel="روم سجل الإشراف / Mod-log channel",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def setup(
        self,
        interaction: discord.Interaction,
        welcome_channel: discord.TextChannel = None,
        ticket_category: discord.CategoryChannel = None,
        admin_role: discord.Role = None,
        mod_role: discord.Role = None,
        mod_log_channel: discord.TextChannel = None,
    ):
        """Configure core server settings for the bot."""
        await interaction.response.defer(ephemeral=True)
        lang = get_lang(interaction.guild_id)
        data = {}
        if welcome_channel:
            data["welcome_channel"] = welcome_channel.id
        if ticket_category:
            data["ticket_category"] = ticket_category.id
        if admin_role:
            data["admin_role"] = admin_role.id
        if mod_role:
            data["mod_role"] = mod_role.id
        if mod_log_channel:
            data["mod_log_channel"] = mod_log_channel.id

        if data:
            set_guild_config(interaction.guild_id, **data)
            add_audit(
                "setup",
                f"Server configured by {interaction.user}",
                interaction.guild_id,
                interaction.user.id,
            )
            await interaction.followup.send(t(lang, "setup_done"), ephemeral=True)
        else:
            msg = "⚠️ " + (
                "لم تختار أي إعدادات!" if lang == "ar" else "You didn't select any settings!"
            )
            await interaction.followup.send(msg, ephemeral=True)

    # ── config ─────────────────────────────────────────────────────────

    @app_commands.command(name="config", description="⚙️ عرض إعدادات السيرفر / View server config")
    @app_commands.checks.has_permissions(administrator=True)
    async def config(self, interaction: discord.Interaction):
        """Display the current guild configuration."""
        await interaction.response.defer(ephemeral=True)
        lang = get_lang(interaction.guild_id)
        cfg = get_guild_config(interaction.guild_id)

        embed = discord.Embed(
            title=t(lang, "config_title"),
            color=CONFIG.get("color", 5792082),
        )

        def val_or_not_set(key):
            v = cfg.get(key)
            if v:
                return f"<#{v}>" if key in ("welcome_channel", "mod_log_channel", "ticket_category") else f"<@&{v}>"
            return t(lang, "not_set")

        embed.add_field(name=t(lang, "welcome_channel"), value=val_or_not_set("welcome_channel"), inline=True)
        embed.add_field(name=t(lang, "ticket_category"), value=val_or_not_set("ticket_category"), inline=True)
        embed.add_field(name=t(lang, "admin_role"), value=val_or_not_set("admin_role"), inline=True)
        embed.add_field(name=t(lang, "mod_role"), value=val_or_not_set("mod_role"), inline=True)
        embed.add_field(name=t(lang, "mod_log"), value=val_or_not_set("mod_log_channel"), inline=True)

        # Extra config fields stored via new commands
        extra = {
            "welcome_image": "🖼️ Welcome Image",
            "leave_channel": "👋 Leave Channel",
            "leave_message": "👋 Leave Message",
            "boost_channel": "💎 Boost Channel",
            "boost_message": "💎 Boost Message",
            "autorole": "🎭 Auto-Role",
        }
        for db_key, label in extra.items():
            v = cfg.get(db_key)
            if v:
                embed.add_field(
                    name=label,
                    value=f"<#{v}>" if db_key.endswith("_channel") else f"<@&{v}>" if db_key == "autorole" else f"`{v[:50]}{'…' if len(str(v)) > 50 else ''}`",
                    inline=True,
                )

        await interaction.followup.send(embed=embed, ephemeral=True)

    # ── sync ───────────────────────────────────────────────────────────

    @app_commands.command(name="sync", description="🔄 إعادة مزامنة الأوامر / Resync slash commands")
    @app_commands.checks.has_permissions(administrator=True)
    async def sync(self, interaction: discord.Interaction):
        """Force-sync all slash commands for this guild."""
        await interaction.response.defer(ephemeral=True)
        lang = get_lang(interaction.guild_id)
        try:
            synced = await self.bot.tree.sync(guild=interaction.guild)
            msg = (
                f"✅ تمت مزامنة {len(synced)} أمر!" if lang == "ar"
                else f"✅ Synced {len(synced)} commands!"
            )
            await interaction.followup.send(msg, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ {e}", ephemeral=True)

    # ── ban ────────────────────────────────────────────────────────────

    @app_commands.command(name="ban", description="🔨 حظر عضو / Ban a member")
    @app_commands.describe(member="العضو / Member", reason="السبب / Reason")
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban(
        self, interaction: discord.Interaction, member: discord.Member, reason: str = "—"
    ):
        """Ban a member from the server."""
        await interaction.response.defer(ephemeral=True)
        lang = get_lang(interaction.guild_id)
        if member.top_role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
            msg = "❌ " + (
                "لا يمكنك حظر هذا العضو!" if lang == "ar" else "You can't ban this member!"
            )
            await interaction.followup.send(msg, ephemeral=True)
            return
        await member.ban(reason=f"{interaction.user}: {reason}")
        add_audit("ban", f"{member} banned by {interaction.user}", interaction.guild_id, interaction.user.id)
        msg = (
            f"🔨 تم حظر {member.mention}!" if lang == "ar"
            else f"🔨 Banned {member.mention}!"
        )
        await interaction.followup.send(msg, ephemeral=True)
        await log_to_mod_log(
            interaction.guild,
            f"🔨 **Ban**\nMember: {member}\nMod: {interaction.user}\nReason: {reason}",
        )

    # ── kick ───────────────────────────────────────────────────────────

    @app_commands.command(name="kick", description="👢 طرد عضو / Kick a member")
    @app_commands.describe(member="العضو / Member", reason="السبب / Reason")
    @app_commands.checks.has_permissions(kick_members=True)
    async def kick(
        self, interaction: discord.Interaction, member: discord.Member, reason: str = "—"
    ):
        """Kick a member from the server."""
        await interaction.response.defer(ephemeral=True)
        lang = get_lang(interaction.guild_id)
        if member.top_role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
            msg = "❌ " + (
                "لا يمكنك طرد هذا العضو!" if lang == "ar" else "You can't kick this member!"
            )
            await interaction.followup.send(msg, ephemeral=True)
            return
        await member.kick(reason=f"{interaction.user}: {reason}")
        add_audit("kick", f"{member} kicked by {interaction.user}", interaction.guild_id, interaction.user.id)
        msg = (
            f"👢 تم طرد {member.mention}!" if lang == "ar"
            else f"👢 Kicked {member.mention}!"
        )
        await interaction.followup.send(msg, ephemeral=True)
        await log_to_mod_log(
            interaction.guild,
            f"👢 **Kick**\nMember: {member}\nMod: {interaction.user}\nReason: {reason}",
        )

    # ── clear ──────────────────────────────────────────────────────────

    @app_commands.command(name="clear", description="🧹 مسح رسائل / Purge messages")
    @app_commands.describe(amount="عدد الرسائل / Number of messages")
    @app_commands.checks.has_permissions(manage_messages=True)
    async def clear(self, interaction: discord.Interaction, amount: int = 10):
        """Bulk-delete messages in the current channel."""
        await interaction.response.defer(ephemeral=True)
        lang = get_lang(interaction.guild_id)
        if amount < 1 or amount > 100:
            msg = "⚠️ " + (
                "العدد بين 1-100" if lang == "ar" else "Amount must be between 1-100"
            )
            await interaction.followup.send(msg, ephemeral=True)
            return
        deleted = await interaction.channel.purge(limit=min(amount, 100))
        add_audit(
            "clear",
            f"{len(deleted)} messages deleted by {interaction.user}",
            interaction.guild_id,
            interaction.user.id,
        )
        msg = (
            f"🧹 تم مسح {len(deleted)} رسالة!" if lang == "ar"
            else f"🧹 Deleted {len(deleted)} messages!"
        )
        await interaction.followup.send(msg, ephemeral=True)

    # ── lock ───────────────────────────────────────────────────────────

    @app_commands.command(name="lock", description="🔒 قفل الروم / Lock a channel")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def lock(self, interaction: discord.Interaction):
        """Lock the current channel (@everyone can't send messages)."""
        await interaction.response.defer(ephemeral=True)
        lang = get_lang(interaction.guild_id)
        await interaction.channel.set_permissions(
            interaction.guild.default_role, send_messages=False
        )
        add_audit("lock", f"Channel locked by {interaction.user}", interaction.guild_id, interaction.user.id)
        msg = "🔒 " + ("تم قفل الروم!" if lang == "ar" else "Channel locked!")
        await interaction.followup.send(msg, ephemeral=True)

    # ── unlock ─────────────────────────────────────────────────────────

    @app_commands.command(name="unlock", description="🔓 فتح الروم / Unlock a channel")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def unlock(self, interaction: discord.Interaction):
        """Unlock the current channel (restore @everyone send permission)."""
        await interaction.response.defer(ephemeral=True)
        lang = get_lang(interaction.guild_id)
        await interaction.channel.set_permissions(
            interaction.guild.default_role, send_messages=None
        )
        add_audit("unlock", f"Channel unlocked by {interaction.user}", interaction.guild_id, interaction.user.id)
        msg = "🔓 " + ("تم فتح الروم!" if lang == "ar" else "Channel unlocked!")
        await interaction.followup.send(msg, ephemeral=True)

    # ── nickname ───────────────────────────────────────────────────────

    @app_commands.command(name="nickname", description="✏️ تغيير الكنية / Change nickname")
    @app_commands.describe(member="العضو / Member", nickname="الكنية الجديدة / New nickname")
    @app_commands.checks.has_permissions(manage_nicknames=True)
    async def nickname(
        self, interaction: discord.Interaction, member: discord.Member, nickname: str
    ):
        """Change a member's server nickname."""
        await interaction.response.defer(ephemeral=True)
        lang = get_lang(interaction.guild_id)
        await member.edit(nick=nickname)
        add_audit("nickname", f"{member} nicknamed by {interaction.user}", interaction.guild_id, interaction.user.id)
        msg = (
            f"✏️ تم تغيير كنية {member.mention}!" if lang == "ar"
            else f"✏️ Changed {member.mention}'s nickname!"
        )
        await interaction.followup.send(msg, ephemeral=True)

    # ── role ───────────────────────────────────────────────────────────

    @app_commands.command(name="role", description="🎭 إضافة/إزالة رول / Add or remove a role")
    @app_commands.describe(member="العضو / Member", role="الرول / Role")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def role(
        self, interaction: discord.Interaction, member: discord.Member, role: discord.Role
    ):
        """Toggle a role on a member (add if absent, remove if present)."""
        await interaction.response.defer(ephemeral=True)
        lang = get_lang(interaction.guild_id)
        if role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
            msg = "❌ " + (
                "لا يمكنك تعديل هذا الرول!" if lang == "ar" else "You can't modify this role!"
            )
            await interaction.followup.send(msg, ephemeral=True)
            return
        if role in member.roles:
            await member.remove_roles(role)
            msg = (
                f"✅ تمت إزالة {role.mention} من {member.mention}!" if lang == "ar"
                else f"✅ Removed {role.mention} from {member.mention}!"
            )
        else:
            await member.add_roles(role)
            msg = (
                f"✅ تمت إضافة {role.mention} لـ {member.mention}!" if lang == "ar"
                else f"✅ Added {role.mention} to {member.mention}!"
            )
        add_audit("role", f"{role} {'removed from' if role in member.roles else 'added to'} {member} by {interaction.user}", interaction.guild_id, interaction.user.id)
        await interaction.followup.send(msg, ephemeral=True)

    # ───────────────────────────────────────────────────────────────────
    #  NEW CHANNEL COMMANDS
    # ───────────────────────────────────────────────────────────────────

    @app_commands.command(name="slowmode", description="🐌 ضبط الوضع البطيء / Set channel slowmode")
    @app_commands.describe(
        seconds="المدة بالثواني (0 لإلغاء) / Duration in seconds (0 to disable)",
        channel="الروم (اختياري) / Channel (optional, defaults to current)",
    )
    @app_commands.checks.has_permissions(manage_channels=True)
    async def slowmode(
        self,
        interaction: discord.Interaction,
        seconds: int,
        channel: discord.TextChannel = None,
    ):
        """Set the slowmode delay on a text channel (0–21600 seconds)."""
        await interaction.response.defer(ephemeral=True)
        lang = get_lang(interaction.guild_id)
        channel = channel or interaction.channel

        if seconds < 0 or seconds > 21600:
            msg = "⚠️ " + (
                "المدة بين 0 و 21600 ثانية!" if lang == "ar" else "Duration must be 0–21600 seconds!"
            )
            await interaction.followup.send(msg, ephemeral=True)
            return

        try:
            await channel.edit(slowmode_delay=seconds)
            add_audit(
                "slowmode",
                f"Slowmode set to {seconds}s in #{channel} by {interaction.user}",
                interaction.guild_id,
                interaction.user.id,
            )
            if seconds == 0:
                msg = (
                    f"🐌 تم إلغاء الوضع البطيء في {channel.mention}!" if lang == "ar"
                    else f"🐌 Disabled slowmode in {channel.mention}!"
                )
            else:
                msg = (
                    f"🐌 تم ضبط الوضع البطيء على {seconds}ث في {channel.mention}!" if lang == "ar"
                    else f"🐌 Set slowmode to {seconds}s in {channel.mention}!"
                )
            await interaction.followup.send(msg, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ {e}", ephemeral=True)

    # ── rename ─────────────────────────────────────────────────────────

    @app_commands.command(name="rename", description="✏️ إعادة تسمية روم أو قسم / Rename a channel or category")
    @app_commands.describe(
        name="الاسم الجديد / New name",
        channel="الروم أو القسم (اختياري) / Channel or category (optional, defaults to current)",
    )
    @app_commands.checks.has_permissions(manage_channels=True)
    async def rename(
        self,
        interaction: discord.Interaction,
        name: str,
        channel: discord.abc.GuildChannel = None,
    ):
        """Rename a text, voice, or category channel."""
        await interaction.response.defer(ephemeral=True)
        lang = get_lang(interaction.guild_id)
        channel = channel or interaction.channel

        old_name = channel.name
        try:
            await channel.edit(name=name)
            add_audit(
                "rename",
                f"#{old_name} → #{name} by {interaction.user}",
                interaction.guild_id,
                interaction.user.id,
            )
            msg = (
                f"✏️ تم تغيير اسم {old_name} إلى {name}!" if lang == "ar"
                else f"✏️ Renamed {old_name} to {name}!"
            )
            await interaction.followup.send(msg, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ {e}", ephemeral=True)

    # ── clone ──────────────────────────────────────────────────────────

    @app_commands.command(name="clone", description="📋 نسخ الروم / Clone a channel")
    @app_commands.describe(
        channel="الروم المراد نسخه (اختياري) / Channel to clone (optional, defaults to current)",
    )
    @app_commands.checks.has_permissions(manage_channels=True)
    async def clone(
        self,
        interaction: discord.Interaction,
        channel: discord.abc.GuildChannel = None,
    ):
        """Create an exact clone of a channel (permissions, topic, etc)."""
        await interaction.response.defer(ephemeral=True)
        lang = get_lang(interaction.guild_id)
        channel = channel or interaction.channel

        try:
            new_channel = await channel.clone()
            add_audit(
                "clone",
                f"#{channel.name} cloned to #{new_channel.name} by {interaction.user}",
                interaction.guild_id,
                interaction.user.id,
            )
            msg = (
                f"📋 تم نسخ {channel.mention} → {new_channel.mention}!" if lang == "ar"
                else f"📋 Cloned {channel.mention} → {new_channel.mention}!"
            )
            await interaction.followup.send(msg, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ {e}", ephemeral=True)

    # ── nuke ───────────────────────────────────────────────────────────

    @app_commands.command(name="nuke", description="💣 تفجير الروم (نسخ + حذف) / Nuke a channel (clone + delete)")
    @app_commands.describe(
        channel="الروم المراد تفجيره (اختياري) / Channel to nuke (optional, defaults to current)",
    )
    @app_commands.checks.has_permissions(manage_channels=True)
    async def nuke(
        self,
        interaction: discord.Interaction,
        channel: discord.abc.GuildChannel = None,
    ):
        """Delete a channel and replace it with a fresh clone."""
        await interaction.response.defer(ephemeral=True)
        lang = get_lang(interaction.guild_id)
        channel = channel or interaction.channel
        ch_name = channel.name
        ch_category = channel.category
        ch_position = channel.position

        # Send confirmation embed to the channel before nuking
        try:
            await channel.send(
                "💣 **NUKE INITIATED** — This channel will self-destruct in 5 seconds…"
            )
        except Exception:
            pass

        await asyncio.sleep(5)

        try:
            new_channel = await channel.clone()
            await channel.delete()
            await new_channel.edit(position=ch_position)
            if ch_category:
                await new_channel.edit(category=ch_category)

            add_audit(
                "nuke",
                f"#{ch_name} nuked by {interaction.user}",
                interaction.guild_id,
                interaction.user.id,
            )
            await new_channel.send(
                f"💣 **NUKE COMPLETE** — {interaction.user.mention} nuked this channel!"
            )
            msg = (
                f"💣 تم تفجير #{ch_name}!" if lang == "ar"
                else f"💣 Nuked #{ch_name}!"
            )
            await interaction.followup.send(msg, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ {e}", ephemeral=True)

    # ───────────────────────────────────────────────────────────────────
    #  NEW VOICE COMMANDS
    # ───────────────────────────────────────────────────────────────────

    @app_commands.command(name="moveall", description="🔊 نقل الجميع من روم صوتي لآخر / Move all members between voice channels")
    @app_commands.describe(
        source="روم المصدر / Source voice channel",
        target="الروم الهدف / Target voice channel",
    )
    @app_commands.checks.has_permissions(move_members=True)
    async def moveall(
        self,
        interaction: discord.Interaction,
        source: discord.VoiceChannel,
        target: discord.VoiceChannel,
    ):
        """Move every member from one voice channel to another."""
        await interaction.response.defer(ephemeral=True)
        lang = get_lang(interaction.guild_id)

        members = source.members
        if not members:
            msg = "⚠️ " + (
                "ما في أعضاء في الروم المصدر!" if lang == "ar" else "No members in the source channel!"
            )
            await interaction.followup.send(msg, ephemeral=True)
            return

        moved = 0
        errors = 0
        for m in members:
            try:
                await m.move_to(target)
                moved += 1
            except Exception:
                errors += 1

        add_audit(
            "moveall",
            f"Moved {moved} members from #{source.name} to #{target.name} by {interaction.user}",
            interaction.guild_id,
            interaction.user.id,
        )
        msg = (
            f"🔊 تم نقل {moved} عضو من {source.mention} إلى {target.mention}!"
            if lang == "ar"
            else f"🔊 Moved {moved} members from {source.mention} to {target.mention}!"
        )
        if errors:
            msg += (
                f"\n⚠️ {errors} فشل." if lang == "ar" else f"\n⚠️ {errors} failed."
            )
        await interaction.followup.send(msg, ephemeral=True)

    # ── voicekick ──────────────────────────────────────────────────────

    @app_commands.command(name="voicekick", description="🔇 فصل عضو من الروم الصوتي / Disconnect a member from voice")
    @app_commands.describe(member="العضو / Member")
    @app_commands.checks.has_permissions(move_members=True)
    async def voicekick(
        self, interaction: discord.Interaction, member: discord.Member
    ):
        """Disconnect a member from their current voice channel."""
        await interaction.response.defer(ephemeral=True)
        lang = get_lang(interaction.guild_id)

        if not member.voice or not member.voice.channel:
            msg = "⚠️ " + (
                "هذا العضو ليس في روم صوتي!" if lang == "ar" else "That member isn't in a voice channel!"
            )
            await interaction.followup.send(msg, ephemeral=True)
            return

        try:
            await member.move_to(None)
            add_audit(
                "voicekick",
                f"{member} disconnected from voice by {interaction.user}",
                interaction.guild_id,
                interaction.user.id,
            )
            msg = (
                f"🔇 تم فصل {member.mention} من الروم الصوتي!" if lang == "ar"
                else f"🔇 Disconnected {member.mention} from voice!"
            )
            await interaction.followup.send(msg, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ {e}", ephemeral=True)

    # ── deafen ─────────────────────────────────────────────────────────

    @app_commands.command(name="deafen", description="🔇 إصماء عضو في الروم الصوتي / Server-deafen a member")
    @app_commands.describe(member="العضو / Member")
    @app_commands.checks.has_permissions(deafen_members=True)
    async def deafen(
        self, interaction: discord.Interaction, member: discord.Member
    ):
        """Server-deafen a member in voice."""
        await interaction.response.defer(ephemeral=True)
        lang = get_lang(interaction.guild_id)
        try:
            await member.edit(deafen=True)
            add_audit(
                "deafen",
                f"{member} deafened by {interaction.user}",
                interaction.guild_id,
                interaction.user.id,
            )
            msg = (
                f"🔇 تم إصماء {member.mention}!" if lang == "ar"
                else f"🔇 Deafened {member.mention}!"
            )
            await interaction.followup.send(msg, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ {e}", ephemeral=True)

    # ── undeafen ───────────────────────────────────────────────────────

    @app_commands.command(name="undeafen", description="🔊 إلغاء إصماء عضو / Undeafen a member")
    @app_commands.describe(member="العضو / Member")
    @app_commands.checks.has_permissions(deafen_members=True)
    async def undeafen(
        self, interaction: discord.Interaction, member: discord.Member
    ):
        """Remove server-deafen from a member."""
        await interaction.response.defer(ephemeral=True)
        lang = get_lang(interaction.guild_id)
        try:
            await member.edit(deafen=False)
            add_audit(
                "undeafen",
                f"{member} undeafened by {interaction.user}",
                interaction.guild_id,
                interaction.user.id,
            )
            msg = (
                f"🔊 تم إلغاء إصماء {member.mention}!" if lang == "ar"
                else f"🔊 Undeafened {member.mention}!"
            )
            await interaction.followup.send(msg, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ {e}", ephemeral=True)

    # ── mute ───────────────────────────────────────────────────────────

    @app_commands.command(name="mute", description="🔇 كتم عضو في الروم الصوتي / Server-mute a member")
    @app_commands.describe(member="العضو / Member")
    @app_commands.checks.has_permissions(mute_members=True)
    async def mute(
        self, interaction: discord.Interaction, member: discord.Member
    ):
        """Server-mute a member in voice."""
        await interaction.response.defer(ephemeral=True)
        lang = get_lang(interaction.guild_id)
        try:
            await member.edit(mute=True)
            add_audit(
                "mute",
                f"{member} muted by {interaction.user}",
                interaction.guild_id,
                interaction.user.id,
            )
            msg = (
                f"🔇 تم كتم {member.mention}!" if lang == "ar"
                else f"🔇 Muted {member.mention}!"
            )
            await interaction.followup.send(msg, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ {e}", ephemeral=True)

    # ── unmute ─────────────────────────────────────────────────────────

    @app_commands.command(name="unmute", description="🔊 إلغاء كتم عضو / Unmute a member")
    @app_commands.describe(member="العضو / Member")
    @app_commands.checks.has_permissions(mute_members=True)
    async def unmute(
        self, interaction: discord.Interaction, member: discord.Member
    ):
        """Remove server-mute from a member."""
        await interaction.response.defer(ephemeral=True)
        lang = get_lang(interaction.guild_id)
        try:
            await member.edit(mute=False)
            add_audit(
                "unmute",
                f"{member} unmuted by {interaction.user}",
                interaction.guild_id,
                interaction.user.id,
            )
            msg = (
                f"🔊 تم إلغاء كتم {member.mention}!" if lang == "ar"
                else f"🔊 Unmuted {member.mention}!"
            )
            await interaction.followup.send(msg, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ {e}", ephemeral=True)

    # ───────────────────────────────────────────────────────────────────
    #  NEW EMOJI COMMANDS
    # ───────────────────────────────────────────────────────────────────

    @app_commands.command(name="addemoji", description="😀 إضافة إيموجي للسيرفر / Add an emoji to the server")
    @app_commands.describe(
        name="اسم الإيموجي / Emoji name (without colons)",
        image="ملف صورة (png/gif) / Image file (png/gif)",
    )
    @app_commands.checks.has_permissions(manage_expressions=True)
    async def addemoji(
        self,
        interaction: discord.Interaction,
        name: str,
        image: discord.Attachment = None,
    ):
        """Upload a new custom emoji to the server. Attach an image or paste a URL."""
        await interaction.response.defer(ephemeral=True)
        lang = get_lang(interaction.guild_id)

        if image is None:
            msg = "⚠️ " + (
                "ارجوك ارفق صورة!" if lang == "ar" else "Please attach an image file!"
            )
            await interaction.followup.send(msg, ephemeral=True)
            return

        if not image.filename.lower().endswith((".png", ".gif", ".jpg", ".jpeg", ".webp")):
            msg = "⚠️ " + (
                "الصورة يجب أن تكون png أو gif أو jpg!" if lang == "ar"
                else "Image must be png, gif, or jpg!"
            )
            await interaction.followup.send(msg, ephemeral=True)
            return

        try:
            img_bytes = await image.read()
            emoji = await interaction.guild.create_custom_emoji(
                name=name, image=img_bytes,
                reason=f"Added by {interaction.user}",
            )
            add_audit(
                "addemoji",
                f"Emoji :{emoji.name}: added by {interaction.user}",
                interaction.guild_id,
                interaction.user.id,
            )
            msg = (
                f"😀 تمت إضافة الإيموجي {emoji}!" if lang == "ar"
                else f"😀 Added emoji {emoji}!"
            )
            await interaction.followup.send(msg, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ {e}", ephemeral=True)

    # ── removeemoji ────────────────────────────────────────────────────

    @app_commands.command(name="removeemoji", description="🗑️ حذف إيموجي من السيرفر / Remove an emoji from the server")
    @app_commands.describe(emoji="الإيموجي / Emoji name (without : :)")
    @app_commands.checks.has_permissions(manage_expressions=True)
    async def removeemoji(
        self, interaction: discord.Interaction, emoji: str
    ):
        """Delete a custom emoji from the server."""
        await interaction.response.defer(ephemeral=True)
        lang = get_lang(interaction.guild_id)
        try:
            # Look up emoji by name
            target = discord.utils.get(interaction.guild.emojis, name=emoji)
            if not target:
                msg = "❌ إيموجي غير موجود!" if lang == "ar" else "❌ Emoji not found!"
                return await interaction.followup.send(msg, ephemeral=True)
            await target.delete(reason=f"Removed by {interaction.user}")
            add_audit(
                "removeemoji",
                f"Emoji :{target.name}: removed by {interaction.user}",
                interaction.guild_id,
                interaction.user.id,
            )
            msg = (
                f"🗑️ تم حذف الإيموجي :{target.name}:!" if lang == "ar"
                else f"🗑️ Removed emoji :{target.name}:!"
            )
            await interaction.followup.send(msg, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ {e}", ephemeral=True)

    # ───────────────────────────────────────────────────────────────────
    #  NEW MASS-ROLE COMMAND
    # ───────────────────────────────────────────────────────────────────

    @app_commands.command(name="massrole", description="👥 إضافة/إزالة رول للكل / Add or remove a role for all members")
    @app_commands.describe(
        role="الرول / Role",
        action="الإجراء (add/remove) / Action",
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="➕ Add / إضافة", value="add"),
        app_commands.Choice(name="➖ Remove / إزالة", value="remove"),
    ])
    @app_commands.checks.has_permissions(manage_roles=True)
    async def massrole(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
        action: str,
    ):
        """Add or remove a role from every server member (respects role hierarchy)."""
        await interaction.response.defer(ephemeral=True)
        lang = get_lang(interaction.guild_id)

        if role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
            msg = "❌ " + (
                "لا يمكنك تعديل هذا الرول!" if lang == "ar" else "You can't modify this role!"
            )
            await interaction.followup.send(msg, ephemeral=True)
            return

        members = [m for m in interaction.guild.members if not m.bot]
        processed = 0
        errors = 0

        msg_start = (
            f"⏳ جاري {'إضافة' if action == 'add' else 'إزالة'} الرول لـ {len(members)} عضو…"
            if lang == "ar"
            else f"⏳ {'Adding' if action == 'add' else 'Removing'} role for {len(members)} members…"
        )
        await interaction.followup.send(msg_start, ephemeral=True)

        for m in members:
            try:
                if role not in m.roles and action == "add":
                    await m.add_roles(role, reason=f"Massrole by {interaction.user}")
                elif role in m.roles and action == "remove":
                    await m.remove_roles(role, reason=f"Massrole by {interaction.user}")
                processed += 1
            except Exception:
                errors += 1

        add_audit(
            "massrole",
            f"Mass-{action} {role} on {processed} members by {interaction.user} ({errors} errors)",
            interaction.guild_id,
            interaction.user.id,
        )
        result_msg = (
            f"👥 تم {'إضافة' if action == 'add' else 'إزالة'} الرول {role.mention} لـ {processed} عضو!"
            if lang == "ar"
            else f"👥 {'Added' if action == 'add' else 'Removed'} {role.mention} for {processed} members!"
        )
        if errors:
            result_msg += (
                f"\n⚠️ فشل {errors}" if lang == "ar" else f"\n⚠️ {errors} failed"
            )
        await interaction.followup.send(result_msg, ephemeral=True)

    # ───────────────────────────────────────────────────────────────────
    #  NEW BACKUP / RESTORE COMMANDS
    # ───────────────────────────────────────────────────────────────────

    @app_commands.command(name="backup", description="💾 إنشاء نسخة احتياطية للسيرفر / Create a server backup")
    @app_commands.checks.has_permissions(administrator=True)
    async def backup(self, interaction: discord.Interaction):
        """Backup server roles and channel structure (names, types, categories) to a JSON file."""
        await interaction.response.defer(ephemeral=True)
        lang = get_lang(interaction.guild_id)

        guild = interaction.guild

        # ── Serialize roles (excluding bot-managed and @everyone) ──
        roles_data = []
        for r in sorted(guild.roles, key=lambda x: x.position, reverse=True):
            if r.is_bot_managed() or r.is_default() or r.is_integration():
                continue
            roles_data.append({
                "name": r.name,
                "color": r.color.value,
                "permissions": r.permissions.value,
                "hoist": r.hoist,
                "mentionable": r.mentionable,
                "position": r.position,
            })

        # ── Serialize channels ──
        channels_data = []
        for c in guild.channels:
            entry = {
                "name": c.name,
                "type": str(c.type),
                "position": c.position,
                "category_id": c.category_id,
            }
            if isinstance(c, discord.TextChannel):
                entry["topic"] = c.topic or ""
                entry["slowmode_delay"] = c.slowmode_delay
                entry["nsfw"] = c.nsfw
            elif isinstance(c, discord.VoiceChannel):
                entry["bitrate"] = c.bitrate
                entry["user_limit"] = c.user_limit
            elif isinstance(c, discord.CategoryChannel):
                entry["nsfw"] = c.nsfw
            channels_data.append(entry)

        backup = {
            "guild_id": guild.id,
            "guild_name": guild.name,
            "created_at": time.time(),
            "roles": roles_data,
            "channels": channels_data,
        }

        timestamp = int(time.time())
        filename = f"backup_{guild.id}_{timestamp}.json"
        filepath = BACKUP_DIR / filename

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(backup, f, indent=2, ensure_ascii=False)

        add_audit(
            "backup",
            f"Backup created by {interaction.user} ({len(roles_data)} roles, {len(channels_data)} channels)",
            guild.id,
            interaction.user.id,
        )

        # Send the backup file as an attachment
        file_size = filepath.stat().st_size
        with open(filepath, "rb") as f:
            discord_file = discord.File(f, filename=filename)

        embed = discord.Embed(
            title="💾 " + ("نسخة احتياطية" if lang == "ar" else "Server Backup"),
            color=CONFIG.get("color", 5792082),
        )
        embed.add_field(
            name="🆔 " + ("المعرف" if lang == "ar" else "Backup ID"),
            value=f"`{timestamp}`",
            inline=False,
        )
        embed.add_field(
            name="🎭 " + ("الرولات" if lang == "ar" else "Roles"),
            value=str(len(roles_data)),
            inline=True,
        )
        embed.add_field(
            name="📁 " + ("القنوات" if lang == "ar" else "Channels"),
            value=str(len(channels_data)),
            inline=True,
        )
        embed.add_field(
            name="📦 " + ("الحجم" if lang == "ar" else "Size"),
            value=f"{file_size / 1024:.1f} KB",
            inline=True,
        )

        await interaction.followup.send(embed=embed, file=discord_file, ephemeral=True)

    # ── restore ────────────────────────────────────────────────────────

    @app_commands.command(name="restore", description="♻️ استعادة نسخة احتياطية / Restore from a backup")
    @app_commands.describe(backup_id="معرف النسخة (الرقم) / Backup ID (the timestamp number)")
    @app_commands.checks.has_permissions(administrator=True)
    async def restore(
        self, interaction: discord.Interaction, backup_id: str
    ):
        """Restore server roles and channels from a backup file. Creates new roles/channels without deleting existing ones."""
        await interaction.response.defer(ephemeral=True)
        lang = get_lang(interaction.guild_id)

        # Find the backup file
        pattern = f"backup_{interaction.guild_id}_{backup_id}.json"
        filepath = BACKUP_DIR / pattern

        if not filepath.exists():
            # Try finding by partial match
            matches = list(BACKUP_DIR.glob(f"backup_{interaction.guild_id}_*.json"))
            matches.sort(reverse=True)
            if matches:
                filepath = matches[0]
            else:
                msg = "❌ " + (
                    "ما فيه نسخة احتياطية بهذا المعرف!" if lang == "ar"
                    else "No backup found with that ID!"
                )
                await interaction.followup.send(msg, ephemeral=True)
                return

        with open(filepath, "r", encoding="utf-8") as f:
            backup = json.load(f)

        guild = interaction.guild
        created_roles = 0
        created_channels = 0

        await interaction.followup.send(
            "⏳ " + ("جاري استعادة النسخة…" if lang == "ar" else "Restoring backup…"),
            ephemeral=True,
        )

        # ── Restore roles ──
        existing_role_names = {r.name.lower(): r for r in guild.roles}
        for rd in backup.get("roles", []):
            if rd["name"].lower() in existing_role_names:
                continue  # Skip roles that already exist
            try:
                await guild.create_role(
                    name=rd["name"],
                    color=discord.Color(rd.get("color", 0)),
                    hoist=rd.get("hoist", False),
                    mentionable=rd.get("mentionable", False),
                    reason=f"Restored from backup by {interaction.user}",
                )
                created_roles += 1
            except Exception:
                pass

        # ── Restore channels ──
        existing_channel_names = {c.name.lower(): c for c in guild.channels}
        categories = {c.name.lower(): c for c in guild.categories}

        for cd in backup.get("channels", []):
            if cd["name"].lower() in existing_channel_names:
                continue
            try:
                parent = None
                if cd.get("category_id"):
                    # Try to find the category by position-matching
                    cat_name = None
                    for c in backup.get("channels", []):
                        if c["position"] == cd["category_id"] and c["type"] == "category":
                            cat_name = c["name"]
                            break
                    if cat_name and cat_name.lower() in categories:
                        parent = categories[cat_name.lower()]

                ctype = cd.get("type", "text")
                if ctype == "category":
                    new_c = await guild.create_category(
                        cd["name"],
                        reason=f"Restored from backup by {interaction.user}",
                    )
                    categories[cd["name"].lower()] = new_c
                    created_channels += 1
                elif ctype in ("text", "news", "forum"):
                    new_c = await guild.create_text_channel(
                        cd["name"],
                        topic=cd.get("topic", ""),
                        slowmode_delay=cd.get("slowmode_delay", 0),
                        nsfw=cd.get("nsfw", False),
                        category=parent,
                        reason=f"Restored from backup by {interaction.user}",
                    )
                    created_channels += 1
                elif ctype == "voice":
                    new_c = await guild.create_voice_channel(
                        cd["name"],
                        bitrate=min(cd.get("bitrate", 64000), guild.bitrate_limit),
                        user_limit=cd.get("user_limit", 0),
                        category=parent,
                        reason=f"Restored from backup by {interaction.user}",
                    )
                    created_channels += 1
            except Exception:
                pass

        add_audit(
            "restore",
            f"Backup restored by {interaction.user} ({created_roles} roles, {created_channels} channels)",
            guild.id,
            interaction.user.id,
        )
        msg = (
            f"♻️ تمت استعادة النسخة! تم إنشاء {created_roles} رول و {created_channels} قناة."
            if lang == "ar"
            else f"♻️ Backup restored! Created {created_roles} roles and {created_channels} channels."
        )
        await interaction.followup.send(msg, ephemeral=True)

    # ───────────────────────────────────────────────────────────────────
    #  NEW WELCOME / LEAVE / BOOST / AUTOROLE CONFIG COMMANDS
    # ───────────────────────────────────────────────────────────────────

    @app_commands.command(name="welcomeimage", description="🖼️ تعيين صورة خلفية الترحيب / Set welcome image background URL")
    @app_commands.describe(
        image_url="رابط الصورة / Image URL",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def welcomeimage(
        self,
        interaction: discord.Interaction,
        image_url: str,
    ):
        """Save a welcome image URL to the guild config."""
        await interaction.response.defer(ephemeral=True)
        lang = get_lang(interaction.guild_id)

        # Basic URL validation
        if not image_url.startswith(("http://", "https://")):
            msg = "⚠️ " + (
                "الرجاء إدخال رابط صورة صحيح!" if lang == "ar" else "Please enter a valid image URL!"
            )
            await interaction.followup.send(msg, ephemeral=True)
            return

        set_guild_config(interaction.guild_id, welcome_image=image_url)
        add_audit(
            "welcomeimage",
            f"Welcome image set by {interaction.user}",
            interaction.guild_id,
            interaction.user.id,
        )
        msg = (
            "🖼️ تم تعيين صورة الترحيب!" if lang == "ar"
            else "🖼️ Welcome image set!"
        )
        embed = discord.Embed(color=CONFIG.get("color", 5792082))
        embed.set_image(url=image_url)
        await interaction.followup.send(msg, embed=embed, ephemeral=True)

    # ── leavemessage ───────────────────────────────────────────────────

    @app_commands.command(name="leavemessage", description="👋 تعيين رسالة المغادرة / Set the leave message")
    @app_commands.describe(
        message="الرسالة (استخدم {member} لاسم العضو) / Message (use {member} for member name)",
        channel="روم المغادرة (اختياري) / Leave channel (optional)",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def leavemessage(
        self,
        interaction: discord.Interaction,
        message: str,
        channel: discord.TextChannel = None,
    ):
        """Set the leave message template and optional channel."""
        await interaction.response.defer(ephemeral=True)
        lang = get_lang(interaction.guild_id)

        data = {"leave_message": message}
        if channel:
            data["leave_channel"] = channel.id

        set_guild_config(interaction.guild_id, **data)
        add_audit(
            "leavemessage",
            f"Leave message set by {interaction.user}",
            interaction.guild_id,
            interaction.user.id,
        )
        msg = (
            "👋 تم تعيين رسالة المغادرة!" if lang == "ar"
            else "👋 Leave message set!"
        )
        extra = ""
        if channel:
            extra = (
                f"\n📢 الروم: {channel.mention}" if lang == "ar"
                else f"\n📢 Channel: {channel.mention}"
            )
        embed = discord.Embed(
            title="👋 " + ("رسالة المغادرة" if lang == "ar" else "Leave Message"),
            description=message,
            color=CONFIG.get("color", 5792082),
        )
        await interaction.followup.send(msg + extra, embed=embed, ephemeral=True)

    # ── autorole ───────────────────────────────────────────────────────

    @app_commands.command(name="autorole", description="🎭 تعيين رول تلقائي للأعضاء الجدد / Set auto-role for new members")
    @app_commands.describe(role="الرول / Role")
    @app_commands.checks.has_permissions(administrator=True)
    async def autorole(
        self, interaction: discord.Interaction, role: discord.Role
    ):
        """Set a role that is automatically assigned to every new member."""
        await interaction.response.defer(ephemeral=True)
        lang = get_lang(interaction.guild_id)

        if role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
            msg = "❌ " + (
                "لا يمكنك تعيين هذا الرول!" if lang == "ar" else "You can't set this role!"
            )
            await interaction.followup.send(msg, ephemeral=True)
            return

        set_guild_config(interaction.guild_id, autorole=role.id)
        add_audit(
            "autorole",
            f"Auto-role set to {role} by {interaction.user}",
            interaction.guild_id,
            interaction.user.id,
        )
        msg = (
            f"🎭 تم تعيين الرول التلقائي: {role.mention}!" if lang == "ar"
            else f"🎭 Auto-role set to {role.mention}!"
        )
        await interaction.followup.send(msg, ephemeral=True)

    # ── boostmessage ───────────────────────────────────────────────────

    @app_commands.command(name="boostmessage", description="💎 تعيين رسالة البوست / Set the boost message")
    @app_commands.describe(
        message="الرسالة (استخدم {member}) / Message (use {member})",
        channel="روم البوست (اختياري) / Boost channel (optional)",
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def boostmessage(
        self,
        interaction: discord.Interaction,
        message: str,
        channel: discord.TextChannel = None,
    ):
        """Set the boost message template and optional channel."""
        await interaction.response.defer(ephemeral=True)
        lang = get_lang(interaction.guild_id)

        data = {"boost_message": message}
        if channel:
            data["boost_channel"] = channel.id

        set_guild_config(interaction.guild_id, **data)
        add_audit(
            "boostmessage",
            f"Boost message set by {interaction.user}",
            interaction.guild_id,
            interaction.user.id,
        )
        msg = (
            "💎 تم تعيين رسالة البوست!" if lang == "ar"
            else "💎 Boost message set!"
        )
        extra = ""
        if channel:
            extra = (
                f"\n📢 الروم: {channel.mention}" if lang == "ar"
                else f"\n📢 Channel: {channel.mention}"
            )
        embed = discord.Embed(
            title="💎 " + ("رسالة البوست" if lang == "ar" else "Boost Message"),
            description=message,
            color=CONFIG.get("color", 5792082),
        )
        await interaction.followup.send(msg + extra, embed=embed, ephemeral=True)

    # ───────────────────────────────────────────────────────────────────
    #  NEW UTILITY COMMAND
    # ───────────────────────────────────────────────────────────────────

    @app_commands.command(name="countmembers", description="🔢 عدد الأعضاء حسب الرول / Count members by role")
    @app_commands.describe(role="الرول / Role")
    async def countmembers(
        self, interaction: discord.Interaction, role: discord.Role
    ):
        """Count how many server members have a specific role."""
        await interaction.response.defer(ephemeral=True)
        lang = get_lang(interaction.guild_id)

        count = len(role.members)
        bots = sum(1 for m in role.members if m.bot)
        humans = count - bots

        embed = discord.Embed(
            title=f"🔢 {role.name}",
            color=role.color if role.color.value else CONFIG.get("color", 5792082),
        )
        embed.add_field(
            name="👥 " + ("الإجمالي" if lang == "ar" else "Total"),
            value=str(count),
            inline=True,
        )
        embed.add_field(
            name="🧑 " + ("أعضاء" if lang == "ar" else "Members"),
            value=str(humans),
            inline=True,
        )
        embed.add_field(
            name="🤖 " + ("بوتات" if lang == "ar" else "Bots"),
            value=str(bots),
            inline=True,
        )
        embed.set_footer(
            text=f"🆔 {role.id}  |  {'الرول' if lang == 'ar' else 'Role'}"
        )

        await interaction.followup.send(embed=embed, ephemeral=True)


# ═══════════════════════════════════════════════════════════════════════
#  SETUP
# ═══════════════════════════════════════════════════════════════════════

async def setup(bot):
    await bot.add_cog(Admin(bot))
