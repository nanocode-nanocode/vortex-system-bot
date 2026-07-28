#!/usr/bin/env python3
"""
VØRTΞX System Bot — Web Dashboard (v2)
Responsive • Discord OAuth • Dark theme • Arabic
"""
import os, sys, json, hashlib, time, uuid, hmac
from pathlib import Path
from functools import wraps
from datetime import datetime, timedelta
from urllib.parse import urlencode
import urllib.request

from flask import (
    Flask, session, redirect, url_for, request,
    render_template, jsonify, flash
)

BASE = Path(__file__).parent
CONFIG_FILE = BASE / "config.json"

app = Flask(__name__)
app.secret_key = hashlib.sha256(b"VortexHost2026SecureDashboard").hexdigest()
app.permanent_session_lifetime = timedelta(hours=4)

# ── Config ────────────────────────────────────────────────────────────
with open(CONFIG_FILE) as f:
    CONFIG = json.load(f)

ADMIN_PASS_HASH = hashlib.sha256("VortexHost2026Secure".encode()).hexdigest()
CLIENT_ID = "1527818267455000847"
CLIENT_SECRET = os.environ.get("DISCORD_CLIENT_SECRET", "")
OAUTH_ENABLED = bool(CLIENT_SECRET)
DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "")

DISCORD_API = "https://discord.com/api/v10"

# ── DB ────────────────────────────────────────────────────────────────
HAS_DB = False
db_mod = None
try:
    sys.path.insert(0, str(BASE))
    import db as db_mod
    HAS_DB = True
except Exception as e:
    print(f"⚠️ DB: {e}")

# ── Helpers ───────────────────────────────────────────────────────────
DATA_FILE = BASE / "dashboard_data.json"
def load_data():
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text())
    return {}
def save_data(d):
    DATA_FILE.write_text(json.dumps(d, indent=2, default=str))

def need_auth(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if not session.get("logged_in"):
            return redirect(url_for("login_page"))
        return f(*a, **kw)
    return wrapper

def get_bot_guilds():
    """Get guilds from bot stats or API"""
    guilds = []
    if HAS_DB and db_mod:
        try:
            db = db_mod.get_db()
            if db:
                rows = db.run("SELECT action, detail, created_at FROM audit_log ORDER BY created_at DESC LIMIT 50")
                pass
        except: pass
    # Read from data file
    data = load_data()
    guilds = data.get("guilds", [])
    return guilds

def get_stats():
    """Get dashboard stats"""
    stats = {"guilds": 0, "users": 0, "commands": 0, "cogs": 0, "db_connected": False, "db_name": "—"}
    if HAS_DB and db_mod:
        try:
            all_stats = db_mod.get_all_stats()
            stats["guilds"] = all_stats.get("total_guilds", 0)
            stats["users"] = all_stats.get("total_users", 0)
            stats["commands"] = all_stats.get("total_commands", 0)
            stats["db_connected"] = True
            stats["db_name"] = "🐘 PostgreSQL (Supabase)"
        except:
            pass
    # Fallback
    data = load_data()
    if "guilds" in data:
        stats["guilds"] = len(data["guilds"]) if isinstance(data["guilds"], list) else stats["guilds"]
    stats["cogs"] = 12
    return stats

# ── Routes ────────────────────────────────────────────────────────────

@app.route("/")
@need_auth
def home():
    guilds = get_bot_guilds()
    stats = get_stats()
    audit = []
    if HAS_DB and db_mod:
        try:
            audit = db_mod.get_audit_log(limit=10)
            for a in audit:
                if hasattr(a.get("time"), "isoformat"):
                    a["time"] = a["time"].isoformat()[:19]
        except: pass
    return render_template("index.html", stats=stats, guilds=guilds, audit=audit,
                         error=request.args.get("error"), msg=request.args.get("msg"))

@app.route("/login", methods=["GET", "POST"])
def login_page():
    if session.get("logged_in"):
        return redirect(url_for("home"))
    
    error = None
    if request.method == "POST":
        pw = request.form.get("password", "")
        if hmac.compare_digest(hashlib.sha256(pw.encode()).hexdigest(), ADMIN_PASS_HASH):
            session.permanent = True
            session["logged_in"] = True
            session["user"] = {"username": "Admin", "id": 0, "avatar": None}
            return redirect(url_for("home"))
        else:
            error = "كلمة المرور خطأ!"
    
    oauth_url = ""
    if OAUTH_ENABLED:
        base_url = DASHBOARD_URL or request.host_url.rstrip("/")
        redirect_uri = f"{base_url}/oauth/callback"
        oauth_url = f"{DISCORD_API}/oauth2/authorize?{urlencode({
            'client_id': CLIENT_ID,
            'redirect_uri': redirect_uri,
            'response_type': 'code',
            'scope': 'identify guilds',
        })}"
    
    return render_template("login.html", oauth_enabled=OAUTH_ENABLED,
                         oauth_url=oauth_url, error=error)

@app.route("/oauth/callback")
def oauth_callback():
    code = request.args.get("code")
    if not code:
        return redirect(url_for("login_page"))
    
    try:
        # Exchange code for token
        base_url = DASHBOARD_URL or request.host_url.rstrip("/")
        redirect_uri = f"{base_url}/oauth/callback"
        data = urlencode({
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': redirect_uri,
        }).encode()
        req = urllib.request.Request(f"{DISCORD_API}/oauth2/token", data=data,
            headers={'Content-Type': 'application/x-www-form-urlencoded'})
        resp = json.loads(urllib.request.urlopen(req).read())
        access_token = resp.get("access_token")
        
        if not access_token:
            return redirect(url_for("login_page", error="فشل التوثيق"))
        
        # Get user info
        req = urllib.request.Request(f"{DISCORD_API}/users/@me",
            headers={'Authorization': f'Bearer {access_token}'})
        user = json.loads(urllib.request.urlopen(req).read())
        
        session.permanent = True
        session["logged_in"] = True
        session["user"] = {
            "id": user["id"],
            "username": user["username"],
            "avatar": user.get("avatar"),
            "global_name": user.get("global_name", ""),
        }
        session["access_token"] = access_token
        return redirect(url_for("home"))
    except Exception as e:
        return redirect(url_for("login_page", error=f"OAuth error: {str(e)[:50]}"))

@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login_page"))

@app.route("/guilds")
@need_auth
def guild_list():
    guilds = get_bot_guilds()
    return render_template("guilds.html", guilds=guilds)

@app.route("/guild/<int:guild_id>")
@need_auth
def guild_view(guild_id):
    guilds = get_bot_guilds()
    guild = next((g for g in guilds if g["id"] == guild_id), None)
    if not guild:
        return redirect(url_for("guild_list"))
    
    cfg = {"language": "ar"}
    if HAS_DB and db_mod:
        try:
            cfg = db_mod.get_guild_config(guild_id)
        except: pass
    
    commands = []
    if HAS_DB and db_mod:
        try:
            commands = db_mod.list_custom_commands(guild_id)
        except: pass
    
    audit = []
    if HAS_DB and db_mod:
        try:
            audit = db_mod.get_audit_log(guild_id=guild_id, limit=20)
            for a in audit:
                if hasattr(a.get("time"), "isoformat"):
                    a["time"] = a["time"].isoformat()[:19]
        except: pass
    
    return render_template("guild.html", guild=guild, cfg=cfg,
                         commands=commands, audit=audit, warns=0)

@app.route("/guild/<int:guild_id>/config", methods=["POST"])
@need_auth
def guild_config(guild_id):
    lang = request.form.get("language", "ar")
    if HAS_DB and db_mod:
        try:
            db_mod.set_guild_config(guild_id, language=lang)
        except: pass
    return redirect(f"/guild/{guild_id}?msg=✅ تم الحفظ!")

@app.route("/audit")
@need_auth
def audit_view():
    audit = []
    if HAS_DB and db_mod:
        try:
            audit = db_mod.get_audit_log(limit=50)
            for a in audit:
                if hasattr(a.get("time"), "isoformat"):
                    a["time"] = a["time"].isoformat()[:19]
        except: pass
    return render_template("audit.html", audit=audit)

@app.route("/api/stats")
def api_stats():
    stats = get_stats()
    return jsonify(stats)

@app.route("/live")
def live():
    return jsonify({"status": "ok", "service": "vortex-dashboard", "time": time.time()})

# ── Main ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"""
╔══════════════════════════════════════════════╗
║      VØRTΞX SYSTEM — Dashboard v2           ║
║      🌐 http://0.0.0.0:{port:<5}                  ║
║      🗄️  DB: {'PostgreSQL' if HAS_DB else 'JSON'}                     ║
║      🔐 {'Discord OAuth + ' if OAUTH_ENABLED else ''}Password Login        ║
╚══════════════════════════════════════════════╝
    """)
    app.run(host="0.0.0.0", port=port, debug=False)
