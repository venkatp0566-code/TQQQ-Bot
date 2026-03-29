# =============================================================================
# config.py — TQQQ Adaptive Regime Bot v2.2
# Fill in YOUR values below. Never commit this file with real keys.
# Add config.py to .gitignore to keep your secrets safe.
# =============================================================================

# ── ALPACA ────────────────────────────────────────────────────────────────────
# Get from: https://app.alpaca.markets → Paper Trading → API Keys
ALPACA_API_KEY      = "YOUR_ALPACA_API_KEY_HERE"
ALPACA_SECRET_KEY   = "YOUR_ALPACA_SECRET_KEY_HERE"
PAPER_MODE          = True   # True = paper trading (safe to test), False = real money
ALPACA_BASE_URL     = "https://paper-api.alpaca.markets" if PAPER_MODE else "https://api.alpaca.markets"

# ── TELEGRAM ──────────────────────────────────────────────────────────────────
# 1. Message @BotFather on Telegram → /newbot → copy the token
# 2. Get your chat_id: https://api.telegram.org/bot<TOKEN>/getUpdates
TELEGRAM_BOT_TOKEN  = "YOUR_TELEGRAM_BOT_TOKEN_HERE"
TELEGRAM_CHAT_ID    = "YOUR_TELEGRAM_CHAT_ID_HERE"

# ── TICKERS ───────────────────────────────────────────────────────────────────
SIGNAL_TICKER  = "QQQ"    # signal source (Nasdaq-100 ETF)
BULL_TICKER    = "TQQQ"   # 3x leveraged bull — buy in bull regime
BEAR_TICKER    = "SGOV"   # T-bill ETF — buy in bear/risk-off regime
VIX_TICKER     = "^VIX"   # fear index (via yfinance — VIX not on Alpaca)

# ── STRATEGY PARAMETERS ───────────────────────────────────────────────────────
SMA_LONG           = 200   # long-term trend filter
SMA_SHORT          = 50    # trend confirmation (golden/death cross)
ATR_PERIOD         = 14    # volatility measurement period
MOMENTUM_LOOKBACK  = 20    # re-entry momentum check (trading days)
DATA_LOOKBACK_DAYS = 300   # how many days of history to fetch

# ── ATR THRESHOLDS ────────────────────────────────────────────────────────────
# Step 3: ATR > ATR_EXTREME  → 100% SGOV (hard exit, checked before sizing)
# Step 4: sizing bands (only reached if ATR <= ATR_EXTREME):
#   < ATR_NORMAL   = full allocation  (x1.00)
#   < ATR_ELEVATED = reduce 25%       (x0.75)
#   else           = reduce 50%       (x0.50)
ATR_NORMAL   = 0.015   # < 1.5%  → full allocation
ATR_ELEVATED = 0.025   # 1.5-2.5% → reduce 25%
ATR_EXTREME  = 0.035   # > 3.5%  → 100% SGOV (step 3 hard exit)
ATR_REENTRY  = 0.030   # re-entry buffer: must drop below this after extreme exit

# ── BREADTH THRESHOLDS ───────────────────────────────────────────────────────
# Step 5 logic (checked in order):
#   < BREADTH_COLLAPSE → 100% SGOV (hard exit)
#   > BREADTH_STRONG   → full allocation (x1.00)
#   > BREADTH_MIXED    → reduce 25%      (x0.75)
#   else (20-45%)      → reduce 50%      (x0.50)
BREADTH_STRONG   = 0.65   # > 65%  → full allocation
BREADTH_MIXED    = 0.45   # 45-65% → reduce 25%
BREADTH_COLLAPSE = 0.20   # < 20%  → 100% SGOV (hard exit, checked first)

# ── ALLOCATION RULES ──────────────────────────────────────────────────────────
ALLOC_STRONG_BULL  = 1.00
ALLOC_WEAK_BULL    = 0.50
ATR_MULT_ELEVATED  = 0.75
ATR_MULT_HIGH      = 0.50
BREADTH_MULT_MIXED = 0.75
BREADTH_MULT_WEAK  = 0.50
VIX_CRISIS         = 35     # VIX above this → cap TQQQ exposure
VIX_CRISIS_CAP     = 0.50   # cap at 50% during VIX crisis

# ── RISK CONTROLS ─────────────────────────────────────────────────────────────
GAP_GUARD       = 0.98    # abort buy if QQQ gaps down > 2% pre-market
DRIFT_TOLERANCE = 0.10    # rebalance if actual vs target drifts > 10%
CB_WARNING      = -0.20   # -20% drawdown → warning alert
CB_HALT         = -0.30   # -30% drawdown → halt new buys
CB_STOP         = -0.40   # -40% drawdown → full stop, manual review
CB_RESUME       =  0.10   # +10% recovery from stop level → auto-resume
DEAD_MANS_DAYS  = 2       # alert if bot silent for this many trading days
MIN_NEW_CAPITAL = 100.00  # minimum deposit amount to trigger rebalance

# ── TIMING (all Eastern time) ─────────────────────────────────────────────────
SIGNAL_HOUR      = 15
SIGNAL_MINUTE    = 55   # 3:55 PM ET — 5 min before close
GAP_CHECK_HOUR   = 9
GAP_CHECK_MINUTE = 25   # 9:25 AM ET — 5 min before open
WEEKLY_CHECK_DAY = 6    # Sunday
WEEKLY_CHECK_HOUR = 20  # 8:00 PM ET
MORNING_HOUR     = 9    # 9:00 AM ET — morning briefing
MORNING_MINUTE   = 0
TIMEZONE         = "America/New_York"

# ── FILES ─────────────────────────────────────────────────────────────────────
DATABASE_FILE = "/home/ubuntu/tqqq-bot/tqqq_bot.db"
LOG_FILE      = "/home/ubuntu/tqqq-bot/tqqq_bot.log"

# ── BACKTEST / TRACKING ───────────────────────────────────────────────────────
BACKTEST_START   = "2010-01-01"
BACKTEST_CAPITAL = 1000.00   # starting capital for inception-return calculation
