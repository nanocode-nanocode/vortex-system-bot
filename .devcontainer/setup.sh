#!/bin/bash
set -e

echo "🚀 VØRTΞX Host Setup - Codespace"

cd /workspaces/vortex-system-bot

# Install Python dependencies (background to not block)
pip install flask flask-limiter flask-cors gunicorn cryptography bcrypt discord.py Pillow pg8000 2>&1 | tail -3 &

# Download config from private gist
echo "📥 Downloading config..."
curl -sL -o config.json "https://gist.githubusercontent.com/nanocode-nanocode/91f8925ed98da6fc50c4c2a5c5fb42a0/raw/307d6cd9e99872a31b9d48c84b1513914f028171/config.json"

if [ ! -f config.json ] || [ ! -s config.json ]; then
    echo "⚠️ Config download failed, creating template"
    echo '{"token": "", "prefix": "!"}' > config.json
fi

# Ensure dirs
mkdir -p data bots sites logs

# Wait for pip
wait

# Start hosting panel directly (not via gunicorn - simpler)
echo "▶️ Starting VORTEX HOSTING Panel..."
cd /workspaces/vortex-system-bot/hosting-panel
python3 -c "
import sys
sys.path.insert(0, '.')
from main import app
from werkzeug.serving import run_simple
run_simple('0.0.0.0', 8080, app, use_reloader=False, use_debugger=False)
" > /tmp/panel.log 2>&1 &
PANEL_PID=$!
cd /workspaces/vortex-system-bot
echo "✅ Panel PID: $PANEL_PID"

# Wait for panel
for i in 1 2 3 4 5 6 7 8 9 10; do
    sleep 2
    if curl -sf http://localhost:8080/login > /dev/null 2>&1; then
        echo "✅ Panel UP"
        break
    fi
done

# Start the bot directly (not through the panel - simpler)
echo "▶️ Starting Bot directly..."
cd /workspaces/vortex-system-bot
nohup python3 bot.py > /tmp/bot.log 2>&1 &
BOT_PID=$!
echo "✅ Bot PID: $BOT_PID"

# Start dashboard directly on port 3000
echo "▶️ Starting Dashboard on port 3000..."
cd /workspaces/vortex-system-bot
nohup python3 -c "
import os
os.environ['PORT'] = '3000'
exec(open('dashboard.py').read())
" > /tmp/dash.log 2>&1 &
DASH_PID=$!
echo "✅ Dashboard PID: $DASH_PID"

sleep 3

echo ""
echo "═══════════════════════════════════════"
echo "  ✅ VØRTΞX HOST IS RUNNING!"
echo "  Panel:     port 8080"
echo "  Dashboard: port 3000"
echo "  Bot:       $(ps aux | grep bot.py | grep -v grep | wc -l) instances"
echo "═══════════════════════════════════════"
