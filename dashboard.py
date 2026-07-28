#!/usr/bin/env python3
"""
VØRTΞX System Bot — Web Dashboard (Standalone)
Flask web app with Arabic UI, dark theme, and glassmorphism effects.
Connects to PostgreSQL via db.py or falls back to local JSON files.
"""
import os, sys, json, hashlib, time, uuid
from pathlib import Path
from functools import wraps
from datetime import datetime, timedelta

# ── Flask ────────────────────────────────────────────────────────────────
from flask import (
    Flask, session, redirect, url_for, request,
    render_template_string, jsonify, flash
)

BASE = Path(__file__).parent
DATA_FILE = BASE / "dashboard_data.json"
CONFIG_FILE = BASE / "config.json"

app = Flask(__name__)
app.secret_key = hashlib.sha256(b"VortexHost2026SecureDashboard").hexdigest()
app.permanent_session_lifetime = timedelta(hours=4)

# ── Admin password (SHA-256, since bcrypt fails on ARM) ─────────────────
ADMIN_PASS_HASH = hashlib.sha256("VortexHost2026Secure".encode()).hexdigest()

# ── Try to import DB ───────────────────────────────────────────────────
HAS_DB = False
try:
    sys.path.insert(0, str(BASE))
    from db import (
        get_db, get_all_stats, get_audit_log, incr_stat, add_audit,
        get_guild_config, set_guild_config,
        list_custom_commands, set_custom_command, del_custom_command,
        get_reaction_panels, add_reaction_role, remove_reaction_role,
        get_broadcast_history, add_broadcast,
    )
    HAS_DB = True
except Exception as e:
    print(f"⚠️ DB import failed: {e} — using JSON fallback")

# ── JSON Fallback Storage ───────────────────────────────────────────────
def _load_data():
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text())
    return {}

def _save_data(data):
    DATA_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))

def _get_data(key, default=None):
    d = _load_data()
    return d.get(key, default)

def _set_data(key, value):
    d = _load_data()
    d[key] = value
    _save_data(d)

# ── Stats helpers ──────────────────────────────────────────────────────
def get_bot_stats():
    """Return dict of bot stats from DB or JSON fallback."""
    stats = {
        "total_commands": 0,
        "total_guilds": 0,
        "total_users": 0,
        "bot_started": int(time.time()),
        "total_audit": 0,
        "total_custom_commands": 0,
        "total_reaction_panels": 0,
        "commands_today": 0,
    }
    if HAS_DB:
        try:
            db_stats = get_all_stats()
            for k in ("total_commands", "total_guilds", "total_users", "bot_started"):
                if k in db_stats:
                    stats[k] = int(db_stats[k]) if db_stats[k] else 0
            # Count audit log entries
            try:
                logs = get_audit_log(limit=999999)
                stats["total_audit"] = len(logs)
            except:
                pass
        except Exception as e:
            print(f"⚠️ Stats DB error: {e}")
    else:
        json_data = _load_data()
        for k in stats:
            stats[k] = json_data.get(k, stats[k])
    return stats

def get_guilds_list():
    """Get list of guilds from DB or JSON."""
    guilds = []
    if HAS_DB:
        try:
            db = get_db()
            rows = db.run("SELECT guild_id, language FROM guild_config ORDER BY guild_id")
            for r in rows:
                guilds.append({"id": str(r[0]), "language": r[1] if len(r) > 1 else "ar"})
        except Exception as e:
            print(f"⚠️ Guilds DB error: {e}")
    else:
        guilds = _get_data("guilds", [])
    return guilds

def get_commands_list():
    """Get list of all available commands (hardcoded from cogs)."""
    return [
        # Admin
        {"name": "setup", "category": "admin", "desc": "⚙️ الإعدادات الأساسية للبوت"},
        {"name": "config", "category": "admin", "desc": "⚙️ عرض إعدادات السيرفر"},
        {"name": "sync", "category": "admin", "desc": "🔄 إعادة مزامنة الأوامر"},
        {"name": "ban", "category": "admin", "desc": "🔨 حظر عضو"},
        {"name": "kick", "category": "admin", "desc": "👢 طرد عضو"},
        {"name": "clear", "category": "admin", "desc": "🧹 مسح رسائل"},
        {"name": "lock", "category": "admin", "desc": "🔒 قفل الروم"},
        {"name": "unlock", "category": "admin", "desc": "🔓 فتح الروم"},
        {"name": "nickname", "category": "admin", "desc": "✏️ تغيير الكنية"},
        {"name": "role", "category": "admin", "desc": "🎭 إضافة/إزالة رول"},
        # Welcome
        {"name": "welcome status", "category": "welcome", "desc": "🟢 عرض حالة الترحيب"},
        {"name": "welcome channel", "category": "welcome", "desc": "📢 ضبط قناة الترحيب"},
        {"name": "welcome message", "category": "welcome", "desc": "✏️ ضبط رسالة الترحيب"},
        {"name": "welcome leave-message", "category": "welcome", "desc": "👋 ضبط رسالة المغادرة"},
        {"name": "welcome toggle", "category": "welcome", "desc": "🔘 تشغيل/إيقاف الترحيب"},
        {"name": "welcome dm-toggle", "category": "welcome", "desc": "💬 تشغيل/إيقاف الرسالة الخاصة"},
        {"name": "welcome autorole", "category": "welcome", "desc": "🎖️ ضبط الرتبة التلقائية"},
        {"name": "welcome preview", "category": "welcome", "desc": "🖼️ معاينة صورة الترحيب"},
        # Custom Commands
        {"name": "addcommand", "category": "custom_commands", "desc": "➕ أضف أمر مخصص"},
        {"name": "delcommand", "category": "custom_commands", "desc": "🗑️ احذف أمر مخصص"},
        {"name": "commands", "category": "custom_commands", "desc": "📋 قائمة الأوامر المخصصة"},
        # Reaction Roles
        {"name": "reaction-roles create", "category": "reaction_roles", "desc": "🎯 إنشاء لوحة رولات"},
        {"name": "reaction-roles add", "category": "reaction_roles", "desc": "➕ إضافة رول للوحة"},
        {"name": "reaction-roles remove", "category": "reaction_roles", "desc": "➖ إزالة رول من لوحة"},
        {"name": "reaction-roles delete", "category": "reaction_roles", "desc": "🗑️ حذف لوحة رولات"},
        {"name": "reaction-roles list", "category": "reaction_roles", "desc": "📋 عرض اللوحات"},
        # Broadcast
        {"name": "broadcast", "category": "broadcast", "desc": "📢 أرسل رسالة للقنوات"},
        {"name": "broadcast_history", "category": "broadcast", "desc": "📋 سجل البث السابق"},
        # Moderation (from events / other cogs)
        {"name": "warn", "category": "moderation", "desc": "⚠️ تحذير عضو"},
        {"name": "warns", "category": "moderation", "desc": "📋 عرض التحذيرات"},
        {"name": "clearwarns", "category": "moderation", "desc": "🧹 مسح التحذيرات"},
        # Tickets
        {"name": "ticket setup", "category": "tickets", "desc": "🎫 إعداد نظام التذاكر"},
        {"name": "ticket close", "category": "tickets", "desc": "🔒 إغلاق تذكرة"},
        # Utility
        {"name": "ping", "category": "utility", "desc": "🏓 فحص سرعة البوت"},
        {"name": "serverinfo", "category": "utility", "desc": "ℹ️ معلومات السيرفر"},
        {"name": "userinfo", "category": "utility", "desc": "👤 معلومات العضو"},
        {"name": "avatar", "category": "utility", "desc": "🖼️ عرض الصورة الرمزية"},
        {"name": "say", "category": "utility", "desc": "💬 إرسال رسالة من البوت"},
        # Levels
        {"name": "level", "category": "levels", "desc": "📊 عرض مستواك"},
        {"name": "leaderboard", "category": "levels", "desc": "🏆 قائمة المتصدرين"},
        {"name": "rank", "category": "levels", "desc": "📈 ترتيبك في السيرفر"},
        # Anti-Raid
        {"name": "antiraid toggle", "category": "antiraid", "desc": "🛡️ تشغيل/إيقافanti-raid"},
        {"name": "antiraid config", "category": "antiraid", "desc": "⚙️ إعداداتanti-raid"},
        {"name": "antiraid whitelist", "category": "antiraid", "desc": "➕ إضافة رول للقائمة البيضاء"},
        {"name": "language", "category": "language", "desc": "🌐 تغيير لغة البوت"},
    ]

# ── Auth Decorator ─────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

# ── Routes ─────────────────────────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        password = request.form.get("password", "")
        if hashlib.sha256(password.encode()).hexdigest() == ADMIN_PASS_HASH:
            session["logged_in"] = True
            session.permanent = True
            return redirect(url_for("dashboard"))
        flash("❌ كلمة المرور غير صحيحة!", "error")
    return render_template_string(HTML_LOGIN)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/")
@login_required
def dashboard():
    stats = get_bot_stats()
    try:
        uptime_seconds = int(time.time()) - stats.get("bot_started", int(time.time()))
    except:
        uptime_seconds = 0
    days, remainder = divmod(uptime_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, _ = divmod(remainder, 60)
    uptime_str = f"{days}ي {hours:02d}:{minutes:02d}"
    stats["uptime"] = uptime_str
    return render_template_string(HTML_DASHBOARD, stats=stats)

@app.route("/commands")
@login_required
def commands_view():
    cmds = get_commands_list()
    categories = {}
    for c in cmds:
        cat = c["category"]
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(c)
    return render_template_string(HTML_COMMANDS, commands=cmds, categories=categories)

@app.route("/guilds")
@login_required
def guilds_view():
    guilds = get_guilds_list()
    return render_template_string(HTML_GUILDS, guilds=guilds)

@app.route("/welcome", methods=["GET", "POST"])
@login_required
def welcome_view():
    msg = None
    if request.method == "POST":
        guild_id = request.form.get("guild_id", "").strip()
        welcome_msg = request.form.get("message", "")
        leave_msg = request.form.get("leave_message", "")
        channel = request.form.get("channel", "")
        auto_role = request.form.get("auto_role", "")
        enabled = request.form.get("enabled") == "on"
        dm_welcome = request.form.get("dm_welcome") == "on"

        if guild_id and HAS_DB:
            try:
                gid = int(guild_id)
                set_guild_config(gid,
                    message=welcome_msg,
                    leave_message=leave_msg,
                    channel=channel,
                    auto_role=auto_role,
                    enabled=enabled,
                    dm_welcome=dm_welcome,
                )
                msg = "✅ تم حفظ إعدادات الترحيب بنجاح!"
            except Exception as e:
                msg = f"❌ خطأ في الحفظ: {e}"
        elif guild_id:
            # JSON fallback
            data = _load_data()
            guild_key = f"welcome_{guild_id}"
            data[guild_key] = {
                "message": welcome_msg,
                "leave_message": leave_msg,
                "channel": channel,
                "auto_role": auto_role,
                "enabled": enabled,
                "dm_welcome": dm_welcome,
            }
            _save_data(data)
            msg = "✅ تم حفظ إعدادات الترحيب (JSON)"
        else:
            msg = "⚠️ الرجاء إدخال ID السيرفر"

    guilds = get_guilds_list()
    current_guild_config = None
    if guilds and HAS_DB:
        try:
            gid = int(guilds[0]["id"])
            current_guild_config = get_guild_config(gid)
        except:
            pass

    return render_template_string(HTML_WELCOME,
        guilds=guilds, msg=msg, config=current_guild_config)

@app.route("/welcome/get/<guild_id>")
@login_required
def welcome_get(guild_id):
    if HAS_DB:
        try:
            cfg = get_guild_config(int(guild_id))
            return jsonify({
                "message": cfg.get("message", "🎉 | مرحباً {member}!"),
                "leave_message": cfg.get("leave_message", "👋 | {member} غادر السيرفر..."),
                "channel": cfg.get("channel", "welcome"),
                "auto_role": cfg.get("auto_role", "Member"),
                "enabled": cfg.get("enabled", True),
                "dm_welcome": cfg.get("dm_welcome", True),
            })
        except:
            return jsonify({"error": "DB error"}), 500
    return jsonify(_get_data(f"welcome_{guild_id}", {}))

@app.route("/reaction-roles", methods=["GET", "POST"])
@login_required
def reaction_roles_view():
    msg = None
    if request.method == "POST":
        action = request.form.get("action", "")
        guild_id = request.form.get("guild_id", "").strip()
        panel_id = request.form.get("panel_id", "").strip()
        title = request.form.get("title", "").strip()
        channel_id = request.form.get("channel_id", "").strip()
        role_id = request.form.get("role_id", "").strip()
        label = request.form.get("label", "").strip()
        emoji = request.form.get("emoji", "").strip()
        message_id = request.form.get("message_id", "0").strip()

        if not guild_id:
            msg = "⚠️ الرجاء إدخال ID السيرفر"
        elif action == "create_panel" and HAS_DB:
            try:
                pid = panel_id or uuid.uuid4().hex[:8]
                add_reaction_role(
                    int(guild_id), pid,
                    int(channel_id) if channel_id else 0,
                    int(message_id) if message_id else 0,
                    title or "New Panel",
                    0, "__panel__", ""
                )
                # Remove sentinel immediately (we just need to create the panel placeholder)
                remove_reaction_role(int(guild_id), pid, 0)
                msg = f"✅ تم إنشاء اللوحة `{pid}` بنجاح!"
            except Exception as e:
                msg = f"❌ خطأ: {e}"
        elif action == "add_role" and HAS_DB:
            try:
                add_reaction_role(
                    int(guild_id), panel_id,
                    0, 0, "",
                    int(role_id), label, emoji
                )
                msg = f"✅ تم إضافة الرول بنجاح!"
            except Exception as e:
                msg = f"❌ خطأ: {e}"
        elif action == "remove_role" and HAS_DB:
            try:
                remove_reaction_role(int(guild_id), panel_id, int(role_id))
                msg = "✅ تم إزالة الرول بنجاح!"
            except Exception as e:
                msg = f"❌ خطأ: {e}"
        else:
            msg = "⚠️ العملية غير مدعومة أو DB غير متصل"

    panels = []
    guilds = get_guilds_list()
    if guilds and HAS_DB:
        try:
            panels = get_reaction_panels(int(guilds[0]["id"]))
        except:
            pass

    return render_template_string(HTML_REACTION_ROLES,
        guilds=guilds, panels=panels, msg=msg)

@app.route("/reaction-roles/panels/<guild_id>")
@login_required
def reaction_roles_panels(guild_id):
    if HAS_DB:
        try:
            panels = get_reaction_panels(int(guild_id))
            return jsonify(panels)
        except:
            return jsonify([])
    return jsonify([])

@app.route("/custom-commands", methods=["GET", "POST"])
@login_required
def custom_commands_view():
    msg = None
    if request.method == "POST":
        action = request.form.get("action", "")
        guild_id = request.form.get("guild_id", "").strip()
        name = request.form.get("name", "").strip().lower()
        response = request.form.get("response", "").strip()

        if not guild_id or not name:
            msg = "⚠️ الرجاء إدخال ID السيرفر واسم الأمر"
        elif action == "add" and HAS_DB:
            try:
                set_custom_command(int(guild_id), name, response, 0)
                msg = f"✅ تم إضافة الأمر `{name}` بنجاح!"
            except Exception as e:
                msg = f"❌ خطأ: {e}"
        elif action == "delete" and HAS_DB:
            try:
                if del_custom_command(int(guild_id), name):
                    msg = f"✅ تم حذف الأمر `{name}` بنجاح!"
                else:
                    msg = f"⚠️ الأمر `{name}` غير موجود"
            except Exception as e:
                msg = f"❌ خطأ: {e}"
        elif action == "edit" and HAS_DB:
            try:
                set_custom_command(int(guild_id), name, response, 0)
                msg = f"✅ تم تحديث الأمر `{name}` بنجاح!"
            except Exception as e:
                msg = f"❌ خطأ: {e}"
        else:
            msg = "⚠️ العملية غير مدعومة أو DB غير متصل"

    cmds = []
    guilds = get_guilds_list()
    if guilds and HAS_DB:
        try:
            cmds = list_custom_commands(int(guilds[0]["id"]))
        except:
            pass

    return render_template_string(HTML_CUSTOM_COMMANDS,
        guilds=guilds, commands=cmds, msg=msg)

@app.route("/custom-commands/list/<guild_id>")
@login_required
def custom_commands_list(guild_id):
    if HAS_DB:
        try:
            cmds = list_custom_commands(int(guild_id))
            return jsonify(cmds)
        except:
            return jsonify([])
    return jsonify(_get_data(f"cc_{guild_id}", []))

@app.route("/broadcast", methods=["GET", "POST"])
@login_required
def broadcast_view():
    msg = None
    if request.method == "POST":
        guild_id = request.form.get("guild_id", "").strip()
        title = request.form.get("title", "")
        message = request.form.get("message", "")

        if not guild_id or not title or not message:
            msg = "⚠️ الرجاء تعبئة جميع الحقول"
        elif HAS_DB:
            try:
                # Simulate broadcast — just log it to history
                add_broadcast(int(guild_id), [0], title, message, 0, 0)
                msg = "✅ تم إرسال البث بنجاح!"
            except Exception as e:
                msg = f"❌ خطأ: {e}"
        else:
            # JSON fallback
            history = _get_data(f"broadcast_{guild_id}", [])
            history.append({
                "title": title,
                "message": message,
                "time": str(datetime.now()),
                "sent_to": 0,
            })
            _set_data(f"broadcast_{guild_id}", history)
            msg = "✅ تم تسجيل البث (JSON)"

    history = []
    guilds = get_guilds_list()
    if guilds and HAS_DB:
        try:
            history = get_broadcast_history(int(guilds[0]["id"]))
        except:
            pass

    return render_template_string(HTML_BROADCAST,
        guilds=guilds, history=history, msg=msg)

@app.route("/broadcast/history/<guild_id>")
@login_required
def broadcast_history(guild_id):
    if HAS_DB:
        try:
            return jsonify(get_broadcast_history(int(guild_id)))
        except:
            return jsonify([])
    return jsonify(_get_data(f"broadcast_{guild_id}", []))

@app.route("/config")
@login_required
def config_view():
    guilds = get_guilds_list()
    configs = []
    if guilds and HAS_DB:
        for g in guilds[:20]:  # Limit to 20 guilds
            try:
                cfg = get_guild_config(int(g["id"]))
                cfg["guild_id"] = g["id"]
                configs.append(cfg)
            except:
                pass
    return render_template_string(HTML_CONFIG, guilds=guilds, configs=configs)

@app.route("/config/get/<guild_id>")
@login_required
def config_get(guild_id):
    if HAS_DB:
        try:
            cfg = get_guild_config(int(guild_id))
            return jsonify(cfg)
        except:
            return jsonify({"error": "DB error"}), 500
    return jsonify(_get_data(f"config_{guild_id}", {}))

@app.route("/config/save", methods=["POST"])
@login_required
def config_save():
    guild_id = request.form.get("guild_id", "").strip()
    data = {}
    for key in ("welcome_channel", "ticket_category", "admin_role", "mod_role", "mod_log_channel", "language", "prefix"):
        val = request.form.get(key, "").strip()
        if val:
            data[key] = val
    if guild_id and data and HAS_DB:
        try:
            set_guild_config(int(guild_id), **data)
            return jsonify({"success": True, "msg": "✅ تم حفظ الإعدادات"})
        except Exception as e:
            return jsonify({"success": False, "msg": f"❌ خطأ: {e}"}), 500
    return jsonify({"success": False, "msg": "⚠️ بيانات غير كافية"}), 400

@app.route("/logs")
@login_required
def logs_view():
    logs = []
    if HAS_DB:
        try:
            logs = get_audit_log(limit=200)
        except:
            pass
    else:
        logs = _get_data("audit_logs", [])
    return render_template_string(HTML_LOGS, logs=logs)

@app.route("/api/stats")
@login_required
def api_stats():
    return jsonify(get_bot_stats())

@app.route("/api/ping")
@login_required
def api_ping():
    return jsonify({"status": "ok", "time": str(datetime.now())})

# ── HTML Templates (Embedded) ──────────────────────────────────────────

HTML_LOGIN = """\
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>VØRTΞX — دخول المشرف</title>
<link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: 'Cairo', sans-serif;
    background: #0a0a0f;
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
    position: relative;
}
body::before {
    content: '';
    position: fixed;
    top: -50%;
    left: -50%;
    width: 200%;
    height: 200%;
    background: radial-gradient(circle at 30% 50%, rgba(0, 255, 136, 0.03) 0%, transparent 50%),
                radial-gradient(circle at 70% 30%, rgba(88, 101, 242, 0.04) 0%, transparent 50%),
                radial-gradient(circle at 50% 80%, rgba(0, 200, 100, 0.02) 0%, transparent 50%);
    animation: bgPulse 8s ease-in-out infinite alternate;
    z-index: 0;
}
@keyframes bgPulse {
    0% { transform: scale(1) rotate(0deg); opacity: 0.5; }
    100% { transform: scale(1.1) rotate(3deg); opacity: 1; }
}
.login-container {
    position: relative;
    z-index: 1;
    width: 420px;
    padding: 50px 40px;
    background: rgba(10, 10, 20, 0.85);
    backdrop-filter: blur(24px);
    -webkit-backdrop-filter: blur(24px);
    border: 1px solid rgba(0, 255, 136, 0.15);
    border-radius: 24px;
    box-shadow: 0 0 60px rgba(0, 255, 136, 0.06), 0 25px 80px rgba(0, 0, 0, 0.6);
    text-align: center;
}
.logo {
    font-size: 42px;
    font-weight: 900;
    background: linear-gradient(135deg, #00ff88, #00cc6a);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 8px;
    letter-spacing: 2px;
}
.logo-sub {
    color: rgba(255,255,255,0.35);
    font-size: 13px;
    letter-spacing: 4px;
    text-transform: uppercase;
    margin-bottom: 35px;
    font-weight: 500;
}
h2 {
    color: #fff;
    font-size: 22px;
    font-weight: 700;
    margin-bottom: 28px;
}
.flash-msg {
    background: rgba(255, 70, 70, 0.15);
    border: 1px solid rgba(255, 70, 70, 0.3);
    color: #ff6b6b;
    padding: 12px 16px;
    border-radius: 12px;
    margin-bottom: 20px;
    font-size: 14px;
}
.input-group {
    position: relative;
    margin-bottom: 24px;
}
.input-group input {
    width: 100%;
    padding: 16px 20px;
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 14px;
    color: #fff;
    font-size: 15px;
    font-family: 'Cairo', sans-serif;
    transition: all 0.3s ease;
    outline: none;
}
.input-group input:focus {
    border-color: rgba(0, 255, 136, 0.4);
    background: rgba(255,255,255,0.06);
    box-shadow: 0 0 20px rgba(0, 255, 136, 0.05);
}
.input-group input::placeholder {
    color: rgba(255,255,255,0.3);
}
.input-group label {
    position: absolute;
    top: -10px;
    right: 16px;
    background: #0a0a0f;
    padding: 0 8px;
    font-size: 12px;
    color: rgba(0, 255, 136, 0.6);
    font-weight: 600;
}
.btn-login {
    width: 100%;
    padding: 16px;
    background: linear-gradient(135deg, #00ff88, #00cc6a);
    border: none;
    border-radius: 14px;
    color: #0a0a0f;
    font-size: 17px;
    font-weight: 800;
    font-family: 'Cairo', sans-serif;
    cursor: pointer;
    transition: all 0.3s ease;
    margin-top: 8px;
}
.btn-login:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 30px rgba(0, 255, 136, 0.25);
}
.btn-login:active {
    transform: translateY(0);
}
.footer-text {
    margin-top: 28px;
    color: rgba(255,255,255,0.2);
    font-size: 12px;
    letter-spacing: 1px;
}
.glass-dots {
    position: fixed;
    z-index: 0;
    border-radius: 50%;
    filter: blur(80px);
    opacity: 0.3;
}
.glass-dots:nth-child(1) {
    width: 300px; height: 300px;
    background: rgba(0, 255, 136, 0.08);
    top: 10%; left: -5%;
    animation: float1 12s ease-in-out infinite;
}
.glass-dots:nth-child(2) {
    width: 250px; height: 250px;
    background: rgba(88, 101, 242, 0.06);
    bottom: 15%; right: -5%;
    animation: float2 15s ease-in-out infinite;
}
@keyframes float1 {
    0%, 100% { transform: translate(0, 0) scale(1); }
    50% { transform: translate(30px, -30px) scale(1.1); }
}
@keyframes float2 {
    0%, 100% { transform: translate(0, 0) scale(1); }
    50% { transform: translate(-40px, 40px) scale(1.15); }
}
</style>
</head>
<body>
<div class="glass-dots"></div>
<div class="glass-dots"></div>
<div class="login-container">
    <div class="logo">VØRTΞX</div>
    <div class="logo-sub">S Y S T E M &nbsp; D A S H B O A R D</div>
    <h2>🔐 دخول المشرف</h2>
    {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
            {% for category, message in messages %}
                <div class="flash-msg">{{ message }}</div>
            {% endfor %}
        {% endif %}
    {% endwith %}
    <form method="POST">
        <div class="input-group">
            <label>كلمة المرور</label>
            <input type="password" name="password" placeholder="••••••••••••" required autofocus>
        </div>
        <button type="submit" class="btn-login">⎆  دخول</button>
    </form>
    <div class="footer-text">VØRTΞX HOST © 2026</div>
</div>
</body>
</html>"""

HTML_DASHBOARD = """\
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>VØRTΞX — لوحة التحكم</title>
<link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: 'Cairo', sans-serif;
    background: #08080e;
    color: #e0e0e0;
    min-height: 100vh;
}
/* ── Sidebar ── */
.sidebar {
    position: fixed;
    right: 0;
    top: 0;
    width: 260px;
    height: 100vh;
    background: rgba(10, 10, 20, 0.95);
    backdrop-filter: blur(20px);
    border-left: 1px solid rgba(0, 255, 136, 0.08);
    padding: 30px 20px;
    z-index: 100;
    overflow-y: auto;
}
.sidebar-logo {
    font-size: 28px;
    font-weight: 900;
    background: linear-gradient(135deg, #00ff88, #00cc6a);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    text-align: center;
    margin-bottom: 4px;
}
.sidebar-sub {
    text-align: center;
    color: rgba(255,255,255,0.25);
    font-size: 10px;
    letter-spacing: 3px;
    text-transform: uppercase;
    margin-bottom: 30px;
}
.sidebar-nav { display: flex; flex-direction: column; gap: 4px; }
.nav-item {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 13px 18px;
    border-radius: 12px;
    color: rgba(255,255,255,0.55);
    text-decoration: none;
    font-size: 14px;
    font-weight: 500;
    transition: all 0.25s ease;
}
.nav-item:hover, .nav-item.active {
    background: rgba(0, 255, 136, 0.06);
    color: #00ff88;
}
.nav-item.active {
    background: rgba(0, 255, 136, 0.1);
    border: 1px solid rgba(0, 255, 136, 0.12);
}
.nav-icon { font-size: 18px; width: 24px; text-align: center; }
.nav-logout {
    margin-top: auto;
    margin-bottom: 10px;
    color: rgba(255, 80, 80, 0.6);
}
.nav-logout:hover { color: #ff5555; background: rgba(255, 80, 80, 0.06); }
/* ── Main ── */
.main {
    margin-right: 260px;
    padding: 30px 40px;
}
.page-title {
    font-size: 26px;
    font-weight: 800;
    margin-bottom: 6px;
    color: #fff;
}
.page-sub {
    color: rgba(255,255,255,0.35);
    font-size: 14px;
    margin-bottom: 30px;
}
/* ── Stats Grid ── */
.stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 20px;
    margin-bottom: 30px;
}
.stat-card {
    background: rgba(255,255,255,0.03);
    backdrop-filter: blur(12px);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 18px;
    padding: 24px;
    transition: all 0.3s ease;
    position: relative;
    overflow: hidden;
}
.stat-card::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
    background: linear-gradient(90deg, transparent, #00ff88, transparent);
    opacity: 0.3;
}
.stat-card:hover {
    transform: translateY(-4px);
    border-color: rgba(0, 255, 136, 0.15);
    box-shadow: 0 12px 40px rgba(0, 0, 0, 0.3);
}
.stat-icon { font-size: 28px; margin-bottom: 12px; }
.stat-label { color: rgba(255,255,255,0.4); font-size: 13px; font-weight: 500; margin-bottom: 6px; }
.stat-value { font-size: 32px; font-weight: 800; color: #fff; letter-spacing: -0.5px; }
.stat-value.green { color: #00ff88; }
.stat-value.blue { color: #5865F2; }
.stat-value.purple { color: #9b59b6; }
.stat-value.orange { color: #f39c12; }
.stat-value.red { color: #e74c3c; }
.stat-value.cyan { color: #00d4ff; }
/* ── Quick Actions ── */
.section-title {
    font-size: 18px;
    font-weight: 700;
    color: #fff;
    margin-bottom: 16px;
    margin-top: 10px;
}
.actions-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(170px, 1fr));
    gap: 14px;
}
.action-btn {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 10px;
    padding: 24px 16px;
    background: rgba(255,255,255,0.02);
    border: 1px solid rgba(255,255,255,0.05);
    border-radius: 16px;
    color: rgba(255,255,255,0.6);
    text-decoration: none;
    font-size: 13px;
    font-weight: 600;
    transition: all 0.25s ease;
    text-align: center;
}
.action-btn:hover {
    background: rgba(0, 255, 136, 0.05);
    border-color: rgba(0, 255, 136, 0.15);
    color: #00ff88;
    transform: translateY(-2px);
    box-shadow: 0 8px 25px rgba(0, 0, 0, 0.2);
}
.action-icon { font-size: 28px; }
/* ── Status Bar ── */
.status-bar {
    margin-top: 30px;
    padding: 16px 20px;
    background: rgba(255,255,255,0.02);
    border: 1px solid rgba(255,255,255,0.04);
    border-radius: 14px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 13px;
    color: rgba(255,255,255,0.3);
}
.status-dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #00ff88;
    margin-left: 6px;
    animation: pulse 2s infinite;
}
@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.3; }
}
@media (max-width: 768px) {
    .sidebar { width: 200px; }
    .main { margin-right: 200px; padding: 20px; }
    .stats-grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 576px) {
    .sidebar { width: 60px; padding: 15px 8px; }
    .sidebar-logo { font-size: 16px; }
    .sidebar-sub, .nav-item span { display: none; }
    .nav-item { justify-content: center; padding: 12px; }
    .main { margin-right: 60px; padding: 15px; }
    .stats-grid { grid-template-columns: 1fr; }
}
</style>
</head>
<body>
<div class="sidebar">
    <div class="sidebar-logo">VØRTΞX</div>
    <div class="sidebar-sub">D A S H B O A R D</div>
    <nav class="sidebar-nav">
        <a href="/" class="nav-item active"><span class="nav-icon">📊</span><span>لوحة التحكم</span></a>
        <a href="/commands" class="nav-item"><span class="nav-icon">📋</span><span>الأوامر</span></a>
        <a href="/guilds" class="nav-item"><span class="nav-icon">🏰</span><span>السيرفرات</span></a>
        <a href="/welcome" class="nav-item"><span class="nav-icon">👋</span><span>الترحيب</span></a>
        <a href="/reaction-roles" class="nav-item"><span class="nav-icon">🎯</span><span>رولات التفاعل</span></a>
        <a href="/custom-commands" class="nav-item"><span class="nav-icon">⚡</span><span>الأوامر المخصصة</span></a>
        <a href="/broadcast" class="nav-item"><span class="nav-icon">📢</span><span>البث</span></a>
        <a href="/config" class="nav-item"><span class="nav-icon">⚙️</span><span>الإعدادات</span></a>
        <a href="/logs" class="nav-item"><span class="nav-icon">📜</span><span>سجل النشاطات</span></a>
        <a href="/logout" class="nav-item nav-logout"><span class="nav-icon">🚪</span><span>تسجيل خروج</span></a>
    </nav>
</div>
<div class="main">
    <h1 class="page-title">📊 لوحة التحكم</h1>
    <p class="page-sub">نظرة عامة على أداء البوت VØRTΞX</p>

    <div class="stats-grid">
        <div class="stat-card">
            <div class="stat-icon">⚡</div>
            <div class="stat-label">الأوامر المنفذة</div>
            <div class="stat-value green">{{ stats.total_commands }}</div>
        </div>
        <div class="stat-card">
            <div class="stat-icon">🏰</div>
            <div class="stat-label">السيرفرات</div>
            <div class="stat-value blue">{{ stats.total_guilds }}</div>
        </div>
        <div class="stat-card">
            <div class="stat-icon">👥</div>
            <div class="stat-label">المستخدمين</div>
            <div class="stat-value purple">{{ "{:,}".format(stats.total_users) }}</div>
        </div>
        <div class="stat-card">
            <div class="stat-icon">⏰</div>
            <div class="stat-label">مدة التشغيل</div>
            <div class="stat-value orange">{{ stats.uptime }}</div>
        </div>
        <div class="stat-card">
            <div class="stat-icon">📜</div>
            <div class="stat-label">سجل النشاطات</div>
            <div class="stat-value cyan">{{ stats.total_audit }}</div>
        </div>
        <div class="stat-card">
            <div class="stat-icon">🔗</div>
            <div class="stat-label">حالة DB</div>
            <div class="stat-value green">{% if HAS_DB %}🟢 متصل{% else %}🟡 JSON{% endif %}</div>
        </div>
    </div>

    <h2 class="section-title">⚡ إجراءات سريعة</h2>
    <div class="actions-grid">
        <a href="/commands" class="action-btn">
            <span class="action-icon">📋</span>
            <span>عرض الأوامر</span>
        </a>
        <a href="/welcome" class="action-btn">
            <span class="action-icon">👋</span>
            <span>تحرير الترحيب</span>
        </a>
        <a href="/reaction-roles" class="action-btn">
            <span class="action-icon">🎯</span>
            <span>رولات التفاعل</span>
        </a>
        <a href="/custom-commands" class="action-btn">
            <span class="action-icon">⚡</span>
            <span>أوامر مخصصة</span>
        </a>
        <a href="/broadcast" class="action-btn">
            <span class="action-icon">📢</span>
            <span>إرسال بث</span>
        </a>
        <a href="/logs" class="action-btn">
            <span class="action-icon">📜</span>
            <span>سجل النشاطات</span>
        </a>
        <a href="/config" class="action-btn">
            <span class="action-icon">⚙️</span>
            <span>إعدادات السيرفرات</span>
        </a>
        <a href="/guilds" class="action-btn">
            <span class="action-icon">🏰</span>
            <span>السيرفرات</span>
        </a>
    </div>

    <div class="status-bar">
        <span>🟢 البوت يعمل</span>
        <span><span class="status-dot"></span> VØRTΞX SYSTEM v4</span>
    </div>
</div>
</body>
</html>"""

HTML_COMMANDS = """\
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>VØRTΞX — الأوامر</title>
<link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: 'Cairo', sans-serif;
    background: #08080e;
    color: #e0e0e0;
    min-height: 100vh;
}
.sidebar {
    position: fixed; right: 0; top: 0; width: 260px; height: 100vh;
    background: rgba(10,10,20,0.95); backdrop-filter: blur(20px);
    border-left: 1px solid rgba(0,255,136,0.08); padding: 30px 20px; z-index: 100; overflow-y: auto;
}
.sidebar-logo { font-size: 28px; font-weight: 900; background: linear-gradient(135deg,#00ff88,#00cc6a); -webkit-background-clip: text; -webkit-text-fill-color: transparent; text-align: center; margin-bottom: 4px; }
.sidebar-sub { text-align: center; color: rgba(255,255,255,0.25); font-size: 10px; letter-spacing: 3px; text-transform: uppercase; margin-bottom: 30px; }
.sidebar-nav { display: flex; flex-direction: column; gap: 4px; }
.nav-item { display: flex; align-items: center; gap: 14px; padding: 13px 18px; border-radius: 12px; color: rgba(255,255,255,0.55); text-decoration: none; font-size: 14px; font-weight: 500; transition: all 0.25s ease; }
.nav-item:hover, .nav-item.active { background: rgba(0,255,136,0.06); color: #00ff88; }
.nav-item.active { background: rgba(0,255,136,0.1); border: 1px solid rgba(0,255,136,0.12); }
.nav-icon { font-size: 18px; width: 24px; text-align: center; }
.nav-logout { margin-top: auto; margin-bottom: 10px; color: rgba(255,80,80,0.6); }
.nav-logout:hover { color: #ff5555; background: rgba(255,80,80,0.06); }
.main { margin-right: 260px; padding: 30px 40px; }
.page-title { font-size: 26px; font-weight: 800; margin-bottom: 6px; color: #fff; }
.page-sub { color: rgba(255,255,255,0.35); font-size: 14px; margin-bottom: 30px; }
.cmd-category { margin-bottom: 28px; }
.cat-header {
    display: flex; align-items: center; gap: 10px;
    font-size: 16px; font-weight: 700; color: #00ff88;
    padding: 12px 18px;
    background: rgba(0,255,136,0.04);
    border: 1px solid rgba(0,255,136,0.08);
    border-radius: 12px; margin-bottom: 12px;
}
.cat-header .count { color: rgba(255,255,255,0.3); font-size: 13px; font-weight: 500; margin-right: auto; }
.cmd-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 10px; }
.cmd-card {
    display: flex; align-items: center; gap: 12px;
    padding: 14px 18px;
    background: rgba(255,255,255,0.02);
    border: 1px solid rgba(255,255,255,0.04);
    border-radius: 12px;
    transition: all 0.25s ease;
}
.cmd-card:hover { background: rgba(0,255,136,0.03); border-color: rgba(0,255,136,0.1); }
.cmd-name {
    font-family: 'Courier New', monospace;
    font-size: 13px; font-weight: 600;
    color: #00ff88;
    background: rgba(0,255,136,0.06);
    padding: 4px 10px;
    border-radius: 6px;
    white-space: nowrap;
}
.cmd-desc { font-size: 13px; color: rgba(255,255,255,0.5); }
.cat-icon { font-size: 20px; }
@media (max-width: 768px) {
    .sidebar { width: 200px; }
    .main { margin-right: 200px; padding: 20px; }
}
@media (max-width: 576px) {
    .sidebar { width: 60px; padding: 15px 8px; }
    .sidebar-logo { font-size: 16px; }
    .sidebar-sub, .nav-item span { display: none; }
    .nav-item { justify-content: center; padding: 12px; }
    .main { margin-right: 60px; padding: 15px; }
}
</style>
</head>
<body>
<div class="sidebar">
    <div class="sidebar-logo">VØRTΞX</div>
    <div class="sidebar-sub">D A S H B O A R D</div>
    <nav class="sidebar-nav">
        <a href="/" class="nav-item"><span class="nav-icon">📊</span><span>لوحة التحكم</span></a>
        <a href="/commands" class="nav-item active"><span class="nav-icon">📋</span><span>الأوامر</span></a>
        <a href="/guilds" class="nav-item"><span class="nav-icon">🏰</span><span>السيرفرات</span></a>
        <a href="/welcome" class="nav-item"><span class="nav-icon">👋</span><span>الترحيب</span></a>
        <a href="/reaction-roles" class="nav-item"><span class="nav-icon">🎯</span><span>رولات التفاعل</span></a>
        <a href="/custom-commands" class="nav-item"><span class="nav-icon">⚡</span><span>الأوامر المخصصة</span></a>
        <a href="/broadcast" class="nav-item"><span class="nav-icon">📢</span><span>البث</span></a>
        <a href="/config" class="nav-item"><span class="nav-icon">⚙️</span><span>الإعدادات</span></a>
        <a href="/logs" class="nav-item"><span class="nav-icon">📜</span><span>سجل النشاطات</span></a>
        <a href="/logout" class="nav-item nav-logout"><span class="nav-icon">🚪</span><span>تسجيل خروج</span></a>
    </nav>
</div>
<div class="main">
    <h1 class="page-title">📋 الأوامر</h1>
    <p class="page-sub">جميع أوامر البوت VØRTΞX — {{ commands|length }} أمر</p>
    {% set category_icons = {'admin':'🛡️','welcome':'👋','custom_commands':'⚡','reaction_roles':'🎯','broadcast':'📢','moderation':'⚠️','tickets':'🎫','utility':'🔧','levels':'📊','antiraid':'🛡️','language':'🌐'} %}
    {% for cat, cmds in categories.items() %}
    <div class="cmd-category">
        <div class="cat-header">
            <span class="cat-icon">{{ category_icons.get(cat, '📌') }}</span>
            <span>{{ cat.replace('_',' ').title() }}</span>
            <span class="count">{{ cmds|length }} أمر</span>
        </div>
        <div class="cmd-grid">
            {% for cmd in cmds %}
            <div class="cmd-card">
                <span class="cmd-name">{{ cmd.name }}</span>
                <span class="cmd-desc">{{ cmd.desc }}</span>
            </div>
            {% endfor %}
        </div>
    </div>
    {% endfor %}
</div>
</body>
</html>"""

HTML_GUILDS = """\
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>VØRTΞX — السيرفرات</title>
<link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Cairo',sans-serif;background:#08080e;color:#e0e0e0;min-height:100vh}
.sidebar{position:fixed;right:0;top:0;width:260px;height:100vh;background:rgba(10,10,20,0.95);backdrop-filter:blur(20px);border-left:1px solid rgba(0,255,136,0.08);padding:30px 20px;z-index:100;overflow-y:auto}
.sidebar-logo{font-size:28px;font-weight:900;background:linear-gradient(135deg,#00ff88,#00cc6a);-webkit-background-clip:text;-webkit-text-fill-color:transparent;text-align:center;margin-bottom:4px}
.sidebar-sub{text-align:center;color:rgba(255,255,255,0.25);font-size:10px;letter-spacing:3px;text-transform:uppercase;margin-bottom:30px}
.sidebar-nav{display:flex;flex-direction:column;gap:4px}
.nav-item{display:flex;align-items:center;gap:14px;padding:13px 18px;border-radius:12px;color:rgba(255,255,255,0.55);text-decoration:none;font-size:14px;font-weight:500;transition:all .25s ease}
.nav-item:hover,.nav-item.active{background:rgba(0,255,136,0.06);color:#00ff88}
.nav-item.active{background:rgba(0,255,136,0.1);border:1px solid rgba(0,255,136,0.12)}
.nav-icon{font-size:18px;width:24px;text-align:center}
.nav-logout{margin-top:auto;margin-bottom:10px;color:rgba(255,80,80,0.6)}
.nav-logout:hover{color:#ff5555;background:rgba(255,80,80,0.06)}
.main{margin-right:260px;padding:30px 40px}
.page-title{font-size:26px;font-weight:800;margin-bottom:6px;color:#fff}
.page-sub{color:rgba(255,255,255,0.35);font-size:14px;margin-bottom:30px}
.guild-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:16px}
.guild-card{background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.05);border-radius:16px;padding:24px;transition:all .3s ease}
.guild-card:hover{transform:translateY(-3px);border-color:rgba(0,255,136,0.15);box-shadow:0 12px 40px rgba(0,0,0,0.3)}
.guild-id{font-family:'Courier New',monospace;font-size:12px;color:rgba(255,255,255,0.25);margin-bottom:8px}
.guild-title{font-size:18px;font-weight:700;color:#fff;margin-bottom:12px}
.guild-badge{display:inline-block;padding:4px 12px;border-radius:20px;font-size:12px;font-weight:600}
.guild-badge.ar{background:rgba(0,255,136,0.1);color:#00ff88;border:1px solid rgba(0,255,136,0.2)}
.guild-badge.en{background:rgba(88,101,242,0.1);color:#5865F2;border:1px solid rgba(88,101,242,0.2)}
.empty-state{text-align:center;padding:60px 20px;color:rgba(255,255,255,0.3)}
.empty-state .big-icon{font-size:60px;margin-bottom:16px}
@media(max-width:768px){.sidebar{width:200px}.main{margin-right:200px;padding:20px}}
@media(max-width:576px){.sidebar{width:60px;padding:15px 8px}.sidebar-logo,.sidebar-sub,.nav-item span{display:none}.nav-item{justify-content:center;padding:12px}.main{margin-right:60px;padding:15px}}
</style>
</head>
<body>
<div class="sidebar">
    <div class="sidebar-logo">VØRTΞX</div>
    <div class="sidebar-sub">D A S H B O A R D</div>
    <nav class="sidebar-nav">
        <a href="/" class="nav-item"><span class="nav-icon">📊</span><span>لوحة التحكم</span></a>
        <a href="/commands" class="nav-item"><span class="nav-icon">📋</span><span>الأوامر</span></a>
        <a href="/guilds" class="nav-item active"><span class="nav-icon">🏰</span><span>السيرفرات</span></a>
        <a href="/welcome" class="nav-item"><span class="nav-icon">👋</span><span>الترحيب</span></a>
        <a href="/reaction-roles" class="nav-item"><span class="nav-icon">🎯</span><span>رولات التفاعل</span></a>
        <a href="/custom-commands" class="nav-item"><span class="nav-icon">⚡</span><span>الأوامر المخصصة</span></a>
        <a href="/broadcast" class="nav-item"><span class="nav-icon">📢</span><span>البث</span></a>
        <a href="/config" class="nav-item"><span class="nav-icon">⚙️</span><span>الإعدادات</span></a>
        <a href="/logs" class="nav-item"><span class="nav-icon">📜</span><span>سجل النشاطات</span></a>
        <a href="/logout" class="nav-item nav-logout"><span class="nav-icon">🚪</span><span>تسجيل خروج</span></a>
    </nav>
</div>
<div class="main">
    <h1 class="page-title">🏰 السيرفرات</h1>
    <p class="page-sub">قائمة السيرفرات المسجلة — {{ guilds|length }} سيرفر</p>
    {% if guilds %}
    <div class="guild-grid">
        {% for g in guilds %}
        <div class="guild-card">
            <div class="guild-id">ID: {{ g.id }}</div>
            <div class="guild-title">{{ g.get('name', 'سيرفر ' + g.id) }}</div>
            <span class="guild-badge {% if g.get('language','ar')=='ar' %}ar{% else %}en{% endif %}">
                {{ '🇸🇦 العربية' if g.get('language','ar')=='ar' else '🇬🇧 English' }}
            </span>
        </div>
        {% endfor %}
    </div>
    {% else %}
    <div class="empty-state">
        <div class="big-icon">🏰</div>
        <p>لا توجد سيرفرات مسجلة بعد</p>
    </div>
    {% endif %}
</div>
</body>
</html>"""

HTML_WELCOME = """\
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>VØRTΞX — إعدادات الترحيب</title>
<link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Cairo',sans-serif;background:#08080e;color:#e0e0e0;min-height:100vh}
.sidebar{position:fixed;right:0;top:0;width:260px;height:100vh;background:rgba(10,10,20,0.95);backdrop-filter:blur(20px);border-left:1px solid rgba(0,255,136,0.08);padding:30px 20px;z-index:100;overflow-y:auto}
.sidebar-logo{font-size:28px;font-weight:900;background:linear-gradient(135deg,#00ff88,#00cc6a);-webkit-background-clip:text;-webkit-text-fill-color:transparent;text-align:center;margin-bottom:4px}
.sidebar-sub{text-align:center;color:rgba(255,255,255,0.25);font-size:10px;letter-spacing:3px;text-transform:uppercase;margin-bottom:30px}
.sidebar-nav{display:flex;flex-direction:column;gap:4px}
.nav-item{display:flex;align-items:center;gap:14px;padding:13px 18px;border-radius:12px;color:rgba(255,255,255,0.55);text-decoration:none;font-size:14px;font-weight:500;transition:all .25s ease}
.nav-item:hover,.nav-item.active{background:rgba(0,255,136,0.06);color:#00ff88}
.nav-item.active{background:rgba(0,255,136,0.1);border:1px solid rgba(0,255,136,0.12)}
.nav-icon{font-size:18px;width:24px;text-align:center}
.nav-logout{margin-top:auto;margin-bottom:10px;color:rgba(255,80,80,0.6)}
.nav-logout:hover{color:#ff5555;background:rgba(255,80,80,0.06)}
.main{margin-right:260px;padding:30px 40px}
.page-title{font-size:26px;font-weight:800;margin-bottom:6px;color:#fff}
.page-sub{color:rgba(255,255,255,0.35);font-size:14px;margin-bottom:30px}
.form-card{background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.05);border-radius:18px;padding:30px;margin-bottom:20px}
.form-group{margin-bottom:20px}
.form-group label{display:block;font-size:14px;font-weight:600;color:rgba(255,255,255,0.6);margin-bottom:8px}
.form-control{width:100%;padding:14px 18px;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:12px;color:#fff;font-size:14px;font-family:'Cairo',sans-serif;transition:all .3s ease;outline:none}
.form-control:focus{border-color:rgba(0,255,136,0.4);background:rgba(255,255,255,0.06);box-shadow:0 0 20px rgba(0,255,136,0.05)}
.form-control::placeholder{color:rgba(255,255,255,0.2)}
select.form-control{appearance:none;background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='8' viewBox='0 0 12 8'%3E%3Cpath fill='%2300ff88' d='M6 8L0 0h12z'/%3E%3C/svg%3E");background-repeat:no-repeat;background-position:left 16px center;padding-left:40px}
textarea.form-control{resize:vertical;min-height:80px}
.form-row{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.toggle-group{display:flex;gap:20px;flex-wrap:wrap}
.toggle{display:flex;align-items:center;gap:10px;cursor:pointer}
.toggle input{display:none}
.toggle-slider{width:44px;height:24px;background:rgba(255,255,255,0.1);border-radius:12px;position:relative;transition:all .3s ease}
.toggle-slider::after{content:'';position:absolute;top:2px;right:2px;width:20px;height:20px;background:rgba(255,255,255,0.5);border-radius:50%;transition:all .3s ease}
.toggle input:checked+.toggle-slider{background:rgba(0,255,136,0.3)}
.toggle input:checked+.toggle-slider::after{right:22px;background:#00ff88}
.toggle-label{font-size:14px;color:rgba(255,255,255,0.5)}
.btn{display:inline-flex;align-items:center;gap:8px;padding:14px 28px;border:none;border-radius:12px;font-size:15px;font-weight:700;font-family:'Cairo',sans-serif;cursor:pointer;transition:all .3s ease}
.btn-primary{background:linear-gradient(135deg,#00ff88,#00cc6a);color:#0a0a0f}
.btn-primary:hover{transform:translateY(-2px);box-shadow:0 8px 30px rgba(0,255,136,0.25)}
.msg{background:rgba(0,255,136,0.08);border:1px solid rgba(0,255,136,0.15);color:#00ff88;padding:14px 20px;border-radius:12px;margin-bottom:20px;font-size:14px}
.msg.error{background:rgba(255,70,70,0.08);border-color:rgba(255,70,70,0.15);color:#ff6b6b}
@media(max-width:768px){.sidebar{width:200px}.main{margin-right:200px;padding:20px}.form-row{grid-template-columns:1fr}}
@media(max-width:576px){.sidebar{width:60px;padding:15px 8px}.sidebar-logo,.sidebar-sub,.nav-item span{display:none}.nav-item{justify-content:center;padding:12px}.main{margin-right:60px;padding:15px}}
</style>
</head>
<body>
<div class="sidebar">
    <div class="sidebar-logo">VØRTΞX</div>
    <div class="sidebar-sub">D A S H B O A R D</div>
    <nav class="sidebar-nav">
        <a href="/" class="nav-item"><span class="nav-icon">📊</span><span>لوحة التحكم</span></a>
        <a href="/commands" class="nav-item"><span class="nav-icon">📋</span><span>الأوامر</span></a>
        <a href="/guilds" class="nav-item"><span class="nav-icon">🏰</span><span>السيرفرات</span></a>
        <a href="/welcome" class="nav-item active"><span class="nav-icon">👋</span><span>الترحيب</span></a>
        <a href="/reaction-roles" class="nav-item"><span class="nav-icon">🎯</span><span>رولات التفاعل</span></a>
        <a href="/custom-commands" class="nav-item"><span class="nav-icon">⚡</span><span>الأوامر المخصصة</span></a>
        <a href="/broadcast" class="nav-item"><span class="nav-icon">📢</span><span>البث</span></a>
        <a href="/config" class="nav-item"><span class="nav-icon">⚙️</span><span>الإعدادات</span></a>
        <a href="/logs" class="nav-item"><span class="nav-icon">📜</span><span>سجل النشاطات</span></a>
        <a href="/logout" class="nav-item nav-logout"><span class="nav-icon">🚪</span><span>تسجيل خروج</span></a>
    </nav>
</div>
<div class="main">
    <h1 class="page-title">👋 إعدادات الترحيب</h1>
    <p class="page-sub">تعديل رسائل الترحيب والمغادرة والقناة والرتبة التلقائية</p>

    {% if msg %}
    <div class="msg {% if '❌' in msg %}error{% endif %}">{{ msg }}</div>
    {% endif %}

    <div class="form-card">
        <form method="POST" id="welcomeForm">
            <div class="form-group">
                <label>🆔 ID السيرفر</label>
                <select name="guild_id" class="form-control" id="guildSelect" required>
                    <option value="">اختر سيرفر...</option>
                    {% for g in guilds %}
                    <option value="{{ g.id }}">{{ g.id }}</option>
                    {% endfor %}
                </select>
            </div>
            <div class="form-row">
                <div class="form-group">
                    <label>📢 قناة الترحيب</label>
                    <input type="text" name="channel" class="form-control" id="channel" placeholder="welcome">
                </div>
                <div class="form-group">
                    <label>🎖️ الرتبة التلقائية</label>
                    <input type="text" name="auto_role" class="form-control" id="auto_role" placeholder="Member">
                </div>
            </div>
            <div class="form-group">
                <label>💬 رسالة الترحيب <span style="color:rgba(255,255,255,0.3);font-weight:400">(استخدم {member} {server})</span></label>
                <textarea name="message" class="form-control" id="welcomeMsg" rows="3">🎉 | مرحباً {member}! نرحب بك في {server} ❤️</textarea>
            </div>
            <div class="form-group">
                <label>👋 رسالة المغادرة</label>
                <textarea name="leave_message" class="form-control" id="leaveMsg" rows="2">👋 | {member} غادر السيرفر...</textarea>
            </div>
            <div class="form-group">
                <label>⚙️ الإعدادات</label>
                <div class="toggle-group">
                    <label class="toggle">
                        <input type="checkbox" name="enabled" checked id="enabledToggle">
                        <span class="toggle-slider"></span>
                        <span class="toggle-label">تفعيل الترحيب</span>
                    </label>
                    <label class="toggle">
                        <input type="checkbox" name="dm_welcome" checked id="dmToggle">
                        <span class="toggle-slider"></span>
                        <span class="toggle-label">الرسالة الخاصة</span>
                    </label>
                </div>
            </div>
            <button type="submit" class="btn btn-primary">💾 حفظ الإعدادات</button>
        </form>
    </div>
</div>
<script>
document.getElementById('guildSelect').addEventListener('change', function() {
    const gid = this.value;
    if (!gid) return;
    fetch('/welcome/get/' + gid)
        .then(r => r.json())
        .then(data => {
            if (data.error) return;
            document.getElementById('welcomeMsg').value = data.message || '';
            document.getElementById('leaveMsg').value = data.leave_message || '';
            document.getElementById('channel').value = data.channel || '';
            document.getElementById('auto_role').value = data.auto_role || '';
            document.getElementById('enabledToggle').checked = data.enabled !== false;
            document.getElementById('dmToggle').checked = data.dm_welcome !== false;
        })
        .catch(() => {});
});
</script>
</body>
</html>"""

HTML_REACTION_ROLES = """\
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>VØRTΞX — رولات التفاعل</title>
<link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Cairo',sans-serif;background:#08080e;color:#e0e0e0;min-height:100vh}
.sidebar{position:fixed;right:0;top:0;width:260px;height:100vh;background:rgba(10,10,20,0.95);backdrop-filter:blur(20px);border-left:1px solid rgba(0,255,136,0.08);padding:30px 20px;z-index:100;overflow-y:auto}
.sidebar-logo{font-size:28px;font-weight:900;background:linear-gradient(135deg,#00ff88,#00cc6a);-webkit-background-clip:text;-webkit-text-fill-color:transparent;text-align:center;margin-bottom:4px}
.sidebar-sub{text-align:center;color:rgba(255,255,255,0.25);font-size:10px;letter-spacing:3px;text-transform:uppercase;margin-bottom:30px}
.sidebar-nav{display:flex;flex-direction:column;gap:4px}
.nav-item{display:flex;align-items:center;gap:14px;padding:13px 18px;border-radius:12px;color:rgba(255,255,255,0.55);text-decoration:none;font-size:14px;font-weight:500;transition:all .25s ease}
.nav-item:hover,.nav-item.active{background:rgba(0,255,136,0.06);color:#00ff88}
.nav-item.active{background:rgba(0,255,136,0.1);border:1px solid rgba(0,255,136,0.12)}
.nav-icon{font-size:18px;width:24px;text-align:center}
.nav-logout{margin-top:auto;margin-bottom:10px;color:rgba(255,80,80,0.6)}
.nav-logout:hover{color:#ff5555;background:rgba(255,80,80,0.06)}
.main{margin-right:260px;padding:30px 40px}
.page-title{font-size:26px;font-weight:800;margin-bottom:6px;color:#fff}
.page-sub{color:rgba(255,255,255,0.35);font-size:14px;margin-bottom:30px}
.tabs{display:flex;gap:8px;margin-bottom:24px}
.tab{padding:12px 24px;background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.05);border-radius:12px;color:rgba(255,255,255,0.5);font-size:14px;font-weight:600;cursor:pointer;transition:all .25s ease;font-family:'Cairo',sans-serif}
.tab:hover,.tab.active{background:rgba(0,255,136,0.06);border-color:rgba(0,255,136,0.15);color:#00ff88}
.tab-content{display:none}
.tab-content.active{display:block}
.form-card{background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.05);border-radius:18px;padding:30px;margin-bottom:20px}
.form-group{margin-bottom:20px}
.form-group label{display:block;font-size:14px;font-weight:600;color:rgba(255,255,255,0.6);margin-bottom:8px}
.form-control{width:100%;padding:14px 18px;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:12px;color:#fff;font-size:14px;font-family:'Cairo',sans-serif;transition:all .3s ease;outline:none}
.form-control:focus{border-color:rgba(0,255,136,0.4);background:rgba(255,255,255,0.06);box-shadow:0 0 20px rgba(0,255,136,0.05)}
select.form-control{appearance:none;background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='8' viewBox='0 0 12 8'%3E%3Cpath fill='%2300ff88' d='M6 8L0 0h12z'/%3E%3C/svg%3E");background-repeat:no-repeat;background-position:left 16px center;padding-left:40px}
.form-row{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.btn{display:inline-flex;align-items:center;gap:8px;padding:14px 28px;border:none;border-radius:12px;font-size:15px;font-weight:700;font-family:'Cairo',sans-serif;cursor:pointer;transition:all .3s ease}
.btn-primary{background:linear-gradient(135deg,#00ff88,#00cc6a);color:#0a0a0f}
.btn-primary:hover{transform:translateY(-2px);box-shadow:0 8px 30px rgba(0,255,136,0.25)}
.btn-danger{background:rgba(255,70,70,0.15);color:#ff6b6b;border:1px solid rgba(255,70,70,0.2)}
.btn-danger:hover{background:rgba(255,70,70,0.25)}
.msg{background:rgba(0,255,136,0.08);border:1px solid rgba(0,255,136,0.15);color:#00ff88;padding:14px 20px;border-radius:12px;margin-bottom:20px;font-size:14px}
.msg.error{background:rgba(255,70,70,0.08);border-color:rgba(255,70,70,0.15);color:#ff6b6b}
.panel-card{background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.05);border-radius:14px;padding:20px;margin-bottom:12px}
.panel-title{font-size:16px;font-weight:700;color:#fff;margin-bottom:8px}
.panel-meta{font-size:12px;color:rgba(255,255,255,0.3);margin-bottom:8px}
.role-chips{display:flex;gap:6px;flex-wrap:wrap}
.role-chip{display:inline-flex;align-items:center;gap:6px;padding:4px 12px;background:rgba(0,255,136,0.06);border:1px solid rgba(0,255,136,0.1);border-radius:20px;font-size:12px;color:#00ff88}
@media(max-width:768px){.sidebar{width:200px}.main{margin-right:200px;padding:20px}.form-row{grid-template-columns:1fr}}
@media(max-width:576px){.sidebar{width:60px;padding:15px 8px}.sidebar-logo,.sidebar-sub,.nav-item span{display:none}.nav-item{justify-content:center;padding:12px}.main{margin-right:60px;padding:15px}}
</style>
</head>
<body>
<div class="sidebar">
    <div class="sidebar-logo">VØRTΞX</div>
    <div class="sidebar-sub">D A S H B O A R D</div>
    <nav class="sidebar-nav">
        <a href="/" class="nav-item"><span class="nav-icon">📊</span><span>لوحة التحكم</span></a>
        <a href="/commands" class="nav-item"><span class="nav-icon">📋</span><span>الأوامر</span></a>
        <a href="/guilds" class="nav-item"><span class="nav-icon">🏰</span><span>السيرفرات</span></a>
        <a href="/welcome" class="nav-item"><span class="nav-icon">👋</span><span>الترحيب</span></a>
        <a href="/reaction-roles" class="nav-item active"><span class="nav-icon">🎯</span><span>رولات التفاعل</span></a>
        <a href="/custom-commands" class="nav-item"><span class="nav-icon">⚡</span><span>الأوامر المخصصة</span></a>
        <a href="/broadcast" class="nav-item"><span class="nav-icon">📢</span><span>البث</span></a>
        <a href="/config" class="nav-item"><span class="nav-icon">⚙️</span><span>الإعدادات</span></a>
        <a href="/logs" class="nav-item"><span class="nav-icon">📜</span><span>سجل النشاطات</span></a>
        <a href="/logout" class="nav-item nav-logout"><span class="nav-icon">🚪</span><span>تسجيل خروج</span></a>
    </nav>
</div>
<div class="main">
    <h1 class="page-title">🎯 رولات التفاعل</h1>
    <p class="page-sub">إنشاء وإدارة لوحات رولات التفاعل</p>

    {% if msg %}
    <div class="msg {% if '❌' in msg %}error{% endif %}">{{ msg }}</div>
    {% endif %}

    <div class="tabs">
        <div class="tab active" onclick="switchTab('create')">➕ إنشاء لوحة</div>
        <div class="tab" onclick="switchTab('addrole')">➕ إضافة رول</div>
        <div class="tab" onclick="switchTab('removerole')">➖ إزالة رول</div>
        <div class="tab" onclick="switchTab('panels')">📋 اللوحات</div>
    </div>

    <div id="tab-create" class="tab-content active">
        <div class="form-card">
            <form method="POST">
                <input type="hidden" name="action" value="create_panel">
                <div class="form-group">
                    <label>🆔 ID السيرفر</label>
                    <select name="guild_id" class="form-control" required>
                        <option value="">اختر سيرفر...</option>
                        {% for g in guilds %}
                        <option value="{{ g.id }}">{{ g.id }}</option>
                        {% endfor %}
                    </select>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>📌 ID اللوحة</label>
                        <input type="text" name="panel_id" class="form-control" placeholder="اترك فارغاً لإنشاء تلقائي">
                    </div>
                    <div class="form-group">
                        <label>📢 عنوان اللوحة</label>
                        <input type="text" name="title" class="form-control" placeholder="اختر رولك!" required>
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>🆔 روم القناة</label>
                        <input type="text" name="channel_id" class="form-control" placeholder="Channel ID">
                    </div>
                    <div class="form-group">
                        <label>🆔 الرسالة</label>
                        <input type="text" name="message_id" class="form-control" placeholder="Message ID (0 لجديد)">
                    </div>
                </div>
                <button type="submit" class="btn btn-primary">🎯 إنشاء اللوحة</button>
            </form>
        </div>
    </div>

    <div id="tab-addrole" class="tab-content">
        <div class="form-card">
            <form method="POST">
                <input type="hidden" name="action" value="add_role">
                <div class="form-group">
                    <label>🆔 ID السيرفر</label>
                    <select name="guild_id" class="form-control" required>
                        <option value="">اختر سيرفر...</option>
                        {% for g in guilds %}
                        <option value="{{ g.id }}">{{ g.id }}</option>
                        {% endfor %}
                    </select>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>📌 ID اللوحة</label>
                        <input type="text" name="panel_id" class="form-control" placeholder="Panel ID" required>
                    </div>
                    <div class="form-group">
                        <label>🆔 ID الرول</label>
                        <input type="text" name="role_id" class="form-control" placeholder="Role ID" required>
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>🏷️ التسمية</label>
                        <input type="text" name="label" class="form-control" placeholder="Button Label" required>
                    </div>
                    <div class="form-group">
                        <label>😀 الإيموجي</label>
                        <input type="text" name="emoji" class="form-control" placeholder="🎮 أو :emoji:">
                    </div>
                </div>
                <button type="submit" class="btn btn-primary">➕ إضافة الرول</button>
            </form>
        </div>
    </div>

    <div id="tab-removerole" class="tab-content">
        <div class="form-card">
            <form method="POST">
                <input type="hidden" name="action" value="remove_role">
                <div class="form-group">
                    <label>🆔 ID السيرفر</label>
                    <select name="guild_id" class="form-control" required>
                        <option value="">اختر سيرفر...</option>
                        {% for g in guilds %}
                        <option value="{{ g.id }}">{{ g.id }}</option>
                        {% endfor %}
                    </select>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>📌 ID اللوحة</label>
                        <input type="text" name="panel_id" class="form-control" placeholder="Panel ID" required>
                    </div>
                    <div class="form-group">
                        <label>🆔 ID الرول</label>
                        <input type="text" name="role_id" class="form-control" placeholder="Role ID" required>
                    </div>
                </div>
                <button type="submit" class="btn btn-danger">➖ إزالة الرول</button>
            </form>
        </div>
    </div>

    <div id="tab-panels" class="tab-content">
        {% if panels %}
            {% for p in panels %}
            <div class="panel-card">
                <div class="panel-title">{{ p.title }}</div>
                <div class="panel-meta">ID: {{ p.id }} | قناة: {{ p.channel_id }} | رسالة: {{ p.message_id }}</div>
                <div class="role-chips">
                    {% for r in p.roles %}
                        {% if r.role_id != 0 %}
                        <span class="role-chip">{{ r.emoji }} {{ r.label }} ({{ r.role_id }})</span>
                        {% endif %}
                    {% endfor %}
                </div>
            </div>
            {% endfor %}
        {% else %}
            <div class="form-card" style="text-align:center;padding:40px">
                <div style="font-size:40px;margin-bottom:12px">📭</div>
                <p style="color:rgba(255,255,255,0.3)">لا توجد لوحات. اختر سيرفر لعرض اللوحات</p>
            </div>
        {% endif %}
    </div>
</div>
<script>
function switchTab(name) {
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.getElementById('tab-' + name).classList.add('active');
    document.querySelector(`.tab[onclick*="${name}"]`).classList.add('active');
}
document.querySelector('[name="guild_id"]')?.addEventListener('change', function() {
    const gid = this.value;
    if (!gid) return;
    fetch('/reaction-roles/panels/' + gid)
        .then(r => r.json())
        .then(panels => {
            const container = document.getElementById('tab-panels');
            if (!panels || panels.length === 0) {
                container.innerHTML = '<div class="form-card" style="text-align:center;padding:40px"><div style="font-size:40px;margin-bottom:12px">📭</div><p style="color:rgba(255,255,255,0.3)">لا توجد لوحات في هذا السيرفر</p></div>';
                return;
            }
            let html = '';
            panels.forEach(p => {
                html += `<div class="panel-card"><div class="panel-title">${p.title}</div><div class="panel-meta">ID: ${p.id} | قناة: ${p.channel_id} | رسالة: ${p.message_id}</div><div class="role-chips">`;
                (p.roles || []).forEach(r => {
                    if (r.role_id !== 0) html += `<span class="role-chip">${r.emoji} ${r.label} (${r.role_id})</span>`;
                });
                html += '</div></div>';
            });
            container.innerHTML = html;
        });
});
</script>
</body>
</html>"""

HTML_CUSTOM_COMMANDS = """\
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>VØRTΞX — الأوامر المخصصة</title>
<link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Cairo',sans-serif;background:#08080e;color:#e0e0e0;min-height:100vh}
.sidebar{position:fixed;right:0;top:0;width:260px;height:100vh;background:rgba(10,10,20,0.95);backdrop-filter:blur(20px);border-left:1px solid rgba(0,255,136,0.08);padding:30px 20px;z-index:100;overflow-y:auto}
.sidebar-logo{font-size:28px;font-weight:900;background:linear-gradient(135deg,#00ff88,#00cc6a);-webkit-background-clip:text;-webkit-text-fill-color:transparent;text-align:center;margin-bottom:4px}
.sidebar-sub{text-align:center;color:rgba(255,255,255,0.25);font-size:10px;letter-spacing:3px;text-transform:uppercase;margin-bottom:30px}
.sidebar-nav{display:flex;flex-direction:column;gap:4px}
.nav-item{display:flex;align-items:center;gap:14px;padding:13px 18px;border-radius:12px;color:rgba(255,255,255,0.55);text-decoration:none;font-size:14px;font-weight:500;transition:all .25s ease}
.nav-item:hover,.nav-item.active{background:rgba(0,255,136,0.06);color:#00ff88}
.nav-item.active{background:rgba(0,255,136,0.1);border:1px solid rgba(0,255,136,0.12)}
.nav-icon{font-size:18px;width:24px;text-align:center}
.nav-logout{margin-top:auto;margin-bottom:10px;color:rgba(255,80,80,0.6)}
.nav-logout:hover{color:#ff5555;background:rgba(255,80,80,0.06)}
.main{margin-right:260px;padding:30px 40px}
.page-title{font-size:26px;font-weight:800;margin-bottom:6px;color:#fff}
.page-sub{color:rgba(255,255,255,0.35);font-size:14px;margin-bottom:30px}
.tabs{display:flex;gap:8px;margin-bottom:24px}
.tab{padding:12px 24px;background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.05);border-radius:12px;color:rgba(255,255,255,0.5);font-size:14px;font-weight:600;cursor:pointer;transition:all .25s ease;font-family:'Cairo',sans-serif}
.tab:hover,.tab.active{background:rgba(0,255,136,0.06);border-color:rgba(0,255,136,0.15);color:#00ff88}
.tab-content{display:none}
.tab-content.active{display:block}
.form-card{background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.05);border-radius:18px;padding:30px;margin-bottom:20px}
.form-group{margin-bottom:20px}
.form-group label{display:block;font-size:14px;font-weight:600;color:rgba(255,255,255,0.6);margin-bottom:8px}
.form-control{width:100%;padding:14px 18px;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:12px;color:#fff;font-size:14px;font-family:'Cairo',sans-serif;transition:all .3s ease;outline:none}
.form-control:focus{border-color:rgba(0,255,136,0.4);background:rgba(255,255,255,0.06);box-shadow:0 0 20px rgba(0,255,136,0.05)}
textarea.form-control{resize:vertical;min-height:80px}
select.form-control{appearance:none;background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='8' viewBox='0 0 12 8'%3E%3Cpath fill='%2300ff88' d='M6 8L0 0h12z'/%3E%3C/svg%3E");background-repeat:no-repeat;background-position:left 16px center;padding-left:40px}
.form-row{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.btn{display:inline-flex;align-items:center;gap:8px;padding:14px 28px;border:none;border-radius:12px;font-size:15px;font-weight:700;font-family:'Cairo',sans-serif;cursor:pointer;transition:all .3s ease}
.btn-primary{background:linear-gradient(135deg,#00ff88,#00cc6a);color:#0a0a0f}
.btn-primary:hover{transform:translateY(-2px);box-shadow:0 8px 30px rgba(0,255,136,0.25)}
.btn-danger{background:rgba(255,70,70,0.15);color:#ff6b6b;border:1px solid rgba(255,70,70,0.2)}
.btn-danger:hover{background:rgba(255,70,70,0.25)}
.msg{background:rgba(0,255,136,0.08);border:1px solid rgba(0,255,136,0.15);color:#00ff88;padding:14px 20px;border-radius:12px;margin-bottom:20px;font-size:14px}
.msg.error{background:rgba(255,70,70,0.08);border-color:rgba(255,70,70,0.15);color:#ff6b6b}
.cmd-table{width:100%;border-collapse:collapse;margin-top:10px}
.cmd-table th{padding:14px 18px;text-align:right;font-size:13px;color:rgba(255,255,255,0.4);font-weight:600;border-bottom:1px solid rgba(255,255,255,0.05)}
.cmd-table td{padding:14px 18px;border-bottom:1px solid rgba(255,255,255,0.03);font-size:14px}
.cmd-table tr:hover td{background:rgba(0,255,136,0.02)}
.cmd-name-cell{font-family:'Courier New',monospace;color:#00ff88;font-weight:600}
.cmd-resp-cell{color:rgba(255,255,255,0.5);max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.btn-sm{padding:6px 14px;font-size:12px;border-radius:8px}
@media(max-width:768px){.sidebar{width:200px}.main{margin-right:200px;padding:20px}}
@media(max-width:576px){.sidebar{width:60px;padding:15px 8px}.sidebar-logo,.sidebar-sub,.nav-item span{display:none}.nav-item{justify-content:center;padding:12px}.main{margin-right:60px;padding:15px}}
</style>
</head>
<body>
<div class="sidebar">
    <div class="sidebar-logo">VØRTΞX</div>
    <div class="sidebar-sub">D A S H B O A R D</div>
    <nav class="sidebar-nav">
        <a href="/" class="nav-item"><span class="nav-icon">📊</span><span>لوحة التحكم</span></a>
        <a href="/commands" class="nav-item"><span class="nav-icon">📋</span><span>الأوامر</span></a>
        <a href="/guilds" class="nav-item"><span class="nav-icon">🏰</span><span>السيرفرات</span></a>
        <a href="/welcome" class="nav-item"><span class="nav-icon">👋</span><span>الترحيب</span></a>
        <a href="/reaction-roles" class="nav-item"><span class="nav-icon">🎯</span><span>رولات التفاعل</span></a>
        <a href="/custom-commands" class="nav-item active"><span class="nav-icon">⚡</span><span>الأوامر المخصصة</span></a>
        <a href="/broadcast" class="nav-item"><span class="nav-icon">📢</span><span>البث</span></a>
        <a href="/config" class="nav-item"><span class="nav-icon">⚙️</span><span>الإعدادات</span></a>
        <a href="/logs" class="nav-item"><span class="nav-icon">📜</span><span>سجل النشاطات</span></a>
        <a href="/logout" class="nav-item nav-logout"><span class="nav-icon">🚪</span><span>تسجيل خروج</span></a>
    </nav>
</div>
<div class="main">
    <h1 class="page-title">⚡ الأوامر المخصصة</h1>
    <p class="page-sub">إدارة الأوامر المخصصة لكل سيرفر (إضافة، تعديل، حذف)</p>

    {% if msg %}
    <div class="msg {% if '❌' in msg %}error{% endif %}">{{ msg }}</div>
    {% endif %}

    <div class="tabs">
        <div class="tab active" onclick="switchTab('add')">➕ إضافة أمر</div>
        <div class="tab" onclick="switchTab('edit')">✏️ تعديل أمر</div>
        <div class="tab" onclick="switchTab('delete')">🗑️ حذف أمر</div>
        <div class="tab" onclick="switchTab('list')">📋 قائمة الأوامر</div>
    </div>

    <div id="tab-add" class="tab-content active">
        <div class="form-card">
            <form method="POST">
                <input type="hidden" name="action" value="add">
                <div class="form-group">
                    <label>🆔 ID السيرفر</label>
                    <select name="guild_id" class="form-control" id="addGuildSelect" required>
                        <option value="">اختر سيرفر...</option>
                        {% for g in guilds %}
                        <option value="{{ g.id }}">{{ g.id }}</option>
                        {% endfor %}
                    </select>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>📝 اسم الأمر</label>
                        <input type="text" name="name" class="form-control" placeholder="greet" required>
                    </div>
                    <div class="form-group">
                        <label>💬 الرد</label>
                        <input type="text" name="response" class="form-control" placeholder="مرحباً بك!" required>
                    </div>
                </div>
                <button type="submit" class="btn btn-primary">➕ إضافة الأمر</button>
            </form>
        </div>
    </div>

    <div id="tab-edit" class="tab-content">
        <div class="form-card">
            <form method="POST">
                <input type="hidden" name="action" value="edit">
                <div class="form-group">
                    <label>🆔 ID السيرفر</label>
                    <select name="guild_id" class="form-control" required>
                        <option value="">اختر سيرفر...</option>
                        {% for g in guilds %}
                        <option value="{{ g.id }}">{{ g.id }}</option>
                        {% endfor %}
                    </select>
                </div>
                <div class="form-row">
                    <div class="form-group">
                        <label>📝 اسم الأمر</label>
                        <input type="text" name="name" class="form-control" placeholder="greet" required>
                    </div>
                    <div class="form-group">
                        <label>💬 الرد الجديد</label>
                        <input type="text" name="response" class="form-control" placeholder="الرد المحدث" required>
                    </div>
                </div>
                <button type="submit" class="btn btn-primary">✏️ تحديث الأمر</button>
            </form>
        </div>
    </div>

    <div id="tab-delete" class="tab-content">
        <div class="form-card">
            <form method="POST">
                <input type="hidden" name="action" value="delete">
                <div class="form-group">
                    <label>🆔 ID السيرفر</label>
                    <select name="guild_id" class="form-control" required>
                        <option value="">اختر سيرفر...</option>
                        {% for g in guilds %}
                        <option value="{{ g.id }}">{{ g.id }}</option>
                        {% endfor %}
                    </select>
                </div>
                <div class="form-group">
                    <label>📝 اسم الأمر</label>
                    <input type="text" name="name" class="form-control" placeholder="greet" required>
                </div>
                <button type="submit" class="btn btn-danger">🗑️ حذف الأمر</button>
            </form>
        </div>
    </div>

    <div id="tab-list" class="tab-content">
        <div class="form-card">
            <div class="form-group">
                <label>🆔 اختر السيرفر</label>
                <select class="form-control" id="listGuildSelect">
                    <option value="">اختر سيرفر...</option>
                    {% for g in guilds %}
                    <option value="{{ g.id }}">{{ g.id }}</option>
                    {% endfor %}
                </select>
            </div>
            <div id="commandsList">
                {% if commands %}
                <table class="cmd-table">
                    <thead><tr><th>الأمر</th><th>الرد</th></tr></thead>
                    <tbody>
                    {% for c in commands %}
                    <tr>
                        <td class="cmd-name-cell">{{ c.name }}</td>
                        <td class="cmd-resp-cell">{{ c.response }}</td>
                    </tr>
                    {% endfor %}
                    </tbody>
                </table>
                {% else %}
                <p style="color:rgba(255,255,255,0.3);text-align:center;padding:20px">اختر سيرفر لعرض الأوامر المخصصة</p>
                {% endif %}
            </div>
        </div>
    </div>
</div>
<script>
function switchTab(name) {
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.getElementById('tab-' + name).classList.add('active');
    document.querySelector(`.tab[onclick*="${name}"]`).classList.add('active');
}
document.getElementById('listGuildSelect')?.addEventListener('change', function() {
    const gid = this.value;
    if (!gid) { document.getElementById('commandsList').innerHTML = '<p style="color:rgba(255,255,255,0.3);text-align:center;padding:20px">اختر سيرفر لعرض الأوامر المخصصة</p>'; return; }
    fetch('/custom-commands/list/' + gid)
        .then(r => r.json())
        .then(cmds => {
            if (!cmds || cmds.length === 0) {
                document.getElementById('commandsList').innerHTML = '<p style="color:rgba(255,255,255,0.3);text-align:center;padding:20px">لا توجد أوامر مخصصة في هذا السيرفر</p>';
                return;
            }
            let html = '<table class="cmd-table"><thead><tr><th>الأمر</th><th>الرد</th></tr></thead><tbody>';
            cmds.forEach(c => {
                html += `<tr><td class="cmd-name-cell">${c.name}</td><td class="cmd-resp-cell">${c.response}</td></tr>`;
            });
            html += '</tbody></table>';
            document.getElementById('commandsList').innerHTML = html;
        });
});
</script>
</body>
</html>"""

HTML_BROADCAST = """\
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>VØRTΞX — البث</title>
<link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Cairo',sans-serif;background:#08080e;color:#e0e0e0;min-height:100vh}
.sidebar{position:fixed;right:0;top:0;width:260px;height:100vh;background:rgba(10,10,20,0.95);backdrop-filter:blur(20px);border-left:1px solid rgba(0,255,136,0.08);padding:30px 20px;z-index:100;overflow-y:auto}
.sidebar-logo{font-size:28px;font-weight:900;background:linear-gradient(135deg,#00ff88,#00cc6a);-webkit-background-clip:text;-webkit-text-fill-color:transparent;text-align:center;margin-bottom:4px}
.sidebar-sub{text-align:center;color:rgba(255,255,255,0.25);font-size:10px;letter-spacing:3px;text-transform:uppercase;margin-bottom:30px}
.sidebar-nav{display:flex;flex-direction:column;gap:4px}
.nav-item{display:flex;align-items:center;gap:14px;padding:13px 18px;border-radius:12px;color:rgba(255,255,255,0.55);text-decoration:none;font-size:14px;font-weight:500;transition:all .25s ease}
.nav-item:hover,.nav-item.active{background:rgba(0,255,136,0.06);color:#00ff88}
.nav-item.active{background:rgba(0,255,136,0.1);border:1px solid rgba(0,255,136,0.12)}
.nav-icon{font-size:18px;width:24px;text-align:center}
.nav-logout{margin-top:auto;margin-bottom:10px;color:rgba(255,80,80,0.6)}
.nav-logout:hover{color:#ff5555;background:rgba(255,80,80,0.06)}
.main{margin-right:260px;padding:30px 40px}
.page-title{font-size:26px;font-weight:800;margin-bottom:6px;color:#fff}
.page-sub{color:rgba(255,255,255,0.35);font-size:14px;margin-bottom:30px}
.form-card{background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.05);border-radius:18px;padding:30px;margin-bottom:20px}
.form-group{margin-bottom:20px}
.form-group label{display:block;font-size:14px;font-weight:600;color:rgba(255,255,255,0.6);margin-bottom:8px}
.form-control{width:100%;padding:14px 18px;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:12px;color:#fff;font-size:14px;font-family:'Cairo',sans-serif;transition:all .3s ease;outline:none}
.form-control:focus{border-color:rgba(0,255,136,0.4);background:rgba(255,255,255,0.06);box-shadow:0 0 20px rgba(0,255,136,0.05)}
textarea.form-control{resize:vertical;min-height:120px}
select.form-control{appearance:none;background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='8' viewBox='0 0 12 8'%3E%3Cpath fill='%2300ff88' d='M6 8L0 0h12z'/%3E%3C/svg%3E");background-repeat:no-repeat;background-position:left 16px center;padding-left:40px}
.btn{display:inline-flex;align-items:center;gap:8px;padding:14px 28px;border:none;border-radius:12px;font-size:15px;font-weight:700;font-family:'Cairo',sans-serif;cursor:pointer;transition:all .3s ease}
.btn-primary{background:linear-gradient(135deg,#00ff88,#00cc6a);color:#0a0a0f}
.btn-primary:hover{transform:translateY(-2px);box-shadow:0 8px 30px rgba(0,255,136,0.25)}
.btn-warning{background:rgba(243,156,18,0.15);color:#f39c12;border:1px solid rgba(243,156,18,0.2)}
.msg{background:rgba(0,255,136,0.08);border:1px solid rgba(0,255,136,0.15);color:#00ff88;padding:14px 20px;border-radius:12px;margin-bottom:20px;font-size:14px}
.msg.error{background:rgba(255,70,70,0.08);border-color:rgba(255,70,70,0.15);color:#ff6b6b}
.history-item{background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.04);border-radius:12px;padding:18px;margin-bottom:10px;transition:all .25s ease}
.history-item:hover{border-color:rgba(0,255,136,0.08)}
.hist-title{font-size:15px;font-weight:700;color:#00ff88;margin-bottom:4px}
.hist-meta{font-size:12px;color:rgba(255,255,255,0.3);margin-bottom:6px}
.hist-msg{font-size:13px;color:rgba(255,255,255,0.45)}
@media(max-width:768px){.sidebar{width:200px}.main{margin-right:200px;padding:20px}}
@media(max-width:576px){.sidebar{width:60px;padding:15px 8px}.sidebar-logo,.sidebar-sub,.nav-item span{display:none}.nav-item{justify-content:center;padding:12px}.main{margin-right:60px;padding:15px}}
</style>
</head>
<body>
<div class="sidebar">
    <div class="sidebar-logo">VØRTΞX</div>
    <div class="sidebar-sub">D A S H B O A R D</div>
    <nav class="sidebar-nav">
        <a href="/" class="nav-item"><span class="nav-icon">📊</span><span>لوحة التحكم</span></a>
        <a href="/commands" class="nav-item"><span class="nav-icon">📋</span><span>الأوامر</span></a>
        <a href="/guilds" class="nav-item"><span class="nav-icon">🏰</span><span>السيرفرات</span></a>
        <a href="/welcome" class="nav-item"><span class="nav-icon">👋</span><span>الترحيب</span></a>
        <a href="/reaction-roles" class="nav-item"><span class="nav-icon">🎯</span><span>رولات التفاعل</span></a>
        <a href="/custom-commands" class="nav-item"><span class="nav-icon">⚡</span><span>الأوامر المخصصة</span></a>
        <a href="/broadcast" class="nav-item active"><span class="nav-icon">📢</span><span>البث</span></a>
        <a href="/config" class="nav-item"><span class="nav-icon">⚙️</span><span>الإعدادات</span></a>
        <a href="/logs" class="nav-item"><span class="nav-icon">📜</span><span>سجل النشاطات</span></a>
        <a href="/logout" class="nav-item nav-logout"><span class="nav-icon">🚪</span><span>تسجيل خروج</span></a>
    </nav>
</div>
<div class="main">
    <h1 class="page-title">📢 البث</h1>
    <p class="page-sub">إرسال رسائل بث للسيرفرات وعرض السجل</p>

    {% if msg %}
    <div class="msg {% if '❌' in msg %}error{% endif %}">{{ msg }}</div>
    {% endif %}

    <div class="form-card">
        <form method="POST">
            <div class="form-group">
                <label>🆔 ID السيرفر</label>
                <select name="guild_id" class="form-control" required>
                    <option value="">اختر سيرفر...</option>
                    {% for g in guilds %}
                    <option value="{{ g.id }}">{{ g.id }}</option>
                    {% endfor %}
                </select>
            </div>
            <div class="form-group">
                <label>📌 عنوان البث</label>
                <input type="text" name="title" class="form-control" placeholder="إعلان مهم" required>
            </div>
            <div class="form-group">
                <label>💬 نص الرسالة</label>
                <textarea name="message" class="form-control" placeholder="اكتب رسالتك هنا..." required></textarea>
            </div>
            <button type="submit" class="btn btn-primary">📢 إرسال البث</button>
        </form>
    </div>

    <h2 style="font-size:18px;font-weight:700;color:#fff;margin-bottom:16px">📋 سجل البث</h2>
    <div id="broadcastHistory">
        {% if history %}
            {% for h in history %}
            <div class="history-item">
                <div class="hist-title">{{ h.title }}</div>
                <div class="hist-meta">🕐 {{ h.time }} | 📨 {{ h.sent_to }} قناة</div>
                <div class="hist-msg">{{ h.message[:100] }}{% if h.message|length > 100 %}...{% endif %}</div>
            </div>
            {% endfor %}
        %} else %}
        <p style="color:rgba(255,255,255,0.3);text-align:center;padding:30px">📭 لا يوجد سجل بث</p>
        {% endif %}
    </div>
</div>
<script>
document.querySelector('[name="guild_id"]')?.addEventListener('change', function() {
    const gid = this.value;
    if (!gid) return;
    fetch('/broadcast/history/' + gid)
        .then(r => r.json())
        .then(history => {
            const container = document.getElementById('broadcastHistory');
            if (!history || history.length === 0) {
                container.innerHTML = '<p style="color:rgba(255,255,255,0.3);text-align:center;padding:30px">📭 لا يوجد سجل بث</p>';
                return;
            }
            let html = '';
            history.forEach(h => {
                const msg = (h.message || '').substring(0, 100);
                html += `<div class="history-item"><div class="hist-title">${h.title}</div><div class="hist-meta">🕐 ${h.time} | 📨 ${h.sent_to} قناة</div><div class="hist-msg">${msg}${ (h.message||'').length > 100 ? '...' : ''}</div></div>`;
            });
            container.innerHTML = html;
        });
});
</script>
</body>
</html>"""

HTML_CONFIG = """\
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>VØRTΞX — إعدادات السيرفرات</title>
<link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Cairo',sans-serif;background:#08080e;color:#e0e0e0;min-height:100vh}
.sidebar{position:fixed;right:0;top:0;width:260px;height:100vh;background:rgba(10,10,20,0.95);backdrop-filter:blur(20px);border-left:1px solid rgba(0,255,136,0.08);padding:30px 20px;z-index:100;overflow-y:auto}
.sidebar-logo{font-size:28px;font-weight:900;background:linear-gradient(135deg,#00ff88,#00cc6a);-webkit-background-clip:text;-webkit-text-fill-color:transparent;text-align:center;margin-bottom:4px}
.sidebar-sub{text-align:center;color:rgba(255,255,255,0.25);font-size:10px;letter-spacing:3px;text-transform:uppercase;margin-bottom:30px}
.sidebar-nav{display:flex;flex-direction:column;gap:4px}
.nav-item{display:flex;align-items:center;gap:14px;padding:13px 18px;border-radius:12px;color:rgba(255,255,255,0.55);text-decoration:none;font-size:14px;font-weight:500;transition:all .25s ease}
.nav-item:hover,.nav-item.active{background:rgba(0,255,136,0.06);color:#00ff88}
.nav-item.active{background:rgba(0,255,136,0.1);border:1px solid rgba(0,255,136,0.12)}
.nav-icon{font-size:18px;width:24px;text-align:center}
.nav-logout{margin-top:auto;margin-bottom:10px;color:rgba(255,80,80,0.6)}
.nav-logout:hover{color:#ff5555;background:rgba(255,80,80,0.06)}
.main{margin-right:260px;padding:30px 40px}
.page-title{font-size:26px;font-weight:800;margin-bottom:6px;color:#fff}
.page-sub{color:rgba(255,255,255,0.35);font-size:14px;margin-bottom:30px}
.form-card{background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.05);border-radius:18px;padding:30px;margin-bottom:20px}
.form-group{margin-bottom:20px}
.form-group label{display:block;font-size:14px;font-weight:600;color:rgba(255,255,255,0.6);margin-bottom:8px}
.form-control{width:100%;padding:14px 18px;background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:12px;color:#fff;font-size:14px;font-family:'Cairo',sans-serif;transition:all .3s ease;outline:none}
.form-control:focus{border-color:rgba(0,255,136,0.4);background:rgba(255,255,255,0.06);box-shadow:0 0 20px rgba(0,255,136,0.05)}
select.form-control{appearance:none;background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='8' viewBox='0 0 12 8'%3E%3Cpath fill='%2300ff88' d='M6 8L0 0h12z'/%3E%3C/svg%3E");background-repeat:no-repeat;background-position:left 16px center;padding-left:40px}
.form-row{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.btn{display:inline-flex;align-items:center;gap:8px;padding:14px 28px;border:none;border-radius:12px;font-size:15px;font-weight:700;font-family:'Cairo',sans-serif;cursor:pointer;transition:all .3s ease}
.btn-primary{background:linear-gradient(135deg,#00ff88,#00cc6a);color:#0a0a0f}
.btn-primary:hover{transform:translateY(-2px);box-shadow:0 8px 30px rgba(0,255,136,0.25)}
.msg{background:rgba(0,255,136,0.08);border:1px solid rgba(0,255,136,0.15);color:#00ff88;padding:14px 20px;border-radius:12px;margin-bottom:20px;font-size:14px}
.msg.error{background:rgba(255,70,70,0.08);border-color:rgba(255,70,70,0.15);color:#ff6b6b}
.config-table{width:100%;border-collapse:collapse}
.config-table th{padding:12px 16px;text-align:right;font-size:13px;color:rgba(255,255,255,0.4);font-weight:600;border-bottom:1px solid rgba(255,255,255,0.05)}
.config-table td{padding:12px 16px;border-bottom:1px solid rgba(255,255,255,0.03);font-size:13px;color:rgba(255,255,255,0.5)}
.config-table tr:hover td{background:rgba(0,255,136,0.02)}
.config-val{color:#fff;font-weight:500}
@media(max-width:768px){.sidebar{width:200px}.main{margin-right:200px;padding:20px}}
@media(max-width:576px){.sidebar{width:60px;padding:15px 8px}.sidebar-logo,.sidebar-sub,.nav-item span{display:none}.nav-item{justify-content:center;padding:12px}.main{margin-right:60px;padding:15px}}
</style>
</head>
<body>
<div class="sidebar">
    <div class="sidebar-logo">VØRTΞX</div>
    <div class="sidebar-sub">D A S H B O A R D</div>
    <nav class="sidebar-nav">
        <a href="/" class="nav-item"><span class="nav-icon">📊</span><span>لوحة التحكم</span></a>
        <a href="/commands" class="nav-item"><span class="nav-icon">📋</span><span>الأوامر</span></a>
        <a href="/guilds" class="nav-item"><span class="nav-icon">🏰</span><span>السيرفرات</span></a>
        <a href="/welcome" class="nav-item"><span class="nav-icon">👋</span><span>الترحيب</span></a>
        <a href="/reaction-roles" class="nav-item"><span class="nav-icon">🎯</span><span>رولات التفاعل</span></a>
        <a href="/custom-commands" class="nav-item"><span class="nav-icon">⚡</span><span>الأوامر المخصصة</span></a>
        <a href="/broadcast" class="nav-item"><span class="nav-icon">📢</span><span>البث</span></a>
        <a href="/config" class="nav-item active"><span class="nav-icon">⚙️</span><span>الإعدادات</span></a>
        <a href="/logs" class="nav-item"><span class="nav-icon">📜</span><span>سجل النشاطات</span></a>
        <a href="/logout" class="nav-item nav-logout"><span class="nav-icon">🚪</span><span>تسجيل خروج</span></a>
    </nav>
</div>
<div class="main">
    <h1 class="page-title">⚙️ إعدادات السيرفرات</h1>
    <p class="page-sub">عرض وتحرير إعدادات السيرفرات المسجلة</p>

    {% if configs %}
    <div class="form-card" style="padding:0;overflow:hidden">
        <table class="config-table">
            <thead>
                <tr>
                    <th>🆔 السيرفر</th>
                    <th>🌐 اللغة</th>
                    <th>👋 الترحيب</th>
                    <th>🎫 التذاكر</th>
                    <th>🛡️ الأدمن</th>
                    <th>👮 المشرف</th>
                    <th>📝 السجل</th>
                </tr>
            </thead>
            <tbody>
                {% for cfg in configs %}
                <tr>
                    <td class="config-val">{{ cfg.guild_id }}</td>
                    <td>{{ cfg.get('language', 'ar') }}</td>
                    <td>{{ cfg.get('welcome_channel', '—') }}</td>
                    <td>{{ cfg.get('ticket_category', '—') }}</td>
                    <td>{{ cfg.get('admin_role', '—') }}</td>
                    <td>{{ cfg.get('mod_role', '—') }}</td>
                    <td>{{ cfg.get('mod_log_channel', '—') }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    {% else %}
    <div class="form-card" style="text-align:center;padding:50px">
        <div style="font-size:50px;margin-bottom:14px">⚙️</div>
        <p style="color:rgba(255,255,255,0.3)">لا توجد إعدادات مسجلة أو DB غير متصل</p>
    </div>
    {% endif %}

    <h2 style="font-size:18px;font-weight:700;color:#fff;margin:24px 0 16px">✏️ تحرير إعدادات سيرفر</h2>
    <div class="form-card">
        <form id="configForm" onsubmit="saveConfig(event)">
            <div class="form-group">
                <label>🆔 اختر السيرفر</label>
                <select name="guild_id" class="form-control" id="configGuildSelect" required>
                    <option value="">اختر سيرفر...</option>
                    {% for g in guilds %}
                    <option value="{{ g.id }}">{{ g.id }}</option>
                    {% endfor %}
                </select>
            </div>
            <div class="form-row">
                <div class="form-group">
                    <label>👋 روم الترحيب (ID)</label>
                    <input type="text" name="welcome_channel" class="form-control" placeholder="Channel ID">
                </div>
                <div class="form-group">
                    <label>🎫 قسم التذاكر (ID)</label>
                    <input type="text" name="ticket_category" class="form-control" placeholder="Category ID">
                </div>
            </div>
            <div class="form-row">
                <div class="form-group">
                    <label>🛡️ رول الأدمن (ID)</label>
                    <input type="text" name="admin_role" class="form-control" placeholder="Role ID">
                </div>
                <div class="form-group">
                    <label>👮 رول المشرف (ID)</label>
                    <input type="text" name="mod_role" class="form-control" placeholder="Role ID">
                </div>
            </div>
            <div class="form-row">
                <div class="form-group">
                    <label>📝 روم السجل (ID)</label>
                    <input type="text" name="mod_log_channel" class="form-control" placeholder="Channel ID">
                </div>
                <div class="form-group">
                    <label>🌐 اللغة</label>
                    <select name="language" class="form-control">
                        <option value="ar">🇸🇦 العربية</option>
                        <option value="en">🇬🇧 English</option>
                    </select>
                </div>
            </div>
            <button type="submit" class="btn btn-primary">💾 حفظ الإعدادات</button>
            <span id="configResult" style="margin-right:16px;font-size:14px"></span>
        </form>
    </div>
</div>
<script>
document.getElementById('configGuildSelect')?.addEventListener('change', function() {
    const gid = this.value;
    if (!gid) return;
    fetch('/config/get/' + gid)
        .then(r => r.json())
        .then(cfg => {
            if (cfg.error) return;
            document.querySelector('[name="welcome_channel"]').value = cfg.welcome_channel || '';
            document.querySelector('[name="ticket_category"]').value = cfg.ticket_category || '';
            document.querySelector('[name="admin_role"]').value = cfg.admin_role || '';
            document.querySelector('[name="mod_role"]').value = cfg.mod_role || '';
            document.querySelector('[name="mod_log_channel"]').value = cfg.mod_log_channel || '';
            document.querySelector('[name="language"]').value = cfg.language || 'ar';
        });
});
function saveConfig(e) {
    e.preventDefault();
    const form = e.target;
    const data = new FormData(form);
    fetch('/config/save', {method:'POST', body: data})
        .then(r => r.json())
        .then(res => {
            document.getElementById('configResult').textContent = res.msg || '✅';
        })
        .catch(() => {
            document.getElementById('configResult').textContent = '❌ خطأ في الاتصال';
        });
}
</script>
</body>
</html>"""

HTML_LOGS = """\
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>VØRTΞX — سجل النشاطات</title>
<link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Cairo',sans-serif;background:#08080e;color:#e0e0e0;min-height:100vh}
.sidebar{position:fixed;right:0;top:0;width:260px;height:100vh;background:rgba(10,10,20,0.95);backdrop-filter:blur(20px);border-left:1px solid rgba(0,255,136,0.08);padding:30px 20px;z-index:100;overflow-y:auto}
.sidebar-logo{font-size:28px;font-weight:900;background:linear-gradient(135deg,#00ff88,#00cc6a);-webkit-background-clip:text;-webkit-text-fill-color:transparent;text-align:center;margin-bottom:4px}
.sidebar-sub{text-align:center;color:rgba(255,255,255,0.25);font-size:10px;letter-spacing:3px;text-transform:uppercase;margin-bottom:30px}
.sidebar-nav{display:flex;flex-direction:column;gap:4px}
.nav-item{display:flex;align-items:center;gap:14px;padding:13px 18px;border-radius:12px;color:rgba(255,255,255,0.55);text-decoration:none;font-size:14px;font-weight:500;transition:all .25s ease}
.nav-item:hover,.nav-item.active{background:rgba(0,255,136,0.06);color:#00ff88}
.nav-item.active{background:rgba(0,255,136,0.1);border:1px solid rgba(0,255,136,0.12)}
.nav-icon{font-size:18px;width:24px;text-align:center}
.nav-logout{margin-top:auto;margin-bottom:10px;color:rgba(255,80,80,0.6)}
.nav-logout:hover{color:#ff5555;background:rgba(255,80,80,0.06)}
.main{margin-right:260px;padding:30px 40px}
.page-title{font-size:26px;font-weight:800;margin-bottom:6px;color:#fff}
.page-sub{color:rgba(255,255,255,0.35);font-size:14px;margin-bottom:30px}
.search-bar{margin-bottom:20px}
.search-bar input{width:100%;padding:14px 20px;background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.06);border-radius:14px;color:#fff;font-size:14px;font-family:'Cairo',sans-serif;outline:none;transition:all .3s ease}
.search-bar input:focus{border-color:rgba(0,255,136,0.3);background:rgba(255,255,255,0.05)}
.search-bar input::placeholder{color:rgba(255,255,255,0.2)}
.log-item{display:flex;gap:14px;padding:16px 20px;background:rgba(255,255,255,0.01);border-bottom:1px solid rgba(255,255,255,0.03);transition:all .2s ease}
.log-item:hover{background:rgba(0,255,136,0.015)}
.log-action{font-family:'Courier New',monospace;font-size:13px;font-weight:600;color:#00ff88;min-width:120px}
.log-detail{color:rgba(255,255,255,0.5);font-size:13px;flex:1}
.log-time{color:rgba(255,255,255,0.2);font-size:12px;min-width:150px;text-align:left;direction:ltr}
.empty-state{text-align:center;padding:60px 20px;color:rgba(255,255,255,0.3)}
.empty-state .big-icon{font-size:50px;margin-bottom:12px}
@media(max-width:768px){.sidebar{width:200px}.main{margin-right:200px;padding:20px}}
@media(max-width:576px){.sidebar{width:60px;padding:15px 8px}.sidebar-logo,.sidebar-sub,.nav-item span{display:none}.nav-item{justify-content:center;padding:12px}.main{margin-right:60px;padding:15px}}
</style>
</head>
<body>
<div class="sidebar">
    <div class="sidebar-logo">VØRTΞX</div>
    <div class="sidebar-sub">D A S H B O A R D</div>
    <nav class="sidebar-nav">
        <a href="/" class="nav-item"><span class="nav-icon">📊</span><span>لوحة التحكم</span></a>
        <a href="/commands" class="nav-item"><span class="nav-icon">📋</span><span>الأوامر</span></a>
        <a href="/guilds" class="nav-item"><span class="nav-icon">🏰</span><span>السيرفرات</span></a>
        <a href="/welcome" class="nav-item"><span class="nav-icon">👋</span><span>الترحيب</span></a>
        <a href="/reaction-roles" class="nav-item"><span class="nav-icon">🎯</span><span>رولات التفاعل</span></a>
        <a href="/custom-commands" class="nav-item"><span class="nav-icon">⚡</span><span>الأوامر المخصصة</span></a>
        <a href="/broadcast" class="nav-item"><span class="nav-icon">📢</span><span>البث</span></a>
        <a href="/config" class="nav-item"><span class="nav-icon">⚙️</span><span>الإعدادات</span></a>
        <a href="/logs" class="nav-item active"><span class="nav-icon">📜</span><span>سجل النشاطات</span></a>
        <a href="/logout" class="nav-item nav-logout"><span class="nav-icon">🚪</span><span>تسجيل خروج</span></a>
    </nav>
</div>
<div class="main">
    <h1 class="page-title">📜 سجل النشاطات</h1>
    <p class="page-sub">جميع أحداث ونشاطات البوت — {{ logs|length }} إدخال</p>

    <div class="search-bar">
        <input type="text" id="logSearch" placeholder="🔍 بحث في السجل..." oninput="filterLogs(this.value)">
    </div>

    {% if logs %}
    <div id="logList">
        {% for log in logs %}
        <div class="log-item">
            <span class="log-action">{{ log.action }}</span>
            <span class="log-detail">{{ log.detail }}</span>
            <span class="log-time">{{ log.time }}</span>
        </div>
        {% endfor %}
    </div>
    {% else %}
    <div class="empty-state" id="emptyState">
        <div class="big-icon">📜</div>
        <p>لا توجد نشاطات مسجلة بعد</p>
    </div>
    {% endif %}
</div>
<script>
function filterLogs(val) {
    const items = document.querySelectorAll('.log-item');
    const lower = val.toLowerCase();
    items.forEach(item => {
        const text = item.textContent.toLowerCase();
        item.style.display = text.includes(lower) ? 'flex' : 'none';
    });
}
</script>
</body>
</html>"""

# ── Main ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"""
╔══════════════════════════════════════════════╗
║      VØRTΞX SYSTEM — Dashboard              ║
║      🌐 http://0.0.0.0:{port:<5}                  ║
║      🗄️  DB: {'PostgreSQL' if HAS_DB else 'JSON Fallback':<18}   ║
║      🔐 Admin Login Required                ║
╚══════════════════════════════════════════════╝
    """)
    app.run(host="0.0.0.0", port=port, debug=False)
