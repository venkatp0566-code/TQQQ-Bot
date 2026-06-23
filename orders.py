# =============================================================================
# orders.py — Trade execution via Alpaca API v2.2
# Fixed: use cash not buying_power to prevent margin usage
# Fixed: skip buy if already at/above target allocation
# =============================================================================

import time
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
import config
import logger


def get_client():
    return TradingClient(
        api_key=config.ALPACA_API_KEY,
        secret_key=config.ALPACA_SECRET_KEY,
        paper=config.PAPER_MODE
    )


def get_account_info(client):
    try:
        account = client.get_account()
        return {
            "total_value":  float(account.portfolio_value),
            "cash":         float(account.cash),
            "buying_power": float(account.buying_power),
            "status":       account.status,
        }
    except Exception as e:
        logger.log_error("get_account_info", str(e))
        raise


def get_positions(client):
    try:
        positions = client.get_all_positions()
        result = {}
        for p in positions:
            result[p.symbol] = {
                "shares":        float(p.qty),
                "market_value":  float(p.market_value),
                "current_price": float(p.current_price),
                "avg_cost":      float(p.avg_entry_price),
            }
        return result
    except Exception as e:
        logger.log_error("get_positions", str(e))
        return {}


def get_position(client, ticker):
    positions = get_positions(client)
    return positions.get(ticker, None)


def buy_shares(client, ticker, shares, reason=""):
    if shares <= 0:
        logger.log_warning("buy_shares", f"Skipping buy — shares={shares}")
        return None
    try:
        order_data = MarketOrderRequest(
            symbol=ticker,
            qty=shares,
            side=OrderSide.BUY,
            time_in_force=TimeInForce.DAY
        )
        order = client.submit_order(order_data)
        logger.log_info("buy_shares",
            f"BUY {shares} {ticker} submitted. OrderID={order.id}. Reason: {reason}")
        return order
    except Exception as e:
        logger.log_error("buy_shares", f"Failed to buy {shares} {ticker}: {e}")
        raise


def sell_all_shares(client, ticker, reason=""):
    try:
        position = get_position(client, ticker)
        if not position:
            logger.log_info("sell_all_shares", f"No {ticker} position to sell")
            return None
        shares = int(position["shares"])
        if shares <= 0:
            return None
        order_data = MarketOrderRequest(
            symbol=ticker,
            qty=shares,
            side=OrderSide.SELL,
            time_in_force=TimeInForce.DAY
        )
        order = client.submit_order(order_data)
        logger.log_info("sell_all_shares",
            f"SELL {shares} {ticker} submitted. OrderID={order.id}. Reason: {reason}")
        return order
    except Exception as e:
        logger.log_error("sell_all_shares", f"Failed to sell {ticker}: {e}")
        raise


def rebalance_to_target(client, ticker_bull, ticker_bear,
                         target_alloc, account, positions, reason=""):
    """
    Rebalances portfolio to target TQQQ/SGOV allocation.
    NEVER uses margin — all buys capped to available cash only.
    """
    orders = []
    total  = account["total_value"]

    target_tqqq_value = total * target_alloc
    target_sgov_value = total * (1 - target_alloc)

    current_tqqq = positions.get(ticker_bull, {})
    current_sgov = positions.get(ticker_bear, {})

    current_tqqq_value = current_tqqq.get("market_value", 0)
    current_sgov_value = current_sgov.get("market_value", 0)

    # Safe actual alloc — capped at 1.0 to prevent margin distortion
    safe_actual = min(current_tqqq_value / total, 1.0) if total > 0 else 0

    logger.log_info("rebalance_to_target",
        f"Target: {target_alloc:.1%} TQQQ / {1-target_alloc:.1%} SGOV | "
        f"Current: TQQQ ${current_tqqq_value:,.2f} ({safe_actual:.1%}) / "
        f"SGOV ${current_sgov_value:,.2f} | Cash: ${account['cash']:,.2f}")

    # ── CASE 1: Full switch to SGOV ───────────────────────────────────────────
    if target_alloc == 0.0:
        if current_tqqq_value > 1:
            order = sell_all_shares(client, ticker_bull, reason)
            if order:
                orders.append(order)
            time.sleep(3)

        try:
            fresh_account = get_account_info(client)
            available     = max(fresh_account["cash"], 0)  # never negative
        except Exception:
            available = max(account["cash"], 0)

        price  = current_sgov.get("current_price", 100)
        if price <= 0:
            price = 100
        shares = int((available * 0.97) / price)
        if shares > 0:
            order = buy_shares(client, ticker_bear, shares, reason)
            if order:
                orders.append(order)
        return orders

    # ── CASE 2: Full switch to TQQQ ──────────────────────────────────────────
    if target_alloc == 1.0:
        # Sell SGOV first if held
        if current_sgov_value > 1:
            order = sell_all_shares(client, ticker_bear, reason)
            if order:
                orders.append(order)
            time.sleep(3)

        # Only buy more TQQQ if we have positive cash to deploy
        try:
            fresh_account = get_account_info(client)
            available     = max(fresh_account["cash"], 0)  # never use margin
        except Exception:
            available = max(account["cash"], 0)

        if available < 10:
            logger.log_info("rebalance_to_target",
                f"No cash to deploy (${available:.2f}) — already fully invested")
            return orders

        price  = current_tqqq.get("current_price", 50)
        if price <= 0:
            price = 50
        shares = int((available * 0.97) / price)
        if shares > 0:
            order = buy_shares(client, ticker_bull, shares, reason)
            if order:
                orders.append(order)
        return orders

    # ── CASE 3: Partial allocation ────────────────────────────────────────────
    tqqq_diff = target_tqqq_value - current_tqqq_value
    sgov_diff = target_sgov_value - current_sgov_value

    sells_placed = []

    # Sell overweight side first
    if tqqq_diff < 0:
        tqqq_price  = current_tqqq.get("current_price", 50) or 50
        shares_sell = int(abs(tqqq_diff) / tqqq_price)
        if shares_sell > 0:
            order_data = MarketOrderRequest(
                symbol=ticker_bull,
                qty=shares_sell,
                side=OrderSide.SELL,
                time_in_force=TimeInForce.DAY
            )
            order = client.submit_order(order_data)
            logger.log_info("rebalance", f"SELL {shares_sell} {ticker_bull} (rebalance)")
            orders.append(order)
            sells_placed.append(order)

    if sgov_diff < 0:
        sgov_price  = current_sgov.get("current_price", 100) or 100
        shares_sell = int(abs(sgov_diff) / sgov_price)
        if shares_sell > 0:
            order_data = MarketOrderRequest(
                symbol=ticker_bear,
                qty=shares_sell,
                side=OrderSide.SELL,
                time_in_force=TimeInForce.DAY
            )
            order = client.submit_order(order_data)
            logger.log_info("rebalance", f"SELL {shares_sell} {ticker_bear} (rebalance)")
            orders.append(order)
            sells_placed.append(order)

    # Wait for cash to settle after sells
    if sells_placed:
        time.sleep(3)

    # Buy underweight side — cash only, never margin
    try:
        fresh_account = get_account_info(client)
        available     = max(fresh_account["cash"], 0)
    except Exception:
        available = max(account["cash"], 0)

    if tqqq_diff > 0:
        tqqq_price = current_tqqq.get("current_price", 50) or 50
        shares_buy = int((min(tqqq_diff, available * 0.97)) / tqqq_price)
        if shares_buy > 0:
            order = buy_shares(client, ticker_bull, shares_buy, reason)
            if order:
                orders.append(order)
                available -= shares_buy * tqqq_price  # track remaining cash

    if sgov_diff > 0:
        sgov_price = current_sgov.get("current_price", 100) or 100
        shares_buy = int((min(sgov_diff, available * 0.97)) / sgov_price)
        if shares_buy > 0:
            order = buy_shares(client, ticker_bear, shares_buy, reason)
            if order:
                orders.append(order)

    return orders


def cancel_all_open_orders(client):
    try:
        client.cancel_orders()
        logger.log_info("cancel_all_open_orders", "All open orders cancelled")
    except Exception as e:
        logger.log_warning("cancel_all_open_orders", f"Could not cancel orders: {e}")


def is_market_open(client):
    try:
        clock = client.get_clock()
        return clock.is_open
    except Exception as e:
        logger.log_error("is_market_open", str(e))
        return False
