# =============================================================================
# signal.py — Calculates all indicators and runs the full decision tree
# This is the brain of the strategy — all 9 steps live here
# =============================================================================

import numpy as np
import config
import logger


def calculate_sma(prices, period):
    """Simple moving average over last N periods."""
    if len(prices) < period:
        return None
    return float(np.mean(prices[-period:]))


def calculate_atr_pct(prices, period=14):
    """
    ATR as a percentage of current price.
    Uses absolute daily returns as a simplified ATR proxy.
    ATR% = average(|daily return|) over last N days
    """
    if len(prices) < period + 1:
        return None
    returns = []
    for i in range(-period, 0):
        daily_ret = abs((prices[i] - prices[i-1]) / prices[i-1])
        returns.append(daily_ret)
    return float(np.mean(returns))


def run_decision_tree(qqq_prices, vix, breadth, atr_extreme_mode=False):
    """
    Runs the full 9-step decision tree.

    Args:
        qqq_prices:      numpy array or list of QQQ closing prices (oldest first)
        vix:             current VIX value (float)
        breadth:         Nasdaq breadth 0.0–1.0 (float)
        atr_extreme_mode: True if currently locked out due to ATR > 3.5%

    Returns dict:
        target_alloc:    float 0.0–1.0 (TQQQ allocation)
        regime:          string label
        signal_detail:   human-readable explanation of every step
        sma200:          float
        sma50:           float
        atr_pct:         float
        atr_extreme_mode: bool (updated value to persist to next run)
    """
    prices = list(qqq_prices)
    detail = []

    sma200  = calculate_sma(prices, config.SMA_LONG)
    sma50   = calculate_sma(prices, config.SMA_SHORT)
    atr_pct = calculate_atr_pct(prices, config.ATR_PERIOD)
    current = prices[-1]

    if sma200 is None or sma50 is None or atr_pct is None:
        return {
            "target_alloc":    0.0,
            "regime":          "INSUFFICIENT_DATA",
            "signal_detail":   "Not enough data yet — staying in SGOV",
            "sma200":          sma200,
            "sma50":           sma50,
            "atr_pct":         atr_pct,
            "atr_extreme_mode": atr_extreme_mode,
        }

    # ── STEP 1: Master Switch ─────────────────────────────────────────────────
    if current <= sma200:
        detail.append(f"STEP1: QQQ ${current:.2f} <= SMA200 ${sma200:.2f} → BEAR REGIME")
        return {
            "target_alloc":    0.0,
            "regime":          "BEAR",
            "signal_detail":   " | ".join(detail),
            "sma200":          sma200,
            "sma50":           sma50,
            "atr_pct":         atr_pct,
            "atr_extreme_mode": False,  # reset when we go bear
        }
    detail.append(f"STEP1: QQQ ${current:.2f} > SMA200 ${sma200:.2f} → BULL")

    # ── STEP 2: Trend Confirmation ────────────────────────────────────────────
    if sma50 > sma200:
        base   = config.ALLOC_STRONG_BULL
        regime = "STRONG_BULL"
        detail.append(f"STEP2: SMA50 ${sma50:.2f} > SMA200 → STRONG BULL → base={base:.0%}")
    else:
        base   = config.ALLOC_WEAK_BULL
        regime = "WEAK_BULL"
        detail.append(f"STEP2: SMA50 ${sma50:.2f} < SMA200 → WEAK BULL → base={base:.0%}")

    # ── STEP 3: ATR Extreme Exit ──────────────────────────────────────────────
    if atr_pct > config.ATR_EXTREME:
        atr_extreme_mode = True
        detail.append(f"STEP3: ATR {atr_pct:.2%} > {config.ATR_EXTREME:.1%} → EXTREME VOLATILITY → SGOV")
        return {
            "target_alloc":    0.0,
            "regime":          "ATR_EXTREME",
            "signal_detail":   " | ".join(detail),
            "sma200":          sma200,
            "sma50":           sma50,
            "atr_pct":         atr_pct,
            "atr_extreme_mode": True,
        }

    if atr_extreme_mode:
        if atr_pct > config.ATR_REENTRY:
            detail.append(f"STEP3: ATR {atr_pct:.2%} still > reentry buffer {config.ATR_REENTRY:.1%} → stay SGOV")
            return {
                "target_alloc":    0.0,
                "regime":          "ATR_REENTRY_WAIT",
                "signal_detail":   " | ".join(detail),
                "sma200":          sma200,
                "sma50":           sma50,
                "atr_pct":         atr_pct,
                "atr_extreme_mode": True,
            }
        else:
            atr_extreme_mode = False
            detail.append(f"STEP3: ATR {atr_pct:.2%} back below {config.ATR_REENTRY:.1%} → extreme mode cleared")
    else:
        detail.append(f"STEP3: ATR {atr_pct:.2%} normal → no extreme exit")

    # ── STEP 4: ATR Normal Sizing ─────────────────────────────────────────────
    if atr_pct < config.ATR_NORMAL:
        atr_mult = 1.00
        detail.append(f"STEP4: ATR {atr_pct:.2%} < {config.ATR_NORMAL:.1%} → full allocation")
    elif atr_pct < config.ATR_ELEVATED:
        atr_mult = config.ATR_MULT_ELEVATED
        detail.append(f"STEP4: ATR {atr_pct:.2%} elevated → x{atr_mult}")
    else:
        atr_mult = config.ATR_MULT_HIGH
        detail.append(f"STEP4: ATR {atr_pct:.2%} high → x{atr_mult}")

    # ── STEP 5: Nasdaq Breadth Filter ────────────────────────────────────────
    if breadth < config.BREADTH_COLLAPSE:
        detail.append(f"STEP5: Breadth {breadth:.1%} < {config.BREADTH_COLLAPSE:.0%} → BREADTH COLLAPSE → SGOV")
        return {
            "target_alloc":    0.0,
            "regime":          "BREADTH_COLLAPSE",
            "signal_detail":   " | ".join(detail),
            "sma200":          sma200,
            "sma50":           sma50,
            "atr_pct":         atr_pct,
            "atr_extreme_mode": atr_extreme_mode,
        }
    elif breadth > config.BREADTH_STRONG:
        breadth_mult = 1.00
        detail.append(f"STEP5: Breadth {breadth:.1%} strong → full")
    elif breadth > config.BREADTH_MIXED:
        breadth_mult = config.BREADTH_MULT_MIXED
        detail.append(f"STEP5: Breadth {breadth:.1%} mixed → x{breadth_mult}")
    else:
        breadth_mult = config.BREADTH_MULT_WEAK
        detail.append(f"STEP5: Breadth {breadth:.1%} weak → x{breadth_mult}")

    # ── STEP 6: VIX Crisis Override ───────────────────────────────────────────
    alloc = base * atr_mult * breadth_mult

    if vix > config.VIX_CRISIS:
        alloc = min(alloc, config.VIX_CRISIS_CAP)
        detail.append(f"STEP6: VIX {vix:.1f} > {config.VIX_CRISIS} → capped at {config.VIX_CRISIS_CAP:.0%}")
        regime = regime + "+VIX_CRISIS"
    else:
        detail.append(f"STEP6: VIX {vix:.1f} normal → no cap")

    alloc = round(min(max(alloc, 0.0), 1.0), 4)
    detail.append(f"FINAL: target_alloc={alloc:.1%} regime={regime}")

    return {
        "target_alloc":    alloc,
        "regime":          regime,
        "signal_detail":   " | ".join(detail),
        "sma200":          sma200,
        "sma50":           sma50,
        "atr_pct":         atr_pct,
        "atr_extreme_mode": atr_extreme_mode,
    }


def check_momentum_reentry(qqq_prices):
    """
    Step 7: Re-entry guard for Bear → Bull transitions.
    QQQ must be higher than it was 20 trading days ago.

    Returns True if momentum is positive (ok to enter), False if not.
    """
    prices = list(qqq_prices)
    if len(prices) < config.MOMENTUM_LOOKBACK + 1:
        return True  # not enough history — allow entry

    current   = prices[-1]
    lookback  = prices[-(config.MOMENTUM_LOOKBACK + 1)]
    result    = current > lookback

    logger.log_info("check_momentum_reentry",
        f"QQQ now ${current:.2f} vs {config.MOMENTUM_LOOKBACK}d ago ${lookback:.2f} → "
        f"{'OK to enter' if result else 'BLOCKED — no momentum'}")
    return result


def check_gap_guard(premarket_price, prior_close):
    """
    Step 8: Gap guard at 9:25 AM.
    Aborts buy if QQQ pre-market is more than 2% below prior close.

    Returns True if safe to buy, False if gap is too large.
    """
    ratio  = premarket_price / prior_close
    safe   = ratio >= config.GAP_GUARD
    pct    = (ratio - 1) * 100

    logger.log_info("check_gap_guard",
        f"Pre-market ${premarket_price:.2f} vs prior close ${prior_close:.2f} "
        f"= {pct:+.2f}% → {'SAFE' if safe else 'GAP TOO LARGE — aborting buy'}")
    return safe


def check_drift(actual_alloc, target_alloc):
    """
    Step 9: Weekly drift check.
    Returns True if rebalance is needed (drift > tolerance).
    """
    drift = abs(actual_alloc - target_alloc)
    needs_rebalance = drift > config.DRIFT_TOLERANCE

    logger.log_info("check_drift",
        f"Actual {actual_alloc:.1%} vs Target {target_alloc:.1%} "
        f"= {drift:.1%} drift → {'REBALANCE NEEDED' if needs_rebalance else 'OK'}")
    return needs_rebalance
