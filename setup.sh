#!/bin/bash
# =============================================================================
# setup.sh — TQQQ Bot v2.1 setup
# Run after uploading files: bash setup.sh
# =============================================================================

set -e

echo ""
echo "=============================================="
echo " TQQQ Adaptive Regime Bot v2.1 — Setup"
echo "=============================================="
echo ""

BOT_DIR="/home/ubuntu/tqqq-bot"

echo "[1/4] Installing Python packages..."
cd "$BOT_DIR"
source venv/bin/activate
pip install --quiet alpaca-py yfinance pandas numpy requests schedule pytz
echo "      ✅ Packages ready"

echo "[2/4] Setting timezone..."
sudo timedatectl set-timezone America/New_York
echo "      ✅ Timezone: America/New_York"

echo "[3/4] Reloading systemd service..."
sudo systemctl daemon-reload
sudo systemctl restart tqqq-bot
sleep 3
echo "      ✅ Service restarted"

echo "[4/4] Verifying files..."
REQUIRED=("config.py" "logger.py" "data.py" "strategy.py" "risk.py" "orders.py" "alerts.py" "reports.py" "bot.py")
ALL_OK=true
for f in "${REQUIRED[@]}"; do
    if [ -f "$BOT_DIR/$f" ]; then
        echo "      ✅ $f"
    else
        echo "      ❌ MISSING: $f"
        ALL_OK=false
    fi
done

echo ""
echo "=============================================="
if [ "$ALL_OK" = true ]; then
    echo " ✅ v2.1 Setup complete!"
else
    echo " ⚠️  Some files missing — check above"
fi
echo "=============================================="
echo ""
echo "Check bot status:  sudo systemctl status tqqq-bot"
echo "Watch live log:    tail -f $BOT_DIR/tqqq_bot.log"
echo ""
