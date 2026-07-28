import discord
from discord.ext import commands
from discord import app_commands
import json, random, datetime, math, io, os
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

BASE = Path(__file__).parent.parent
with open(BASE / "config.json") as f:
    CONFIG = json.load(f)

LEVEL_FILE = BASE / "data" / "levels.json"
LVL_CONFIG_FILE = BASE / "data" / "level_config.json"
FONT_DIR = BASE / "data" / "fonts"

# ── Data helpers ─────────────────────────────────────────────────────

def load_levels():
    return json.loads(LEVEL_FILE.read_text()) if LEVEL_FILE.exists() else {}

def save_levels(data):
    LEVEL_FILE.parent.mkdir(exist_ok=True)
    LEVEL_FILE.write_text(json.dumps(data, indent=2))

def load_lvl_config():
    return json.loads(LVL_CONFIG_FILE.read_text()) if LVL_CONFIG_FILE.exists() else {}

def save_lvl_config(data):
    LVL_CONFIG_FILE.parent.mkdir(exist_ok=True)
    LVL_CONFIG_FILE.write_text(json.dumps(data, indent=2))

def xp_for_level(level):
    return 50 * level * (level + 1)

def level_from_xp(xp):
    return int((math.sqrt(1 + 8 * xp / 50) - 1) / 2) if xp > 0 else 0

def progress_to_next(xp):
    lvl = level_from_xp(xp)
    cur = xp_for_level(lvl)
    nxt = xp_for_level(lvl + 1) - cur
    return lvl, xp - cur, nxt

def get_user_data(guild_id, user_id):
    data = load_levels()
    gid, uid = str(guild_id), str(user_id)
    data.setdefault(gid, {})
    data[gid].setdefault(uid, {"xp": 0, "last_msg": 0, "level": 0})
    return data, gid, uid

# ── Fonts ────────────────────────────────────────────────────────────

def get_fonts():
    candidates = [
        (FONT_DIR / "DejaVuSans.ttf", 50, 32, 22),
        (FONT_DIR / "NotoNaskhArabic.ttf", 50, 32, 22),
        (Path("/data/data/com.termux/files/usr/share/fonts/TTF/DejaVuSans.ttf"), 50, 32, 22),
        (Path("/system/fonts/NotoNaskhArabic-Regular.ttf"), 50, 32, 22),
    ]
    for fp, ls, ms, ss in candidates:
        try:
            if fp and fp.exists():
                return (ImageFont.truetype(str(fp), ls), ImageFont.truetype(str(fp), ms), ImageFont.truetype(str(fp), ss))
        except:
            continue
    fl = ImageFont.load_default()
    return fl, fl, fl

# ── Avatar loader ───────────────────────────────────────────────────

def load_avatar(user, size=120):
    """Return circular RGBA avatar from user object. Falls back to colored initial."""
    av = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(av)
    try:
        import urllib.request
        url = user.display_avatar.with_size(size * 2).url
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; DiscordBot/1.0)'
        })
        with urllib.request.urlopen(req, timeout=5) as resp:
            buf = io.BytesIO(resp.read())
        src = Image.open(buf).convert("RGBA").resize((size, size), Image.LANCZOS)
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).ellipse([(0, 0), (size, size)], fill=255)
        av.paste(src, (0, 0), mask)
    except:
        # Colored circle with initial letter
        d.ellipse([(0, 0), (size, size)], fill=(88, 101, 242, 255))
        init = (user.display_name or "?")[0].upper()
        try:
            fl, _, _ = get_fonts()
        except:
            fl = ImageFont.load_default()
        bb = d.textbbox((0, 0), init, font=fl)
        d.text(((size - (bb[2] - bb[0])) // 2, (size - (bb[3] - bb[1])) // 2), init, fill=(255, 255, 255, 200), font=fl)
    return av

# ── Rounded-rect helper ──────────────────────────────────────────────

def rr(d, xy, r, **kw):
    d.rounded_rectangle(xy, radius=r, **kw)

# ══════════════════════════════════════════════════════════════════════
#  RANK CARD  — 900×300  (dark premium, glassmorphism accents)
# ══════════════════════════════════════════════════════════════════════

def generate_rank_card(user, guild, xp, level, xp_progress, xp_needed, rank=None):
    if not HAS_PIL:
        return None
    fl, fm, fs = get_fonts()
    W, H = 900, 300
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # background gradient
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=(int(15 + 35 * (1 - t)), int(15 + 30 * (1 - t)), int(35 + 65 * (1 - t)), 255))

    # glass circles
    d.ellipse([(-80, -80), (100, 140)], fill=(88, 101, 242, 35))
    d.ellipse([(650, -40), (950, 160)], fill=(88, 101, 242, 28))
    d.ellipse([(780, 160), (990, 350)], fill=(114, 137, 254, 22))

    # left accent bar
    d.rectangle([(0, 0), (6, H)], fill=(88, 101, 242, 255))
    for x in range(6, 14):
        d.rectangle([(x, 0), (x, H)], fill=(88, 101, 242, max(0, 55 - (x - 6) * 7)))

    # avatar
    av = load_avatar(user, 130)
    ax, ay = 34, H // 2 - 65
    cx, cy = ax + 65, ay + 65
    for r2 in range(72, 66, -1):
        d.ellipse([(cx - r2, cy - r2), (cx + r2, cy + r2)], outline=(88, 101, 242, int(70 * (1 - (72 - r2) / 6))), width=2)
    d.ellipse([(cx - 68, cy - 68), (cx + 68, cy + 68)], outline=(255, 255, 255, 90), width=3)
    img.paste(av, (ax, ay), av)
    xo = ax + 130 + 32

    # username
    nm = (user.display_name or "Unknown")[:18]
    d.text((xo, 28), nm, fill=(255, 255, 255, 255), font=fl)

    # level badge
    lt = f"LEVEL {level}"
    lb = d.textbbox((0, 0), lt, font=fm)
    lw, lh = lb[2] - lb[0], lb[3] - lb[1]
    rr(d, (xo - 8, 84, xo + lw + 18, 84 + lh + 8), 10, fill=(88, 101, 242, 220))
    d.text((xo + 5, 84 + 2), lt, fill=(255, 255, 255, 255), font=fm)

    # rank
    if rank is not None:
        rt = f"#{rank}"
        rb = d.textbbox((0, 0), rt, font=fl)
        rx = W - (rb[2] - rb[0]) - 22
        d.text((rx, 28), rt, fill=(255, 215, 0, 255), font=fl)
        d.rectangle([(rx, 78), (W - 22, 80)], fill=(255, 215, 0, 100))

    # xp bar
    bx, by = xo, 153
    bw, bh = W - bx - 35, 26
    pct = min(xp_progress / xp_needed, 1) if xp_needed > 0 else 0
    rr(d, (bx, by, bx + bw, by + bh), 13, fill=(40, 40, 70, 255))
    if pct > 0:
        fw = int(bw * pct)
        for x in range(bx, bx + fw):
            rt = (x - bx) / fw
            r2, g2, b2 = int(88 + 26 * rt), int(101 + 36 * rt), int(242 - 30 * rt)
            # clip to rounded rect shape
            for y in range(by, by + bh):
                if x - bx < 13 and y < by + 13:
                    if ((x - bx - 13)**2 + (y - (by + 13))**2)**0.5 > 13:
                        continue
                if x - bx > bw - 13 and y < by + 13:
                    if ((x - bx - (bw - 13))**2 + (y - (by + 13))**2)**0.5 > 13:
                        continue
                if x - bx < 13 and y > by + bh - 13:
                    if ((x - bx - 13)**2 + (y - (by + bh - 13))**2)**0.5 > 13:
                        continue
                if x - bx > bw - 13 and y > by + bh - 13:
                    if ((x - bx - (bw - 13))**2 + (y - (by + bh - 13))**2)**0.5 > 13:
                        continue
                d.point((x, y), fill=(r2, g2, b2, 255))
    # xp label on bar
    xt = f"{xp_progress:,} / {xp_needed:,} XP"
    xb = d.textbbox((0, 0), xt, font=fs)
    xtw = xb[2] - xb[0]
    d.text((bx + bw // 2 - xtw // 2, by + 2), xt, fill=(255, 255, 255, 240), font=fs)
    # total below
    d.text((bx, by + bh + 8), f"Total: {xp:,} XP", fill=(180, 180, 210, 180), font=fs)

    # footer
    gn = (guild.name[:18] if guild else "Server")
    d.text((bx, H - 26), gn, fill=(140, 140, 180, 130), font=fs)
    f2 = "VØRTΞX SYSTEM"
    fb = d.textbbox((0, 0), f2, font=fs)
    d.text((W - (fb[2] - fb[0]) - 18, H - 26), f2, fill=(140, 140, 180, 130), font=fs)

    buf = io.BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    return buf

# ══════════════════════════════════════════════════════════════════════
#  LEVEL-UP  — 800×400  (gold celebration)
# ══════════════════════════════════════════════════════════════════════

def generate_level_up(user, guild, old_level, new_level, total_xp, xp_progress, xp_needed):
    if not HAS_PIL:
        return None
    fl, fm, fs = get_fonts()
    W, H = 800, 400
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=(int(18 + 38 * (1 - t)), int(12 + 28 * (1 - t)), int(42 + 78 * (1 - t)), 255))

    d.ellipse([(-100, -100), (160, 160)], fill=(88, 101, 242, 30))
    d.ellipse([(600, -50), (880, 200)], fill=(114, 137, 254, 25))
    d.ellipse([(620, 240), (920, 460)], fill=(88, 101, 242, 22))

    title = "LEVEL UP!"
    tb = d.textbbox((0, 0), title, font=fl)
    tw = tb[2] - tb[0]
    for ox, oy in [(-2, -2), (-2, 2), (2, -2), (2, 2), (0, 0)]:
        d.text((W // 2 - tw // 2 + ox, 22 + oy), title, fill=(88, 101, 242, 50) if ox or oy else (255, 215, 0, 255), font=fl)
    d.text((W // 2 - tw // 2, 22), title, fill=(255, 215, 0, 255), font=fl)
    d.rectangle([(W // 2 - tw // 2 - 10, 78), (W // 2 + tw // 2 + 10, 80)], fill=(255, 215, 0, 90))

    # avatar
    av = load_avatar(user, 110)
    ax, ay = W // 2 - 55, 98
    cx, cy = ax + 55, ay + 55
    for r2 in range(62, 55, -1):
        d.ellipse([(cx - r2, cy - r2), (cx + r2, cy + r2)], outline=(88, 101, 242, int(80 * (1 - (62 - r2) / 7))), width=2)
    d.ellipse([(cx - 58, cy - 58), (cx + 58, cy + 58)], outline=(255, 255, 255, 70), width=3)
    img.paste(av, (ax, ay), av)

    # old → new
    ot = str(old_level)
    ob = d.textbbox((0, 0), ot, font=fl)
    ow = ob[2] - ob[0]
    ox2 = W // 2 - 55 - ow - 30
    rr(d, (ox2 - 14, cy - 22, ox2 + ow + 14, cy + 22), 10, fill=(60, 60, 100, 180))
    d.text((ox2, cy - 17), ot, fill=(180, 180, 200, 200), font=fl)

    arrow = "▶"
    ab = d.textbbox((0, 0), arrow, font=fm)
    d.text((W // 2 - (ab[2] - ab[0]) // 2, cy - 14), arrow, fill=(255, 215, 0, 200), font=fm)

    nt = str(new_level)
    nb = d.textbbox((0, 0), nt, font=fl)
    nw = nb[2] - nb[0]
    nx2 = W // 2 + 55 + 20
    rr(d, (nx2 - 14, cy - 22, nx2 + nw + 14, cy + 22), 10, fill=(88, 101, 242, 200))
    d.text((nx2, cy - 17), nt, fill=(255, 255, 255, 255), font=fl)

    d.text((W // 2 - 18, cy + 28), "LEVEL", fill=(180, 180, 210, 120), font=fs)

    # xp bar
    bx, by = 90, 310
    bw, bh = W - 180, 22
    pct = min(xp_progress / xp_needed, 1) if xp_needed > 0 else 0
    rr(d, (bx, by, bx + bw, by + bh), 11, fill=(40, 40, 70, 200))
    if pct > 0:
        rr(d, (bx, by, bx + int(bw * pct), by + bh), 11, fill=(88, 101, 242, 220))
    xt = f"{xp_progress:,} / {xp_needed:,} XP  |  Total: {total_xp:,} XP"
    xb2 = d.textbbox((0, 0), xt, font=fs)
    d.text((bx + bw // 2 - (xb2[2] - xb2[0]) // 2, by + 1), xt, fill=(255, 255, 255, 240), font=fs)

    d.text((16, H - 26), f"{guild.name[:20]} • VØRTΞX SYSTEM", fill=(140, 140, 180, 100), font=fs)

    buf = io.BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    return buf

# ══════════════════════════════════════════════════════════════════════
#  LEADERBOARD  — 780 × dynamic  (creative modern)
# ══════════════════════════════════════════════════════════════════════

def generate_leaderboard(users_data, guild, page, total_pages, guild_icon=None):
    """780 px wide leaderboard as a full image."""
    if not HAS_PIL:
        return None
    fl, fm, fs = get_fonts()
    ROW = 78
    PAD = 18
    HEADER = 90
    FOOTER = 44
    W = 780
    N = len(users_data)
    H = HEADER + N * ROW + FOOTER

    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # ── background ──
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=(int(14 + 32 * (1 - t)), int(14 + 27 * (1 - t)), int(36 + 60 * (1 - t)), 255))

    # decorative glass
    d.ellipse([(-50, -50), (150, 150)], fill=(88, 101, 242, 28))
    d.ellipse([(W - 180, 20), (W + 50, 220)], fill=(114, 137, 254, 22))

    # ── header bar ──
    # dark header bg
    rr(d, (10, 10, W - 10, HEADER - 4), 12, fill=(30, 30, 60, 200))
    # accent line
    d.rectangle([(10, HEADER - 6), (W - 10, HEADER - 4)], fill=(88, 101, 242, 180))

    # guild icon (tiny) or server initial
    if guild_icon:
        try:
            gi = guild_icon.resize((36, 36), Image.LANCZOS)
            gmask = Image.new("L", (36, 36), 0)
            ImageDraw.Draw(gmask).ellipse([(0, 0), (36, 36)], fill=255)
            gio = Image.new("RGBA", (36, 36), (0, 0, 0, 0))
            gio.paste(gi, (0, 0), gmask)
            img.paste(gio, (24, 27), gio)
        except:
            pass
    else:
        # guild initial
        init = (guild.name or "S")[0].upper() if guild else "S"
        rr(d, (24, 27, 60, 63), 18, fill=(88, 101, 242, 200))
        ib = d.textbbox((0, 0), init, font=fs)
        d.text((42 - (ib[2] - ib[0]) // 2, 36), init, fill=(255, 255, 255, 230), font=fs)

    # title
    title = f"LEADERBOARD — {guild.name[:20]}"
    tb = d.textbbox((0, 0), title, font=fm)
    d.text((74, 30), title, fill=(255, 215, 0, 255), font=fm)

    # page indicator
    pg = f"P.{page}/{total_pages}"
    pb = d.textbbox((0, 0), pg, font=fs)
    d.text((W - (pb[2] - pb[0]) - 22, 34), pg, fill=(180, 180, 210, 130), font=fs)

    # ── column headers ──
    ch_y = HEADER - 22
    col_positions = [
        (PAD + 10, "#", 50),         # rank
        (95, "MEMBER", 360),          # member
        (475, "LEVEL", 70),           # level
        (565, "XP", 180),             # xp
    ]
    for cx, ct, cw in col_positions:
        d.text((cx, ch_y), ct, fill=(180, 180, 210, 150), font=fs)

    # separator under headers
    d.line([(PAD, HEADER), (W - PAD, HEADER)], fill=(100, 100, 140, 60))

    # ── rows ──
    medals = ["🥇", "🥈", "🥉"]
    mcolors = [(255, 215, 0, 255), (192, 192, 192, 255), (180, 120, 50, 255)]

    for idx, (uid, udata) in enumerate(users_data):
        row_y = HEADER + idx * ROW
        rank_num = idx + 1

        # alternating row tint
        if idx % 2 == 0:
            d.rectangle([(PAD, row_y), (W - PAD, row_y + ROW - 4)], fill=(255, 255, 255, 6))

        # rank badge
        if rank_num <= 3:
            d.text((PAD + 8, row_y + 18), medals[idx], font=fl)
        else:
            rt2 = f"#{rank_num}"
            rbb = d.textbbox((0, 0), rt2, font=fs)
            rw = rbb[2] - rbb[0]
            d.text((PAD + 24 - rw // 2, row_y + 22), rt2, fill=(180, 180, 210, 140), font=fs)

        # avatar (small)
        av_size = 46
        try:
            uid_int = int(uid)
            m = guild.get_member(uid_int) if isinstance(guild, discord.Guild) else None
            # Try to load real avatar
            if m:
                av2 = load_avatar(m, av_size)
            else:
                raise ValueError
        except:
            # Fallback: colored initial
            av2 = Image.new("RGBA", (av_size, av_size), (0, 0, 0, 0))
            ad = ImageDraw.Draw(av2)
            hue = (hash(uid) % 360) / 360.0 if uid else 0.5
            r3 = int(180 + 75 * math.sin(hue * 2 * math.pi))
            g3 = int(180 + 75 * math.sin((hue + 0.33) * 2 * math.pi))
            b3 = int(180 + 75 * math.sin((hue + 0.67) * 2 * math.pi))
            ad.ellipse([(0, 0), (av_size, av_size)], fill=(r3, g3, b3, 220))
            ad.text((av_size // 4, av_size // 4 - 2), "?", fill=(255, 255, 255, 200), font=fs)

        mask2 = Image.new("L", (av_size, av_size), 0)
        ImageDraw.Draw(mask2).ellipse([(0, 0), (av_size, av_size)], fill=255)
        av_out = Image.new("RGBA", (av_size, av_size), (0, 0, 0, 0))
        av_out.paste(av2, (0, 0), mask2)
        img.paste(av_out, (72, row_y + 12), av_out)
        # avatar ring
        d.ellipse([(72, row_y + 12), (72 + av_size, row_y + 12 + av_size)], outline=(255, 255, 255, 40), width=2)

        # name
        uname = f"User#{uid[:4]}"
        try:
            if isinstance(guild, discord.Guild):
                mem = guild.get_member(int(uid))
                if mem:
                    uname = mem.display_name[:18]
        except:
            pass
        d.text((142, row_y + 18), uname, fill=(230, 230, 240, 240), font=fs)

        # level
        lvl = level_from_xp(udata["xp"])
        lvl_str = str(lvl)
        lb2 = d.textbbox((0, 0), lvl_str, font=fm)
        # level badge pill
        lvl_bx = 475
        rr(d, (lvl_bx - 6, row_y + 14, lvl_bx + (lb2[2] - lb2[0]) + 12, row_y + 14 + (lb2[3] - lb2[1]) + 8),
           8, fill=(88, 101, 242, 200))
        d.text((lvl_bx, row_y + 18), lvl_str, fill=(255, 255, 255, 255), font=fm)

        # xp + mini bar
        xp_val = udata["xp"]
        xp_str = f"{xp_val:,}"
        xp_bx = 565
        d.text((xp_bx, row_y + 10), xp_str, fill=(200, 200, 220, 200), font=fs)

        _, xp_pg, xp_nd = progress_to_next(xp_val)
        pct2 = min(xp_pg / xp_nd, 1) if xp_nd > 0 else 0
        mbx, mby = xp_bx, row_y + 36
        mbw, mbh = 170, 10
        rr(d, (mbx, mby, mbx + mbw, mby + mbh), 5, fill=(40, 40, 70, 200))
        if pct2 > 0:
            rr(d, (mbx, mby, mbx + int(mbw * pct2), mby + mbh), 5, fill=(88, 101, 242, 220))

        # row separator
        if idx < N - 1:
            d.line([(PAD + 10, row_y + ROW - 2), (W - PAD - 10, row_y + ROW - 2)], fill=(100, 100, 140, 30))

    # ── footer ──
    rr(d, (10, H - FOOTER + 4, W - 10, H - 8), 10, fill=(25, 25, 50, 160))
    ft = f"Page {page}/{total_pages}    ✦    VØRTΞX SYSTEM"
    fb2 = d.textbbox((0, 0), ft, font=fs)
    d.text((W // 2 - (fb2[2] - fb2[0]) // 2, H - 32), ft, fill=(160, 160, 190, 150), font=fs)

    buf = io.BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    return buf

# ══════════════════════════════════════════════════════════════════════
#  COG
# ══════════════════════════════════════════════════════════════════════

class Levels(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cooldowns = {}

    def get_guild_config(self, gid):
        data = load_lvl_config()
        g = str(gid)
        data.setdefault(g, {
            "enabled": True, "xp_per_msg": (10, 25), "cooldown": 45,
            "announce_channel": None, "level_up_channel": None, "role_rewards": {},
        })
        save_lvl_config(data)
        return data[g]

    # ── Listener ─────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or message.guild is None:
            return
        cfg = self.get_guild_config(message.guild.id)
        if not cfg.get("enabled", True):
            return
        uid = message.author.id
        now = message.created_at.timestamp()
        cd = cfg.get("cooldown", 45)
        if now - self.cooldowns.get(uid, 0) < cd:
            return
        self.cooldowns[uid] = now

        xpr = cfg.get("xp_per_msg", (10, 25))
        gain = random.randint(xpr[0], xpr[1])
        data, gid, us = get_user_data(message.guild.id, uid)
        old = level_from_xp(data[gid][us]["xp"])
        data[gid][us]["xp"] += gain
        data[gid][us]["last_msg"] = now
        new = level_from_xp(data[gid][us]["xp"])
        data[gid][us]["level"] = new
        save_levels(data)
        if new > old:
            await self.handle_level_up(message, old, new, data[gid][us]["xp"], cfg)

    async def handle_level_up(self, message, old, new, total, cfg):
        gc = load_lvl_config().get(str(message.guild.id), {})
        rr_cfg = gc.get("role_rewards", {})
        added = None
        rn = rr_cfg.get(str(new))
        if rn:
            r = discord.utils.get(message.guild.roles, name=rn)
            if r:
                try:
                    await message.author.add_roles(r)
                    added = r
                except:
                    pass
        lvl, prog, need = progress_to_next(total)
        f = None
        try:
            b = generate_level_up(message.author, message.guild, old, new, total, prog, need)
            if b:
                f = discord.File(b, filename="levelup.png")
        except Exception as e:
            print(f"⚠️ lvl-up img: {e}")

        ch = None
        lc = cfg.get("level_up_channel")
        if lc:
            ch = message.guild.get_channel(lc)
        if not ch:
            ac = cfg.get("announce_channel")
            if ac:
                ch = message.guild.get_channel(ac)
        if not ch:
            ch = message.channel

        rm = added.mention if added else ""
        if f:
            await ch.send(content=f"🎉 **{message.author.mention} — LEVEL UP!** → **Level {new}** {rm}", file=f)
        else:
            e = discord.Embed(title=f"🎉 Level {new}!", description=f"{rm}", color=0xFFD700)
            e.add_field(name="✨ XP", value=f"**{total:,}**", inline=True)
            await ch.send(content=message.author.mention, embed=e)

    # ── /rank ────────────────────────────────────────────────────────

    @app_commands.command(name="rank", description="🏆 عرض رتبتك كصورة احترافية")
    @app_commands.describe(member="العضو (اختياري)")
    async def rank_slash(self, interaction: discord.Interaction, member: discord.Member = None):
        await interaction.response.defer()
        m = member or interaction.user
        data, gid, us = get_user_data(interaction.guild.id, m.id)
        xp = data[gid][us]["xp"]
        lvl, prog, need = progress_to_next(xp)
        all_u = sorted(data[gid].items(), key=lambda x: x[1]["xp"], reverse=True)
        rank = next((i + 1 for i, (u, _) in enumerate(all_u) if int(u) == m.id), None)
        try:
            b = generate_rank_card(m, interaction.guild, xp, lvl, prog, need, rank)
            if b:
                await interaction.followup.send(file=discord.File(b, filename="rank.png"))
                return
        except Exception as e:
            print(f"⚠️ rank img: {e}")
        e = discord.Embed(title=f"🏆 {m.display_name}", color=CONFIG.get("color", 0x5865F2))
        e.add_field(name="🏅 Level", value=str(lvl), inline=True)
        e.add_field(name="✨ XP", value=f"{xp:,}", inline=True)
        e.add_field(name="📊 Rank", value=f"#{rank or '-'}", inline=True)
        await interaction.followup.send(embed=e)

    # ── /leaderboard ─────────────────────────────────────────────────

    @app_commands.command(name="leaderboard", description="🏆 لوحة الشرف كصورة ديناميكية")
    @app_commands.describe(page="رقم الصفحة")
    async def leaderboard_slash(self, interaction: discord.Interaction, page: int = 1):
        await interaction.response.defer()
        data, gid, _ = get_user_data(interaction.guild.id, 0)
        sorted_u = sorted(data[gid].items(), key=lambda x: x[1]["xp"], reverse=True)
        filtered = [(k, v) for k, v in sorted_u if k != "0"]
        if not filtered:
            return await interaction.followup.send("❌ | لا يوجد أعضاء بعد!")

        per_page = 8
        total = max(1, (len(filtered) + per_page - 1) // per_page)
        page = max(1, min(page, total))
        start = (page - 1) * per_page
        end = start + per_page
        page_data = filtered[start:end]

        # Pre-load guild icon
        guild_icon = None
        try:
            if interaction.guild.icon:
                buf = io.BytesIO()
                interaction.guild.icon.with_size(64).save(buf)
                buf.seek(0)
                guild_icon = Image.open(buf).convert("RGBA")
        except:
            pass

        try:
            b = generate_leaderboard(page_data, interaction.guild, page, total, guild_icon)
            if b:
                await interaction.followup.send(file=discord.File(b, filename="leaderboard.png"))
                return
        except Exception as e:
            print(f"⚠️ lb img: {e}")
            import traceback
            traceback.print_exc()

        # fallback embed
        medals = ["🥇", "🥈", "🥉"]
        emb = discord.Embed(title=f"🏆 Leaderboard — {interaction.guild.name}", color=0xFFD700)
        for i, (uid, ud) in enumerate(page_data, start=start + 1):
            mem = interaction.guild.get_member(int(uid))
            nm = mem.display_name if mem else f"#{uid[:4]}"
            lv = level_from_xp(ud["xp"])
            m = medals[i - 1] if i <= 3 else f"{i}."
            emb.add_field(name=f"{m} {nm}", value=f"Lv.{lv} • {ud['xp']:,} XP", inline=False)
        await interaction.followup.send(embed=emb)

    # ── /level ───────────────────────────────────────────────────────

    @app_commands.command(name="level", description="⚙️ إعدادات المستويات")
    @app_commands.default_permissions(administrator=True)
    async def level_settings(self, interaction: discord.Interaction):
        cfg = self.get_guild_config(interaction.guild.id)
        gc = load_lvl_config().get(str(interaction.guild.id), {})
        e = discord.Embed(
            title="⚙️ | إعدادات المستويات",
            description=f"**الحالة:** {'🟢 شغال' if cfg.get('enabled', True) else '🔴 متوقف'}",
            color=CONFIG.get("color", 0x5865F2),
        )
        e.add_field(name="XP لكل رسالة", value=str(cfg.get("xp_per_msg", (10, 25))), inline=True)
        e.add_field(name="الكولدون", value=f"{cfg.get('cooldown', 45)} ث", inline=True)
        lc = cfg.get("level_up_channel")
        if lc:
            ch = interaction.guild.get_channel(lc)
            e.add_field(name="🎉 قناة الرفع", value=ch.mention if ch else "غير مضبوطة", inline=True)
        else:
            ac = cfg.get("announce_channel")
            e.add_field(name="📢 الإعلانات", value=f"<#{ac}>" if ac else "🗣️ نفس القناة", inline=True)
        rw = gc.get("role_rewards", {})
        if rw:
            e.add_field(name="🎖️ جوائز", value="\n".join([f"Lv.{l} → `{r}`" for l, r in sorted(rw.items(), key=lambda x: int(x[0]))[:5]]), inline=False)
        else:
            e.add_field(name="🎖️ جوائز", value="لا يوجد", inline=False)
        await interaction.response.send_message(embed=e)

    # ── /level-config ────────────────────────────────────────────────

    @app_commands.command(name="level-config", description="⚙️ ضبط إعدادات المستويات")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(setting="الإعداد", value="القيمة")
    async def level_config(self, interaction: discord.Interaction, setting: str, value: str = None):
        cfg = self.get_guild_config(interaction.guild.id)
        gc = load_lvl_config()
        g = str(interaction.guild.id)
        gc.setdefault(g, cfg)

        async def ok(msg):
            await interaction.response.send_message(f"✅ | {msg}")
        async def err(msg):
            await interaction.response.send_message(f"❌ | {msg}", ephemeral=True)

        if setting in ("enabled", "toggle"):
            cfg["enabled"] = not cfg.get("enabled", True)
            gc[g]["enabled"] = cfg["enabled"]
            save_lvl_config(gc)
            await ok(f"تم {'🟢 تشغيل' if cfg['enabled'] else '🔴 إيقاف'} النظام")
        elif setting in ("xp-range", "xp"):
            try:
                lo, hi = map(int, value.split("-"))
                cfg["xp_per_msg"] = (lo, hi)
                gc[g]["xp_per_msg"] = (lo, hi)
                save_lvl_config(gc)
                await ok(f"XP: {lo}-{hi} لكل رسالة")
            except:
                await err("استخدم: `5-15`")
        elif setting == "cooldown":
            try:
                s = int(value)
                cfg["cooldown"] = s
                gc[g]["cooldown"] = s
                save_lvl_config(gc)
                await ok(f"كولدون: {s} ث")
            except:
                await err("استخدم رقم: `45`")
        elif setting in ("announce-channel", "channel"):
            try:
                cid = int(value.strip("<#>"))
                cfg["announce_channel"] = cid
                gc[g]["announce_channel"] = cid
                save_lvl_config(gc)
                await ok(f"قناة إعلانات: <#{cid}>")
            except:
                await err("منشن القناة: `#channel`")
        elif setting in ("level-up-channel", "lvlchannel"):
            try:
                cid = int(value.strip("<#>"))
                cfg["level_up_channel"] = cid
                gc[g]["level_up_channel"] = cid
                save_lvl_config(gc)
                await ok(f"قناة رفع: <#{cid}>")
            except:
                await err("منشن القناة: `#channel`")
        elif setting in ("add-role", "reward"):
            try:
                parts = value.split()
                lv = int(parts[0])
                rn = " ".join(parts[1:])
                gc[g].setdefault("role_rewards", {})
                gc[g]["role_rewards"][str(lv)] = rn
                save_lvl_config(gc)
                await ok(f"جائزة Lv.{lv} → `{rn}`")
            except:
                await err("استخدم: `5 VIP`")
        else:
            await err("خيارات: enabled, xp, cooldown, channel, lvlchannel, reward")

    @level_config.autocomplete("setting")
    async def lc_auto(self, interaction: discord.Interaction, cur: str):
        opts = [
            ("🟢 تشغيل/إيقاف", "enabled"),
            ("✨ XP لكل رسالة", "xp"),
            ("⏱️ الكولدون (ث)", "cooldown"),
            ("📢 قناة الإعلانات", "announce-channel"),
            ("🎉 قناة الرفع", "level-up-channel"),
            ("🎖️ جائزة مستوى", "add-role"),
        ]
        return [app_commands.Choice(name=n, value=v) for n, v in opts if cur.lower() in n.lower() or cur.lower() in v.lower()]

async def setup(bot):
    await bot.add_cog(Levels(bot))
