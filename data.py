# =============================================================================
# data.py — Market data v2.4
# History:   yfinance (replaces Stooq for QQQ — Stooq unreliable at 3:55 PM)
# Real-time: Alpaca (live quotes, pre-market, trading)
# VIX:       yfinance
# Breadth:   yfinance bulk download
# =============================================================================

import time
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


def _fetch_stooq(ticker, retries=3):
    """
    Kept as fallback only. Not called in normal operation anymore.
    Stooq proved unreliable at 3:55 PM ET on high-volume days.
    """
    stooq_ticker = ticker.lower() + ".us"
    url = f"https://stooq.com/q/d/l/?s={stooq_ticker}&i=d"

    for attempt in range(retries):
        try:
            r = requests.get(url, timeout=15)
            if r.status_code != 200:
                raise ValueError(f"Stooq returned {r.status_code} for {ticker}")

            text = r.text.strip()
            if not text or len(text) < 30 or "No data" in text:
                raise ValueError(f"Stooq empty response for {ticker}: '{text[:80]}'")

            df = pd.read_csv(StringIO(text))

            if df.empty or 'Close' not in df.columns:
                raise ValueError(f"No data returned from Stooq for {ticker}")

            df['Date'] = pd.to_datetime(df['Date'])
            df = df.sort_values('Date')
            prices = df.set_index('Date')['Close'].dropna()

            logger.log_info("fetch_stooq",
                f"Stooq: {len(prices)} days of {ticker}. "
                f"Latest: ${prices.iloc[-1]:.2f} ({prices.index[-1].date()})")
            return prices

        except Exception as e:
            if attempt < retries - 1:
                logger.log_warning("fetch_stooq",
                    f"Attempt {attempt+1} failed for {ticker}: {e}. Retrying in 5s...")
                time.sleep(5)
            else:
                raise


def _fetch_yfinance(ticker, days=300):
    """
    Fetches daily price history via yfinance.
    Reliable, no rate limiting, matches Stooq/Yahoo Finance SMA values exactly.
    Returns pandas Series oldest → newest.
    """
    try:
        period = "2y" if days > 365 else "1y"
        raw = yf.download(
            ticker,
            period=period,
            interval="1d",
            progress=False,
            auto_adjust=True
        )

        if raw.empty:
            raise ValueError(f"yfinance returned empty data for {ticker}")

        close = raw["Close"] if "Close" in raw.columns else raw.iloc[:, 0]

        if hasattr(close, 'squeeze'):
            close = close.squeeze()

        prices = close.dropna().sort_index()

        if len(prices) == 0:
            raise ValueError(f"No price data after cleaning for {ticker}")

        logger.log_info("fetch_yfinance",
            f"yfinance: {len(prices)} days of {ticker}. "
            f"Latest: ${float(prices.iloc[-1]):.2f} ({prices.index[-1].date()})")
        return prices

    except Exception as e:
        logger.log_error("fetch_yfinance", f"yfinance failed for {ticker}: {e}")
        raise


def get_qqq_history():
    """
    QQQ daily history via yfinance.
    Replaced Stooq which was failing every day at 3:55 PM ET.
    SMA values match Stooq/Yahoo Finance exactly — same underlying data.
    """
    try:
        prices = _fetch_yfinance(config.SIGNAL_TICKER, days=config.DATA_LOOKBACK_DAYS)
        if len(prices) < config.SMA_LONG:
            raise ValueError(f"Insufficient data: {len(prices)} days")
        return prices
    except Exception as e:
        logger.log_error("get_qqq_history", f"yfinance failed: {e}")
        raise


def get_current_qqq_price():
    """
    Real-time QQQ price via Alpaca live quote.
    Falls back to yfinance latest close if Alpaca unavailable.
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
            f"Alpaca real-time failed ({e}) — using yfinance latest close")
        prices = get_qqq_history()
        return float(prices.iloc[-1])


def get_premarket_qqq_price():
    """
    Pre-market QQQ price via Alpaca at 9:25 AM.
    Falls back to yfinance latest close if Alpaca unavailable.
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
            f"Pre-market failed ({e}) — using yfinance latest close")
        prices = get_qqq_history()
        return float(prices.iloc[-1])


def get_current_vix():
    """
    VIX via yfinance.
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
    Uses yfinance bulk download — ONE request for all 20 holdings.
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

    try:
        raw = yf.download(
            " ".join(holdings),
            period="1y",
            interval="1d",
            progress=False,
            auto_adjust=True
        )

        close = raw["Close"] if "Close" in raw.columns else raw

        for sym in holdings:
            try:
                if sym not in close.columns:
                    continue
                prices = close[sym].dropna()
                if len(prices) < 200:
                    continue
                if float(prices.iloc[-1]) > float(prices.iloc[-200:].mean()):
                    above_sma += 1
                total += 1
            except Exception:
                continue

    except Exception as e:
        logger.log_warning("get_nasdaq_breadth",
            f"yfinance bulk download failed ({e}) — defaulting to 0.60")
        return 0.60

    if total == 0:
        logger.log_warning("get_nasdaq_breadth",
            "Could not calculate breadth — defaulting to 0.60")
        return 0.60

    breadth = above_sma / total
    logger.log_info("get_nasdaq_breadth",
        f"Breadth: {above_sma}/{total} = {breadth:.1%}")
    return breadth
