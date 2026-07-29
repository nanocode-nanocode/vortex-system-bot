#!/bin/bash
set -e

echo "🚀 VØRTΞX Host Setup - Codespace"

cd /workspaces/vortex-system-bot

# Install Python dependencies
pip install -q flask flask-limiter flask-cors gunicorn cryptography bcrypt discord.py Pillow pg8000 pyflakes 2>&1 | tail -3

# Ensure directories exist
mkdir -p data bots sites logs

# Download config from private gist
echo "📥 Downloading config..."
curl -sL -o config.json "https://gist.githubusercontent.com/nanocode-nanocode/91f8925ed98da6fc50c4c2a5c5fb42a0/raw/307d6cd9e99872a31b9d48c84b1513914f028171/config.json"
if [ -f config.json ] && [ -s config.json ]; then
    echo "✅ Config loaded"
else
    echo "❌ Failed to load config"
    exit 1
fi

# Create bot ZIP from repo files
echo "📦 Creating bot ZIP..."
mkdir -p /tmp/bot-zip
cp bot.py db.py config.json i18n.py requirements.txt /tmp/bot-zip/
mkdir -p /tmp/bot-zip/cogs
cp cogs/*.py /tmp/bot-zip/cogs/
cd /tmp/bot-zip
zip -r /workspaces/vortex-system-bot/bot-upload.zip . > /dev/null 2>&1
cd /workspaces/vortex-system-bot
rm -rf /tmp/bot-zip
echo "✅ Bot ZIP created"

# Create dashboard ZIP
echo "📦 Creating dashboard ZIP..."
mkdir -p /tmp/dash-zip
cp dashboard.py config.json /tmp/dash-zip/
mkdir -p /tmp/dash-zip/templates
cp templates/*.html /tmp/dash-zip/templates/
echo -e "flask>=3.0.0\nPillow>=10.0.0" > /tmp/dash-zip/requirements.txt
cd /tmp/dash-zip
zip -r /workspaces/vortex-system-bot/dash-upload.zip . > /dev/null 2>&1
cd /workspaces/vortex-system-bot
rm -rf /tmp/dash-zip
echo "✅ Dashboard ZIP created"

# Start the hosting panel
echo "▶️ Starting VORTEX HOSTING Panel..."
gunicorn --bind 0.0.0.0:8080 --workers 2 --timeout 120 --log-level info hosting-panel.main:app > /tmp/panel.log 2>&1 &
PANEL_PID=$!
echo "✅ Panel starting (PID: $PANEL_PID)"

# Wait for panel
for i in {1..10}; do
    sleep 2
    if curl -sf http://localhost:8080/login > /dev/null 2>&1; then
        echo "✅ Panel is UP on port 8080"
        break
    fi
    if [ $i -eq 10 ]; then
        echo "❌ Panel failed to start"
        cat /tmp/panel.log | tail -20
        exit 1
    fi
done

# Python setup
python3 << 'SETUP_EOF'
import urllib.request, urllib.parse, json, http.cookiejar, time, uuid

HOST = "http://localhost:8080"
PASSWORD = "VortexHost2026Secure"

cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

# Login
data = urllib.parse.urlencode({"password": PASSWORD}).encode()
opener.open(urllib.request.Request(f"{HOST}/login", data=data))
print("✅ Logged in")

# Upload bot ZIP
def upload_zip(path, endpoint, name_field="id"):
    with open(path, "rb") as f:
        data = f.read()
    boundary = uuid.uuid4().hex
    body = (
        b"--" + boundary.encode() + b"\r\n"
        + b'Content-Disposition: form-data; name="file"; filename="upload.zip"\r\n'
        + b"Content-Type: application/zip\r\n\r\n"
        + data
        + b"\r\n--" + boundary.encode() + b"--\r\n"
    )
    req = urllib.request.Request(
        f"{HOST}{endpoint}", data=body, method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
    )
    r = opener.open(req)
    return json.loads(r.read())

# Upload bot
resp = upload_zip("/workspaces/vortex-system-bot/bot-upload.zip", "/api/bot/upload")
print(f"✅ Bot upload: {resp}")
bot_id = resp.get("id") or resp.get("bot_id")

# Start bot
if bot_id:
    time.sleep(1)
    r = opener.open(urllib.request.Request(f"{HOST}/api/bot/{bot_id}/start", data=b"", method="POST"))
    print(f"✅ Bot start: {json.loads(r.read())}")

# Upload dashboard
resp2 = upload_zip("/workspaces/vortex-system-bot/dash-upload.zip", "/api/site/upload", "site_id")
print(f"✅ Dashboard upload: {resp2}")
site_id = resp2.get("site_id")

# Start dashboard
if site_id:
    time.sleep(1)
    r = opener.open(urllib.request.Request(f"{HOST}/api/site/{site_id}/start", data=b"", method="POST"))
    print(f"✅ Dashboard start: {json.loads(r.read())}")

# Final
time.sleep(2)
r = opener.open(urllib.request.Request(f"{HOST}/api/bots"))
bots = json.loads(r.read())
r2 = opener.open(urllib.request.Request(f"{HOST}/api/sites"))
sites = json.loads(r2.read())
for bid, bot in bots.items():
    print(f"\n🤖 Bot {bid}: alive={bot.get('process_alive')}")
for sid, site in sites.items():
    print(f"🌐 Dashboard {sid}: port={site.get('port')}, alive={site.get('process_alive')}")
SETUP_EOF

echo ""
echo "══════════════════════════════════════════════════"
echo "  ✅ VØRTΞX HOST is FULLY RUNNING!"
echo ""
echo "  📋 Summary:"
echo "  Panel:      http://localhost:8080"
echo "  Dashboard:  http://localhost:3000"
echo ""
echo "  🌐 Public URLs:"
echo "  Run: gh codespace ports visibility 3000:public"
echo "  Run: gh codespace ports visibility 8080:public"
echo "  Then run: gh codespace ports"
echo "══════════════════════════════════════════════════"
