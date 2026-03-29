# =============================================================================
# orders.py — Trade execution via Alpaca API
# Handles all buy/sell orders with safety checks
# =============================================================================

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
import config
import logger


def get_client():
    """Returns an authenticated Alpaca trading client."""
    return TradingClient(
        api_key=config.ALPACA_API_KEY,
        secret_key=config.ALPACA_SECRET_KEY,
        paper=config.PAPER_MODE
    )


def get_account_info(client):
    """
    Returns account summary dict.
    """
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
    """
    Returns current positions as dict: {ticker: {shares, value, price, avg_cost}}
    """
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
    """Returns single position or None if not held."""
    positions = get_positions(client)
    return positions.get(ticker, None)


def buy_shares(client, ticker, shares, reason=""):
    """
    Places a market buy order.

    Args:
        client:  Alpaca TradingClient
        ticker:  e.g. "TQQQ"
        shares:  integer number of shares
        reason:  notes for the log

    Returns:
        order object or None on failure
    """
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
    """
    Liquidates entire position in a ticker.

    Returns:
        order object or None if no position held
    """
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

    Logic:
    - If target_alloc = 0   → sell all TQQQ, buy SGOV with proceeds
    - If target_alloc = 1   → sell all SGOV, buy TQQQ with proceeds
    - If target_alloc = 0.5 → sell excess of whichever is overweight, buy underweight

    Args:
        client:       Alpaca TradingClient
        ticker_bull:  "TQQQ"
        ticker_bear:  "SGOV"
        target_alloc: float 0.0–1.0 (TQQQ allocation)
        account:      dict from get_account_info()
        positions:    dict from get_positions()
        reason:       notes for log

    Returns:
        list of orders placed
    """
    orders = []
    total  = account["total_value"]

    target_tqqq_value = total * target_alloc
    target_sgov_value = total * (1 - target_alloc)

    current_tqqq = positions.get(ticker_bull, {})
    current_sgov = positions.get(ticker_bear, {})

    current_tqqq_value = current_tqqq.get("market_value", 0)
    current_sgov_value = current_sgov.get("market_value", 0)

    logger.log_info("rebalance_to_target",
        f"Target: {target_alloc:.1%} TQQQ / {1-target_alloc:.1%} SGOV | "
        f"Current: TQQQ ${current_tqqq_value:,.2f} / SGOV ${current_sgov_value:,.2f}")

    # ── CASE 1: Full switch to SGOV ───────────────────────────────────────────
    if target_alloc == 0.0:
        if current_tqqq_value > 1:
            order = sell_all_shares(client, ticker_bull, reason)
            if order:
                orders.append(order)
        # buy SGOV with all available cash
        cash  = account["cash"] + current_tqqq_value  # approximate
        price = current_sgov.get("current_price", 100)
        if price <= 0:
            price = 100
        shares = int(cash / price)
        if shares > 0:
            order = buy_shares(client, ticker_bear, shares, reason)
            if order:
                orders.append(order)
        return orders

    # ── CASE 2: Full switch to TQQQ ──────────────────────────────────────────
    if target_alloc == 1.0:
        if current_sgov_value > 1:
            order = sell_all_shares(client, ticker_bear, reason)
            if order:
                orders.append(order)
        cash  = account["cash"] + current_sgov_value
        price = current_tqqq.get("current_price", 50)
        if price <= 0:
            price = 50
        shares = int(cash / price)
        if shares > 0:
            order = buy_shares(client, ticker_bull, shares, reason)
            if order:
                orders.append(order)
        return orders

    # ── CASE 3: Partial allocation ────────────────────────────────────────────
    tqqq_diff = target_tqqq_value - current_tqqq_value
    sgov_diff = target_sgov_value - current_sgov_value

    # Sell the overweight side first to free up cash
    if tqqq_diff < 0:
        # Reduce TQQQ
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

    if sgov_diff < 0:
        # Reduce SGOV
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

    # Buy the underweight side
    if tqqq_diff > 0:
        tqqq_price  = current_tqqq.get("current_price", 50) or 50
        shares_buy  = int(tqqq_diff / tqqq_price)
        if shares_buy > 0:
            order = buy_shares(client, ticker_bull, shares_buy, reason)
            if order:
                orders.append(order)

    if sgov_diff > 0:
        sgov_price = current_sgov.get("current_price", 100) or 100
        shares_buy = int(sgov_diff / sgov_price)
        if shares_buy > 0:
            order = buy_shares(client, ticker_bear, shares_buy, reason)
            if order:
                orders.append(order)

    return orders


def cancel_all_open_orders(client):
    """Cancels all open/pending orders. Used for safety before new orders."""
    try:
        client.cancel_orders()
        logger.log_info("cancel_all_open_orders", "All open orders cancelled")
    except Exception as e:
        logger.log_warning("cancel_all_open_orders", f"Could not cancel orders: {e}")


def is_market_open(client):
    """Returns True if the market is currently open."""
    try:
        clock = client.get_clock()
        return clock.is_open
    except Exception as e:
        logger.log_error("is_market_open", str(e))
        return False
