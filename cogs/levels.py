import discord
from discord.ext import commands
from discord import app_commands
import json, random, math, io, time
from pathlib import Path

from db import (
    get_user_level, set_user_level,
    get_leaderboard, get_rank,
    add_audit,
)

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

BASE = Path(__file__).parent.parent
with open(BASE / "config.json") as f:
    CONFIG = json.load(f)

LVL_CONFIG_FILE = BASE / "data" / "level_config.json"
FONT_DIR = BASE / "data" / "fonts"

# ── Data helpers ─────────────────────────────────────────────────────

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

    # background gradient (dark premium)
    for y in range(H):
        t = y / H
        r_i = int(15 + 35 * (1 - t))
        g_i = int(15 + 30 * (1 - t))
        b_i = int(35 + 65 * (1 - t))
        d.line([(0, y), (W, y)], fill=(r_i, g_i, b_i, 255))

    # glassmorphism decorative circles
    d.ellipse([(-80, -80), (100, 140)], fill=(88, 101, 242, 35))
    d.ellipse([(650, -40), (950, 160)], fill=(88, 101, 242, 28))
    d.ellipse([(780, 160), (990, 350)], fill=(114, 137, 254, 22))

    # left accent bar
    d.rectangle([(0, 0), (6, H)], fill=(88, 101, 242, 255))
    for x in range(6, 14):
        d.rectangle([(x, 0), (x, H)], fill=(88, 101, 242, max(0, 55 - (x - 6) * 7)))

    # avatar with glow ring
    av = load_avatar(user, 130)
    ax, ay = 34, H // 2 - 65
    cx, cy = ax + 65, ay + 65
    for r2 in range(72, 66, -1):
        alpha = int(70 * (1 - (72 - r2) / 6))
        d.ellipse([(cx - r2, cy - r2), (cx + r2, cy + r2)], outline=(88, 101, 242, alpha), width=2)
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
            for y in range(by, by + bh):
                # clip to rounded rect shape
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
#  LEVEL-UP  — 800×400  (avatar left, level text right, dark gradient)
# ══════════════════════════════════════════════════════════════════════

def generate_level_up(user, guild, old_level, new_level, total_xp, xp_progress, xp_needed):
    if not HAS_PIL:
        return None
    fl, fm, fs = get_fonts()
    W, H = 800, 400
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # glowing gradient background — dark with purple/blue hues
    for y in range(H):
        t = y / H
        r_i = int(10 + 28 * (1 - t) + 10 * math.sin(y * 0.02))
        g_i = int(8 + 22 * (1 - t) + 8 * math.sin(y * 0.015 + 1))
        b_i = int(30 + 60 * (1 - t) + 20 * math.sin(y * 0.01 + 2))
        d.line([(0, y), (W, y)], fill=(min(r_i, 255), min(g_i, 255), min(b_i, 255), 255))

    # glowing orbs for atmospheric effect
    d.ellipse([(-120, -100), (80, 180)], fill=(88, 101, 242, 45))
    d.ellipse([(550, -80), (850, 150)], fill=(114, 137, 254, 40))
    d.ellipse([(600, 250), (950, 500)], fill=(88, 101, 242, 30))
    # extra glow near level text
    d.ellipse([(450, 60), (750, 260)], fill=(255, 215, 0, 12))

    # ── LEFT SIDE: Avatar ──
    av_size = 140
    av = load_avatar(user, av_size)
    ax, ay = 50, H // 2 - av_size // 2 - 10
    cx, cy = ax + av_size // 2, ay + av_size // 2

    # avatar glow rings (multi-layer)
    for r2 in range(80, 70, -2):
        alpha = int(60 * (1 - (80 - r2) / 10))
        d.ellipse([(cx - r2, cy - r2), (cx + r2, cy + r2)], outline=(88, 101, 242, alpha), width=2)
    # outer white ring
    d.ellipse([(cx - 74, cy - 74), (cx + 74, cy + 74)], outline=(255, 255, 255, 80), width=3)
    # gold accent ring
    d.ellipse([(cx - 72, cy - 72), (cx + 72, cy + 72)], outline=(255, 215, 0, 40), width=1)
    img.paste(av, (ax, ay), av)

    # username below avatar
    un = (user.display_name or "Unknown")[:14]
    ub = d.textbbox((0, 0), un, font=fm)
    uw = ub[2] - ub[0]
    d.text((cx - uw // 2, ay + av_size + 12), un, fill=(200, 200, 220, 200), font=fm)

    # ── RIGHT SIDE: Level Up Text ──
    title = "LEVEL UP!"
    # bold glow effect — multiple passes with shadow
    tb = d.textbbox((0, 0), title, font=fl)
    tw, th = tb[2] - tb[0], tb[3] - tb[1]
    tx, ty = 380, 80

    # outer glow (blur by drawing multiple semi-transparent layers)
    for ox in range(-8, 9, 2):
        for oy in range(-8, 9, 2):
            d.text((tx + ox, ty + oy), title, fill=(255, 215, 0, 35), font=fl)
    # shadow
    for ox, oy in [(-3, -3), (-3, 3), (3, -3), (3, 3)]:
        d.text((tx + ox, ty + oy), title, fill=(0, 0, 0, 120), font=fl)
    # main text
    d.text((tx, ty), title, fill=(255, 215, 0, 255), font=fl)

    # gold underline
    d.rectangle([(tx, ty + th + 4), (tx + tw, ty + th + 6)], fill=(255, 215, 0, 120))

    # ── Large level number ──
    level_str = str(new_level)
    # Find a bigger font by scaling up
    try:
        try:
            f_big = ImageFont.truetype(str(FONT_DIR / "DejaVuSans.ttf"), 72)
        except:
            f_big = ImageFont.truetype(str(FONT_DIR / "NotoNaskhArabic.ttf"), 72)
    except:
        f_big = fl

    lb = d.textbbox((0, 0), level_str, font=f_big)
    lw, lh = lb[2] - lb[0], lb[3] - lb[1]
    lx, ly = tx, ty + th + 20

    # level number glow
    for ox in range(-10, 11, 2):
        for oy in range(-10, 11, 2):
            d.text((lx + ox, ly + oy), level_str, fill=(114, 137, 254, 40), font=f_big)
    # shadow
    for ox, oy in [(-4, -4), (4, -4)]:
        d.text((lx + ox, ly + oy), level_str, fill=(0, 0, 0, 100), font=f_big)
    # main level number
    d.text((lx, ly), level_str, fill=(255, 255, 255, 255), font=f_big)

    # "LEVEL" label under the number
    ll = "LEVEL"
    llb = d.textbbox((0, 0), ll, font=fm)
    d.text((lx + lw // 2 - (llb[2] - llb[0]) // 2, ly + lh + 4), ll, fill=(180, 180, 210, 140), font=fm)

    # Old level indicator
    old_str = f"From Level {old_level}"
    d.textbbox((0, 0), old_str, font=fs)
    d.text((tx, ly + lh + 32), old_str, fill=(140, 140, 180, 120), font=fs)

    # ── XP Bar (bottom) ──
    bx, by = 60, 340
    bw, bh = W - 120, 20
    pct = min(xp_progress / xp_needed, 1) if xp_needed > 0 else 0
    # bar background
    rr(d, (bx, by, bx + bw, by + bh), 10, fill=(30, 30, 60, 200))
    # bar fill with gradient
    if pct > 0:
        fw = int(bw * pct)
        for x in range(bx, bx + fw):
            t = (x - bx) / fw
            r2 = int(88 + 26 * t)
            g2 = int(101 + 36 * t)
            b2 = int(242 - 30 * t)
            for y in range(by, by + bh):
                # rounded rect clip
                if x - bx < 10 and y < by + 10 and ((x - bx - 10)**2 + (y - (by + 10))**2)**0.5 > 10:
                    continue
                if x - bx > bw - 10 and y < by + 10 and ((x - bx - (bw - 10))**2 + (y - (by + 10))**2)**0.5 > 10:
                    continue
                if x - bx < 10 and y > by + bh - 10 and ((x - bx - 10)**2 + (y - (by + bh - 10))**2)**0.5 > 10:
                    continue
                if x - bx > bw - 10 and y > by + bh - 10 and ((x - bx - (bw - 10))**2 + (y - (by + bh - 10))**2)**0.5 > 10:
                    continue
                d.point((x, y), fill=(r2, g2, b2, 255))

    # xp label
    xt = f"{xp_progress:,} / {xp_needed:,} XP  |  Total: {total_xp:,} XP"
    xb = d.textbbox((0, 0), xt, font=fs)
    xtw = xb[2] - xb[0]
    d.text((bx + bw // 2 - xtw // 2, by + 1), xt, fill=(255, 255, 255, 230), font=fs)

    # footer
    d.text((16, H - 22), f"{guild.name[:20]} • VØRTΞX SYSTEM", fill=(140, 140, 180, 100), font=fs)

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
    rr(d, (10, 10, W - 10, HEADER - 4), 12, fill=(30, 30, 60, 200))
    d.rectangle([(10, HEADER - 6), (W - 10, HEADER - 4)], fill=(88, 101, 242, 180))

    # guild icon
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
        init = (guild.name or "S")[0].upper() if guild else "S"
        rr(d, (24, 27, 60, 63), 18, fill=(88, 101, 242, 200))
        ib = d.textbbox((0, 0), init, font=fs)
        d.text((42 - (ib[2] - ib[0]) // 2, 36), init, fill=(255, 255, 255, 230), font=fs)

    # title
    title = f"LEADERBOARD — {guild.name[:20]}"
    d.textbbox((0, 0), title, font=fm)
    d.text((74, 30), title, fill=(255, 215, 0, 255), font=fm)

    # page indicator
    pg = f"P.{page}/{total_pages}"
    pb = d.textbbox((0, 0), pg, font=fs)
    d.text((W - (pb[2] - pb[0]) - 22, 34), pg, fill=(180, 180, 210, 130), font=fs)

    # ── column headers ──
    ch_y = HEADER - 22
    col_positions = [
        (PAD + 10, "#", 50),
        (95, "MEMBER", 360),
        (475, "LEVEL", 70),
        (565, "XP", 180),
    ]
    for cx, ct, cw in col_positions:
        d.text((cx, ch_y), ct, fill=(180, 180, 210, 150), font=fs)

    d.line([(PAD, HEADER), (W - PAD, HEADER)], fill=(100, 100, 140, 60))

    # ── rows ──
    medals = ["🥇", "🥈", "🥉"]

    for idx, (uid, udata) in enumerate(users_data):
        row_y = HEADER + idx * ROW
        rank_num = idx + 1

        if idx % 2 == 0:
            d.rectangle([(PAD, row_y), (W - PAD, row_y + ROW - 4)], fill=(255, 255, 255, 6))

        if rank_num <= 3:
            d.text((PAD + 8, row_y + 18), medals[idx], font=fl)
        else:
            rt2 = f"#{rank_num}"
            rbb = d.textbbox((0, 0), rt2, font=fs)
            rw = rbb[2] - rbb[0]
            d.text((PAD + 24 - rw // 2, row_y + 22), rt2, fill=(180, 180, 210, 140), font=fs)

        # avatar
        av_size = 46
        try:
            uid_int = int(uid)
            m = guild.get_member(uid_int) if isinstance(guild, discord.Guild) else None
            if m:
                av2 = load_avatar(m, av_size)
            else:
                raise ValueError
        except:
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
#  XP STATISTICS CARD  — 700×350
# ══════════════════════════════════════════════════════════════════════

def generate_xpstats_card(user, guild, xp, level, xp_progress, xp_needed, rank, weekly_xp, total_msgs):
    if not HAS_PIL:
        return None
    fl, fm, fs = get_fonts()
    W, H = 700, 350
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # gradient background
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=(int(12 + 30 * (1 - t)), int(12 + 25 * (1 - t)), int(30 + 55 * (1 - t)), 255))

    # glass orbs
    d.ellipse([(-60, -60), (100, 130)], fill=(88, 101, 242, 30))
    d.ellipse([(520, -30), (750, 180)], fill=(114, 137, 254, 25))

    # left accent
    d.rectangle([(0, 0), (5, H)], fill=(88, 101, 242, 255))

    # avatar
    av = load_avatar(user, 80)
    ax, ay = 30, 30
    img.paste(av, (ax, ay), av)
    d.ellipse([(ax, ay), (ax + 80, ay + 80)], outline=(255, 255, 255, 50), width=2)

    # name
    nm = (user.display_name or "Unknown")[:16]
    d.text((125, 32), nm, fill=(255, 255, 255, 255), font=fm)

    # level + rank badge
    d.text((125, 68), f"Level {level}  |  Rank #{rank}", fill=(180, 180, 210, 200), font=fs)

    # XP bar
    bx, by = 125, 94
    bw, bh = W - 155, 16
    pct = min(xp_progress / xp_needed, 1) if xp_needed > 0 else 0
    rr(d, (bx, by, bx + bw, by + bh), 8, fill=(35, 35, 65, 200))
    if pct > 0:
        rr(d, (bx, by, bx + int(bw * pct), by + bh), 8, fill=(88, 101, 242, 220))
    xt = f"{xp_progress:,} / {xp_needed:,} XP"
    xb = d.textbbox((0, 0), xt, font=fs)
    d.text((bx + bw // 2 - (xb[2] - xb[0]) // 2, by), xt, fill=(255, 255, 255, 220), font=fs)

    # stats grid
    stats = [
        ("Total XP", f"{xp:,}"),
        ("Weekly XP", f"{weekly_xp:,}"),
        ("Messages", f"{total_msgs:,}"),
        ("Level", str(level)),
    ]
    cols = 4
    cell_w = (W - 30) // cols
    gy = 150
    for i, (label, value) in enumerate(stats):
        gx = 15 + i * cell_w
        # stat card
        rr(d, (gx, gy, gx + cell_w - 10, gy + 85), 10, fill=(25, 25, 55, 180))
        # label
        lb_d = d.textbbox((0, 0), label, font=fs)
        d.text((gx + (cell_w - 10) // 2 - (lb_d[2] - lb_d[0]) // 2, gy + 8), label, fill=(160, 160, 200, 150), font=fs)
        # value
        vb = d.textbbox((0, 0), value, font=fl)
        d.text((gx + (cell_w - 10) // 2 - (vb[2] - vb[0]) // 2, gy + 30), value, fill=(255, 255, 255, 255), font=fl)

    # XP earned today placeholder
    d.text((15, H - 28), f"{guild.name[:18]} • VØRTΞX SYSTEM", fill=(130, 130, 170, 100), font=fs)

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
        self._xp_boost_cache = {}  # guild_id -> {"roles": {role_id: mult}, "channels": {channel_id: mult}}

    def _get_guild_config(self, gid):
        data = load_lvl_config()
        g = str(gid)
        if g not in data:
            data[g] = {
                "enabled": True, "xp_per_msg": [10, 25], "cooldown": 45,
                "announce_channel": None, "level_up_channel": None, "role_rewards": {},
                "xp_boost": {"roles": {}, "channels": {}},
                "rank_cards": {},
                "weekly_xp": {"start": 0, "users": {}},
                "weekly_msgs": {},
            }
            save_lvl_config(data)
        return data[g]

    def _save_gcfg(self, gid, cfg):
        data = load_lvl_config()
        data[str(gid)] = cfg
        save_lvl_config(data)

    def _ensure_weekly(self, cfg):
        """Reset weekly XP if a new week has started."""
        now = time.time()
        week_sec = 7 * 24 * 3600
        wk = cfg.setdefault("weekly_xp", {"start": 0, "users": {}})
        if not wk.get("start") or now - wk["start"] > week_sec:
            wk["start"] = int(now)
            wk["users"] = {}
        return wk

    def _apply_xp_boost(self, guild_id, channel_id, member, base_xp):
        """Apply XP multiplier from role/channel boosts."""
        cfg = self._get_guild_config(guild_id)
        boost = cfg.get("xp_boost", {})
        multiplier = 1.0
        for role_id_str, mult in boost.get("roles", {}).items():
            try:
                if discord.utils.get(member.roles, id=int(role_id_str)):
                    multiplier = max(multiplier, mult)
            except:
                pass
        for ch_id_str, mult in boost.get("channels", {}).items():
            try:
                if int(ch_id_str) == channel_id:
                    multiplier = max(multiplier, mult)
            except:
                pass
        return int(base_xp * multiplier)

    def _get_rank_card_cfg(self, guild_id, user_id):
        """Get per-user rank card customization."""
        cfg = self._get_guild_config(guild_id)
        return cfg.get("rank_cards", {}).get(str(user_id), {})

    # ── Listener ─────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or message.guild is None:
            return
        cfg = self._get_guild_config(message.guild.id)
        if not cfg.get("enabled", True):
            return
        uid = message.author.id
        now = message.created_at.timestamp()
        cd = cfg.get("cooldown", 45)
        if now - self.cooldowns.get(uid, 0) < cd:
            return
        self.cooldowns[uid] = now

        xpr = cfg.get("xp_per_msg", [10, 25])
        gain = random.randint(xpr[0], xpr[1])
        # Apply XP boost
        gain = self._apply_xp_boost(message.guild.id, message.channel.id, message.author, gain)

        user_data = get_user_level(message.guild.id, uid)
        old_xp = user_data.get("xp", 0) or 0
        old_level = level_from_xp(old_xp)
        new_xp = old_xp + gain
        new_level = level_from_xp(new_xp)
        set_user_level(message.guild.id, uid, xp=new_xp, level=new_level, last_msg=int(now))

        # Track weekly XP
        cfg = self._get_guild_config(message.guild.id)
        wk = self._ensure_weekly(cfg)
        wk["users"][str(uid)] = wk["users"].get(str(uid), 0) + gain
        # Track message count
        msgs = cfg.setdefault("weekly_msgs", {})
        msgs[str(uid)] = msgs.get(str(uid), 0) + 1
        self._save_gcfg(message.guild.id, cfg)

        if new_level > old_level:
            await self.handle_level_up(message, old_level, new_level, new_xp, cfg)

    async def handle_level_up(self, message, old, new, total, cfg):
        gc = cfg
        rr_cfg = gc.get("role_rewards", {})
        added = None
        rn = rr_cfg.get(str(new))
        if rn:
            r = discord.utils.get(message.guild.roles, name=rn)
            if not r:
                r = message.guild.get_role(int(rn)) if rn.isdigit() else None
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

    @app_commands.command(name="rank", description="🏆 Show XP rank card with avatar")
    @app_commands.describe(member="Member (optional)")
    async def rank_slash(self, interaction: discord.Interaction, member: discord.Member = None):
        await interaction.response.defer()
        m = member or interaction.user
        user_data = get_user_level(interaction.guild.id, m.id)
        xp = user_data.get("xp", 0) or 0
        lvl, prog, need = progress_to_next(xp)
        rank = get_rank(interaction.guild.id, m.id)
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

    @app_commands.command(name="leaderboard", description="🏆 Server leaderboard image")
    @app_commands.describe(page="Page number")
    async def leaderboard_slash(self, interaction: discord.Interaction, page: int = 1):
        await interaction.response.defer()
        lb_raw = get_leaderboard(interaction.guild.id, limit=200)
        all_users = [(str(entry["user_id"]), {"xp": entry.get("xp", 0) or 0}) for entry in lb_raw]
        filtered = all_users
        if not filtered:
            return await interaction.followup.send("❌ | No members yet!")

        per_page = 8
        total = max(1, (len(filtered) + per_page - 1) // per_page)
        page = max(1, min(page, total))
        start = (page - 1) * per_page
        end = start + per_page
        page_data = filtered[start:end]

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

        medals = ["🥇", "🥈", "🥉"]
        emb = discord.Embed(title=f"🏆 Leaderboard — {interaction.guild.name}", color=0xFFD700)
        for i, (uid, ud) in enumerate(page_data, start=start + 1):
            mem = interaction.guild.get_member(int(uid))
            nm = mem.display_name if mem else f"#{uid[:4]}"
            lv = level_from_xp(ud["xp"])
            m = medals[i - 1] if i <= 3 else f"{i}."
            emb.add_field(name=f"{m} {nm}", value=f"Lv.{lv} • {ud['xp']:,} XP", inline=False)
        await interaction.followup.send(embed=emb)

    # ── /levelup ─────────────────────────────────────────────────────

    @app_commands.command(name="levelup", description="🎉 Show your level up card")
    @app_commands.describe(member="Member (optional)")
    async def levelup_slash(self, interaction: discord.Interaction, member: discord.Member = None):
        await interaction.response.defer()
        m = member or interaction.user
        user_data = get_user_level(interaction.guild.id, m.id)
        xp = user_data.get("xp", 0) or 0
        lvl, prog, need = progress_to_next(xp)
        try:
            b = generate_level_up(m, interaction.guild, lvl, lvl, xp, prog, need)
            if b:
                await interaction.followup.send(file=discord.File(b, filename="levelup.png"))
                return
        except Exception as e:
            print(f"⚠️ levelup img: {e}")
        e = discord.Embed(title=f"🎉 Level {lvl}!", color=0xFFD700)
        e.add_field(name="✨ XP", value=f"{xp:,}", inline=True)
        e.add_field(name="📊 Progress", value=f"{prog:,}/{need:,}", inline=True)
        await interaction.followup.send(embed=e)

    # ── /setlevel ────────────────────────────────────────────────────

    @app_commands.command(name="setlevel", description="⚙️ Set a member's level (admin)")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(member="Member", level="New level number")
    async def setlevel_slash(self, interaction: discord.Interaction, member: discord.Member, level: int):
        await interaction.response.defer()
        if level < 0:
            return await interaction.followup.send("❌ | Level must be >= 0", ephemeral=True)
        xp = xp_for_level(level)
        set_user_level(interaction.guild.id, member.id, xp=xp, level=level)
        add_audit("setlevel", f"{interaction.user} set {member} to level {level}", interaction.guild.id, interaction.user.id)
        e = discord.Embed(title="✅ Level Updated", color=0x00FF00)
        e.add_field(name="Member", value=member.mention)
        e.add_field(name="New Level", value=str(level))
        e.add_field(name="XP", value=f"{xp:,}")
        await interaction.followup.send(embed=e)

    # ── /setxp ───────────────────────────────────────────────────────

    @app_commands.command(name="setxp", description="⚙️ Set a member's XP (admin)")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(member="Member", xp="New XP amount")
    async def setxp_slash(self, interaction: discord.Interaction, member: discord.Member, xp: int):
        await interaction.response.defer()
        if xp < 0:
            return await interaction.followup.send("❌ | XP must be >= 0", ephemeral=True)
        level = level_from_xp(xp)
        set_user_level(interaction.guild.id, member.id, xp=xp, level=level)
        add_audit("setxp", f"{interaction.user} set {member} to {xp} XP (level {level})", interaction.guild.id, interaction.user.id)
        e = discord.Embed(title="✅ XP Updated", color=0x00FF00)
        e.add_field(name="Member", value=member.mention)
        e.add_field(name="New XP", value=f"{xp:,}")
        e.add_field(name="New Level", value=str(level))
        await interaction.followup.send(embed=e)

    # ── /levelconfig ─────────────────────────────────────────────────

    @app_commands.command(name="levelconfig", description="⚙️ Configure level system settings")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        setting="Setting to configure",
        value="Value for the setting"
    )
    async def levelconfig_slash(self, interaction: discord.Interaction, setting: str, value: str = None):
        await interaction.response.defer()
        cfg = self._get_guild_config(interaction.guild.id)
        gc = load_lvl_config()
        g = str(interaction.guild.id)
        gc.setdefault(g, cfg)

        async def ok(msg):
            await interaction.followup.send(f"✅ | {msg}")
        async def err(msg):
            await interaction.followup.send(f"❌ | {msg}", ephemeral=True)

        if setting in ("enabled", "toggle"):
            cfg["enabled"] = not cfg.get("enabled", True)
            gc[g]["enabled"] = cfg["enabled"]
            save_lvl_config(gc)
            await ok(f"System {'enabled 🟢' if cfg['enabled'] else 'disabled 🔴'}")

        elif setting in ("xp", "xp-range"):
            try:
                lo, hi = map(int, value.split("-"))
                cfg["xp_per_msg"] = [lo, hi]
                gc[g]["xp_per_msg"] = [lo, hi]
                save_lvl_config(gc)
                add_audit("levelconfig_xp", f"XP range set to {lo}-{hi}", interaction.guild.id, interaction.user.id)
                await ok(f"XP range: {lo}-{hi} per message")
            except:
                await err("Usage: `5-15` (min-max)")

        elif setting == "cooldown":
            try:
                s = int(value)
                if s < 0:
                    return await err("Must be >= 0")
                cfg["cooldown"] = s
                gc[g]["cooldown"] = s
                save_lvl_config(gc)
                await ok(f"Cooldown: {s}s")
            except:
                await err("Usage: `45` (seconds)")

        elif setting in ("channel", "announce-channel"):
            try:
                cid = int(value.strip("<>#"))
                cfg["announce_channel"] = cid
                gc[g]["announce_channel"] = cid
                save_lvl_config(gc)
                ch = interaction.guild.get_channel(cid)
                await ok(f"Announce channel: {ch.mention if ch else f'<#{cid}>'}")
            except:
                await err("Mention a channel: `#channel`")

        elif setting in ("lvlchannel", "level-up-channel"):
            try:
                cid = int(value.strip("<>#"))
                cfg["level_up_channel"] = cid
                gc[g]["level_up_channel"] = cid
                save_lvl_config(gc)
                ch = interaction.guild.get_channel(cid)
                await ok(f"Level-up channel: {ch.mention if ch else f'<#{cid}>'}")
            except:
                await err("Mention a channel: `#channel`")

        elif setting in ("reward", "add-role"):
            try:
                parts = value.split()
                lv = int(parts[0])
                rn = " ".join(parts[1:])
                gc[g].setdefault("role_rewards", {})
                gc[g]["role_rewards"][str(lv)] = rn
                save_lvl_config(gc)
                add_audit("levelconfig_reward", f"Lv.{lv} → {rn}", interaction.guild.id, interaction.user.id)
                await ok(f"Reward Lv.{lv} → `{rn}`")
            except:
                await err("Usage: `5 @Role` or `5 RoleName`")

        elif setting == "remove-reward":
            try:
                lv = str(int(value))
                if gc[g].get("role_rewards", {}).pop(lv, None):
                    save_lvl_config(gc)
                    await ok(f"Removed reward at Lv.{lv}")
                else:
                    await err(f"No reward at Lv.{lv}")
            except:
                await err("Usage: `5` (level number)")

        elif setting == "info":
            e = discord.Embed(title="⚙️ Level Config", color=CONFIG.get("color", 0x5865F2))
            e.add_field(name="Status", value="🟢 Enabled" if cfg.get("enabled", True) else "🔴 Disabled", inline=True)
            e.add_field(name="XP Range", value=str(cfg.get("xp_per_msg", [10, 25])), inline=True)
            e.add_field(name="Cooldown", value=f"{cfg.get('cooldown', 45)}s", inline=True)
            ac = cfg.get("announce_channel")
            if ac:
                ch = interaction.guild.get_channel(ac)
                e.add_field(name="Announce Channel", value=ch.mention if ch else f"<#{ac}>", inline=True)
            lc = cfg.get("level_up_channel")
            if lc:
                ch = interaction.guild.get_channel(lc)
                e.add_field(name="Level-Up Channel", value=ch.mention if ch else f"<#{lc}>", inline=True)
            rw = cfg.get("role_rewards", {})
            if rw:
                rw_text = "\n".join([f"Lv.{l} → `{r}`" for l, r in sorted(rw.items(), key=lambda x: int(x[0]))[:10]])
                e.add_field(name="Role Rewards", value=rw_text or "None", inline=False)
            boost = cfg.get("xp_boost", {})
            boost_lines = []
            for role_id, mult in boost.get("roles", {}).items():
                r = interaction.guild.get_role(int(role_id))
                boost_lines.append(f"Role {r.mention if r else role_id}: {mult}x")
            for ch_id, mult in boost.get("channels", {}).items():
                c = interaction.guild.get_channel(int(ch_id))
                boost_lines.append(f"Channel {c.mention if c else ch_id}: {mult}x")
            if boost_lines:
                e.add_field(name="XP Boosts", value="\n".join(boost_lines) or "None", inline=False)
            await interaction.followup.send(embed=e)

        else:
            await err("Options: enabled, xp, cooldown, channel, lvlchannel, reward, remove-reward, info")

    @levelconfig_slash.autocomplete("setting")
    async def levelconfig_auto(self, interaction: discord.Interaction, cur: str):
        opts = [
            ("🟢 Toggle enabled/disabled", "toggle"),
            ("✨ XP range (min-max)", "xp"),
            ("⏱️ Cooldown (seconds)", "cooldown"),
            ("📢 Announce channel", "announce-channel"),
            ("🎉 Level-up channel", "level-up-channel"),
            ("🎖️ Add role reward", "add-role"),
            ("🗑️ Remove role reward", "remove-reward"),
            ("ℹ️ Show config info", "info"),
        ]
        return [app_commands.Choice(name=n, value=v) for n, v in opts if cur.lower() in n.lower() or cur.lower() in v.lower()]

    # ── /levelroles ──────────────────────────────────────────────────

    @app_commands.command(name="levelroles", description="🎖️ Manage auto-roles on level up")
    @app_commands.default_permissions(administrator=True)
    async def levelroles_slash(self, interaction: discord.Interaction):
        await interaction.response.defer()
        cfg = self._get_guild_config(interaction.guild.id)
        rw = cfg.get("role_rewards", {})
        if not rw:
            return await interaction.followup.send("❌ | No level roles configured. Use `/levelconfig add-role` to add one.", ephemeral=True)

        embed = discord.Embed(
            title="🎖️ Level Roles",
            description="Roles automatically assigned on level up",
            color=CONFIG.get("color", 0x5865F2)
        )
        for lvl, rn in sorted(rw.items(), key=lambda x: int(x[0])):
            r = discord.utils.get(interaction.guild.roles, name=rn)
            if not r:
                r = interaction.guild.get_role(int(rn)) if rn.isdigit() else None
            role_display = r.mention if r else f"`{rn}`"
            embed.add_field(name=f"Level {lvl}", value=role_display, inline=True)
        await interaction.followup.send(embed=embed)

    # ── /xpboost ─────────────────────────────────────────────────────

    @app_commands.command(name="xpboost", description="⚡ Boost XP for specific roles or channels")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        target_type="Boost type: role or channel",
        target_id="The role/channel ID or mention",
        multiplier="XP multiplier (e.g. 1.5 for 50% bonus, 2.0 for double)"
    )
    async def xpboost_slash(self, interaction: discord.Interaction, target_type: str, target_id: str, multiplier: float):
        await interaction.response.defer()

        if multiplier < 1.0:
            return await interaction.followup.send("❌ | Multiplier must be >= 1.0", ephemeral=True)
        if multiplier > 10.0:
            return await interaction.followup.send("❌ | Max multiplier is 10.0", ephemeral=True)

        cfg = self._get_guild_config(interaction.guild.id)
        boost = cfg.setdefault("xp_boost", {"roles": {}, "channels": {}})
        gc = load_lvl_config()
        g = str(interaction.guild.id)
        gc.setdefault(g, cfg)

        # Parse ID (could be mention like <@&123> or <#123> or raw number)
        raw = target_id.strip("<>@&#!")
        try:
            tid = int(raw)
        except ValueError:
            return await interaction.followup.send("❌ | Invalid ID. Use a role/channel mention or numeric ID.", ephemeral=True)

        target_type = target_type.lower()
        if target_type in ("role", "roles"):
            role = interaction.guild.get_role(tid)
            if not role:
                return await interaction.followup.send("❌ | Role not found in this server.", ephemeral=True)
            boost.setdefault("roles", {})[str(tid)] = multiplier
            gc[g].setdefault("xp_boost", {})[str(tid)] = multiplier
            save_lvl_config(gc)
            add_audit("xpboost_role", f"{interaction.user}: {role.name} x{multiplier}", interaction.guild.id, interaction.user.id)
            await interaction.followup.send(f"✅ | **{role.name}** now gets **{multiplier}x** XP!")

        elif target_type in ("channel", "channels"):
            channel = interaction.guild.get_channel(tid)
            if not channel:
                return await interaction.followup.send("❌ | Channel not found in this server.", ephemeral=True)
            boost.setdefault("channels", {})[str(tid)] = multiplier
            gc[g].setdefault("xp_boost", {})[str(tid)] = multiplier
            save_lvl_config(gc)
            add_audit("xpboost_channel", f"{interaction.user}: {channel.name} x{multiplier}", interaction.guild.id, interaction.user.id)
            await interaction.followup.send(f"✅ | **{channel.mention}** now gives **{multiplier}x** XP!")

        else:
            await interaction.followup.send("❌ | Use `role` or `channel` as target type.", ephemeral=True)

    @xpboost_slash.autocomplete("target_type")
    async def xpboost_auto(self, interaction: discord.Interaction, cur: str):
        opts = [
            ("🎭 Role-based boost", "role"),
            ("📢 Channel-based boost", "channel"),
        ]
        return [app_commands.Choice(name=n, value=v) for n, v in opts if cur.lower() in n.lower() or cur.lower() in v.lower()]

    # ── /rankcard ────────────────────────────────────────────────────

    @app_commands.command(name="rankcard", description="🎨 Customize your rank card appearance")
    @app_commands.describe(
        bg_color="Background color (hex, e.g. #0f0f23)",
        accent_color="Accent color (hex, e.g. #5865F2)"
    )
    async def rankcard_slash(self, interaction: discord.Interaction, bg_color: str = None, accent_color: str = None):
        await interaction.response.defer()
        cfg = self._get_guild_config(interaction.guild.id)
        rc = cfg.setdefault("rank_cards", {})
        uid = str(interaction.user.id)
        user_cfg = rc.setdefault(uid, {})

        if bg_color is None and accent_color is None:
            # Show current settings
            current_bg = user_cfg.get("bg_color", "Default")
            current_accent = user_cfg.get("accent_color", "Default")
            e = discord.Embed(
                title="🎨 Rank Card Customization",
                description=f"**Background:** `{current_bg}`\n**Accent:** `{current_accent}`",
                color=int((accent_color or "5865F2").lstrip("#"), 16)
            )
            return await interaction.followup.send(embed=e)

        changes = []
        if bg_color:
            bg_color = bg_color.strip("#")
            if len(bg_color) != 6:
                return await interaction.followup.send("❌ | Invalid hex color. Use format `#RRGGBB` (e.g. `#0f0f23`)", ephemeral=True)
            try:
                int(bg_color, 16)
            except ValueError:
                return await interaction.followup.send("❌ | Invalid hex color.", ephemeral=True)
            user_cfg["bg_color"] = f"#{bg_color}"
            changes.append(f"background → `#{bg_color}`")

        if accent_color:
            accent_color = accent_color.strip("#")
            if len(accent_color) != 6:
                return await interaction.followup.send("❌ | Invalid hex color. Use format `#RRGGBB`", ephemeral=True)
            try:
                int(accent_color, 16)
            except ValueError:
                return await interaction.followup.send("❌ | Invalid hex color.", ephemeral=True)
            user_cfg["accent_color"] = f"#{accent_color}"
            changes.append(f"accent → `#{accent_color}`")

        gc = load_lvl_config()
        gc.setdefault(str(interaction.guild.id), cfg)
        gc[str(interaction.guild.id)] = cfg
        save_lvl_config(gc)

        await interaction.followup.send(f"✅ | Updated: {', '.join(changes)}")

    # ── /topxp ───────────────────────────────────────────────────────

    @app_commands.command(name="topxp", description="📊 Top XP earners this week")
    @app_commands.describe(page="Page number")
    async def topxp_slash(self, interaction: discord.Interaction, page: int = 1):
        await interaction.response.defer()
        cfg = self._get_guild_config(interaction.guild.id)
        wk = self._ensure_weekly(cfg)

        if not wk["users"]:
            return await interaction.followup.send("📊 | No XP earned yet this week!")

        # Sort by weekly XP descending
        sorted_users = sorted(wk["users"].items(), key=lambda x: x[1], reverse=True)

        per_page = 10
        total = max(1, (len(sorted_users) + per_page - 1) // per_page)
        page = max(1, min(page, total))
        start = (page - 1) * per_page
        end = start + per_page
        page_data = sorted_users[start:end]

        medals = ["🥇", "🥈", "🥉"]
        embed = discord.Embed(
            title="📊 Top XP This Week",
            description=f"Page {page}/{total}",
            color=0xFFD700
        )
        for i, (uid_str, xp) in enumerate(page_data, start=start + 1):
            uid = int(uid_str)
            member = interaction.guild.get_member(uid)
            nm = member.display_name if member else f"Unknown#{uid_str[:4]}"
            medal = medals[i - 1] if i <= 3 else f"`#{i}`"
            # Get their level
            user_data = get_user_level(interaction.guild.id, uid)
            total_xp = user_data.get("xp", 0) or 0
            lvl = level_from_xp(total_xp)
            embed.add_field(
                name=f"{medal} {nm}",
                value=f"**{xp:,} XP** this week • Lv.{lvl}",
                inline=False
            )

        await interaction.followup.send(embed=embed)

    # ── /xpstats ─────────────────────────────────────────────────────

    @app_commands.command(name="xpstats", description="📊 View your XP statistics")
    @app_commands.describe(member="Member (optional)")
    async def xpstats_slash(self, interaction: discord.Interaction, member: discord.Member = None):
        await interaction.response.defer()
        m = member or interaction.user
        user_data = get_user_level(interaction.guild.id, m.id)
        xp = user_data.get("xp", 0) or 0
        lvl, prog, need = progress_to_next(xp)
        rank = get_rank(interaction.guild.id, m.id)

        # Weekly stats from config
        cfg = self._get_guild_config(interaction.guild.id)
        wk = self._ensure_weekly(cfg)
        weekly_xp = wk["users"].get(str(m.id), 0)
        msgs = cfg.get("weekly_msgs", {}).get(str(m.id), 0)

        try:
            b = generate_xpstats_card(m, interaction.guild, xp, lvl, prog, need, rank, weekly_xp, msgs)
            if b:
                await interaction.followup.send(file=discord.File(b, filename="xpstats.png"))
                return
        except Exception as e:
            print(f"⚠️ xpstats img: {e}")

        embed = discord.Embed(
            title=f"📊 {m.display_name}'s XP Stats",
            color=CONFIG.get("color", 0x5865F2)
        )
        embed.add_field(name="Level", value=str(lvl), inline=True)
        embed.add_field(name="Total XP", value=f"{xp:,}", inline=True)
        embed.add_field(name="Rank", value=f"#{rank}", inline=True)
        embed.add_field(name="XP Progress", value=f"{prog:,} / {need:,}", inline=True)
        embed.add_field(name="Weekly XP", value=f"{weekly_xp:,}", inline=True)
        embed.add_field(name="Messages (week)", value=f"{msgs:,}", inline=True)
        await interaction.followup.send(embed=embed)

    # ── /resetxp ─────────────────────────────────────────────────────

    @app_commands.command(name="resetxp", description="⚠️ Reset XP for a member (admin)")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(member="Member to reset")
    async def resetxp_slash(self, interaction: discord.Interaction, member: discord.Member):
        await interaction.response.defer()
        # Confirm via a followup with a button
        view = discord.ui.View()
        confirm_btn = discord.ui.Button(label="Confirm Reset", style=discord.ButtonStyle.danger, emoji="⚠️")
        cancel_btn = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.secondary)

        async def confirm_cb(btn_interaction: discord.Interaction):
            if btn_interaction.user.id != interaction.user.id:
                return await btn_interaction.response.send_message("❌ | Not your command!", ephemeral=True)
            set_user_level(interaction.guild.id, member.id, xp=0, level=0)
            # Also reset weekly XP
            cfg = self._get_guild_config(interaction.guild.id)
            wk = cfg.setdefault("weekly_xp", {"start": 0, "users": {}})
            wk["users"].pop(str(member.id), None)
            msgs = cfg.setdefault("weekly_msgs", {})
            msgs.pop(str(member.id), None)
            gc = load_lvl_config()
            gc[str(interaction.guild.id)] = cfg
            save_lvl_config(gc)
            add_audit("resetxp", f"{interaction.user} reset {member}", interaction.guild.id, interaction.user.id)
            await btn_interaction.response.edit_message(
                content=f"✅ | **{member.display_name}** has been reset to Level 0 / 0 XP",
                view=None
            )

        async def cancel_cb(btn_interaction: discord.Interaction):
            if btn_interaction.user.id != interaction.user.id:
                return await btn_interaction.response.send_message("❌ | Not your command!", ephemeral=True)
            await btn_interaction.response.edit_message(content="❌ | Reset cancelled.", view=None)

        confirm_btn.callback = confirm_cb
        cancel_btn.callback = cancel_cb
        view.add_item(confirm_btn)
        view.add_item(cancel_btn)

        user_data = get_user_level(interaction.guild.id, member.id)
        xp = user_data.get("xp", 0) or 0
        lvl = level_from_xp(xp)
        await interaction.followup.send(
            content=f"⚠️ **Reset {member.display_name}?**\nCurrent: Level {lvl} — {xp:,} XP\nThis cannot be undone.",
            view=view
        )

    # ── /level ───────────────────────────────────────────────────────

    @app_commands.command(name="level", description="⚙️ Level system settings overview")
    @app_commands.default_permissions(administrator=True)
    async def level_settings(self, interaction: discord.Interaction):
        await interaction.response.defer()
        cfg = self._get_guild_config(interaction.guild.id)
        e = discord.Embed(
            title="⚙️ | Level System Settings",
            description=f"**Status:** {'🟢 Enabled' if cfg.get('enabled', True) else '🔴 Disabled'}",
            color=CONFIG.get("color", 0x5865F2),
        )
        e.add_field(name="XP per Message", value=str(cfg.get("xp_per_msg", [10, 25])), inline=True)
        e.add_field(name="Cooldown", value=f"{cfg.get('cooldown', 45)}s", inline=True)
        lc = cfg.get("level_up_channel")
        if lc:
            ch = interaction.guild.get_channel(lc)
            e.add_field(name="🎉 Level-Up Channel", value=ch.mention if ch else "Not set", inline=True)
        else:
            ac = cfg.get("announce_channel")
            e.add_field(name="📢 Announce Channel", value=f"<#{ac}>" if ac else "🗣️ Same channel", inline=True)
        rw = cfg.get("role_rewards", {})
        if rw:
            rw_text = "\n".join([f"Lv.{l} → `{r}`" for l, r in sorted(rw.items(), key=lambda x: int(x[0]))[:5]])
            e.add_field(name="🎖️ Rewards", value=rw_text or "None", inline=False)
        else:
            e.add_field(name="🎖️ Rewards", value="None", inline=False)
        # XP boosts
        boost = cfg.get("xp_boost", {})
        boost_lines = []
        for role_id, mult in boost.get("roles", {}).items():
            r = interaction.guild.get_role(int(role_id))
            boost_lines.append(f"{r.mention if r else f'Role {role_id}'}: {mult}x")
        for ch_id, mult in boost.get("channels", {}).items():
            c = interaction.guild.get_channel(int(ch_id))
            boost_lines.append(f"{c.mention if c else f'Channel {ch_id}'}: {mult}x")
        if boost_lines:
            e.add_field(name="⚡ XP Boosts", value="\n".join(boost_lines) or "None", inline=False)
        await interaction.followup.send(embed=e)

    # ── /level-config (keep existing) ────────────────────────────────

    @app_commands.command(name="level-config", description="⚙️ Configure level settings (legacy)")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(setting="Setting", value="Value")
    async def level_config(self, interaction: discord.Interaction, setting: str, value: str = None):
        await interaction.response.defer()
        cfg = self._get_guild_config(interaction.guild.id)
        gc = load_lvl_config()
        g = str(interaction.guild.id)
        gc.setdefault(g, cfg)

        async def ok(msg):
            await interaction.followup.send(f"✅ | {msg}")
        async def err(msg):
            await interaction.followup.send(f"❌ | {msg}", ephemeral=True)

        if setting in ("enabled", "toggle"):
            cfg["enabled"] = not cfg.get("enabled", True)
            gc[g]["enabled"] = cfg["enabled"]
            save_lvl_config(gc)
            await ok(f"System {'enabled 🟢' if cfg['enabled'] else 'disabled 🔴'}")
        elif setting in ("xp-range", "xp"):
            try:
                lo, hi = map(int, value.split("-"))
                cfg["xp_per_msg"] = [lo, hi]
                gc[g]["xp_per_msg"] = [lo, hi]
                save_lvl_config(gc)
                await ok(f"XP: {lo}-{hi} per message")
            except:
                await err("Use: `5-15`")
        elif setting == "cooldown":
            try:
                s = int(value)
                cfg["cooldown"] = s
                gc[g]["cooldown"] = s
                save_lvl_config(gc)
                await ok(f"Cooldown: {s}s")
            except:
                await err("Use number: `45`")
        elif setting in ("announce-channel", "channel"):
            try:
                cid = int(value.strip("<>#"))
                cfg["announce_channel"] = cid
                gc[g]["announce_channel"] = cid
                save_lvl_config(gc)
                await ok(f"Announce channel: <#{cid}>")
            except:
                await err("Mention channel: `#channel`")
        elif setting in ("level-up-channel", "lvlchannel"):
            try:
                cid = int(value.strip("<>#"))
                cfg["level_up_channel"] = cid
                gc[g]["level_up_channel"] = cid
                save_lvl_config(gc)
                await ok(f"Level-up channel: <#{cid}>")
            except:
                await err("Mention channel: `#channel`")
        elif setting in ("add-role", "reward"):
            try:
                parts = value.split()
                lv = int(parts[0])
                rn = " ".join(parts[1:])
                gc[g].setdefault("role_rewards", {})
                gc[g]["role_rewards"][str(lv)] = rn
                save_lvl_config(gc)
                await ok(f"Reward Lv.{lv} → `{rn}`")
            except:
                await err("Use: `5 VIP`")
        else:
            await err("Options: enabled, xp, cooldown, channel, lvlchannel, reward")

    @level_config.autocomplete("setting")
    async def lc_auto(self, interaction: discord.Interaction, cur: str):
        opts = [
            ("🟢 Toggle", "toggle"),
            ("✨ XP range", "xp"),
            ("⏱️ Cooldown", "cooldown"),
            ("📢 Announce channel", "announce-channel"),
            ("🎉 Level-up channel", "level-up-channel"),
            ("🎖️ Add role reward", "add-role"),
        ]
        return [app_commands.Choice(name=n, value=v) for n, v in opts if cur.lower() in n.lower() or cur.lower() in v.lower()]

async def setup(bot):
    await bot.add_cog(Levels(bot))
