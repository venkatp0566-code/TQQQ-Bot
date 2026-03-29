# =============================================================================
# logger.py — Logging and SQLite database management
# Every signal, trade, and portfolio snapshot is saved here forever
# =============================================================================

import sqlite3
import logging
import config

# ── TEXT LOG FILE ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(config.LOG_FILE),
        logging.StreamHandler()
    ]
)

def log_info(source, message):
    logging.info(f"[{source}] {message}")

def log_warning(source, message):
    logging.warning(f"[{source}] {message}")

def log_error(source, message):
    logging.error(f"[{source}] {message}")

# ── DATABASE INIT ─────────────────────────────────────────────────────────────
def init_db():
    """Creates all tables. Safe to call on every startup."""
    conn = sqlite3.connect(config.DATABASE_FILE)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS signals (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            date          TEXT NOT NULL,
            qqq_price     REAL,
            sma200        REAL,
            sma50         REAL,
            atr_pct       REAL,
            vix           REAL,
            breadth_pct   REAL,
            regime        TEXT,
            target_alloc  REAL,
            signal_detail TEXT,
            created_at    TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            date       TEXT NOT NULL,
            action     TEXT,
            ticker     TEXT,
            shares     REAL,
            price      REAL,
            value      REAL,
            notes      TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS portfolio (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            date         TEXT NOT NULL,
            total_value  REAL,
            tqqq_shares  REAL,
            tqqq_value   REAL,
            sgov_shares  REAL,
            sgov_value   REAL,
            cash         REAL,
            target_alloc REAL,
            actual_alloc REAL,
            drawdown_pct REAL,
            peak_value   REAL,
            created_at   TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS circuit_breakers (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            date       TEXT NOT NULL,
            level      TEXT,
            drawdown   REAL,
            action     TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS bot_runs (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            date       TEXT NOT NULL,
            status     TEXT,
            notes      TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()
    log_info("init_db", "Database initialised successfully")

# ── SAVE FUNCTIONS ────────────────────────────────────────────────────────────
def save_signal(date, qqq_price, sma200, sma50, atr_pct, vix,
                breadth_pct, regime, target_alloc, signal_detail):
    conn = sqlite3.connect(config.DATABASE_FILE)
    c = conn.cursor()
    c.execute("""
        INSERT INTO signals
        (date, qqq_price, sma200, sma50, atr_pct, vix,
         breadth_pct, regime, target_alloc, signal_detail)
        VALUES (?,?,?,?,?,?,?,?,?,?)
    """, (date, qqq_price, sma200, sma50, atr_pct, vix,
          breadth_pct, regime, target_alloc, signal_detail))
    conn.commit()
    conn.close()

def save_trade(date, action, ticker, shares, price, value, notes=""):
    conn = sqlite3.connect(config.DATABASE_FILE)
    c = conn.cursor()
    c.execute("""
        INSERT INTO trades (date, action, ticker, shares, price, value, notes)
        VALUES (?,?,?,?,?,?,?)
    """, (date, action, ticker, shares, price, value, notes))
    conn.commit()
    conn.close()
    log_info("save_trade", f"{action} {shares:.4f} {ticker} @ ${price:.2f} = ${value:.2f}")

def save_portfolio(date, total_value, tqqq_shares, tqqq_value,
                   sgov_shares, sgov_value, cash,
                   target_alloc, actual_alloc, drawdown_pct, peak_value):
    conn = sqlite3.connect(config.DATABASE_FILE)
    c = conn.cursor()
    c.execute("""
        INSERT INTO portfolio
        (date, total_value, tqqq_shares, tqqq_value,
         sgov_shares, sgov_value, cash, target_alloc,
         actual_alloc, drawdown_pct, peak_value)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, (date, total_value, tqqq_shares, tqqq_value,
          sgov_shares, sgov_value, cash, target_alloc,
          actual_alloc, drawdown_pct, peak_value))
    conn.commit()
    conn.close()

def save_circuit_breaker(date, level, drawdown, action):
    conn = sqlite3.connect(config.DATABASE_FILE)
    c = conn.cursor()
    c.execute("""
        INSERT INTO circuit_breakers (date, level, drawdown, action)
        VALUES (?,?,?,?)
    """, (date, level, drawdown, action))
    conn.commit()
    conn.close()
    log_warning("circuit_breaker", f"Level={level} Drawdown={drawdown:.1%} Action={action}")

def save_bot_run(date, status, notes=""):
    conn = sqlite3.connect(config.DATABASE_FILE)
    c = conn.cursor()
    c.execute("""
        INSERT INTO bot_runs (date, status, notes) VALUES (?,?,?)
    """, (date, status, notes))
    conn.commit()
    conn.close()

# ── READ FUNCTIONS ────────────────────────────────────────────────────────────
def get_last_signal():
    conn = sqlite3.connect(config.DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM signals ORDER BY id DESC LIMIT 1")
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None

def get_peak_value():
    conn = sqlite3.connect(config.DATABASE_FILE)
    c = conn.cursor()
    c.execute("SELECT MAX(total_value) FROM portfolio")
    result = c.fetchone()[0]
    conn.close()
    return result if result else config.BACKTEST_CAPITAL

def get_last_n_portfolio(n=7):
    conn = sqlite3.connect(config.DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM portfolio ORDER BY id DESC LIMIT ?", (n,))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_trades_since(date_str):
    conn = sqlite3.connect(config.DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM trades WHERE date >= ? ORDER BY date DESC", (date_str,))
    rows = c.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_last_run_dates(n=5):
    conn = sqlite3.connect(config.DATABASE_FILE)
    c = conn.cursor()
    c.execute("SELECT date FROM bot_runs ORDER BY id DESC LIMIT ?", (n,))
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]

def get_circuit_breaker_status():
    conn = sqlite3.connect(config.DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM circuit_breakers ORDER BY id DESC LIMIT 1")
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None
