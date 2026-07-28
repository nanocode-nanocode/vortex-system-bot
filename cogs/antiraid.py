import discord
from discord.ext import commands
from discord import app_commands
import datetime, time

from db import get_antiraid_config, set_antiraid_config, add_audit

EMBED_COLOR = 0x5865F2

DEFAULT_CONFIG = {
    "enabled": True,
    "raid_joins": 10,
    "raid_seconds": 10,
    "in_raid": False,
    "whitelist_roles": [],
    "admin_channel": None,
    "spam_msgs": 5,
    "spam_seconds": 3,
    "spam_action": "warn",
    "bad_words": [],
    "max_mentions": 5,
}


# ── Helpers ─────────────────────────────────────────────────────────────

def get_guild_config(guild_id: int) -> dict:
    """Return default-populated guild config from DB, creating if missing."""
    cfg = get_antiraid_config(guild_id)
    if not cfg:
        set_antiraid_config(guild_id, **DEFAULT_CONFIG)
        return dict(DEFAULT_CONFIG)
    # Fill in any missing keys with defaults
    full = dict(DEFAULT_CONFIG)
    full.update(cfg)
    return full


async def apply_raid_lock(guild: discord.Guild, lock: bool):
    """Lock or unlock the guild's system channel (or first text channel)."""
    target = guild.system_channel
    if target is None and guild.text_channels:
        target = guild.text_channels[0]
    if target is None:
        return None
    try:
        if lock:
            await target.set_slowmode_delay(21600)
            await target.set_permissions(guild.default_role, send_messages=False)
        else:
            await target.set_slowmode_delay(0)
            await target.set_permissions(guild.default_role, send_messages=None)
        return target
    except Exception:
        return None


async def send_to_admin_channel(guild: discord.Guild, embed: discord.Embed):
    """Send an embed to the configured admin channel, falling back to system channel."""
    cfg = get_guild_config(guild.id)
    channel = None
    if cfg.get("admin_channel"):
        channel = guild.get_channel(cfg["admin_channel"])
    if channel is None:
        channel = guild.system_channel
    if channel is None and guild.text_channels:
        channel = guild.text_channels[0]
    if channel is not None:
        await channel.send(embed=embed)


async def apply_spam_action(member: discord.Member, action: str, reason: str):
    """Execute the configured spam action against a member."""
    if action == "warn":
        try:
            await member.send(
                f"⚠️ **تحذير تلقائي** في **{member.guild.name}**\n"
                f"السبب: {reason}\n"
                f"الرجاء التوقف عن التكرار."
            )
        except Exception:
            pass
    elif action == "mute":
        try:
            duration = datetime.timedelta(minutes=10)
            await member.timeout(duration, reason=reason)
        except Exception:
            pass
    elif action == "kick":
        try:
            await member.kick(reason=reason)
        except Exception:
            pass


class AntiRaid(commands.Cog):
    """Anti-raid protection & auto-moderation system."""

    def __init__(self, bot):
        self.bot = bot
        # Track join times per guild: {guild_id: [timestamp, ...]}
        self.join_tracker: dict[int, list[float]] = {}
        # Track message timestamps per user: {user_id: [timestamp, ...]}
        self.msg_tracker: dict[int, list[float]] = {}

    # ── Listeners ───────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot:
            return

        cfg = get_guild_config(member.guild.id)
        if not cfg.get("enabled", True):
            return

        # Check whitelist
        if any(role.id in cfg.get("whitelist_roles", []) for role in member.roles):
            return

        gid = member.guild.id
        now = time.time()
        if gid not in self.join_tracker:
            self.join_tracker[gid] = []
        self.join_tracker[gid].append(now)

        # Prune entries older than raid_seconds
        raid_window = cfg.get("raid_seconds", 10)
        cutoff = now - raid_window
        self.join_tracker[gid] = [t for t in self.join_tracker[gid] if t > cutoff]

        # Check if raid threshold exceeded
        join_threshold = cfg.get("raid_joins", 10)
        recent_joins = len(self.join_tracker[gid])

        if recent_joins >= join_threshold and not cfg.get("in_raid", False):
            cfg["in_raid"] = True
            set_antiraid_config(gid, in_raid=True)

            channel = await apply_raid_lock(member.guild, lock=True)

            embed = discord.Embed(
                title="🚨 **رصد هجوم — RAID DETECTED**",
                description=(
                    f"تم رصد **{recent_joins}** أعضاء جدد خلال **{raid_window}** ثانية!\n\n"
                    f"**الحالة:** تم تفعيل وضع الحماية 🛡️\n"
                    f"**القناة المقفولة:** {channel.mention if channel else 'غير متوفرة'}"
                ),
                color=0xED4245,
                timestamp=datetime.datetime.now(),
            )
            embed.set_footer(text=f"VØRTΞX Anti-Raid • {member.guild.name}")
            await send_to_admin_channel(member.guild, embed)

            add_audit("raid_detected", f"{recent_joins} joins in {raid_window}s", gid)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.guild is None:
            return

        cfg = get_guild_config(message.guild.id)
        if not cfg.get("enabled", True):
            return

        # Check whitelist
        if any(role.id in cfg.get("whitelist_roles", []) for role in message.author.roles):
            return

        author = message.author
        now = time.time()
        actions_taken = []

        # ── Bad words filter ────────────────────────────────────────────
        bad_words = cfg.get("bad_words", [])
        if bad_words:
            content_lower = message.content.lower()
            for word in bad_words:
                if word.lower() in content_lower:
                    try:
                        await message.delete()
                    except Exception:
                        pass
                    actions_taken.append(f"كلمة ممنوعة: `{word}`")
                    embed = discord.Embed(
                        title="🛑 **كلمة ممنوعة — تم الحذف**",
                        description=(
                            f"**العضو:** {author.mention} (`{author.id}`)\n"
                            f"**القناة:** {message.channel.mention}\n"
                            f"**الكلمة:** `{word}`\n"
                            f"**الرسالة:** `{message.content[:200]}`"
                        ),
                        color=0xED4245,
                        timestamp=datetime.datetime.now(),
                    )
                    embed.set_footer(text="VØRTΞX Auto-Mod")
                    await send_to_admin_channel(message.guild, embed)
                    # Warn the user
                    try:
                        await author.send(
                            f"🛑 **تحذير: كلمة ممنوعة** في {message.guild.name}\n"
                            f"كلمتك `{word}` ممنوعة. تم حذف الرسالة تلقائياً."
                        )
                    except Exception:
                        pass
                    break  # one strike per message

        # ── Mass mention detection ──────────────────────────────────────
        max_mentions = cfg.get("max_mentions", 5)
        if len(message.mentions) > max_mentions:
            try:
                await message.delete()
            except Exception:
                pass
            actions_taken.append(
                f"منشن جماعي: {len(message.mentions)} منشن (الحد {max_mentions})"
            )
            embed = discord.Embed(
                title="📢 **منشن جماعي — تم الحذف**",
                description=(
                    f"**العضو:** {author.mention} (`{author.id}`)\n"
                    f"**القناة:** {message.channel.mention}\n"
                    f"**عدد المنشن:** {len(message.mentions)}\n"
                    f"**الرسالة:** `{message.content[:200]}`"
                ),
                color=0xED4245,
                timestamp=datetime.datetime.now(),
            )
            embed.set_footer(text="VØRTΞX Auto-Mod")
            await send_to_admin_channel(message.guild, embed)
            try:
                await author.send(
                    f"📢 **منشن جماعي ممنوع** في {message.guild.name}\n"
                    f"لقد أرسلت {len(message.mentions)} منشن (الحد الأقصى {max_mentions}). تم حذف الرسالة."
                )
            except Exception:
                pass

        # ── Spam detection ──────────────────────────────────────────────
        uid = author.id
        if uid not in self.msg_tracker:
            self.msg_tracker[uid] = []
        self.msg_tracker[uid].append(now)

        spam_window = cfg.get("spam_seconds", 3)
        cutoff = now - spam_window
        self.msg_tracker[uid] = [t for t in self.msg_tracker[uid] if t > cutoff]

        spam_threshold = cfg.get("spam_msgs", 5)
        if len(self.msg_tracker[uid]) >= spam_threshold:
            # Briefly mute to stop the spam
            try:
                duration = datetime.timedelta(minutes=1)
                await author.timeout(duration, reason="Spam detection (auto-mod)")
            except Exception:
                pass

            # Also purge recent messages from this user if possible
            try:
                def is_user(msg):
                    return msg.author.id == uid
                await message.channel.purge(limit=10, check=is_user)
            except Exception:
                pass

            # Apply the configured spam action
            spam_action = cfg.get("spam_action", "warn")
            await apply_spam_action(author, spam_action, "تجاوز حد السرعة في الإرسال (Spam)")

            actions_taken.append(
                f"سرعة إرسال: {len(self.msg_tracker[uid])} رسائل في {spam_window}ث"
            )

            embed = discord.Embed(
                title="⚡ **سرعة إرسال — Spam Detection**",
                description=(
                    f"**العضو:** {author.mention} (`{author.id}`)\n"
                    f"**القناة:** {message.channel.mention}\n"
                    f"**رسائل:** {len(self.msg_tracker[uid])} في {spam_window} ثانية\n"
                    f"**الإجراء:** `{spam_action}`"
                ),
                color=0xFEE75C,
                timestamp=datetime.datetime.now(),
            )
            embed.set_footer(text="VØRTΞX Auto-Mod")
            await send_to_admin_channel(message.guild, embed)

            # Reset counter so they don't get spammed further
            self.msg_tracker[uid] = []

    # ── Anti-Raid Command Group ─────────────────────────────────────────

    antiraid = app_commands.Group(
        name="antiraid", description="🛡️ إعدادات الحماية من الهجمات"
    )

    @antiraid.command(name="config", description="ضبط عتبات اكتشاف الهجوم")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        joins="عدد الأعضاء قبل تفعيل الحماية",
        seconds="الفترة الزمنية بالثواني",
    )
    async def antiraid_config(
        self,
        interaction: discord.Interaction,
        joins: int,
        seconds: int,
    ):
        await interaction.response.defer()
        if joins < 1 or seconds < 1:
            return await interaction.followup.send(
                "❌ | القيم يجب أن تكون أكبر من 0", ephemeral=True
            )
        set_antiraid_config(interaction.guild.id, raid_joins=joins, raid_seconds=seconds)

        add_audit("antiraid_config", f"joins={joins}, seconds={seconds}", interaction.guild.id, interaction.user.id)

        embed = discord.Embed(
            title="🛡️ **تم ضبط إعدادات الحماية**",
            description=(
                f"**عدد الأعضاء:** {joins}\n"
                f"**الفترة الزمنية:** {seconds} ثانية\n"
                f"يعني إذا دخل **{joins} أعضاء** خلال **{seconds} ثانية** يتم تفعيل الحماية."
            ),
            color=EMBED_COLOR,
        )
        await interaction.followup.send(embed=embed)

    @antiraid.command(name="toggle", description="تفعيل/تعطيل نظام الحماية")
    @app_commands.default_permissions(administrator=True)
    async def antiraid_toggle(self, interaction: discord.Interaction):
        await interaction.response.defer()
        cfg = get_guild_config(interaction.guild.id)
        new_enabled = not cfg.get("enabled", True)
        set_antiraid_config(interaction.guild.id, enabled=new_enabled)

        add_audit("antiraid_toggle", f"enabled={new_enabled}", interaction.guild.id, interaction.user.id)

        status = "✅ **مفعل**" if new_enabled else "❌ **معطل**"
        embed = discord.Embed(
            title="🛡️ **حالة الحماية**",
            description=f"النظام الآن: {status}",
            color=EMBED_COLOR,
        )
        await interaction.followup.send(embed=embed)

    @antiraid.command(name="status", description="عرض إعدادات الحماية الحالية")
    @app_commands.default_permissions(administrator=True)
    async def antiraid_status(self, interaction: discord.Interaction):
        await interaction.response.defer()
        cfg = get_guild_config(interaction.guild.id)
        in_raid = "🚨 **في وضع الهجوم**" if cfg.get("in_raid") else "✅ **وضع طبيعي**"
        enabled = "✅ مفعل" if cfg.get("enabled", True) else "❌ معطل"

        whitelist_roles = []
        for rid in cfg.get("whitelist_roles", []):
            role = interaction.guild.get_role(rid)
            if role:
                whitelist_roles.append(role.mention)
        whitelist_str = ", ".join(whitelist_roles) if whitelist_roles else "لا يوجد"

        admin_ch = interaction.guild.get_channel(cfg.get("admin_channel", 0))
        admin_ch_str = admin_ch.mention if admin_ch else "غير مضبوط (يستخدم الافتراضي)"

        embed = discord.Embed(
            title="🛡️ **إعدادات Anti-Raid**",
            color=EMBED_COLOR,
            timestamp=datetime.datetime.now(),
        )
        embed.add_field(name="الحالة", value=enabled, inline=True)
        embed.add_field(name="وضع الهجوم", value=in_raid, inline=True)
        embed.add_field(name="", value="", inline=False)
        embed.add_field(
            name="عتبة الهجوم",
            value=f"**{cfg['raid_joins']}** أعضاء خلال **{cfg['raid_seconds']}** ثانية",
            inline=False,
        )
        embed.add_field(name="رول الاستثناء", value=whitelist_str, inline=False)
        embed.add_field(name="قناة الإدارة", value=admin_ch_str, inline=False)
        embed.set_footer(text="VØRTΞX Anti-Raid")

        await interaction.followup.send(embed=embed)

    # ── Whitelist sub-group ────────────────────────────────────────────

    whitelist = app_commands.Group(
        name="whitelist",
        description="☑️ إدارة رولات الاستثناء",
        parent=antiraid,
    )

    @whitelist.command(name="add", description="إضافة رول للاستثناء من الحماية")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(role="الرول المراد استثناؤه")
    async def whitelist_add(
        self, interaction: discord.Interaction, role: discord.Role
    ):
        await interaction.response.defer()
        cfg = get_guild_config(interaction.guild.id)
        whitelist_roles = cfg.get("whitelist_roles", [])
        if role.id in whitelist_roles:
            return await interaction.followup.send(
                f"⚠️ | الرول {role.mention} موجود مسبقاً في القائمة", ephemeral=True
            )
        whitelist_roles.append(role.id)
        set_antiraid_config(interaction.guild.id, whitelist_roles=whitelist_roles)

        add_audit("whitelist_add", f"role={role.id} ({role.name})", interaction.guild.id, interaction.user.id)

        embed = discord.Embed(
            title="☑️ **تمت الإضافة**",
            description=f"تمت إضافة {role.mention} إلى قائمة الاستثناء بنجاح.",
            color=EMBED_COLOR,
        )
        await interaction.followup.send(embed=embed)

    @whitelist.command(name="remove", description="إزالة رول من قائمة الاستثناء")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(role="الرول المراد إزالته")
    async def whitelist_remove(
        self, interaction: discord.Interaction, role: discord.Role
    ):
        await interaction.response.defer()
        cfg = get_guild_config(interaction.guild.id)
        whitelist_roles = cfg.get("whitelist_roles", [])
        if role.id not in whitelist_roles:
            return await interaction.followup.send(
                f"⚠️ | الرول {role.mention} ليس في القائمة", ephemeral=True
            )
        whitelist_roles.remove(role.id)
        set_antiraid_config(interaction.guild.id, whitelist_roles=whitelist_roles)

        add_audit("whitelist_remove", f"role={role.id} ({role.name})", interaction.guild.id, interaction.user.id)

        embed = discord.Embed(
            title="☑️ **تمت الإزالة**",
            description=f"تمت إزالة {role.mention} من قائمة الاستثناء بنجاح.",
            color=EMBED_COLOR,
        )
        await interaction.followup.send(embed=embed)

    @whitelist.command(name="list", description="عرض رولات الاستثناء")
    @app_commands.default_permissions(administrator=True)
    async def whitelist_list(self, interaction: discord.Interaction):
        await interaction.response.defer()
        cfg = get_guild_config(interaction.guild.id)
        whitelist_roles = cfg.get("whitelist_roles", [])
        if not whitelist_roles:
            return await interaction.followup.send(
                "📭 | لا يوجد رولات مستثناة حالياً", ephemeral=True
            )

        mentions = []
        for rid in whitelist_roles:
            role = interaction.guild.get_role(rid)
            mentions.append(role.mention if role else f"`{rid}` (محذوف)")

        embed = discord.Embed(
            title="☑️ **رولات الاستثناء**",
            description="\n".join(f"• {r}" for r in mentions),
            color=EMBED_COLOR,
        )
        await interaction.followup.send(embed=embed)

    # ── Auto-Mod Command Group ─────────────────────────────────────────

    automod = app_commands.Group(
        name="automod", description="🤖 إعدادات التحكم التلقائي"
    )

    @automod.command(name="spam", description="ضبط إعدادات كشف السبام")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        msgs="عدد الرسائل المسموح بها",
        seconds="الفترة الزمنية بالثواني",
        action="الإجراء (warn/mute/kick)",
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="⚠️ تحذير (warn)", value="warn"),
        app_commands.Choice(name="🔇 كتم (mute)", value="mute"),
        app_commands.Choice(name="👢 طرد (kick)", value="kick"),
    ])
    async def automod_spam(
        self,
        interaction: discord.Interaction,
        msgs: int,
        seconds: int,
        action: app_commands.Choice[str],
    ):
        await interaction.response.defer()
        if msgs < 1 or seconds < 1:
            return await interaction.followup.send(
                "❌ | القيم يجب أن تكون أكبر من 0", ephemeral=True
            )
        set_antiraid_config(interaction.guild.id, spam_msgs=msgs, spam_seconds=seconds, spam_action=action.value)

        add_audit("automod_spam", f"msgs={msgs}, seconds={seconds}, action={action.value}", interaction.guild.id, interaction.user.id)

        embed = discord.Embed(
            title="⚡ **تم ضبط إعدادات السبام**",
            description=(
                f"**عدد الرسائل:** {msgs}\n"
                f"**الفترة:** {seconds} ثانية\n"
                f"**الإجراء:** `{action.value}`"
            ),
            color=EMBED_COLOR,
        )
        await interaction.followup.send(embed=embed)

    badwords = app_commands.Group(
        name="badwords",
        description="🔤 إدارة الكلمات الممنوعة",
        parent=automod,
    )

    @badwords.command(name="add", description="إضافة كلمة ممنوعة")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(word="الكلمة المراد منعها")
    async def badwords_add(self, interaction: discord.Interaction, word: str):
        await interaction.response.defer()
        cfg = get_guild_config(interaction.guild.id)
        bad_words = cfg.get("bad_words", [])
        word_lower = word.lower().strip()
        if not word_lower:
            return await interaction.followup.send(
                "❌ | الكلمة لا يمكن أن تكون فارغة", ephemeral=True
            )
        if word_lower in bad_words:
            return await interaction.followup.send(
                f"⚠️ | الكلمة `{word_lower}` موجودة مسبقاً", ephemeral=True
            )
        bad_words.append(word_lower)
        set_antiraid_config(interaction.guild.id, bad_words=bad_words)

        add_audit("badwords_add", f"word={word_lower}", interaction.guild.id, interaction.user.id)

        embed = discord.Embed(
            title="🔤 **تمت الإضافة**",
            description=f"تمت إضافة `{word_lower}` إلى قائمة الكلمات الممنوعة.",
            color=EMBED_COLOR,
        )
        await interaction.followup.send(embed=embed)

    @badwords.command(name="remove", description="إزالة كلمة من الممنوعة")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(word="الكلمة المراد إزالتها")
    async def badwords_remove(self, interaction: discord.Interaction, word: str):
        await interaction.response.defer()
        cfg = get_guild_config(interaction.guild.id)
        bad_words = cfg.get("bad_words", [])
        word_lower = word.lower().strip()
        if word_lower not in bad_words:
            return await interaction.followup.send(
                f"⚠️ | الكلمة `{word_lower}` ليست في القائمة", ephemeral=True
            )
        bad_words.remove(word_lower)
        set_antiraid_config(interaction.guild.id, bad_words=bad_words)

        add_audit("badwords_remove", f"word={word_lower}", interaction.guild.id, interaction.user.id)

        embed = discord.Embed(
            title="🔤 **تمت الإزالة**",
            description=f"تمت إزالة `{word_lower}` من قائمة الكلمات الممنوعة.",
            color=EMBED_COLOR,
        )
        await interaction.followup.send(embed=embed)

    @badwords.command(name="list", description="عرض الكلمات الممنوعة")
    @app_commands.default_permissions(administrator=True)
    async def badwords_list(self, interaction: discord.Interaction):
        await interaction.response.defer()
        cfg = get_guild_config(interaction.guild.id)
        bad_words = cfg.get("bad_words", [])
        if not bad_words:
            return await interaction.followup.send(
                "📭 | لا يوجد كلمات ممنوعة حالياً", ephemeral=True
            )
        embed = discord.Embed(
            title="🔤 **الكلمات الممنوعة**",
            description="\n".join(f"• `{w}`" for w in bad_words),
            color=EMBED_COLOR,
        )
        await interaction.followup.send(embed=embed)

    # ── Mentions setting (under automod) ───────────────────────────────

    @automod.command(name="mentions", description="ضبط الحد الأقصى للمنشن قبل الحذف")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(max="الحد الأقصى للمنشن في الرسالة الواحدة")
    async def automod_mentions(self, interaction: discord.Interaction, max: int):
        await interaction.response.defer()
        if max < 1:
            return await interaction.followup.send(
                "❌ | الحد يجب أن يكون 1 على الأقل", ephemeral=True
            )
        set_antiraid_config(interaction.guild.id, max_mentions=max)

        add_audit("automod_mentions", f"max_mentions={max}", interaction.guild.id, interaction.user.id)

        embed = discord.Embed(
            title="📢 **تم ضبط حد المنشن**",
            description=f"الحد الأقصى للمنشن أصبح: **{max}** منشن لكل رسالة",
            color=EMBED_COLOR,
        )
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(AntiRaid(bot))
