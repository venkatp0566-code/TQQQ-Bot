# 📈 TQQQ Adaptive Regime Bot

> **An open-source algorithmic trading bot that rotates between TQQQ (3x leveraged Nasdaq ETF) and SGOV (T-bill ETF) based on market regime, volatility, and breadth signals.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/)
[![Paper Trading](https://img.shields.io/badge/default-paper%20trading-green.svg)](https://github.com/venkatp0566-code/TQQQ-Bot)

---

## ⚠️ DISCLAIMER — READ FIRST

> **This project is for educational purposes only. It is NOT financial or investment advice. Leveraged ETFs like TQQQ can lose value extremely rapidly. You are solely responsible for any financial outcomes from using this software. The author(s) accept no liability for losses.**
>
> **See [DISCLAIMER.md](DISCLAIMER.md) for full terms. By using this software, you agree to them.**

---

## What It Does

The bot runs fully automatically on a cloud server. Every trading day at **3:55 PM ET**, it evaluates QQQ's trend, volatility, and market breadth through a 9-step decision tree and either:

* **Holds / buys TQQQ** — when the market is in a confirmed bull regime with manageable volatility
* **Holds / buys SGOV** — when the market is bearish, extremely volatile, or showing breadth collapse

Trades are **queued at 3:55 PM** and executed at **9:25 AM the next morning** after a pre-market gap check. A Telegram bot sends real-time alerts for every decision.

---

## Strategy Overview

### Core Logic: 9-Step Decision Tree

---

#### Step 1 — Master Switch (QQQ vs 200-day SMA)

| Condition | Result |
|---|---|
| QQQ price > 200-day SMA | → Continue to Step 2 (BULL mode) |
| QQQ price ≤ 200-day SMA | → **100% SGOV** (BEAR regime, stop here) |

This is the primary filter. If Nasdaq-100 is below its long-term average, no leveraged exposure is taken.

---

#### Step 2 — Trend Confirmation (50-day vs 200-day SMA)

| Condition | Result |
|---|---|
| 50-day SMA > 200-day SMA (Golden Cross) | → **STRONG BULL** — 100% base allocation |
| 50-day SMA ≤ 200-day SMA (Death Cross) | → **WEAK BULL** — 50% base allocation |

---

#### Step 3 — ATR Extreme Exit (Volatility Crisis)

ATR% = average of absolute daily returns over 14 days.

| Condition | Result |
|---|---|
| ATR% > 3.5% | → **100% SGOV** (ATR_EXTREME, stop here) |
| Coming out of extreme: ATR% still > 3.0% | → **100% SGOV** (re-entry buffer) |
| ATR% drops back below 3.0% | → Extreme mode cleared, proceed to Step 4 |

---

#### Step 4 — ATR Normal Sizing

| ATR% Range | Multiplier |
|---|---|
| < 1.5% | x1.00 — full allocation |
| 1.5% – 2.5% | x0.75 — reduce 25% |
| 2.5% – 3.5% | x0.50 — reduce 50% |

---

#### Step 5 — Nasdaq Breadth Filter

Breadth = % of top 20 QQQ holdings trading above their own 200-day SMA.

| Breadth | Result |
|---|---|
| < 20% | → **100% SGOV** (BREADTH_COLLAPSE, stop here) |
| 20% – 45% | x0.50 — reduce 50% |
| 45% – 65% | x0.75 — reduce 25% |
| > 65% | x1.00 — full allocation |

---

#### Step 6 — VIX Crisis Override

| VIX | Result |
|---|---|
| > 35 | Cap TQQQ at 50% maximum |
| ≤ 35 | No change |

---

#### Final Allocation Calculation
target_alloc = base × ATR_multiplier × breadth_multiplier

target_alloc = min(target_alloc, VIX_cap)   # if VIX crisis active

Example — Strong Bull, calm volatility, strong breadth, calm VIX:
1.00 × 1.00 × 1.00 = 100% TQQQ

Example — Strong Bull, elevated ATR, mixed breadth:
1.00 × 0.75 × 0.75 = 56.25% TQQQ

---

#### Step 7 — Momentum Re-entry Guard

Only checked when transitioning from a bearish regime back to bull:

| Condition | Result |
|---|---|
| QQQ price > QQQ price 20 trading days ago | ✅ Allow entry |
| QQQ price ≤ QQQ price 20 trading days ago | ❌ Stay SGOV (MOMENTUM_WAIT) |

---

#### Step 8 — Gap Guard (9:25 AM Pre-market Check)

| Condition | Result |
|---|---|
| Pre-market QQQ ≥ 98% of prior close | ✅ Execute trade |
| Pre-market QQQ < 98% of prior close | ❌ Abort trade, hold position |

---

#### Step 9 — Weekly Drift Rebalance (Sunday 8 PM)

| Drift | Result |
|---|---|
| > 10% from target | Queue rebalance for Monday 9:25 AM |
| ≤ 10% | No action |

---

### Circuit Breakers

| Drawdown from Peak | State | Action |
|---|---|---|
| -20% | WARNING | Telegram alert, continue trading |
| -30% | HALT | Alert, no new TQQQ buys |
| -40% | STOP | Alert, full trading stop, manual review |
| +10% recovery from stop level | RESUME | Auto-resume trading |

---

### Dead Man's Switch

If the bot goes silent for 2+ consecutive trading days, it fires a Telegram alert with instructions to check the service.

---

### Schedule

| Job | Time | What It Does |
|---|---|---|
| Morning Briefing | Mon–Fri 9:00 AM ET | Regime, key levels, queued trades |
| Gap Guard + Execute | Mon–Fri 9:25 AM ET | Pre-market check, execute queued trades |
| Signal Check | Mon–Fri 3:55 PM ET | Runs 9-step decision tree, queues trade |
| Weekly Check | Sunday 8:00 PM ET | Drift rebalance + weekly summary |

---

### Data Sources

| Data | Source | Why |
|---|---|---|
| QQQ daily history (SMA, ATR) | yfinance | Reliable, no rate limits, accurate |
| Real-time / pre-market QQQ price | Alpaca | Accurate live quotes |
| VIX | yfinance | Only reliable free source |
| Nasdaq breadth (top 20 holdings) | yfinance bulk download | Single request, no rate limiting |

---

## File Structure
tqqq-bot/

├── config.py        # ⚙️  All settings — fill in your keys (gitignored)

├── bot.py           # 🤖 Main scheduler — run this to start the bot

├── strategy.py      # 🧠 9-step decision tree (the brain)

├── data.py          # 📊 Market data: QQQ, VIX, breadth (all via yfinance)

├── risk.py          # 🛡️  Circuit breakers + dead man switch

├── orders.py        # 💱 Alpaca trade execution (cash-only, no margin)

├── alerts.py        # 📱 Telegram notifications

├── reports.py       # 📋 Daily/weekly Telegram summaries

├── logger.py        # 🗄️  SQLite database + log file + state persistence

├── setup.sh         # 🚀 Setup script

├── requirements.txt # 📦 Python dependencies

├── DISCLAIMER.md    # ⚠️  Legal disclaimer — read first

├── CONTRIBUTING.md  # 🤝 How to contribute

└── .gitignore       # 🔒 Keeps your keys and database out of git

---

## Hosting Guide — Hetzner Cloud

### Prerequisites

* An [Alpaca Markets](https://alpaca.markets) account (free paper trading account to start)
* A Telegram account and bot token from [@BotFather](https://t.me/BotFather)
* A [Hetzner Cloud](https://www.hetzner.com/cloud) account

---

### Step 1 — Create Hetzner Server

1. Go to Hetzner Cloud Console → Projects → New Server
2. Location: Any (US or EU)
3. OS: **Ubuntu 24.04 LTS**
4. Type: **CX22** (~€4/month, 2 vCPU, 4GB RAM) — more than enough
5. Add your SSH public key
6. Create server, note the public IP address

---

### Step 2 — SSH into Server

```bash
ssh root@YOUR_HETZNER_IP
```

---

### Step 3 — Prepare the Server

```bash
apt update && apt upgrade -y
apt install -y python3 python3-pip python3-venv git

mkdir -p /opt/tqqq-bot
cd /opt/tqqq-bot
python3 -m venv venv
source venv/bin/activate
```

---

### Step 4 — Clone from GitHub

```bash
cd /opt/tqqq-bot
git clone https://github.com/venkatp0566-code/TQQQ-Bot.git .
```

---

### Step 5 — Configure the Bot

```bash
vi /opt/tqqq-bot/config.py
```

Fill in your credentials — the file has placeholders showing exactly what goes where:

```python
ALPACA_API_KEY      = "your-alpaca-api-key"
ALPACA_SECRET_KEY   = "your-alpaca-secret-key"
PAPER_MODE          = True   # ← always start with True!

TELEGRAM_BOT_TOKEN  = "your-telegram-bot-token"
TELEGRAM_CHAT_ID    = "your-telegram-chat-id"

DATABASE_FILE = "/opt/tqqq-bot/tqqq_bot.db"
LOG_FILE      = "/opt/tqqq-bot/tqqq_bot.log"
```

Save with `Esc` → `:wq` → `Enter`

---

### Step 6 — Get Your Alpaca Keys

1. Sign up at [alpaca.markets](https://alpaca.markets)
2. Go to **Paper Trading** → **API Keys** → **Generate New Key**
3. Copy the API Key and Secret Key (secret shown only once)
4. Paste both into `config.py`

---

### Step 7 — Get Your Telegram Bot Token and Chat ID

**Create a bot:**
1. Open Telegram → search `@BotFather`
2. Send `/newbot`, follow prompts, copy the token

**Find your Chat ID:**
1. Send any message to your new bot
2. Visit: `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
3. Find `"chat": {"id": 123456789}` — that number is your Chat ID

---

### Step 8 — Install Dependencies and Set Timezone

```bash
source /opt/tqqq-bot/venv/bin/activate
pip install alpaca-py yfinance pandas numpy requests schedule pytz
timedatectl set-timezone America/New_York
```

---

### Step 9 — Test the Bot

```bash
cd /opt/tqqq-bot
source venv/bin/activate
python3 -c "import bot; bot.startup()"
```

Expected output:
[INFO] [startup] === TQQQ Adaptive Regime Bot starting ===

[INFO] [startup] Alpaca connected. Portfolio: $100,000.00 | Cash: $100,000.00

[INFO] [startup] Telegram test sent successfully

[INFO] [startup] Startup complete. Scheduler running...

You should also receive a startup message in Telegram.

---

### Step 10 — Create systemd Service (Run 24/7)

```bash
vi /etc/systemd/system/tqqq-bot.service
```

Paste:

```ini
[Unit]
Description=TQQQ Adaptive Regime Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/tqqq-bot
ExecStart=/opt/tqqq-bot/venv/bin/python3 /opt/tqqq-bot/bot.py
Restart=always
RestartSec=30
StartLimitIntervalSec=0
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
systemctl daemon-reload
systemctl enable tqqq-bot
systemctl start tqqq-bot
systemctl status tqqq-bot
```

---

### Step 11 — Verify Everything is Working

```bash
# Watch live log
tail -f /opt/tqqq-bot/tqqq_bot.log

# Check service status
systemctl status tqqq-bot

# Query recent signals from database
sqlite3 /opt/tqqq-bot/tqqq_bot.db \
  "SELECT date, regime, target_alloc, signal_detail FROM signals ORDER BY id DESC LIMIT 5;"

# Query recent trades
sqlite3 /opt/tqqq-bot/tqqq_bot.db \
  "SELECT date, action, ticker, shares, price FROM trades ORDER BY id DESC LIMIT 10;"

# Query portfolio history
sqlite3 /opt/tqqq-bot/tqqq_bot.db \
  "SELECT date, total_value, actual_alloc, drawdown_pct FROM portfolio ORDER BY id DESC LIMIT 10;"
```

---

### Useful Commands

```bash
# Stop the bot
systemctl stop tqqq-bot

# Restart the bot (after config or code changes)
systemctl restart tqqq-bot

# View last 50 log lines
tail -50 /opt/tqqq-bot/tqqq_bot.log

# Check bot state (pending trades, current regime)
sqlite3 /opt/tqqq-bot/tqqq_bot.db \
  "SELECT state_json FROM bot_state WHERE id = 1;"
```

---

### Going Live (When Ready)

> ⚠️ **Only do this after weeks of successful paper trading with zero errors.**

1. Deposit real money into your Alpaca live account
2. Edit `config.py`:
```python
   PAPER_MODE = False
```
3. Restart the bot:
```bash
   systemctl restart tqqq-bot
```
4. Watch logs and Telegram alerts closely for the first few days

---

## Cost to Run

| Component | Cost |
|---|---|
| Hetzner CX22 VPS | ~€4/month |
| Alpaca Markets | Free |
| Telegram Bot API | Free |
| yfinance market data | Free |
| **Total** | **~€4/month** |

---

## How to Contribute

See [CONTRIBUTING.md](CONTRIBUTING.md). Ideas for contributions:

* Additional regime filters (RSI, MACD, put/call ratio)
* SPY/SPXL strategy alongside TQQQ/SGOV
* Backtesting module
* Discord alert support
* Web dashboard for portfolio monitoring

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

## Acknowledgements

* [Alpaca Markets](https://alpaca.markets) — commission-free brokerage API
* [yfinance](https://github.com/ranaroussi/yfinance) — reliable free market data
* [Hetzner Cloud](https://www.hetzner.com/cloud) — affordable VPS hosting
* The algorithmic trading community for regime-switching strategy research

---

*Built with Python. Runs on a €4/month server. Sends Telegram alerts while you sleep.*
