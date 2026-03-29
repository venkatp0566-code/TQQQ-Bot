# 📈 TQQQ Adaptive Regime Bot

> **An open-source algorithmic trading bot that rotates between TQQQ (3x leveraged Nasdaq ETF) and SGOV (T-bill ETF) based on market regime, volatility, and breadth signals.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/)
[![Paper Trading](https://img.shields.io/badge/default-paper%20trading-green.svg)]()

---

## ⚠️ DISCLAIMER — READ FIRST

> **This project is for educational purposes only. It is NOT financial or investment advice. Leveraged ETFs like TQQQ can lose value extremely rapidly. You are solely responsible for any financial outcomes from using this software. The author(s) accept no liability for losses.**
>
> **See [DISCLAIMER.md](DISCLAIMER.md) for full terms. By using this software, you agree to them.**

---

## What It Does

The bot runs fully automatically on a cloud server (EC2 or similar). Every trading day at **3:55 PM ET**, it evaluates QQQ's trend, volatility, and market breadth through a 9-step decision tree and either:

- **Holds / buys TQQQ** — when the market is in a confirmed bull regime with manageable volatility
- **Holds / buys SGOV** — when the market is bearish, extremely volatile, or showing breadth collapse

Trades are **queued at 3:55 PM** and executed at **9:25 AM the next morning** after a pre-market gap check. A Telegram bot sends you real-time alerts for every decision.

---

## Strategy Overview

### Core Logic: 9-Step Decision Tree

The bot evaluates the following conditions in order every trading day. Steps that trigger a hard exit return immediately without checking further steps.

---

#### Step 1 — Master Switch (QQQ vs 200-day SMA)

| Condition | Result |
|-----------|--------|
| QQQ price > 200-day SMA | → Continue to Step 2 (BULL mode) |
| QQQ price ≤ 200-day SMA | → **100% SGOV** (BEAR regime, stop here) |

This is the primary filter. If the Nasdaq-100 is below its long-term average, no leveraged exposure is taken. This alone avoids most major drawdown periods.

---

#### Step 2 — Trend Confirmation (50-day vs 200-day SMA)

| Condition | Result |
|-----------|--------|
| 50-day SMA > 200-day SMA (Golden Cross) | → **STRONG BULL** — 100% base allocation |
| 50-day SMA ≤ 200-day SMA (Death Cross) | → **WEAK BULL** — 50% base allocation |

Even when QQQ is above its 200-day, a death cross signals weakening trend and reduces base exposure in half.

---

#### Step 3 — ATR Extreme Exit (Volatility Crisis)

ATR% = average of |daily returns| over 14 days, expressed as a percentage of price.

| Condition | Result |
|-----------|--------|
| ATR% > 3.5% | → **100% SGOV** (ATR_EXTREME regime, stop here) |
| Coming out of extreme: ATR% still > 3.0% | → **100% SGOV** (waiting for re-entry buffer) |
| ATR% drops back below 3.0% | → Extreme mode cleared, proceed to Step 4 |

A re-entry buffer (3.5% entry / 3.0% exit) prevents whipsawing back into TQQQ during brief volatility lulls.

---

#### Step 4 — ATR Normal Sizing (Volatility Adjustment)

| ATR% Range | Multiplier Applied |
|------------|-------------------|
| < 1.5% | x1.00 — full base allocation |
| 1.5% – 2.5% | x0.75 — reduce by 25% |
| 2.5% – 3.5% | x0.50 — reduce by 50% |

This step scales down TQQQ exposure as volatility rises, even when not in extreme territory.

---

#### Step 5 — Nasdaq Breadth Filter

Breadth = % of the top 20 QQQ holdings (by weight) trading above their own 200-day SMA.

| Breadth | Result |
|---------|--------|
| < 20% | → **100% SGOV** (BREADTH_COLLAPSE, stop here) |
| 45% – 65% | x0.75 — reduce by 25% |
| < 45% | x0.50 — reduce by 50% |
| > 65% | x1.00 — no reduction |

Market breadth measures whether the rally is broad-based or concentrated in a few stocks. Narrow rallies are fragile.

---

#### Step 6 — VIX Crisis Override

| VIX Level | Result |
|-----------|--------|
| VIX > 35 | Cap TQQQ allocation at 50% maximum |
| VIX ≤ 35 | No change |

When the market fear gauge is elevated, TQQQ exposure is capped regardless of other signals.

---

#### Final Allocation Calculation

```
target_alloc = base × ATR_multiplier × breadth_multiplier
target_alloc = min(target_alloc, VIX_cap)   # if VIX crisis active
```

Example (Strong Bull, normal volatility, good breadth, calm VIX):
```
1.00 × 1.00 × 1.00 = 100% TQQQ
```

Example (Strong Bull, elevated ATR, mixed breadth):
```
1.00 × 0.75 × 0.75 = 56.25% TQQQ → rounds to nearest tradeable amount
```

---

#### Step 7 — Momentum Re-entry Guard

Only checked when transitioning from a bearish regime (BEAR, ATR_EXTREME, BREADTH_COLLAPSE) back to bull:

| Condition | Result |
|-----------|--------|
| QQQ price > QQQ price 20 trading days ago | ✅ Allow entry — positive momentum |
| QQQ price ≤ QQQ price 20 trading days ago | ❌ Stay in SGOV (MOMENTUM_WAIT) |

Prevents re-entering TQQQ during "dead cat bounces" that lack follow-through.

---

#### Step 8 — Gap Guard (9:25 AM Pre-market Check)

Before executing any queued trade the next morning:

| Condition | Result |
|-----------|--------|
| Pre-market QQQ ≥ 98% of prior close | ✅ Execute trade |
| Pre-market QQQ < 98% of prior close | ❌ Abort trade, hold current position |

If QQQ gaps down more than 2% overnight, the scheduled trade is cancelled. The signal will be re-evaluated at 3:55 PM.

---

#### Step 9 — Weekly Drift Rebalance (Sunday 8 PM)

Every Sunday, the bot checks if actual allocation has drifted more than 10% from target:

| Drift | Result |
|-------|--------|
| > 10% from target | Queue rebalance trade for Monday 9:25 AM |
| ≤ 10% | No action |

---

### Circuit Breakers

The bot tracks all-time peak portfolio value and monitors drawdown:

| Drawdown from Peak | State | Action |
|-------------------|-------|--------|
| -20% | WARNING | Telegram alert, continue trading |
| -30% | HALT | Alert, no new TQQQ buys |
| -40% | STOP | Alert, full trading stop, manual review required |
| +10% recovery from stop level | RESUME | Auto-resume trading |

---

### Dead Man's Switch

If the bot goes silent for 2+ consecutive trading days (crash, server issue, etc.), it fires a Telegram alert with instructions to SSH in and check the service.

---

### Schedule

| Job | Time | What It Does |
|-----|------|-------------|
| Morning Briefing | Mon–Fri 9:00 AM ET | Sends regime, key levels, any queued trades |
| Gap Guard + Execute | Mon–Fri 9:25 AM ET | Pre-market check, executes queued trades |
| Signal Check | Mon–Fri 3:55 PM ET | Runs 9-step decision tree, queues trade if needed |
| Weekly Check | Sunday 8:00 PM ET | Drift rebalance + weekly summary + dead man switch |

---

### Data Sources

| Data | Source | Why |
|------|--------|-----|
| QQQ daily history (SMA, ATR) | Stooq | 6800+ days, matches Yahoo Finance exactly |
| Real-time / pre-market QQQ price | Alpaca | Accurate live quotes |
| VIX | yfinance | Only reliable free source |
| Nasdaq breadth (top 20 holdings) | Stooq | Same accuracy as main QQQ data |

---

## File Structure

```
tqqq-bot/
├── config.py        # ⚙️  All settings — fill in your keys (gitignored)
├── bot.py           # 🤖 Main scheduler — run this to start the bot
├── strategy.py      # 🧠 9-step decision tree (the brain)
├── data.py          # 📊 Market data: QQQ, VIX, breadth
├── risk.py          # 🛡️  Circuit breakers + dead man switch
├── orders.py        # 💱 Alpaca trade execution
├── alerts.py        # 📱 Telegram notifications
├── reports.py       # 📋 Daily/weekly Telegram summaries
├── logger.py        # 🗄️  SQLite database + log file
├── setup.sh         # 🚀 One-command EC2 setup script
├── requirements.txt # 📦 Python dependencies
├── DISCLAIMER.md    # ⚠️  Legal disclaimer — read first
├── CONTRIBUTING.md  # 🤝 How to contribute
└── .gitignore       # 🔒 Keeps your keys out of git
```

---

## Hosting Guide — AWS EC2

### Prerequisites

- An [Alpaca Markets](https://alpaca.markets) account (free paper trading account is enough to start)
- A Telegram account and a bot token from [@BotFather](https://t.me/BotFather)
- An AWS account (free tier t2.micro or t3.micro is sufficient)

---

### Step 1 — Launch an EC2 Instance

1. Go to AWS Console → EC2 → Launch Instance
2. Choose: **Ubuntu Server 22.04 LTS** (free tier eligible)
3. Instance type: **t2.micro** (free tier) or **t3.micro** (~$8/month)
4. Create a key pair, download the `.pem` file
5. Security group: Allow SSH (port 22) from your IP only
6. Launch the instance, note the Public IPv4 address

---

### Step 2 — Prepare the Server

SSH into your instance:

```bash
ssh -i YOUR_KEY.pem ubuntu@YOUR_EC2_IP
```

Install Python and create the bot directory:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv git

mkdir -p /home/ubuntu/tqqq-bot
cd /home/ubuntu/tqqq-bot
python3 -m venv venv
source venv/bin/activate
```

---

### Step 3 — Upload the Bot Files

**Option A — Clone from GitHub (recommended):**

```bash
cd /home/ubuntu/tqqq-bot
git clone https://github.com/YOUR_USERNAME/tqqq-bot.git .
```

**Option B — Upload files manually from your local machine:**

```bash
# Run this from your local machine in the folder containing the bot files
scp -i YOUR_KEY.pem *.py setup.sh requirements.txt ubuntu@YOUR_EC2_IP:/home/ubuntu/tqqq-bot/
```

---

### Step 4 — Configure the Bot

```bash
cd /home/ubuntu/tqqq-bot
cp config.py config.py.example   # keep a clean template
nano config.py
```

Fill in your credentials:

```python
ALPACA_API_KEY    = "your-alpaca-api-key"
ALPACA_SECRET_KEY = "your-alpaca-secret-key"
PAPER_MODE        = True   # ← always start with True!

TELEGRAM_BOT_TOKEN = "your-telegram-bot-token"
TELEGRAM_CHAT_ID   = "your-telegram-chat-id"
```

Save: `Ctrl+X` → `Y` → `Enter`

---

### Step 5 — Get Your Alpaca Keys

1. Sign up at [alpaca.markets](https://alpaca.markets)
2. Go to **Paper Trading** → **API Keys** → **Generate New Key**
3. Copy the API Key and Secret Key (the secret is shown only once)
4. Paste both into `config.py`

---

### Step 6 — Get Your Telegram Bot Token and Chat ID

**Create a bot:**
1. Open Telegram → search for `@BotFather`
2. Send `/newbot`
3. Follow the prompts, copy the token

**Find your Chat ID:**
1. Send any message to your new bot
2. Visit: `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
3. Find `"chat": {"id": 123456789}` — that number is your Chat ID

---

### Step 7 — Run Setup and Install Dependencies

```bash
cd /home/ubuntu/tqqq-bot
bash setup.sh
```

Or manually:

```bash
source venv/bin/activate
pip install -r requirements.txt
sudo timedatectl set-timezone America/New_York
```

---

### Step 8 — Test the Bot

```bash
cd /home/ubuntu/tqqq-bot
source venv/bin/activate
python3 -c "import bot; bot.startup()"
```

Expected output:
```
[INFO] [startup] === TQQQ Adaptive Regime Bot v2.2 starting ===
[INFO] [startup] Alpaca connected. Portfolio: $100,000.00 | Cash: $100,000.00
[INFO] [startup] Telegram test sent successfully
[INFO] [startup] Startup complete. Scheduler running...
```

You should receive a startup message in Telegram.

---

### Step 9 — Create a systemd Service (Run on Boot)

Create the service file:

```bash
sudo nano /etc/systemd/system/tqqq-bot.service
```

Paste this:

```ini
[Unit]
Description=TQQQ Adaptive Regime Bot
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/tqqq-bot
ExecStart=/home/ubuntu/tqqq-bot/venv/bin/python3 bot.py
Restart=always
RestartSec=30
StandardOutput=append:/home/ubuntu/tqqq-bot/tqqq_bot.log
StandardError=append:/home/ubuntu/tqqq-bot/tqqq_bot.log

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable tqqq-bot
sudo systemctl start tqqq-bot
sudo systemctl status tqqq-bot
```

---

### Step 10 — Verify Everything is Working

```bash
# Watch live log output
tail -f /home/ubuntu/tqqq-bot/tqqq_bot.log

# Check service status
sudo systemctl status tqqq-bot

# Query the database
cd /home/ubuntu/tqqq-bot
source venv/bin/activate
python3 -c "
import sqlite3, json
conn = sqlite3.connect('tqqq_bot.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()
c.execute('SELECT * FROM signals ORDER BY id DESC LIMIT 3')
for row in c.fetchall():
    print(json.dumps(dict(row), indent=2))
"
```

---

### Useful Commands

```bash
# Stop the bot
sudo systemctl stop tqqq-bot

# Restart the bot (after config changes)
sudo systemctl restart tqqq-bot

# Watch live logs
tail -f /home/ubuntu/tqqq-bot/tqqq_bot.log

# View recent signals
sqlite3 /home/ubuntu/tqqq-bot/tqqq_bot.db \
  "SELECT date, regime, target_alloc, signal_detail FROM signals ORDER BY id DESC LIMIT 5;"

# View recent trades
sqlite3 /home/ubuntu/tqqq-bot/tqqq_bot.db \
  "SELECT date, action, ticker, shares, price FROM trades ORDER BY id DESC LIMIT 10;"

# View portfolio history
sqlite3 /home/ubuntu/tqqq-bot/tqqq_bot.db \
  "SELECT date, total_value, drawdown_pct FROM portfolio ORDER BY id DESC LIMIT 10;"
```

---

### Going Live (When Ready)

> ⚠️ **Only do this after weeks of successful paper trading.**

1. Deposit real money into your Alpaca live account
2. Edit `config.py`:
   ```python
   PAPER_MODE = False
   ```
3. Restart the bot:
   ```bash
   sudo systemctl restart tqqq-bot
   ```
4. Watch the logs and Telegram alerts closely for the first few days

---

## Cost to Run

| Component | Cost |
|-----------|------|
| AWS t2.micro (free tier, 12 months) | Free |
| AWS t3.micro (after free tier) | ~$8/month |
| Alpaca Markets | Free |
| Telegram Bot API | Free |
| Stooq / yfinance data | Free |
| **Total** | **$0–$8/month** |

---

## How to Contribute

See [CONTRIBUTING.md](CONTRIBUTING.md). Ideas for contributions:

- Additional regime filters (RSI, MACD, put/call ratio)
- SPY/SPXL strategy alongside TQQQ/SGOV
- Backtesting module
- Discord alert support
- Web dashboard for portfolio monitoring
- More sophisticated position sizing

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

## Acknowledgements

- [Alpaca Markets](https://alpaca.markets) — commission-free brokerage API
- [Stooq](https://stooq.com) — reliable free historical price data
- [yfinance](https://github.com/ranaroussi/yfinance) — VIX data access
- The algorithmic trading community for regime-switching strategy research

---

*Built with Python. Runs on a $8/month server. Sends you Telegram alerts while you sleep.*
