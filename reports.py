# =============================================================================
# reports.py — Daily, weekly, and morning Telegram reports (v2.1)
# =============================================================================

from datetime import datetime, timedelta, date
import config
import logger
from alerts import _send_telegram


def _fmt_pct(v, show_plus=True):
    sign = "+" if v > 0 and show_plus else ""
    return f"{sign}{v:.2f}%"

def _pct_arrow(v):
    return "📈" if v >= 0 else "📉"

def _regime_emoji(regime):
    if "STRONG_BULL" in regime: return "🟢"
    if "WEAK_BULL"   in regime: return "🟡"
    if "BEAR"        in regime: return "🔴"
    return "⚪"


def _plain_english_signal(signal_result):
    """
    Converts raw STEP1/STEP2 signal detail into plain English explanation.
    This is the human-friendly version of what the bot decided and why.
    """
    regime       = signal_result.get("regime", "UNKNOWN")
    qqq_price    = signal_result.get("qqq_price", 0) or 0
    sma200       = signal_result.get("sma200", 0) or 0
    sma50        = signal_result.get("sma50", 0) or 0
    atr_pct      = (signal_result.get("atr_pct") or 0) * 100
    vix          = signal_result.get("vix", 0) or 0
    breadth      = (signal_result.get("breadth_pct") or 0) * 100
    target_alloc = signal_result.get("target_alloc", 0)

    lines = []

    # Step 1 — master switch
    if qqq_price > 0 and sma200 > 0:
        dist = ((qqq_price / sma200) - 1) * 100
        if qqq_price > sma200:
            lines.append(f"✅ QQQ (${qqq_price:.2f}) is {dist:+.1f}% ABOVE 200-day average (${sma200:.2f}) → long-term trend is UP")
        else:
            lines.append(f"❌ QQQ (${qqq_price:.2f}) is {dist:+.1f}% BELOW 200-day average (${sma200:.2f}) → long-term trend is DOWN → BEAR MODE")

    # Step 2 — trend confirmation
    if "BEAR" not in regime and sma50 > 0 and sma200 > 0:
        if sma50 > sma200:
            lines.append(f"✅ Short-term trend (${sma50:.2f}) is above long-term (${sma200:.2f}) → STRONG BULL → 100% base")
        else:
            lines.append(f"⚠️ Short-term trend (${sma50:.2f}) is below long-term (${sma200:.2f}) → WEAK BULL → 50% base")

    # ATR
    if atr_pct > 0:
        if atr_pct > 3.5:
            lines.append(f"❌ Volatility extreme ({atr_pct:.2f}%) → TQQQ decay risk → move to SGOV")
        elif atr_pct > 2.5:
            lines.append(f"⚠️ Volatility high ({atr_pct:.2f}%) → reducing allocation by 50%")
        elif atr_pct > 1.5:
            lines.append(f"⚠️ Volatility elevated ({atr_pct:.2f}%) → reducing allocation by 25%")
        else:
            lines.append(f"✅ Volatility calm ({atr_pct:.2f}%) → no reduction needed")

    # Breadth
    if breadth > 0:
        if breadth < 20:
            lines.append(f"❌ Only {breadth:.0f}% of Nasdaq stocks healthy → BREADTH COLLAPSE → SGOV")
        elif breadth < 45:
            lines.append(f"⚠️ {breadth:.0f}% of Nasdaq stocks healthy → weak internals → reducing 50%")
        elif breadth < 65:
            lines.append(f"⚠️ {breadth:.0f}% of Nasdaq stocks healthy → mixed internals → reducing 25%")
        else:
            lines.append(f"✅ {breadth:.0f}% of Nasdaq stocks healthy → strong internals → no reduction")

    # VIX
    if vix > 0:
        if vix > 35:
            lines.append(f"❌ VIX {vix:.1f} → market panic → capping TQQQ at 50%")
        else:
            lines.append(f"✅ VIX {vix:.1f} → no crisis signal")

    # Final decision
    lines.append(f"\n🎯 <b>Final decision: {target_alloc:.0%} TQQQ / {1-target_alloc:.0%} SGOV</b>")

    return "\n".join(lines)


def send_morning_message(signal_result, account, positions):
    """
    Sends morning pre-market briefing at 9:00 AM Eastern.
    Shows current regime, key levels, and any trades queued for today.
    """
    now_str      = datetime.now().strftime("%B %d, %Y")
    regime       = signal_result.get("regime", "UNKNOWN") if signal_result else "UNKNOWN"
    qqq_price    = signal_result.get("qqq_price", 0) if signal_result else 0
    sma200       = signal_result.get("sma200", 0) if signal_result else 0
    sma50        = signal_result.get("sma50", 0) if signal_result else 0
    atr_pct      = ((signal_result.get("atr_pct") or 0) * 100) if signal_result else 0
    vix          = signal_result.get("vix", 0) if signal_result else 0
    breadth      = ((signal_result.get("breadth_pct") or 0) * 100) if signal_result else 0
    target_alloc = signal_result.get("target_alloc", 0) if signal_result else 0

    total        = account.get("total_value", 0)
    tqqq_pos     = positions.get(config.BULL_TICKER, {})
    tqqq_val     = tqqq_pos.get("market_value", 0)
    actual_alloc = (tqqq_val / total * 100) if total > 0 else 0

    sma200_dist  = ((qqq_price / sma200) - 1) * 100 if sma200 > 0 else 0
    regime_emoji = _regime_emoji(regime)

    # Trade queued?
    alloc_diff = abs(target_alloc - actual_alloc / 100)
    trade_line = ""
    if alloc_diff > 0.05:
        if target_alloc == 0:
            trade_line = "🔴 Trade queued: SELL ALL TQQQ → BUY SGOV at 9:25 AM"
        elif target_alloc == 1.0:
            trade_line = "🟢 Trade queued: SELL ALL SGOV → BUY TQQQ at 9:25 AM"
        else:
            trade_line = f"🟡 Trade queued: Rebalance to {target_alloc:.0%} TQQQ at 9:25 AM"
    else:
        trade_line = "✅ No trades today — holding current position"

    msg = (
        f"🌅 <b>Good Morning — {now_str}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{regime_emoji} Regime: <b>{regime}</b>\n"
        f"💼 Portfolio: <b>${total:,.2f}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>Key Levels:</b>\n"
        f"  QQQ:      ${qqq_price:.2f} ({sma200_dist:+.1f}% vs 200 SMA)\n"
        f"  200 SMA:  ${sma200:.2f}\n"
        f"  50 SMA:   ${sma50:.2f}\n"
        f"  ATR:      {atr_pct:.2f}%\n"
        f"  VIX:      {vix:.1f}\n"
        f"  Breadth:  {breadth:.0f}%\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🎯 Target: {target_alloc:.0%} TQQQ | Actual: {actual_alloc:.1f}%\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{trade_line}"
    )
    _send_telegram(msg)
    logger.log_info("send_morning_message", "Morning Telegram sent")


def send_daily_summary(portfolio, signal_result, trades_today, account):
    """
    Sends EOD daily summary via Telegram at 3:55 PM Eastern.
    Includes plain English explanation of bot decision.
    """
    now_str      = datetime.now().strftime("%B %d, %Y")
    total        = account.get("total_value", 0)
    cash         = account.get("cash", 0)

    tqqq_val     = portfolio.get("tqqq_value", 0) if portfolio else 0
    tqqq_sh      = portfolio.get("tqqq_shares", 0) if portfolio else 0
    sgov_val     = portfolio.get("sgov_value", 0) if portfolio else 0
    sgov_sh      = portfolio.get("sgov_shares", 0) if portfolio else 0
    drawdown     = portfolio.get("drawdown_pct", 0) if portfolio else 0
    peak         = portfolio.get("peak_value", total) if portfolio else total

    # Day change — compare to previous snapshot
    prev_total   = portfolio.get("prev_total", total) if portfolio else total
    day_change_val = total - prev_total
    day_change_pct = ((total / prev_total) - 1) * 100 if prev_total > 0 else 0

    regime       = signal_result.get("regime", "UNKNOWN")
    target_alloc = signal_result.get("target_alloc", 0)
    actual_alloc = (tqqq_val / total * 100) if total > 0 else 0
    qqq_price    = signal_result.get("qqq_price", 0) or 0
    sma200       = signal_result.get("sma200", 0) or 0
    atr_pct      = (signal_result.get("atr_pct") or 0) * 100
    vix          = signal_result.get("vix", 0) or 0
    breadth      = (signal_result.get("breadth_pct") or 0) * 100
    sma200_dist  = ((qqq_price / sma200) - 1) * 100 if sma200 > 0 else 0

    regime_emoji = _regime_emoji(regime)
    day_arrow    = _pct_arrow(day_change_pct)

    # Trades section
    if trades_today:
        trades_text = "\n".join([
            f"  {'🟢' if 'BUY' in t.get('action','') else '🔴'} "
            f"{t.get('action','')} {t.get('shares',0):.0f} "
            f"{t.get('ticker','')} @ ${t.get('price',0):.2f}"
            for t in trades_today
        ])
    else:
        trades_text = "  No trades today"

    # Plain English signal
    plain_signal = _plain_english_signal(signal_result)

    msg = (
        f"📊 <b>Daily Summary — {now_str}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{regime_emoji} Regime: <b>{regime}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💼 <b>Portfolio</b>\n"
        f"  Total:    <b>${total:,.2f}</b>\n"
        f"  Today:    {day_arrow} <b>${day_change_val:+,.2f} ({_fmt_pct(day_change_pct)})</b>\n"
        f"  Drawdown: <b>{_fmt_pct(drawdown)}</b> from peak ${peak:,.0f}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📈 <b>Positions</b>\n"
        f"  TQQQ: {tqqq_sh:.0f} shares = ${tqqq_val:,.2f}\n"
        f"  SGOV: {sgov_sh:.0f} shares = ${sgov_val:,.2f}\n"
        f"  Cash: ${cash:,.2f}\n"
        f"  Target: {target_alloc:.0%} | Actual: {actual_alloc:.1f}%\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📉 <b>Market</b>\n"
        f"  QQQ:     ${qqq_price:.2f} ({sma200_dist:+.1f}% vs 200 SMA)\n"
        f"  200 SMA: ${sma200:.2f}\n"
        f"  ATR:     {atr_pct:.2f}% | VIX: {vix:.1f} | Breadth: {breadth:.0f}%\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🧠 <b>Why the bot decided this:</b>\n"
        f"{plain_signal}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🔄 <b>Trades</b>\n"
        f"{trades_text}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🕐 {datetime.now().strftime('%H:%M ET')} | Paper: {config.PAPER_MODE}"
    )
    _send_telegram(msg)
    logger.log_info("send_daily_summary", "Daily Telegram summary sent")


def send_weekly_summary(portfolio_history, trades_this_week, signal_result, account):
    """
    Sends weekly summary every Sunday at 8 PM Eastern.
    """
    now_str      = datetime.now().strftime("%B %d, %Y")
    total        = account.get("total_value", 0)
    cash         = account.get("cash", 0)

    week_start   = portfolio_history[-1]["total_value"] if portfolio_history else total
    week_change_val = total - week_start
    week_change_pct = ((total / week_start) - 1) * 100 if week_start > 0 else 0
    inception_pct   = ((total / config.BACKTEST_CAPITAL) - 1) * 100

    latest       = portfolio_history[0] if portfolio_history else {}
    tqqq_val     = latest.get("tqqq_value", 0)
    tqqq_sh      = latest.get("tqqq_shares", 0)
    sgov_val     = latest.get("sgov_value", 0)
    sgov_sh      = latest.get("sgov_shares", 0)
    drawdown     = latest.get("drawdown_pct", 0)
    peak         = latest.get("peak_value", total)

    regime       = signal_result.get("regime", "UNKNOWN") if signal_result else "UNKNOWN"
    target_alloc = signal_result.get("target_alloc", 0) if signal_result else 0
    qqq_price    = signal_result.get("qqq_price", 0) if signal_result else 0
    sma200       = signal_result.get("sma200", 0) if signal_result else 0
    sma50        = signal_result.get("sma50", 0) if signal_result else 0
    atr_pct      = ((signal_result.get("atr_pct") or 0) * 100) if signal_result else 0
    vix          = signal_result.get("vix", 0) if signal_result else 0
    breadth      = ((signal_result.get("breadth_pct") or 0) * 100) if signal_result else 0

    sma200_dist  = ((qqq_price / sma200) - 1) * 100 if sma200 > 0 else 0
    sma50_dist   = ((qqq_price / sma50) - 1) * 100  if sma50 > 0  else 0
    regime_emoji = _regime_emoji(regime)
    week_arrow   = _pct_arrow(week_change_pct)

    # Trade log
    if trades_this_week:
        trades_text = "\n".join([
            f"  {'🟢' if 'BUY' in t.get('action','') else '🔴'} "
            f"{t.get('date','')} {t.get('action','')} "
            f"{t.get('shares',0):.0f} {t.get('ticker','')}"
            for t in trades_this_week
        ])
    else:
        trades_text = "  No trades this week"

    msg = (
        f"📅 <b>Weekly Summary — {now_str}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{regime_emoji} Regime: <b>{regime}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>Performance</b>\n"
        f"  Portfolio:  <b>${total:,.2f}</b>\n"
        f"  This Week:  {week_arrow} <b>${week_change_val:+,.2f} ({_fmt_pct(week_change_pct)})</b>\n"
        f"  Inception:  <b>{_fmt_pct(inception_pct)}</b>\n"
        f"  Drawdown:   <b>{_fmt_pct(drawdown)}</b> from peak ${peak:,.0f}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📈 <b>Positions</b>\n"
        f"  TQQQ: {tqqq_sh:.0f} shares = ${tqqq_val:,.2f}\n"
        f"  SGOV: {sgov_sh:.0f} shares = ${sgov_val:,.2f}\n"
        f"  Cash: ${cash:,.2f}\n"
        f"  Target allocation: {target_alloc:.0%} TQQQ\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📉 <b>Market This Week</b>\n"
        f"  QQQ:    ${qqq_price:.2f} ({sma200_dist:+.1f}% vs 200 SMA)\n"
        f"  50 SMA: ${sma50:.2f} ({sma50_dist:+.1f}% away)\n"
        f"  ATR:    {atr_pct:.2f}% | VIX: {vix:.1f} | Breadth: {breadth:.0f}%\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🎯 <b>Next Trigger Levels</b>\n"
        f"  Bear trigger (200 SMA): ${sma200:.2f} ({sma200_dist:+.1f}% away)\n"
        f"  Death Cross (50 SMA):   ${sma50:.2f} ({sma50_dist:+.1f}% away)\n"
        f"  ATR extreme:  >3.5% (now {atr_pct:.2f}%)\n"
        f"  VIX crisis:   >35   (now {vix:.1f})\n"
        f"  Breadth collapse: <20% (now {breadth:.0f}%)\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🔄 <b>Trades This Week ({len(trades_this_week)})</b>\n"
        f"{trades_text}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🕐 Generated {datetime.now().strftime('%Y-%m-%d %H:%M ET')}"
    )
    _send_telegram(msg)
    logger.log_info("send_weekly_summary", "Weekly Telegram summary sent")
