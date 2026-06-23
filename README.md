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
