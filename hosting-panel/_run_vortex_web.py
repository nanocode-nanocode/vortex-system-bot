#!/usr/bin/env python3
"""VØRTΞX Web App Runner — Starts a Flask/WSGI app on a dynamic port"""
import os, sys, signal, importlib.util
from pathlib import Path

SITE_DIR = Path(os.environ.get("SITE_DIR", "."))
MAIN_FILE = os.environ.get("MAIN_FILE", "dashboard.py")
PORT = int(os.environ.get("PORT", 5000))

sys.path.insert(0, str(SITE_DIR))
os.chdir(SITE_DIR)

# Install requirements if available
req_file = SITE_DIR / "requirements.txt"
if req_file.exists():
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "-r", str(req_file)])

os.environ["PORT"] = str(PORT)

# Import the app
spec = importlib.util.spec_from_file_location("app_module", SITE_DIR / MAIN_FILE)
app_module = importlib.util.module_from_spec(spec)
sys.modules["app_module"] = app_module
spec.loader.exec_module(app_module)

# Find Flask app
app = getattr(app_module, "app", None)
if app is None:
    for attr in ["application", "server", "create_app"]:
        obj = getattr(app_module, attr, None)
        if obj and callable(obj):
            app = obj()
            break

if app is None:
    print("ERROR: No Flask app found")
    sys.exit(1)

# Run
from werkzeug.serving import run_simple
print(f"Starting web app on port {PORT}...")
run_simple("0.0.0.0", PORT, app, use_reloader=False, use_debugger=False)
