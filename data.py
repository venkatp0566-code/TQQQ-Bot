# =============================================================================
# data.py — Market data v2.2
# History:   Stooq (matches Yahoo Finance exactly, 6800+ days)
# Real-time: Alpaca (live quotes, pre-market, trading)
# VIX:       yfinance (not available elsewhere)
# =============================================================================

import yfinance as yf
import pandas as pd
import numpy as np
import requests
from io import StringIO
from datetime import datetime, timedelta
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest
import config
import logger


def _get_data_client():
    return StockHistoricalDataClient(
        api_key=config.ALPACA_API_KEY,
        secret_key=config.ALPACA_SECRET_KEY
    )


def _fetch_stooq(ticker):
    """
    Fetches full daily price history from Stooq.
    Matches Yahoo Finance daily SMA exactly.
    Stooq format ticker: QQQ → qqq.us, SPY → spy.us
    Returns pandas Series oldest → newest.
    """
    stooq_ticker = ticker.lower() + ".us"
    url = f"https://stooq.com/q/d/l/?s={stooq_ticker}&i=d"

    r = requests.get(url, timeout=15)
    if r.status_code != 200:
        raise ValueError(f"Stooq returned {r.status_code} for {ticker}")

    df = pd.read_csv(StringIO(r.text))

    if df.empty or 'Close' not in df.columns:
        raise ValueError(f"No data returned from Stooq for {ticker}")

    df['Date'] = pd.to_datetime(df['Date'])
    df = df.sort_values('Date')
    prices = df.set_index('Date')['Close'].dropna()

    logger.log_info("fetch_stooq",
        f"Stooq: {len(prices)} days of {ticker}. "
        f"Latest: ${prices.iloc[-1]:.2f} ({prices.index[-1].date()})")
    return prices


def get_qqq_history():
    """
    QQQ daily history via Stooq.
    Matches Yahoo Finance 200/50 SMA exactly.
    """
    try:
        prices = _fetch_stooq(config.SIGNAL_TICKER)
        if len(prices) < config.SMA_LONG:
            raise ValueError(f"Insufficient data: {len(prices)} days")
        return prices
    except Exception as e:
        logger.log_error("get_qqq_history", f"Stooq failed: {e}")
        raise



def get_current_qqq_price():
    """
    Real-time QQQ price via Alpaca live quote.
    Much more accurate than Stooq for current price.
    """
    try:
        client  = _get_data_client()
        request = StockLatestQuoteRequest(
            symbol_or_symbols=config.SIGNAL_TICKER)
        quote   = client.get_stock_latest_quote(request)
        q       = quote[config.SIGNAL_TICKER]

        bid = float(q.bid_price or 0)
        ask = float(q.ask_price or 0)

        if bid > 0 and ask > 0:
            price = (bid + ask) / 2
        elif ask > 0:
            price = ask
        elif bid > 0:
            price = bid
        else:
            raise ValueError("No valid bid/ask from Alpaca")

        logger.log_info("get_current_qqq_price",
            f"Alpaca real-time {config.SIGNAL_TICKER}: ${price:.2f}")
        return price

    except Exception as e:
        logger.log_warning("get_current_qqq_price",
            f"Alpaca real-time failed ({e}) — using Stooq latest close")
        prices = get_qqq_history()
        return float(prices.iloc[-1])


def get_premarket_qqq_price():
    """
    Pre-market QQQ price via Alpaca at 9:25 AM.
    Falls back to last close if pre-market unavailable.
    """
    try:
        client  = _get_data_client()
        request = StockLatestQuoteRequest(
            symbol_or_symbols=config.SIGNAL_TICKER)
        quote   = client.get_stock_latest_quote(request)
        q       = quote[config.SIGNAL_TICKER]

        bid = float(q.bid_price or 0)
        ask = float(q.ask_price or 0)

        if bid > 0 and ask > 0:
            price = (bid + ask) / 2
        elif ask > 0:
            price = ask
        elif bid > 0:
            price = bid
        else:
            raise ValueError("No valid bid/ask")

        logger.log_info("get_premarket_qqq_price",
            f"Alpaca pre-market {config.SIGNAL_TICKER}: ${price:.2f}")
        return price

    except Exception as e:
        logger.log_warning("get_premarket_qqq_price",
            f"Pre-market failed ({e}) — using last Stooq close")
        prices = get_qqq_history()
        return float(prices.iloc[-1])


def get_current_vix():
    """
    VIX via yfinance (not available on Alpaca or Stooq).
    Defaults to 20.0 if unavailable — non-fatal.
    """
    try:
        vix = yf.Ticker(config.VIX_TICKER).fast_info["last_price"]
        if not vix or vix <= 0:
            raise ValueError(f"Invalid VIX: {vix}")
        logger.log_info("get_current_vix", f"VIX: {vix:.1f}")
        return float(vix)
    except Exception as e:
        logger.log_warning("get_current_vix",
            f"VIX unavailable ({e}) — defaulting to 20.0")
        return 20.0


def get_nasdaq_breadth(qqq_history=None):
    """
    Nasdaq-100 breadth: % of top 20 QQQ holdings above their 200-day SMA.
    Uses Stooq for each holding — same accuracy as main QQQ data.
    Returns float 0.0-1.0
    """
    holdings = [
        "MSFT", "AAPL", "NVDA", "AMZN", "META",
        "GOOGL", "GOOG", "TSLA", "AVGO", "COST",
        "NFLX", "AMD", "ADBE", "QCOM", "INTC",
        "INTU", "CSCO", "TXN", "AMGN", "HON"
    ]

    above_sma = 0
    total     = 0

    for sym in holdings:
        try:
            prices = _fetch_stooq(sym)
            if len(prices) < 200:
                continue
            if prices.iloc[-1] > prices.iloc[-200:].mean():
                above_sma += 1
            total += 1
        except Exception:
            continue

    if total == 0:
        logger.log_warning("get_nasdaq_breadth",
            "Could not calculate breadth — defaulting to 0.60")
        return 0.60

    breadth = above_sma / total
    logger.log_info("get_nasdaq_breadth",
        f"Breadth: {above_sma}/{total} = {breadth:.1%}")
    return breadth
