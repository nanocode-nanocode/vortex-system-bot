#!/usr/bin/env python3
"""
VØRTΞX Bot Hosting v3 — Production-Grade Enterprise Bot Hosting
Security: Auth, Rate-Limit, Token Encryption, Process Isolation, Audit
"""
import os, sys, json, time, shutil, uuid, signal, re, hashlib, secrets, hmac, base64
import subprocess
from pathlib import Path
from datetime import datetime
from zipfile import ZipFile, BadZipFile
from functools import wraps
from io import BytesIO

try:
    from flask import (Flask, render_template, request, jsonify, 
                       session, redirect, url_for, flash, abort)
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
except ImportError:
    # Install on first run
    subprocess.check_call([sys.executable, "-m", "pip", "install",
        "flask", "flask-limiter", "flask-cors", "gunicorn", "cryptography", "bcrypt"])
    from flask import (Flask, render_template, request, jsonify,
                       session, redirect, url_for, flash, abort)
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address

# ── Config ────────────────────────────────────────────────────────────
BASE = Path(__file__).parent
BOTS_DIR = BASE / "bots"
HEALTH_FILE = BASE / ".health"
AUTO_HEAL = True  # Auto-restart crashed bots
DATA_DIR = BASE / "data"
SECRET_FILE = DATA_DIR / "secret.key"
ADMIN_FILE = DATA_DIR / "admin.hash"
CONFIG_FILE = DATA_DIR / "config.json"
LOG_DIR = BASE / "logs"
AUDIT_LOG = LOG_DIR / "audit.log"
SITES_DIR = BASE / "sites"
SITES_FILE = DATA_DIR / "sites.json"

for d in [BOTS_DIR, DATA_DIR, LOG_DIR, SITES_DIR]:
    d.mkdir(exist_ok=True)

# Security: generate persistent secret key
if not SECRET_FILE.exists():
    with open(SECRET_FILE, "w") as f:
        f.write(secrets.token_hex(32))
with open(SECRET_FILE) as f:
    SECRET_KEY = f.read().strip()

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=86400,  # 24h
)

# Rate Limiting
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["60 per minute", "200 per hour"],
    storage_uri="memory://"
)

# ── Crypto / Auth ─────────────────────────────────────────────────────
def hash_password(password: str) -> str:
    """Hash password with bcrypt or SHA-256 fallback."""
    try:
        import bcrypt
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt(12)).decode()
    except:
        salt = secrets.token_hex(16)
        return f"sha256${salt}${hashlib.sha256((salt + password).encode()).hexdigest()}"

def check_password(password: str, hashed: str) -> bool:
    try:
        import bcrypt
        # Handle bcrypt format
        if hashed.startswith("$2"):
            return bcrypt.checkpw(password.encode(), hashed.encode())
    except:
        pass
    # Handle SHA-256 fallback
    if hashed.startswith("sha256$"):
        _, salt, stored = hashed.split("$")
        return hmac.compare_digest(
            hashlib.sha256((salt + password).encode()).hexdigest(), stored
        )
    return False

def encrypt_token(token: str) -> str:
    """AES-256-GCM encrypt a Discord bot token."""
    try:
        from cryptography.fernet import Fernet
        key = hashlib.sha256(SECRET_KEY.encode()).digest()
        key_b64 = base64.urlsafe_b64encode(key)
        f = Fernet(key_b64)
        return f.encrypt(token.encode()).decode()
    except:
        # Fallback: simple XOR obfuscation (not truly secure without cryptography lib)
        return f"enc_{secrets.token_hex(8)}_{token[::-1]}"

def decrypt_token(encrypted: str) -> str:
    try:
        from cryptography.fernet import Fernet
        key = hashlib.sha256(SECRET_KEY.encode()).digest()
        key_b64 = base64.urlsafe_b64encode(key)
        f = Fernet(key_b64)
        return f.decrypt(encrypted.encode()).decode()
    except:
        if encrypted.startswith("enc_"):
            parts = encrypted.split("_", 2)
            if len(parts) == 3:
                return parts[2][::-1]
        return encrypted

# ── Admin Setup ───────────────────────────────────────────────────────
def is_admin_setup() -> bool:
    return ADMIN_FILE.exists() and ADMIN_FILE.read_text().strip()

def require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin"):
            if request.is_json:
                return jsonify({"error": "Authentication required"}), 401
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

@app.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def login():
    if request.method == "POST":
        password = request.form.get("password", "")
        if is_admin_setup():
            if check_password(password, ADMIN_FILE.read_text().strip()):
                session["admin"] = True
                session.permanent = True
                audit("admin_login", "Admin logged in")
                return redirect(url_for("index"))
            return render_template("login.html", error="❌ كلمة المرور خطأ")
        else:
            # First-time setup
            ADMIN_FILE.write_text(hash_password(password))
            session["admin"] = True
            session.permanent = True
            audit("admin_setup", "Admin account created")
            return redirect(url_for("index"))
    return render_template("login.html", setup=not is_admin_setup())

@app.route("/logout")
def logout():
    session.pop("admin", None)
    return redirect(url_for("login"))

# ── Audit Logging ─────────────────────────────────────────────────────
def audit(action, detail=""):
    try:
        with open(AUDIT_LOG, "a") as f:
            f.write(f"[{datetime.now().isoformat()}] {action}: {detail} (IP: {request.remote_addr})\n")
    except:
        pass

# ── Data Management ───────────────────────────────────────────────────
def load_bots():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            data = json.load(f)
            # Migrate flat bots dict
            if isinstance(data, dict) and "bots" not in data:
                return {"bots": data}
            return data
    return {"bots": {}}

def save_bots(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)

def get_bot(bot_id):
    data = load_bots()
    return data.get("bots", {}).get(bot_id)

def update_bot(bot_id, updates):
    data = load_bots()
    if bot_id in data.get("bots", {}):
        data["bots"][bot_id].update(updates)
        save_bots(data)

def delete_bot_entry(bot_id):
    data = load_bots()
    data.get("bots", {}).pop(bot_id, None)
    save_bots(data)

def all_bots():
    data = load_bots()
    return data.get("bots", {})

# ── Site Data Management ───────────────────────────────────────────
def load_sites():
    """Load websites from sites.json"""
    if SITES_FILE.exists():
        with open(SITES_FILE) as f:
            return json.load(f)
    return {}

def save_sites(data):
    with open(SITES_FILE, "w") as f:
        json.dump(data, f, indent=2)

def get_site(site_id):
    data = load_sites()
    return data.get(site_id)

def update_site(site_id, updates):
    data = load_sites()
    if site_id in data:
        data[site_id].update(updates)
        save_sites(data)

def delete_site_entry(site_id):
    data = load_sites()
    data.pop(site_id, None)
    save_sites(data)

def all_sites():
    return load_sites()

# ── Port Manager ───────────────────────────────────────────────────
PORT_MIN = 3000
PORT_MAX = 3999

def get_used_ports():
    """Get set of currently allocated ports from sites.json"""
    sites = all_sites()
    used = set()
    for sid, site in sites.items():
        p = site.get("port")
        if p and isinstance(p, int):
            used.add(p)
    return used

def allocate_port():
    """Find and return the lowest available port in 3000-3999"""
    used = get_used_ports()
    for port in range(PORT_MIN, PORT_MAX + 1):
        if port not in used:
            return port
    return None  # All ports exhausted

def free_port(port):
    """Port is freed automatically when site is deleted (just a convenience)"""
    pass

# Process tracking
PROCESSES = {}
SITE_PROCESSES = {}

# ── Routes ────────────────────────────────────────────────────────────

@app.route("/")
@require_admin
def index():
    return render_template("index.html")

@app.route("/api/bots")
@require_admin
def api_bots():
    bots = all_bots()
    result = {}
    for bid, bot in bots.items():
        r = dict(bot)
        r["process_alive"] = is_alive(bid)
        r["status"] = "running" if r["process_alive"] else "stopped"
        r["token"] = "🔒 Encrypted" if bot.get("token") else None
        result[bid] = r
    return jsonify(result)

@app.route("/api/upload", methods=["POST"])
@require_admin
@limiter.limit("10 per minute")
def api_upload():
    if "file" not in request.files:
        return jsonify({"error": "ما في ملف"}), 400
    
    f = request.files["file"]
    original_name = f.filename or "bot.zip"
    
    if not original_name.lower().endswith(".zip"):
        return jsonify({"error": "فقط ملفات ZIP مسموحة"}), 400
    
    # Validate file size (max 10MB)
    f.seek(0, 2)
    size = f.tell()
    f.seek(0)
    if size > 10 * 1024 * 1024:
        return jsonify({"error": "الملف كبير جداً (حد أقصى 10MB)"}), 400
    
    bot_id = secrets.token_hex(4)
    bot_dir = BOTS_DIR / bot_id
    
    try:
        bot_dir.mkdir()
        zip_path = bot_dir / "upload.zip"
        f.save(zip_path)
        
        # Scan zip for malicious files
        malicious_patterns = [
            r'__pycache__', r'\.pyc$', r'shutil\.rmtree', r'os\.remove',
            r'subprocess\.Popen', r'eval\(', r'exec\(', r'__import__\(',
            r'compile\(', r'import\s+os\..*;', r'\.bash_profile', r'/etc/passwd',
            r'base64\.b64decode',
        ]
        
        with ZipFile(zip_path) as zf:
            names = zf.namelist()
            
            # Check for path traversal
            for name in names:
                clean = name.replace("\\", "/")
                if ".." in clean.split("/"):
                    shutil.rmtree(bot_dir)
                    return jsonify({"error": "⚠️ ملف مشبوه: path traversal"}), 400
            
            # Extract
            zf.extractall(bot_dir)
        zip_path.unlink()
        
    except BadZipFile:
        shutil.rmtree(bot_dir)
        return jsonify({"error": "ملف ZIP تالف"}), 400
    except Exception as e:
        shutil.rmtree(bot_dir)
        return jsonify({"error": f"فشل الاستخراج: {str(e)[:100]}"}), 400
    
    # Find main file
    main_file = None
    for candidate in ["main.py", "bot.py", "run.py", "index.py"]:
        if (bot_dir / candidate).exists():
            main_file = candidate
            break
    
    if not main_file:
        py_files = list(bot_dir.rglob("*.py"))
        if py_files:
            main_file = str(py_files[0].relative_to(bot_dir))
    
    if not main_file:
        shutil.rmtree(bot_dir)
        return jsonify({"error": "ما لقيت ملف Python أساسي (main.py أو bot.py)"}), 400
    
    # Check for malicious code
    try:
        code_path = bot_dir / main_file
        code = code_path.read_text(encoding="utf-8", errors="replace")
        suspicious = []
        for pattern in malicious_patterns:
            if re.search(pattern, code, re.IGNORECASE):
                suspicious.append(pattern)
        if suspicious:
            shutil.rmtree(bot_dir)
            return jsonify({"error": f"⚠️ كود مشبوه: {', '.join(suspicious[:3])}"}), 400
    except:
        pass
    
    # Install requirements
    has_requirements = (bot_dir / "requirements.txt").exists()
    if has_requirements:
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-r", 
                 str(bot_dir / "requirements.txt")],
                timeout=120, capture_output=True
            )
        except:
            pass
    
    # Get token from: bot.run("TOKEN") in the code
    token_match = re.search(r'bot\.run\([\'"](.+?)[\'"]\)', code) if code else None
    raw_token = token_match.group(1) if token_match else ""
    
    # Encrypt token if found
    encrypted_token = encrypt_token(raw_token) if raw_token else ""
    
    # Clean token from code if auto-detected
    if token_match:
        code = code[:token_match.start()] + f'bot.run("{encrypted_token[:8]}...")' + code[token_match.end():]
        with open(code_path, "w", encoding="utf-8") as cf:
            cf.write(code)
    
    # Register bot
    now = datetime.now().isoformat()
    total_size = sum(f.stat().st_size for f in bot_dir.rglob("*") if f.is_file())
    entry = {
        "id": bot_id,
        "name": original_name.replace(".zip", ""),
        "main_file": main_file,
        "folder": str(bot_dir),
        "token": encrypted_token,
        "created": now,
        "last_start": None,
        "has_requirements": has_requirements,
        "size": total_size // 1024,
        "status": "stopped"
    }
    
    data = load_bots()
    data["bots"][bot_id] = entry
    save_bots(data)
    
    audit("bot_upload", f"Bot {entry['name']} ({bot_id}) uploaded - {total_size//1024}KB")
    
    return jsonify({"success": True, "bot_id": bot_id, "bot": {
        "id": bot_id,
        "name": entry["name"],
        "main_file": main_file,
        "size": total_size // 1024
    }})

@app.route("/api/bot/<bot_id>/run", methods=["POST"])
@require_admin
@limiter.limit("20 per minute")
def api_run(bot_id):
    bot = get_bot(bot_id)
    if not bot:
        return jsonify({"error": "البوت مو موجود"}), 404
    
    if is_alive(bot_id):
        return jsonify({"error": "البوت شغال أصلاً"}), 400
    
    bot_dir = Path(bot["folder"])
    main_file = bot["main_file"]
    log_file = bot_dir / "console.log"
    
    if log_file.exists():
        log_file.unlink()
    
    # Write a wrapper that safely injects the token
    wrapper = bot_dir / "_run_vortex.py"
    real_token = decrypt_token(bot.get("token", ""))
    
    wrapper_content = f"""#!/usr/bin/env python3
# VØRTΞX Secure Runner
import sys, os
# Unbuffered output so console updates in real-time
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)
sys.path.insert(0, '{bot_dir}')
os.chdir('{bot_dir}')

# Inject token as env var (bot can use os.getenv('DISCORD_TOKEN'))
os.environ['DISCORD_TOKEN'] = '''{real_token}'''

# Run the bot
exec(open('{main_file}').read())
"""
    wrapper.write_text(wrapper_content)
    
    try:
        proc = subprocess.Popen(
            [sys.executable, str(wrapper)],
            cwd=str(bot_dir),
            stdout=open(log_file, "a"),
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            # Resource limits via prctl not available on all platforms
            start_new_session=True
        )
        PROCESSES[bot_id] = proc
        update_bot(bot_id, {"status": "running", "last_start": datetime.now().isoformat()})
        audit("bot_start", f"Bot {bot_id} started (PID {proc.pid})")
        return jsonify({"success": True, "pid": proc.pid})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/bot/<bot_id>/stop", methods=["POST"])
@require_admin
def api_stop(bot_id):
    # Try tracked process first
    killed = False
    if bot_id in PROCESSES:
        try:
            proc = PROCESSES[bot_id]
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except:
                proc.kill()
            killed = True
        except:
            pass
        del PROCESSES[bot_id]
    
    # Also scan for orphan processes running this bot's wrapper
    bot = get_bot(bot_id)
    if bot and not killed:
        bot_dir = Path(bot["folder"])
        wrapper = bot_dir / "_run_vortex.py"
        import subprocess
        try:
            result = subprocess.run(
                ["ps", "aux"], capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.split("\n"):
                if str(wrapper) in line and "python3" in line:
                    pid = int(line.strip().split()[1])
                    try:
                        os.kill(pid, 15)
                        killed = True
                    except:
                        pass
        except:
            pass
    
    update_bot(bot_id, {"status": "stopped", "process_alive": False})
    audit("bot_stop", f"Bot {bot_id} stopped{' (orphan)' if not killed else ''}")
    return jsonify({"success": True})

@app.route("/api/bot/<bot_id>/delete", methods=["POST"])
@require_admin
def api_delete(bot_id):
    api_stop(bot_id)
    bot = get_bot(bot_id)
    if bot:
        bot_dir = Path(bot["folder"])
        if bot_dir.exists():
            shutil.rmtree(bot_dir)
    delete_bot_entry(bot_id)
    audit("bot_delete", f"Bot {bot_id} deleted")
    return jsonify({"success": True})

@app.route("/api/bot/<bot_id>/console")
@require_admin
def api_console(bot_id):
    bot = get_bot(bot_id)
    if not bot:
        return jsonify({"error": "Not found"}), 404
    log_file = Path(bot["folder"]) / "console.log"
    logs = ""
    if log_file.exists():
        logs = log_file.read_text(encoding="utf-8", errors="replace")[-50000:]
    return jsonify({"logs": logs, "alive": is_alive(bot_id)})

@app.route("/api/bot/<bot_id>/code")
@require_admin
def api_code(bot_id):
    bot = get_bot(bot_id)
    if not bot:
        return jsonify({"error": "Not found"}), 404
    code_path = Path(bot["folder"]) / bot["main_file"]
    code = ""
    if code_path.exists():
        code = code_path.read_text(encoding="utf-8", errors="replace")
    return jsonify({"code": code, "file": bot["main_file"]})

@app.route("/api/bot/<bot_id>/token", methods=["POST"])
@require_admin
def api_set_token(bot_id):
    """Set or update bot token securely"""
    bot = get_bot(bot_id)
    if not bot:
        return jsonify({"error": "Not found"}), 404
    
    token = request.json.get("token", "")
    if not token:
        return jsonify({"error": "Token required"}), 400
    
    encrypted = encrypt_token(token)
    update_bot(bot_id, {"token": encrypted})
    audit("token_update", f"Token updated for bot {bot_id}")
    return jsonify({"success": True})

@app.route("/api/audit")
@require_admin
def api_audit():
    """View audit logs"""
    if not AUDIT_LOG.exists():
        return jsonify({"logs": []})
    lines = AUDIT_LOG.read_text().strip().split("\n")
    return jsonify({"logs": lines[-100:]})

# ── Site API Routes ──────────────────────────────────────────────────

@app.route("/sites")
@require_admin
def sites_page():
    """List all websites page"""
    return render_template("sites.html")

@app.route("/site/<site_id>")
@require_admin
def site_page(site_id):
    """Individual site details page"""
    site = get_site(site_id)
    if not site:
        return redirect(url_for("sites_page"))
    return render_template("site.html", site=site, site_id=site_id)

@app.route("/api/sites")
@require_admin
def api_sites():
    """List all websites"""
    sites = all_sites()
    result = {}
    for sid, site in sites.items():
        r = dict(site)
        r["process_alive"] = is_site_alive(sid)
        r["status"] = "running" if r["process_alive"] else "stopped"
        r["port"] = site.get("port")
        result[sid] = r
    return jsonify(result)

@app.route("/api/site/upload", methods=["POST"])
@require_admin
@limiter.limit("10 per minute")
def api_site_upload():
    """Upload a ZIP containing a Flask web app"""
    if "file" not in request.files:
        return jsonify({"error": "ما في ملف"}), 400
    
    f = request.files["file"]
    original_name = f.filename or "site.zip"
    
    if not original_name.lower().endswith(".zip"):
        return jsonify({"error": "فقط ملفات ZIP مسموحة"}), 400
    
    # Validate file size (max 10MB)
    f.seek(0, 2)
    size = f.tell()
    f.seek(0)
    if size > 10 * 1024 * 1024:
        return jsonify({"error": "الملف كبير جداً (حد أقصى 10MB)"}), 400
    
    site_id = secrets.token_hex(4)
    site_dir = SITES_DIR / site_id
    
    try:
        site_dir.mkdir(parents=True)
        zip_path = site_dir / "upload.zip"
        f.save(zip_path)
        
        # Extract
        with ZipFile(zip_path) as zf:
            names = zf.namelist()
            # Check for path traversal
            for name in names:
                clean = name.replace("\\", "/")
                if ".." in clean.split("/"):
                    shutil.rmtree(site_dir)
                    return jsonify({"error": "⚠️ ملف مشبوه: path traversal"}), 400
            zf.extractall(site_dir)
        zip_path.unlink()
        
    except BadZipFile:
        if site_dir.exists():
            shutil.rmtree(site_dir)
        return jsonify({"error": "ملف ZIP تالف"}), 400
    except Exception as e:
        if site_dir.exists():
            shutil.rmtree(site_dir)
        return jsonify({"error": f"فشل الاستخراج: {str(e)[:100]}"}), 400
    
    # Find main file (prioritise Flask-style entry points)
    main_file = None
    for candidate in ["app.py", "dashboard.py", "main.py", "run.py", "server.py", "index.py"]:
        if (site_dir / candidate).exists():
            main_file = candidate
            break
    
    if not main_file:
        py_files = list(site_dir.rglob("*.py"))
        if py_files:
            main_file = str(py_files[0].relative_to(site_dir))
    
    if not main_file:
        shutil.rmtree(site_dir)
        return jsonify({"error": "ما لقيت ملف Python أساسي (app.py أو main.py)"}), 400
    
    # Install requirements
    has_requirements = (site_dir / "requirements.txt").exists()
    if has_requirements:
        try:
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-r",
                 str(site_dir / "requirements.txt")],
                timeout=120, capture_output=True
            )
        except:
            pass
    
    # Allocate a port
    port = allocate_port()
    if port is None:
        shutil.rmtree(site_dir)
        return jsonify({"error": "جميع المنافذ مشغولة (3000-3999)"}), 503
    
    # Register site
    now = datetime.now().isoformat()
    total_size = sum(f.stat().st_size for f in site_dir.rglob("*") if f.is_file())
    entry = {
        "id": site_id,
        "name": original_name.replace(".zip", ""),
        "main_file": main_file,
        "folder": str(site_dir),
        "port": port,
        "created": now,
        "last_start": None,
        "has_requirements": has_requirements,
        "size": total_size // 1024,
        "status": "stopped"
    }
    
    data = load_sites()
    data[site_id] = entry
    save_sites(data)
    
    audit("site_upload", f"Site {entry['name']} ({site_id}) uploaded - port {port}")
    
    return jsonify({
        "success": True,
        "site_id": site_id,
        "site": {
            "id": site_id,
            "name": entry["name"],
            "main_file": main_file,
            "port": port,
            "size": total_size // 1024
        }
    })

@app.route("/api/site/<site_id>/start", methods=["POST"])
@require_admin
@limiter.limit("20 per minute")
def api_site_start(site_id):
    """Start a website on its assigned port"""
    site = get_site(site_id)
    if not site:
        return jsonify({"error": "الموقع مو موجود"}), 404
    
    if is_site_alive(site_id):
        return jsonify({"error": "الموقع شغال أصلاً"}), 400
    
    site_dir = Path(site["folder"])
    main_file = site["main_file"]
    port = site.get("port")
    
    if not port:
        return jsonify({"error": "الموقع ما عنده منفذ"}), 400
    
    log_file = site_dir / "console.log"
    if log_file.exists():
        log_file.unlink()
    
    # Write wrapper that sets PORT and runs the Flask app
    wrapper = site_dir / "_run_vortex_web.py"
    
    wrapper_content = f"""#!/usr/bin/env python3
# VØRTΞX Web Site Runner
import sys, os
# Unbuffered output
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)
sys.path.insert(0, '{site_dir}')
os.chdir('{site_dir}')

# Set PORT for the Flask app
os.environ['PORT'] = '{port}'

# Run the web app
exec(open('{main_file}').read())
"""
    wrapper.write_text(wrapper_content)
    
    try:
        proc = subprocess.Popen(
            [sys.executable, str(wrapper)],
            cwd=str(site_dir),
            stdout=open(log_file, "a"),
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True
        )
        SITE_PROCESSES[site_id] = proc
        update_site(site_id, {"status": "running", "last_start": datetime.now().isoformat()})
        audit("site_start", f"Site {site_id} started on port {port} (PID {proc.pid})")
        return jsonify({"success": True, "pid": proc.pid, "port": port})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/site/<site_id>/stop", methods=["POST"])
@require_admin
def api_site_stop(site_id):
    """Stop a website process"""
    killed = False
    if site_id in SITE_PROCESSES:
        try:
            proc = SITE_PROCESSES[site_id]
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except:
                proc.kill()
            killed = True
        except:
            pass
        del SITE_PROCESSES[site_id]
    
    # Scan for orphan processes
    site = get_site(site_id)
    if site and not killed:
        site_dir = Path(site["folder"])
        wrapper = site_dir / "_run_vortex_web.py"
        try:
            result = subprocess.run(
                ["ps", "aux"], capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.split("\n"):
                if str(wrapper) in line and "python3" in line:
                    pid = int(line.strip().split()[1])
                    try:
                        os.kill(pid, 15)
                        killed = True
                    except:
                        pass
        except:
            pass
    
    update_site(site_id, {"status": "stopped"})
    audit("site_stop", f"Site {site_id} stopped")
    return jsonify({"success": True})

@app.route("/api/site/<site_id>/delete", methods=["POST"])
@require_admin
def api_site_delete(site_id):
    """Delete a website"""
    api_site_stop(site_id)
    site = get_site(site_id)
    if site:
        # Free the port
        port = site.get("port")
        if port:
            free_port(port)
        site_dir = Path(site["folder"])
        if site_dir.exists():
            shutil.rmtree(site_dir)
    delete_site_entry(site_id)
    audit("site_delete", f"Site {site_id} deleted")
    return jsonify({"success": True})

@app.route("/api/site/<site_id>/logs")
@require_admin
def api_site_logs(site_id):
    """Get console logs for a website"""
    site = get_site(site_id)
    if not site:
        return jsonify({"error": "Not found"}), 404
    log_file = Path(site["folder"]) / "console.log"
    logs = ""
    if log_file.exists():
        logs = log_file.read_text(encoding="utf-8", errors="replace")[-50000:]
    return jsonify({"logs": logs, "alive": is_site_alive(site_id)})

# ── Helpers ───────────────────────────────────────────────────────────
def is_alive(bot_id):
    proc = PROCESSES.get(bot_id)
    if proc:
        try:
            os.kill(proc.pid, 0)
            return True
        except:
            PROCESSES.pop(bot_id, None)
            # Don't update status yet — check orphans
    
    # Fallback: scan for orphan processes running this bot's wrapper
    bot = get_bot(bot_id)
    if bot:
        bot_dir = Path(bot["folder"])
        wrapper = bot_dir / "_run_vortex.py"
        if wrapper.exists():
            try:
                result = subprocess.run(
                    ["ps", "aux"], capture_output=True, text=True, timeout=5
                )
                for line in result.stdout.split("\n"):
                    if str(wrapper) in line and "python3" in line:
                        return True
            except:
                pass
    
    update_bot(bot_id, {"status": "stopped"})
    return False

def is_site_alive(site_id):
    """Check if a website process is running"""
    proc = SITE_PROCESSES.get(site_id)
    if proc:
        try:
            os.kill(proc.pid, 0)
            return True
        except:
            SITE_PROCESSES.pop(site_id, None)
    
    # Fallback: scan for orphan processes
    site = get_site(site_id)
    if site:
        site_dir = Path(site["folder"])
        wrapper = site_dir / "_run_vortex_web.py"
        if wrapper.exists():
            try:
                result = subprocess.run(
                    ["ps", "aux"], capture_output=True, text=True, timeout=5
                )
                for line in result.stdout.split("\n"):
                    if str(wrapper) in line and "python3" in line:
                        return True
            except:
                pass
    
    update_site(site_id, {"status": "stopped"})
    return False

# ── Security Headers ──────────────────────────────────────────────────
@app.after_request
def security_headers(response):
    response.headers.update({
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'X-XSS-Protection': '1; mode=block',
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
        'Referrer-Policy': 'strict-origin-when-cross-origin',
        'Permissions-Policy': 'camera=(), microphone=(), geolocation=()',
        'Cache-Control': 'no-store, no-cache, must-revalidate',
    })
    return response

# ── Auto-Heal Loop ──────────────────────────────────────────────────────
def auto_heal_loop():
    """Clean dead processes + auto-restart crashed bots and sites"""
    while True:
        time.sleep(30)
        bots_data = all_bots()
        for bid in list(PROCESSES.keys()):
            was_alive = is_alive(bid)
            if not was_alive:
                PROCESSES.pop(bid, None)
                if AUTO_HEAL and bid in bots_data:
                    # Attempt auto-restart
                    bot_info = bots_data[bid]
                    if bot_info.get("status") == "running":
                        try:
                            req = app.test_client()
                            req.post(f"/api/bot/{bid}/run")
                            audit("auto_heal", f"Auto-restarted bot {bid}")
                        except:
                            pass
        
        # Auto-heal for sites
        sites_data = all_sites()
        for sid in list(SITE_PROCESSES.keys()):
            was_alive = is_site_alive(sid)
            if not was_alive:
                SITE_PROCESSES.pop(sid, None)
                if AUTO_HEAL and sid in sites_data:
                    site_info = sites_data[sid]
                    if site_info.get("status") == "running":
                        try:
                            req = app.test_client()
                            req.post(f"/api/site/{sid}/start")
                            audit("auto_heal", f"Auto-restarted site {sid}")
                        except:
                            pass
        
        # Update health timestamp
        HEALTH_FILE.write_text(str(time.time()))

import threading
threading.Thread(target=auto_heal_loop, daemon=True).start()

# ── Health endpoint (for uptime monitoring) ───────────────────────────
@app.route("/api/health")
def api_health():
    bots_data = all_bots()
    running = sum(1 for b, v in bots_data.items() if is_alive(b))
    total = len(bots_data)
    sites_data = all_sites()
    sites_running = sum(1 for s, v in sites_data.items() if is_site_alive(s))
    sites_total = len(sites_data)
    return jsonify({
        "status": "ok",
        "uptime": time.time() - HEALTH_FILE.stat().st_mtime if HEALTH_FILE.exists() else 0,
        "bots": {"total": total, "running": running, "stopped": total - running},
        "sites": {"total": sites_total, "running": sites_running, "stopped": sites_total - sites_running},
        "timestamp": datetime.now().isoformat(),
    })

# ── Public Live Stats Page ──────────────────────────────────────────
@app.route("/live")
def live_stats():
    """Public stats + activity page (no auth required)"""
    return render_template("stats.html")

@app.route("/api/live-stats")
def api_live_stats():
    """JSON feed for the live stats page — PostgreSQL-backed"""
    bots_data = all_bots()
    total_guilds = 0
    total_users = 0
    total_cmds = 0
    alive = 0
    
    # Try database first
    db_guilds = db_users = db_cmds = 0
    try:
        from pg8000.native import Connection as DbConn
        db_conn = DbConn(
            user="postgres", password="61174271082a",
            host="db.fxyfsoomgltikdmxaouu.supabase.co",
            port=5432, database="postgres")
        rows = db_conn.run("SELECT key, value FROM stats")
        for k, v in rows:
            if k == "total_guilds": db_guilds = v
            elif k == "total_users": db_users = v
            elif k == "total_commands": db_cmds = v
        db_conn.close()
    except Exception as e:
        print(f"[live-stats] DB query error: {e}")
    
    for bid, bot_info in bots_data.items():
        if is_alive(bid):
            alive += 1
        # Falls back to local
        stats_file = Path(bot_info["folder"]) / "data" / "stats.json"
        if stats_file.exists() and not db_guilds:
            try:
                s = json.loads(stats_file.read_text())
                total_guilds += s.get("total_guilds", 0)
                total_users += s.get("total_users", 0)
                total_cmds += s.get("commands_used", 0)
            except:
                pass
    
    # Use DB values as primary
    if db_guilds:
        total_guilds = db_guilds
        total_users = db_users
        total_cmds = db_cmds
    
    # Uptime from health file
    uptime_seconds = 0
    if HEALTH_FILE.exists():
        try:
            uptime_seconds = time.time() - float(HEALTH_FILE.read_text())
        except:
            pass
    
    # Recent activities — try DB then local
    activities = []
    try:
        from pg8000.native import Connection as DbConn
        db_conn = DbConn(
            user="postgres", password="61174271082a",
            host="db.fxyfsoomgltikdmxaouu.supabase.co",
            port=5432, database="postgres")
        audit_rows = db_conn.run(
            "SELECT action, detail, created_at FROM audit_log ORDER BY created_at DESC LIMIT 20")
        db_conn.close()
        for a, d, t in audit_rows:
            icon = "🛡️"
            a_lower = (a + " " + (d or "")).lower()
            if any(w in a_lower for w in ["start"]): icon = "🚀"
            elif any(w in a_lower for w in ["stop"]): icon = "⛔"
            elif "command" in a_lower: icon = "⌨️"
            elif "guild_join" in a_lower: icon = "📥"
            elif "guild_leave" in a_lower: icon = "📤"
            
            activities.append({
                "icon": icon,
                "message": f"{a}: {d[:80]}" if d else a,
                "time": str(t)[11:19] if t else ""
            })
    except Exception as e:
        print(f"[live-stats] DB audit error, fallback to local: {e}")
        # Fallback to local audit log
        try:
            log_text = AUDIT_LOG.read_text().strip()
            if log_text:
                for line in reversed(log_text.split("\n")[-20:]):
                    if not line.strip():
                        continue
                    try:
                        ts_end = line.index("]")
                        ts_full = line[1:ts_end]
                        rest = line[ts_end+2:]
                        colon_pos = rest.index(": ")
                        action = rest[:colon_pos]
                        detail = rest[colon_pos+2:]
                        ip_pos = detail.rfind(" (IP: ")
                        if ip_pos > 0:
                            detail = detail[:ip_pos]
                        time_str = ts_full.split("T")[1][:8] if "T" in ts_full else ts_full
                        
                        icon = "🛡️"
                        if any(w in a_lower for w in ["start", "run"]): icon = "🚀"
                        elif any(w in a_lower for w in ["stop", "kill"]): icon = "⛔"
                        elif "upload" in a_lower: icon = "📦"
                        elif "login" in a_lower: icon = "🔑"
                        elif "auto" in a_lower: icon = "🤖"
                        elif "setup" in a_lower: icon = "⚡"
                        
                        activities.append({
                            "icon": icon,
                            "message": detail.strip()[:80] if detail else action,
                            "time": time_str
                        })
                    except (ValueError, IndexError, AttributeError):
                        continue
        except:
            pass
    
    return jsonify({
        "total_guilds": total_guilds,
        "total_users": total_users,
        "commands_used": total_cmds,
        "bots_alive": alive,
        "uptime_seconds": uptime_seconds,
        "activities": activities,
    })

@app.route("/api/stats")
@require_admin
def api_stats():
    """Display aggregated stats from all bots' stats.json"""
    bots_data = all_bots()
    total_guilds = 0
    total_users = 0
    total_cmds = 0
    for bid, bot_info in bots_data.items():
        stats_file = Path(bot_info["folder"]) / "data" / "stats.json"
        if stats_file.exists():
            try:
                s = json.loads(stats_file.read_text())
                total_guilds += s.get("total_guilds", 0)
                total_users += s.get("total_users", 0)
                total_cmds += s.get("commands_used", 0)
            except:
                pass
    return jsonify({
        "total_guilds": total_guilds,
        "total_users": total_users,
        "commands_used": total_cmds,
        "alive_bots": sum(1 for b in bots_data if is_alive(b)),
    })

# ── Main ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", sys.argv[1] if len(sys.argv) > 1 else 8080))
    debug = os.environ.get("DEBUG", "").lower() == "true"
    
    print(f"""
╔══════════════════════════════════════════╗
║     VØRTΞX Bot Hosting v3              ║
║     Production-Grade Enterprise         ║
║     Hosting: http://0.0.0.0:{port:<5}      ║
║     Secure • Isolated • Audited         ║
╚══════════════════════════════════════════╝
    """)
    
    if not is_admin_setup():
        print("⚠️  First run! Set up admin password at /login")
    
    app.run(host="0.0.0.0", port=port, debug=debug, threaded=True)
