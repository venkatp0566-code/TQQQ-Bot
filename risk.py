# =============================================================================
# risk.py — Circuit breakers + dead man switch v2.2
# =============================================================================

from datetime import datetime, date, timedelta
import pytz
import config
import logger


def check_circuit_breaker(current_value, peak_value, cb_state):
    """
    Checks portfolio drawdown against circuit breaker levels.

    Args:
        current_value: current total portfolio value
        peak_value:    all-time high portfolio value
        cb_state:      current CB state string ("OK", "WARNING", "HALT", "STOP")

    Returns dict:
        state:   "OK" | "WARNING" | "HALT" | "STOP"
        action:  what the bot should do
        drawdown: current drawdown as float (e.g. -0.25)
        message: human-readable description
    """
    if peak_value <= 0:
        return {"state": "OK", "action": "NORMAL", "drawdown": 0.0, "message": "No peak yet"}

    drawdown = (current_value - peak_value) / peak_value

    # Check if we're in STOP and should auto-resume
    if cb_state == "STOP":
        stop_level = peak_value * (1 + config.CB_STOP)
        resume_level = stop_level * (1 + config.CB_RESUME)
        if current_value >= resume_level:
            logger.log_info("circuit_breaker",
                f"Auto-resuming: ${current_value:.2f} >= resume level ${resume_level:.2f}")
            return {
                "state":    "OK",
                "action":   "RESUME",
                "drawdown": drawdown,
                "message":  f"Auto-resumed. Recovery +{config.CB_RESUME:.0%} reached.",
            }
        else:
            return {
                "state":    "STOP",
                "action":   "HOLD",
                "drawdown": drawdown,
                "message":  f"Still in STOP. Drawdown {drawdown:.1%}. Need ${resume_level:,.2f} to resume.",
            }

    # Fresh CB evaluation
    if drawdown <= config.CB_STOP:
        logger.log_warning("circuit_breaker", f"FULL STOP triggered. Drawdown: {drawdown:.1%}")
        return {
            "state":   "STOP",
            "action":  "STOP_ALL",
            "drawdown": drawdown,
            "message": f"CIRCUIT BREAKER FULL STOP. Drawdown {drawdown:.1%}. Manual review required.",
        }
    elif drawdown <= config.CB_HALT:
        logger.log_warning("circuit_breaker", f"HALT triggered. Drawdown: {drawdown:.1%}")
        return {
            "state":   "HALT",
            "action":  "HALT_BUYS",
            "drawdown": drawdown,
            "message": f"CIRCUIT BREAKER HALT. Drawdown {drawdown:.1%}. No new TQQQ buys.",
        }
    elif drawdown <= config.CB_WARNING:
        logger.log_warning("circuit_breaker", f"WARNING triggered. Drawdown: {drawdown:.1%}")
        return {
            "state":   "WARNING",
            "action":  "EMAIL_ONLY",
            "drawdown": drawdown,
            "message": f"CIRCUIT BREAKER WARNING. Drawdown {drawdown:.1%}. Monitoring closely.",
        }
    else:
        return {
            "state":   "OK",
            "action":  "NORMAL",
            "drawdown": drawdown,
            "message": f"Normal. Drawdown {drawdown:.1%}.",
        }


def check_dead_mans_switch(last_run_dates):
    """
    Checks if the bot has gone silent for too many trading days.

    Args:
        last_run_dates: list of date strings "YYYY-MM-DD" from bot_runs table

    Returns:
        True if dead man switch should fire (bot went silent), False if OK
    """
    if not last_run_dates:
        return True  # no runs ever recorded — fire alert

    tz    = pytz.timezone(config.TIMEZONE)
    today = datetime.now(tz).date()

    last_run = datetime.strptime(last_run_dates[0], "%Y-%m-%d").date()
    trading_days_missed = count_trading_days_between(last_run, today)

    if trading_days_missed >= config.DEAD_MANS_DAYS:
        logger.log_warning("dead_mans_switch",
            f"Bot silent for {trading_days_missed} trading days. Last run: {last_run}")
        return True

    return False


def count_trading_days_between(start_date, end_date):
    """
    Counts approximate trading days between two dates.
    Excludes weekends. Does not account for holidays (acceptable approximation).
    """
    count = 0
    current = start_date + timedelta(days=1)
    while current <= end_date:
        if current.weekday() < 5:  # Monday=0, Friday=4
            count += 1
        current += timedelta(days=1)
    return count
