# =============================================================================
# bot.py — Main scheduler v2.1
# Changes: 3:55 PM signal, morning message, Telegram alerts
# =============================================================================

import schedule
import time
import traceback
from datetime import datetime, date, timedelta
import pytz

import config
import logger
import data
import strategy
import risk
import orders
import alerts
import reports


# ── STATE ─────────────────────────────────────────────────────────────────────
_state = {
    "atr_extreme_mode": False,
    "cb_state":         "OK",
    "last_regime":      None,
    "pending_buy":      False,
    "pending_alloc":    0.0,
    "pending_regime":   None,
    "last_signal":      None,  # stores full signal result for morning message
}


def get_eastern_now():
    tz = pytz.timezone(config.TIMEZONE)
    return datetime.now(tz)


def is_trading_day():
    return get_eastern_now().weekday() < 5


# =============================================================================
# JOB 0 — 9:00 AM: Morning pre-market briefing
# =============================================================================
def job_morning():
    """Sends morning Telegram message with regime + any queued trades."""
    if not is_trading_day():
        return

    logger.log_info("job_morning", "Sending morning briefing...")
    try:
        client    = orders.get_client()
        account   = orders.get_account_info(client)
        positions = orders.get_positions(client)

        reports.send_morning_message(
            signal_result=_state["last_signal"],
            account=account,
            positions=positions
        )
    except Exception as e:
        logger.log_error("job_morning", str(e))


# =============================================================================
# JOB 1 — 3:55 PM: Signal check (changed from 3:50)
# =============================================================================
def job_signal_check():
    """Runs every trading day at 3:55 PM Eastern."""
    if not is_trading_day():
        return

    today = date.today().isoformat()
    logger.log_info("job_signal_check", f"=== Signal check starting {today} ===")

    try:
        # ── 1. Fetch data ─────────────────────────────────────────────────────
        qqq_prices = data.get_qqq_history()
        vix        = data.get_current_vix()
        breadth    = data.get_nasdaq_breadth(qqq_prices)
        qqq_now    = float(qqq_prices.iloc[-1])

        # ── 2. Run decision tree ──────────────────────────────────────────────
        result = strategy.run_decision_tree(
            qqq_prices=qqq_prices.values,
            vix=vix,
            breadth=breadth,
            atr_extreme_mode=_state["atr_extreme_mode"]
        )

        _state["atr_extreme_mode"] = result["atr_extreme_mode"]
        _state["last_signal"]      = result
        _state["last_signal"]["qqq_price"]   = qqq_now
        _state["last_signal"]["vix"]         = vix
        _state["last_signal"]["breadth_pct"] = breadth

        target_alloc  = result["target_alloc"]
        regime        = result["regime"]
        signal_detail = result["signal_detail"]
        sma200        = result["sma200"]
        sma50         = result["sma50"]
        atr_pct       = result["atr_pct"]

        logger.log_info("job_signal_check",
            f"Regime={regime} target_alloc={target_alloc:.1%}")

        # ── 3. Momentum re-entry guard ────────────────────────────────────────
        if _state["last_regime"] in (None, "BEAR", "ATR_EXTREME",
                                      "BREADTH_COLLAPSE", "MOMENTUM_WAIT"):
            if target_alloc > 0:
                if not strategy.check_momentum_reentry(qqq_prices.values):
                    target_alloc  = 0.0
                    regime        = "MOMENTUM_WAIT"
                    signal_detail += " | STEP7: Momentum guard — staying SGOV"

        # ── 4. Get Alpaca state ───────────────────────────────────────────────
        client    = orders.get_client()
        account   = orders.get_account_info(client)
        positions = orders.get_positions(client)

        total_val    = account["total_value"]
        tqqq_pos     = positions.get(config.BULL_TICKER, {})
        tqqq_val     = tqqq_pos.get("market_value", 0)
        actual_alloc = (tqqq_val / total_val) if total_val > 0 else 0

        # ── 5. Circuit breaker ────────────────────────────────────────────────
        peak = logger.get_peak_value()
        # Fix: use actual peak, not backtest capital
        if peak < total_val:
            peak = total_val

        cb = risk.check_circuit_breaker(total_val, peak, _state["cb_state"])

        if cb["state"] != _state["cb_state"]:
            _state["cb_state"] = cb["state"]
            alerts.alert_circuit_breaker(
                cb["state"], cb["drawdown"], total_val, peak, cb["action"])
            logger.save_circuit_breaker(
                today, cb["state"], cb["drawdown"], cb["action"])

        if cb["action"] in ("STOP_ALL", "HOLD"):
            target_alloc = actual_alloc
        elif cb["action"] == "HALT_BUYS" and target_alloc > actual_alloc:
            target_alloc = actual_alloc

        # ── 6. Regime change alert ────────────────────────────────────────────
        if _state["last_regime"] and regime != _state["last_regime"]:
            old_is_bull = "BULL" in (_state["last_regime"] or "")
            new_is_bull = "BULL" in regime
            if old_is_bull != new_is_bull:
                alerts.alert_regime_change(
                    _state["last_regime"], regime,
                    qqq_now, sma200, signal_detail)

        # ── 7. Queue trade if needed ──────────────────────────────────────────
        alloc_diff = abs(target_alloc - actual_alloc)
        if alloc_diff > 0.05:
            _state["pending_buy"]    = True
            _state["pending_alloc"]  = target_alloc
            _state["pending_regime"] = regime
            logger.log_info("job_signal_check",
                f"Trade queued: target={target_alloc:.1%} current={actual_alloc:.1%}")
        else:
            _state["pending_buy"] = False

        # ── 8. Save to database ───────────────────────────────────────────────
        logger.save_signal(
            date=today, qqq_price=qqq_now, sma200=sma200, sma50=sma50,
            atr_pct=atr_pct, vix=vix, breadth_pct=breadth,
            regime=regime, target_alloc=target_alloc, signal_detail=signal_detail
        )

        # ── 9. Portfolio snapshot ─────────────────────────────────────────────
        sgov_pos  = positions.get(config.BEAR_TICKER, {})
        sgov_val  = sgov_pos.get("market_value", 0)
        sgov_sh   = sgov_pos.get("shares", 0)
        tqqq_sh   = tqqq_pos.get("shares", 0)
        drawdown  = cb["drawdown"] * 100

        logger.save_portfolio(
            date=today, total_value=total_val,
            tqqq_shares=tqqq_sh, tqqq_value=tqqq_val,
            sgov_shares=sgov_sh, sgov_value=sgov_val,
            cash=account["cash"], target_alloc=target_alloc,
            actual_alloc=actual_alloc, drawdown_pct=drawdown,
            peak_value=peak
        )

        # ── 10. Get previous day for day change calculation ───────────────────
        portfolio_rows = logger.get_last_n_portfolio(2)
        current_row    = portfolio_rows[0] if portfolio_rows else {}
        if len(portfolio_rows) >= 2:
            current_row["prev_total"] = portfolio_rows[1]["total_value"]
        else:
            current_row["prev_total"] = total_val

        # ── 11. Daily Telegram summary ────────────────────────────────────────
        trades_today = logger.get_trades_since(today)
        result["qqq_price"]   = qqq_now
        result["vix"]         = vix
        result["breadth_pct"] = breadth

        reports.send_daily_summary(
            portfolio=current_row,
            signal_result=result,
            trades_today=trades_today,
            account=account
        )

        _state["last_regime"] = regime
        logger.save_bot_run(today, "OK", f"Regime={regime} alloc={target_alloc:.1%}")
        logger.log_info("job_signal_check", "=== Signal check complete ===")

    except Exception as e:
        err = traceback.format_exc()
        logger.log_error("job_signal_check", err)
        alerts.alert_error("job_signal_check", str(e), err)
        logger.save_bot_run(date.today().isoformat(), "ERROR", str(e))


# =============================================================================
# JOB 2 — 9:25 AM: Gap guard + execute trade
# =============================================================================
def job_gap_guard():
    """Runs at 9:25 AM on days when a trade is queued."""
    if not is_trading_day():
        return
    if not _state["pending_buy"]:
        return

    today = date.today().isoformat()
    logger.log_info("job_gap_guard", "Gap guard check starting...")

    try:
        last_signal = logger.get_last_signal()
        if not last_signal:
            logger.log_warning("job_gap_guard", "No prior signal — skipping")
            _state["pending_buy"] = False
            return

        prior_close   = last_signal["qqq_price"]
        premarket_now = data.get_premarket_qqq_price()
        safe          = strategy.check_gap_guard(premarket_now, prior_close)

        if not safe:
            logger.log_warning("job_gap_guard", "Gap too large — aborting trade")
            _state["pending_buy"] = False
            alerts.alert_error("job_gap_guard",
                f"Gap guard blocked: pre-market ${premarket_now:.2f} "
                f"vs close ${prior_close:.2f} "
                f"({(premarket_now/prior_close-1)*100:.1f}%)")
            return

        client       = orders.get_client()
        account      = orders.get_account_info(client)
        positions    = orders.get_positions(client)
        target_alloc = _state["pending_alloc"]

        logger.log_info("job_gap_guard",
            f"Gap guard passed. Executing to {target_alloc:.1%} TQQQ...")

        orders_placed = orders.rebalance_to_target(
            client=client,
            ticker_bull=config.BULL_TICKER,
            ticker_bear=config.BEAR_TICKER,
            target_alloc=target_alloc,
            account=account,
            positions=positions,
            reason=f"regime={_state['pending_regime']}"
        )

        for order in orders_placed:
            action     = "BUY" if order.side.value == "buy" else "SELL"
            qty        = float(order.qty)
            fill_price = premarket_now

            logger.save_trade(
                date=today,
                action=f"{action}_{order.symbol}",
                ticker=order.symbol,
                shares=qty,
                price=fill_price,
                value=qty * fill_price,
                notes=f"regime={_state['pending_regime']}"
            )
            alerts.alert_trade(
                action=action,
                ticker=order.symbol,
                shares=int(qty),
                price=fill_price,
                value=qty * fill_price,
                regime=_state["pending_regime"],
                reason="Regime signal"
            )

        _state["pending_buy"] = False
        logger.log_info("job_gap_guard",
            f"Done. {len(orders_placed)} orders placed.")

    except Exception as e:
        err = traceback.format_exc()
        logger.log_error("job_gap_guard", err)
        alerts.alert_error("job_gap_guard", str(e), err)
        _state["pending_buy"] = False


# =============================================================================
# JOB 3 — Sunday 8 PM: Weekly drift + summary
# =============================================================================
def job_weekly():
    """Runs every Sunday at 8 PM Eastern."""
    today = date.today().isoformat()
    logger.log_info("job_weekly", "Weekly check starting...")

    try:
        client    = orders.get_client()
        account   = orders.get_account_info(client)
        positions = orders.get_positions(client)

        total_val    = account["total_value"]
        tqqq_pos     = positions.get(config.BULL_TICKER, {})
        tqqq_val     = tqqq_pos.get("market_value", 0)
        actual_alloc = (tqqq_val / total_val) if total_val > 0 else 0

        last_signal  = logger.get_last_signal()
        target_alloc = last_signal["target_alloc"] if last_signal else 0

        # Drift check
        if strategy.check_drift(actual_alloc, target_alloc):
            _state["pending_buy"]    = True
            _state["pending_alloc"]  = target_alloc
            _state["pending_regime"] = last_signal["regime"] if last_signal else "DRIFT"

        # Weekly summary
        portfolio_history = logger.get_last_n_portfolio(7)
        monday = (date.today() - timedelta(days=6)).isoformat()
        trades_this_week  = logger.get_trades_since(monday)

        reports.send_weekly_summary(
            portfolio_history=portfolio_history,
            trades_this_week=trades_this_week,
            signal_result=last_signal or {},
            account=account
        )

        # Dead man switch
        run_dates = logger.get_last_run_dates(5)
        if risk.check_dead_mans_switch(run_dates):
            days = risk.count_trading_days_between(
                date.fromisoformat(run_dates[0]) if run_dates else date.today(),
                date.today()
            )
            alerts.alert_dead_mans_switch(
                run_dates[0] if run_dates else "Never", days)

        logger.log_info("job_weekly", "Weekly check complete")

    except Exception as e:
        err = traceback.format_exc()
        logger.log_error("job_weekly", err)
        alerts.alert_error("job_weekly", str(e), err)


# =============================================================================
# STARTUP
# =============================================================================
def startup():
    logger.log_info("startup", "=== TQQQ Adaptive Regime Bot v2.1 starting ===")
    logger.log_info("startup", f"Paper mode: {config.PAPER_MODE}")

    logger.init_db()

    # Test Alpaca
    try:
        client  = orders.get_client()
        account = orders.get_account_info(client)
        logger.log_info("startup",
            f"Alpaca connected. Portfolio: ${account['total_value']:,.2f} "
            f"| Cash: ${account['cash']:,.2f}")
    except Exception as e:
        logger.log_error("startup", f"Alpaca connection failed: {e}")
        alerts.alert_error("startup", f"Bot failed to connect to Alpaca: {e}")
        raise

    # Test Telegram
    try:
        client  = orders.get_client()
        account = orders.get_account_info(client)
        alerts.alert_startup(
            config.PAPER_MODE,
            account["total_value"],
            account["cash"]
        )
        logger.log_info("startup", "Telegram test sent successfully")
    except Exception as e:
        logger.log_error("startup", f"Telegram test failed: {e}")

    # Load last signal into state for morning message
    try:
        last = logger.get_last_signal()
        if last:
            _state["last_signal"]  = last
            _state["last_regime"]  = last["regime"]
    except Exception:
        pass

    logger.log_info("startup", "Startup complete. Scheduler running...")


# =============================================================================
# MAIN
# =============================================================================
if __name__ == "__main__":
    startup()

    # Morning briefing: Mon-Fri 9:00 AM ET
    schedule.every().monday.at("09:00").do(job_morning)
    schedule.every().tuesday.at("09:00").do(job_morning)
    schedule.every().wednesday.at("09:00").do(job_morning)
    schedule.every().thursday.at("09:00").do(job_morning)
    schedule.every().friday.at("09:00").do(job_morning)

    # Gap guard: Mon-Fri 9:25 AM ET
    schedule.every().monday.at("09:25").do(job_gap_guard)
    schedule.every().tuesday.at("09:25").do(job_gap_guard)
    schedule.every().wednesday.at("09:25").do(job_gap_guard)
    schedule.every().thursday.at("09:25").do(job_gap_guard)
    schedule.every().friday.at("09:25").do(job_gap_guard)

    # Signal check: Mon-Fri 3:55 PM ET (changed from 3:50)
    schedule.every().monday.at("15:55").do(job_signal_check)
    schedule.every().tuesday.at("15:55").do(job_signal_check)
    schedule.every().wednesday.at("15:55").do(job_signal_check)
    schedule.every().thursday.at("15:55").do(job_signal_check)
    schedule.every().friday.at("15:55").do(job_signal_check)

    # Weekly: Sunday 8 PM ET
    schedule.every().sunday.at("20:00").do(job_weekly)

    logger.log_info("main", "All jobs scheduled. Bot v2.1 is live.")
    logger.log_info("main", "Morning:     Mon-Fri 9:00 AM ET")
    logger.log_info("main", "Gap guard:   Mon-Fri 9:25 AM ET")
    logger.log_info("main", "Signal:      Mon-Fri 3:55 PM ET")
    logger.log_info("main", "Weekly:      Sunday  8:00 PM ET")

    while True:
        schedule.run_pending()
        time.sleep(30)
