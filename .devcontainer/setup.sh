#!/bin/bash
set -e

echo "🚀 VØRTΞX Host Setup - Codespace"

cd /workspaces/vortex-system-bot

# Download config from private gist
echo "📥 Downloading config..."
curl -sL -o config.json "https://gist.githubusercontent.com/nanocode-nanocode/91f8925ed98da6fc50c4c2a5c5fb42a0/raw/307d6cd9e99872a31b9d48c84b1513914f028171/config.json" 2>&1
ls -la config.json
echo "Config first 50 chars: $(head -c 50 config.json)"

echo ""
echo "📦 Installing Python packages..."
pip install flask --quiet 2>&1 | tail -1
pip install Pillow discord.py pg8000 gunicorn cryptography bcrypt 2>&1 | tail -1

echo ""
echo "▶️ Starting VORTEX HOSTING Panel on port 8080..."
cd hosting-panel
nohup python3 main.py > /tmp/panel.log 2>&1 &
echo "Panel PID: $!"

# Wait for panel
for i in 1 2 3 4 5 6 7 8 9 10; do
    sleep 1
    if curl -sf http://localhost:8080/login > /dev/null 2>&1; then
        echo "✅ Panel UP on port 8080"
        break
    fi
done

echo ""
echo "▶️ Starting Dashboard on port 3000..."
cd /workspaces/vortex-system-bot
PORT=3000 nohup python3 dashboard.py > /tmp/dash.log 2>&1 &
echo "Dashboard PID: $!"

for i in 1 2 3 4 5 6 7 8 9 10; do
    sleep 1
    if curl -sf http://localhost:3000/live > /dev/null 2>&1; then
        echo "✅ Dashboard UP on port 3000"
        break
    fi
done
# Check if it succeeded
if ! curl -sf http://localhost:3000/live > /dev/null 2>&1; then
    echo "⚠️ Dashboard failed to start. Log:"
    cat /tmp/dash.log
fi

echo ""
echo "▶️ Starting Bot..."
nohup python3 bot.py > /tmp/bot.log 2>&1 &
echo "Bot PID: $!"

sleep 2

echo ""
echo "═══════════════════════════════════════"
echo "  ✅ VØRTΞX HOST IS RUNNING!"
echo "  Panel:     http://localhost:8080"
echo "  Dashboard: http://localhost:3000"
echo "═══════════════════════════════════════"
echo ""
echo "Final processes:"
ps aux | grep python | grep -v grep | awk '{print $11, $2}'
