# =============================================================================
# alerts.py — Telegram alerts (v2.1)
# Replaced Gmail SMTP with Telegram Bot API
# =============================================================================

import requests
from datetime import datetime
import config
import logger


def _send_telegram(message, parse_mode="HTML"):
    """
    Core Telegram sender. All alert functions call this.
    Uses Telegram Bot API — instant, reliable, no spam folder.
    """
    try:
        url  = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {
            "chat_id":    config.TELEGRAM_CHAT_ID,
            "text":       message,
            "parse_mode": parse_mode
        }
        response = requests.post(url, data=data, timeout=10)
        response.raise_for_status()
        logger.log_info("telegram", f"Sent: {message[:60]}...")
        return True

    except Exception as e:
        logger.log_error("telegram", f"Failed to send message: {e}")
        return False


def _regime_emoji(regime):
    if "STRONG_BULL" in regime: return "🟢"
    if "WEAK_BULL"   in regime: return "🟡"
    if "BEAR"        in regime: return "🔴"
    if "ATR"         in regime: return "⚠️"
    if "BREADTH"     in regime: return "⚠️"
    return "⚪"


def alert_trade(action, ticker, shares, price, value, regime, reason):
    """Fires immediately when a trade is executed."""
    emoji = "🟢 BUY" if "BUY" in action else "🔴 SELL"
    msg = (
        f"{emoji} <b>Trade Executed</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📌 Action: <b>{action}</b>\n"
        f"📊 Ticker: <b>{ticker}</b>\n"
        f"🔢 Shares: <b>{shares:,}</b>\n"
        f"💲 Price:  <b>${price:.2f}</b>\n"
        f"💰 Value:  <b>${value:,.2f}</b>\n"
        f"📈 Regime: <b>{regime}</b>\n"
        f"📝 Reason: {reason}\n"
        f"🕐 Time:   {datetime.now().strftime('%Y-%m-%d %H:%M ET')}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"Paper Mode: {config.PAPER_MODE}"
    )
    _send_telegram(msg)


def alert_regime_change(old_regime, new_regime, qqq_price, sma200, signal_detail):
    """Fires when regime switches between BULL and BEAR."""
    bull  = "BULL" in new_regime
    emoji = "📈" if bull else "📉"
    action_text = "BUY TQQQ queued for tomorrow open" if bull else "SELL TQQQ queued for tomorrow open"
    dist  = ((qqq_price / sma200) - 1) * 100

    msg = (
        f"{emoji} <b>REGIME CHANGE ALERT</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"Previous: <b>{old_regime}</b>\n"
        f"New:      <b>{new_regime}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"QQQ Price:   <b>${qqq_price:.2f}</b>\n"
        f"200-Day SMA: <b>${sma200:.2f}</b>\n"
        f"Distance:    <b>{dist:+.2f}%</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🔔 {action_text}\n"
        f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M ET')}"
    )
    _send_telegram(msg)


def alert_circuit_breaker(level, drawdown, current_value, peak_value, action):
    """Fires at each circuit breaker threshold."""
    emojis = {"WARNING": "⚠️", "HALT": "🛑", "STOP": "🚨", "RESUME": "✅"}
    emoji  = emojis.get(level, "❗")

    action_text = {
        "WARNING":   "Bot continues trading. Monitoring closely.",
        "HALT_BUYS": "New TQQQ purchases halted until recovery.",
        "STOP_ALL":  "Bot fully stopped. Manual review required.\nLog into Alpaca to check positions.",
        "RESUME":    "Bot auto-resumed. Trading back to normal."
    }.get(action, action)

    msg = (
        f"{emoji} <b>CIRCUIT BREAKER: {level}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"Drawdown:      <b>{drawdown:.1%}</b>\n"
        f"Current Value: <b>${current_value:,.2f}</b>\n"
        f"Peak Value:    <b>${peak_value:,.2f}</b>\n"
        f"Action:        <b>{action}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{action_text}\n"
        f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M ET')}"
    )
    _send_telegram(msg)


def alert_error(source, error_message, context=""):
    """Fires when any unexpected exception occurs."""
    msg = (
        f"🔴 <b>BOT ERROR</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"Source: <b>{source}</b>\n"
        f"Time:   {datetime.now().strftime('%Y-%m-%d %H:%M:%S ET')}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"Error: {error_message[:300]}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"Bot held current position (no trades on error)."
    )
    _send_telegram(msg)


def alert_dead_mans_switch(last_run_date, days_missed):
    """Fires if bot has been silent for 2+ trading days."""
    msg = (
        f"🚨 <b>DEAD MAN SWITCH TRIGGERED</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"Last Run:     <b>{last_run_date}</b>\n"
        f"Days Missed:  <b>{days_missed}</b>\n"
        f"Bot Action:   Holding position — no trades\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"⚠️ Check your EC2 instance:\n"
        f"SSH in and run:\n"
        f"<code>sudo systemctl status tqqq-bot</code>"
    )
    _send_telegram(msg)


def alert_startup(paper_mode, portfolio_value, cash):
    """Fires when bot starts successfully."""
    mode = "📄 PAPER TRADING" if paper_mode else "💰 LIVE TRADING"
    msg = (
        f"✅ <b>TQQQ Bot Started</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"Mode:      <b>{mode}</b>\n"
        f"Portfolio: <b>${portfolio_value:,.2f}</b>\n"
        f"Cash:      <b>${cash:,.2f}</b>\n"
        f"Version:   v2.1\n"
        f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M ET')}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"Schedule:\n"
        f"  📊 Signal: Mon-Fri 3:55 PM ET\n"
        f"  🔍 Gap guard: Mon-Fri 9:25 AM ET\n"
        f"  📅 Weekly: Sunday 8:00 PM ET\n"
        f"  🌅 Morning: Mon-Fri 9:00 AM ET"
    )
    _send_telegram(msg)
