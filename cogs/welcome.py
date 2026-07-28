import discord, math, io
from discord.ext import commands
from discord import app_commands
from pathlib import Path

from db import get_guild_config, set_guild_config, add_welcome, add_audit

# ── Constants ──────────────────────────────────────────────────────────
BLURPLE = 0x5865F2
RED = 0xED4245

# ── Welcome Image Generator ─────────────────────────────────────────────
try:
    from PIL import Image, ImageDraw, ImageFont
    WELCOME_HAS_PIL = True
except ImportError:
    WELCOME_HAS_PIL = False

BASE = Path(__file__).parent.parent
FONT_DIR = BASE / "data" / "fonts"


def get_fonts_welcome():
    fl, fm, fs = None, None, None
    dejavu = FONT_DIR / "DejaVuSans.ttf"
    arabic = FONT_DIR / "NotoNaskhArabic.ttf"
    if dejavu.exists():
        try:
            fl = ImageFont.truetype(str(dejavu), 44)
            fm = ImageFont.truetype(str(dejavu), 26)
            fs = ImageFont.truetype(str(dejavu), 18)
        except:
            pass
    if not fl and arabic.exists():
        try:
            fl = ImageFont.truetype(str(arabic), 44)
            fm = ImageFont.truetype(str(arabic), 26)
            fs = ImageFont.truetype(str(arabic), 18)
        except:
            pass
    if not fl:
        fl = fm = fs = ImageFont.load_default()
    return fl, fm, fs


def rr(draw, xy, r, **kw):
    """Rounded rectangle helper"""
    x1, y1, x2, y2 = xy
    draw.rounded_rectangle([x1, y1, x2, y2], radius=r, **kw)


def load_avatar_welcome(user, size=200):
    """Load a circular avatar for welcome card. Falls back to colored initial."""
    from PIL import ImageDraw as PID
    av = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = PID.Draw(av)
    try:
        if isinstance(user, int) or not hasattr(user, 'display_avatar'):
            raise ValueError
        import urllib.request
        url = user.display_avatar.with_size(size * 2).url
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; DiscordBot/1.0)'
        })
        with urllib.request.urlopen(req, timeout=5) as resp:
            buf = io.BytesIO(resp.read())
        src = Image.open(buf).convert("RGBA").resize((size, size), Image.LANCZOS)
        mask = Image.new("L", (size, size), 0)
        PID.Draw(mask).ellipse([(0, 0), (size, size)], fill=255)
        av.paste(src, (0, 0), mask)
    except:
        # Colored circle with initial
        name_str = "?"
        if hasattr(user, 'display_name') and user.display_name:
            name_str = user.display_name[0].upper()
        elif hasattr(user, 'name') and user.name:
            name_str = user.name[0].upper()
        hue = hash(name_str) % 360 / 360.0
        r = int(180 + 75 * math.sin(hue * 2 * math.pi))
        g = int(180 + 75 * math.sin((hue + 0.33) * 2 * math.pi))
        b = int(180 + 75 * math.sin((hue + 0.67) * 2 * math.pi))
        d.ellipse([(0, 0), (size, size)], fill=(r, g, b, 220))
        fl2, _, _ = get_fonts_welcome()
        bbx = d.textbbox((0, 0), name_str, font=fl2)
        tw = bbx[2] - bbx[0]
        th = bbx[3] - bbx[1]
        d.text((size//2 - tw//2, size//2 - th//2), name_str, fill=(255, 255, 255, 240), font=fl2)
    return av


def generate_welcome_image(member, guild, member_count):
    """
    Generate a welcome card: 800×300 px
    Dark premium design with guild branding, member avatar, welcome text.
    """
    if not WELCOME_HAS_PIL:
        return None
    fl, fm, fs = get_fonts_welcome()
    W, H = 800, 300
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Background: dark gradient with premium feel
    for y in range(H):
        t = y / H
        r_val = int(12 + 28 * (1 - t))
        g_val = int(12 + 24 * (1 - t))
        b_val = int(12 + 60 * (1 - t))
        d.line([(0, y), (W, y)], fill=(r_val, g_val, b_val, 255))

    # Decorative glassmorphism circles
    d.ellipse([(-60, -70), (120, 130)], fill=(88, 101, 242, 30))
    d.ellipse([(600, -50), (870, 160)], fill=(114, 137, 254, 22))
    d.ellipse([(720, 180), (940, 370)], fill=(88, 101, 242, 18))

    # Left accent bar
    d.rectangle([(0, 0), (5, H)], fill=(88, 101, 242, 255))
    for x in range(5, 12):
        d.rectangle([(x, 0), (x, H)], fill=(88, 101, 242, max(0, 60 - (x - 5) * 8)))

    # Avatar (large, centered left)
    av = load_avatar_welcome(member, 140)
    ax, ay = 30, H // 2 - 70
    cx, cy = ax + 70, ay + 70
    # Glow ring
    for r2 in range(78, 72, -1):
        alpha = int(80 * (1 - (78 - r2) / 6))
        d.ellipse([(cx - r2, cy - r2), (cx + r2, cy + r2)],
                  outline=(88, 101, 242, alpha), width=2)
    # Outer ring
    d.ellipse([(cx - 73, cy - 73), (cx + 73, cy + 73)],
              outline=(255, 255, 255, 80), width=3)
    img.paste(av, (ax, ay), av)

    # Welcome text (right side)
    x_text = 210

    # 👋 WELCOME
    welcome_label = "🎉  WELCOME"
    d.text((x_text, 45), welcome_label, fill=(88, 101, 242, 240), font=fm)

    # Member name
    mem_name = (member.display_name or "Member")[:16]
    d.text((x_text, 88), mem_name, fill=(255, 255, 255, 255), font=fl)

    # Subtitle
    sub = f"to {guild.name[:20]}"
    d.text((x_text, 145), sub, fill=(180, 180, 210, 200), font=fm)

    # Member count badge
    count_text = f"👤 Member #{member_count}"
    cb = d.textbbox((0, 0), count_text, font=fs)
    ctw = cb[2] - cb[0]
    badge_x = x_text - 8
    badge_w = ctw + 20
    rr(d, (badge_x, 190, badge_x + badge_w, 190 + 30), 15, fill=(88, 101, 242, 180))
    d.text((badge_x + 10, 194), count_text, fill=(255, 255, 255, 240), font=fs)

    # Decorative bottom line
    d.rectangle([(x_text, 242), (W - 30, 243)], fill=(88, 101, 242, 60))

    # Footer brand
    d.text((x_text, 258), "⚡  VØRTΞX SYSTEM", fill=(140, 140, 180, 120), font=fs)

    buf = io.BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    return buf


# ── Default Config ────────────────────────────────────────────────────
WELCOME_DEFAULTS = {
    "enabled": True,
    "channel": "welcome",
    "message": "🎉 | مرحباً {member}! نرحب بك في {server} ❤️",
    "leave_message": "👋 | {member} غادر السيرفر...",
    "auto_role": "Member",
    "dm_welcome": True,
}


class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # In-memory cache: guild_id -> config dict
        self._config_cache = {}

    # ── Config helpers ───────────────────────────────────────────────

    def _ensure_defaults(self, cfg: dict) -> dict:
        """Fill missing keys with defaults and persist if changed."""
        changed = False
        for k, v in WELCOME_DEFAULTS.items():
            if k not in cfg or cfg[k] is None:
                cfg[k] = v
                changed = True
        return cfg, changed

    def _get_cfg(self, guild_id: int) -> dict:
        """Get guild welcome config from DB (cached)."""
        if guild_id in self._config_cache:
            return self._config_cache[guild_id]
        cfg = get_guild_config(guild_id)
        cfg, changed = self._ensure_defaults(cfg)
        if changed:
            set_guild_config(guild_id, **cfg)
        self._config_cache[guild_id] = cfg
        return cfg

    def _save_cfg(self, guild_id: int):
        """Persist cached config to DB."""
        cfg = self._config_cache.get(guild_id)
        if cfg:
            set_guild_config(guild_id, **cfg)

    def _invalidate_cache(self, guild_id: int):
        self._config_cache.pop(guild_id, None)

    # ── Listeners ──────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_member_join(self, member):
        cfg = self._get_cfg(member.guild.id)
        if not cfg.get("enabled", True):
            return

        # Log welcome to DB
        try:
            add_welcome(member.guild.id, member.id)
            add_audit("member_join", f"{member} joined", member.guild.id, member.id)
        except Exception:
            pass

        # DM welcome
        if cfg.get("dm_welcome", True):
            try:
                rules_ch = None
                for ch in member.guild.text_channels:
                    if "قوانين" in ch.name or "rules" in ch.name:
                        rules_ch = ch
                        break
                embed = discord.Embed(
                    title=f"🎉 | مرحباً في {member.guild.name}!",
                    description=(
                        f"نرحب بك يا {member.name}! 🎊\n\n"
                        f"📖 | اقرأ القوانين في {rules_ch.mention if rules_ch else 'قناة القوانين'}\n"
                        f"💬 | شارك معنا في النقاشات\n"
                        f"🎫 | إذا احتجت مساعدة استخدم `/ticket setup`\n\n"
                        f"**VØRTΞX HOST**"
                    ),
                    color=BLURPLE,
                )
                if member.guild.icon:
                    embed.set_thumbnail(url=member.guild.icon.url)
                await member.send(embed=embed)
            except Exception:
                pass

        # Auto role
        role_name = cfg.get("auto_role")
        if role_name:
            role = discord.utils.get(member.guild.roles, name=role_name)
            if role:
                try:
                    await member.add_roles(role)
                except Exception:
                    pass

        # Channel welcome message
        channel = discord.utils.get(
            member.guild.text_channels,
            name=cfg.get("channel", "welcome"),
        )
        if channel:
            # Generate welcome image
            welcome_img = None
            try:
                welcome_img = generate_welcome_image(
                    member,
                    member.guild,
                    len(member.guild.members),
                )
            except Exception:
                pass

            msg = (
                cfg.get("message", "🎉 | مرحباً {member}!")
                .replace("{member}", member.mention)
                .replace("{server}", member.guild.name)
            )
            embed = discord.Embed(
                title="🎉 | عضو جديد!",
                description=msg,
                color=BLURPLE,
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.add_field(
                name="📅 | تاريخ الانضمام",
                value=member.joined_at.strftime("%Y-%m-%d") if member.joined_at else "غير معروف",
            )
            embed.add_field(
                name="👤 | العضو رقم",
                value=len(member.guild.members),
            )
            embed.set_footer(text=f"ID: {member.id}")

            if welcome_img:
                file = discord.File(welcome_img, filename="welcome.png")
                embed.set_image(url="attachment://welcome.png")
                await channel.send(embed=embed, file=file)
            else:
                await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        cfg = self._get_cfg(member.guild.id)
        if not cfg.get("enabled", True):
            return
        channel = discord.utils.get(
            member.guild.text_channels,
            name=cfg.get("channel", "welcome"),
        )
        if channel:
            msg = (
                cfg.get("leave_message", "👋 | {member} غادر السيرفر...")
                .replace("{member}", member.name)
                .replace("{server}", member.guild.name)
            )
            embed = discord.Embed(
                title="👋 | عضو غادر",
                description=msg,
                color=RED,
            )
            embed.set_thumbnail(
                url=member.display_avatar.url if member.display_avatar else None,
            )
            await channel.send(embed=embed)

    # ── Slash Commands ─────────────────────────────────────────────

    welcome_group = app_commands.Group(
        name="welcome",
        description="🎉 إعدادات الترحيب",
    )

    @welcome_group.command(
        name="status",
        description="🟢 عرض حالة الترحيب",
    )
    @app_commands.default_permissions(administrator=True)
    async def welcome_status(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        cfg = self._get_cfg(interaction.guild.id)

        embed = discord.Embed(
            title="🎉 | إعدادات الترحيب",
            color=BLURPLE,
        )
        embed.add_field(
            name="الحالة",
            value="🟢 شغال" if cfg.get("enabled", True) else "🔴 متوقف",
            inline=True,
        )
        embed.add_field(
            name="قناة الترحيب",
            value=f"#{cfg.get('channel', 'غير مضبوط')}",
            inline=True,
        )
        embed.add_field(
            name="الرتبة التلقائية",
            value=cfg.get("auto_role", "لا يوجد"),
            inline=True,
        )
        embed.add_field(
            name="رسالة الترحيب",
            value=f"```{cfg.get('message', 'لا يوجد')[:80]}```",
            inline=False,
        )
        embed.add_field(
            name="الرسالة الخاصة",
            value="✅ مفعلة" if cfg.get("dm_welcome", True) else "❌ معطلة",
            inline=True,
        )
        await interaction.followup.send(embed=embed)

    @welcome_group.command(
        name="channel",
        description="📢 ضبط قناة الترحيب",
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(channel="القناة")
    async def welcome_channel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
    ):
        await interaction.response.defer(ephemeral=True)
        cfg = self._get_cfg(interaction.guild.id)
        cfg["channel"] = channel.name
        self._save_cfg(interaction.guild.id)
        await interaction.followup.send(
            f"✅ | تم ضبط قناة الترحيب: {channel.mention}",
        )

    @welcome_group.command(
        name="message",
        description="✏️ ضبط رسالة الترحيب (استخدم {member} {server})",
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(message="الرسالة")
    async def welcome_message(
        self,
        interaction: discord.Interaction,
        message: str,
    ):
        await interaction.response.defer(ephemeral=True)
        cfg = self._get_cfg(interaction.guild.id)
        cfg["message"] = message
        self._save_cfg(interaction.guild.id)
        await interaction.followup.send(
            f"✅ | تم ضبط رسالة الترحيب\n```{message}```",
        )

    @welcome_group.command(
        name="leave-message",
        description="👋 ضبط رسالة المغادرة",
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(message="الرسالة")
    async def leave_message(
        self,
        interaction: discord.Interaction,
        message: str,
    ):
        await interaction.response.defer(ephemeral=True)
        cfg = self._get_cfg(interaction.guild.id)
        cfg["leave_message"] = message
        self._save_cfg(interaction.guild.id)
        await interaction.followup.send(
            f"✅ | تم ضبط رسالة المغادرة\n```{message}```",
        )

    @welcome_group.command(
        name="toggle",
        description="🔘 تشغيل/إيقاف الترحيب",
    )
    @app_commands.default_permissions(administrator=True)
    async def welcome_toggle(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        cfg = self._get_cfg(interaction.guild.id)
        cfg["enabled"] = not cfg.get("enabled", True)
        self._save_cfg(interaction.guild.id)
        state = "🟢 شغال" if cfg["enabled"] else "🔴 متوقف"
        await interaction.followup.send(f"✅ | تم {state} نظام الترحيب")

    @welcome_group.command(
        name="dm-toggle",
        description="💬 تشغيل/إيقاف الرسالة الخاصة",
    )
    @app_commands.default_permissions(administrator=True)
    async def welcome_dm_toggle(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        cfg = self._get_cfg(interaction.guild.id)
        cfg["dm_welcome"] = not cfg.get("dm_welcome", True)
        self._save_cfg(interaction.guild.id)
        state = "✅ مفعلة" if cfg["dm_welcome"] else "❌ معطلة"
        await interaction.followup.send(f"✅ | تم {state} الرسالة الخاصة للترحيب")

    @welcome_group.command(
        name="autorole",
        description="🎖️ ضبط الرتبة التلقائية للمستخدمين الجدد",
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(role="الرتبة (اسم أو none للإلغاء)")
    async def welcome_autorole(
        self,
        interaction: discord.Interaction,
        role: str,
    ):
        await interaction.response.defer(ephemeral=True)
        cfg = self._get_cfg(interaction.guild.id)
        if role.lower() == "none":
            cfg["auto_role"] = ""
            self._save_cfg(interaction.guild.id)
            await interaction.followup.send("✅ | تم إلغاء الرتبة التلقائية")
        else:
            cfg["auto_role"] = role
            self._save_cfg(interaction.guild.id)
            await interaction.followup.send(
                f"✅ | تم ضبط الرتبة التلقائية: `{role}`",
            )

    @welcome_group.command(
        name="preview",
        description="🖼️ معاينة صورة الترحيب",
    )
    @app_commands.default_permissions(administrator=True)
    async def welcome_preview(self, interaction: discord.Interaction):
        """Generate and send a welcome image preview (deferred for image work)."""
        await interaction.response.defer(ephemeral=True)
        if not WELCOME_HAS_PIL:
            await interaction.followup.send(
                "❌ | مكتبة Pillow غير مثبتة. لا يمكن إنشاء صورة الترحيب.",
            )
            return
        try:
            welcome_img = generate_welcome_image(
                interaction.user,
                interaction.guild,
                len(interaction.guild.members),
            )
            if welcome_img is None:
                await interaction.followup.send(
                    "❌ | فشل إنشاء صورة الترحيب.",
                )
                return
            file = discord.File(welcome_img, filename="welcome_preview.png")
            embed = discord.Embed(
                title="🖼️ | معاينة صورة الترحيب",
                description="هكذا ستبدو صورة الترحيب للأعضاء الجدد",
                color=BLURPLE,
            )
            embed.set_image(url="attachment://welcome_preview.png")
            await interaction.followup.send(embed=embed, file=file)
        except Exception as e:
            await interaction.followup.send(
                f"❌ | خطأ أثناء إنشاء الصورة: {e}",
            )


async def setup(bot):
    await bot.add_cog(Welcome(bot))
