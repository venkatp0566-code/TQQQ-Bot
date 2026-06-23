# Contributing to TQQQ Adaptive Regime Bot

Thank you for your interest in contributing! This is an open-source educational project and all contributions are welcome.

## How to Contribute

### Reporting Bugs
Open a GitHub Issue with:
- What you expected to happen
- What actually happened
- Your Python version and OS
- Relevant log output (remove any API keys!)

### Suggesting Features
Open a GitHub Issue with the `enhancement` label. Good ideas include:
- Additional regime filters (RSI, MACD, etc.)
- New signal tickers (SPY/SPXL strategy)
- Better breadth calculations
- Backtesting improvements
- Additional alert channels (Discord, email, etc.)

### Submitting Code

1. Fork the repo
2. Create a feature branch: `git checkout -b feature/my-improvement`
3. Make your changes
4. Test in paper mode
5. Submit a Pull Request with a clear description

### Code Style
- Follow the existing style (comments, docstrings, logging)
- Never commit real API keys or credentials
- Always test in paper mode (`PAPER_MODE = True`) before submitting

### Key Rules
- **Never commit `config.py`** — it contains secrets
- All new features should degrade gracefully (log warning, don't crash)
- Add logging (`logger.log_info / log_warning / log_error`) to new code
- Keep the decision tree in `strategy.py` clean and well-commented

## Project Structure

```
tqqq-bot/
├── config.py       # Your settings (gitignored)
├── bot.py          # Main scheduler — entry point
├── strategy.py     # Decision tree — the brain
├── data.py         # Market data fetching
├── risk.py         # Circuit breakers + dead man switch
├── orders.py       # Alpaca trade execution
├── alerts.py       # Telegram notifications
├── reports.py      # Daily/weekly summaries
├── logger.py       # SQLite + log file management
└── setup.sh        # EC2 setup script
```
