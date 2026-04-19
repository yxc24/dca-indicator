"""yfinance source: primary VIX and fallback candles.

yfinance is unofficial and scrapes Yahoo Finance. Intraday quotes
are ~15 minutes delayed, which is acceptable for VIX (a smoothed
volatility index that doesn't move dramatically over 15 minutes).
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


def fetch_vix_latest() -> dict[str, Any]:
    """Latest VIX value.

    Returns: {'value': 28.3, 'as_of': '...', 'source': 'yfinance'}
    """
    t = yf.Ticker("^VIX")
    # fast_info is faster and more reliable than info for intraday
    try:
        last_price = float(t.fast_info["last_price"])
    except Exception:
        # fallback to a 2d history fetch
        hist = t.history(period="2d")
        if hist.empty:
            raise RuntimeError("no VIX data from yfinance")
        last_price = float(hist["Close"].iloc[-1])

    return {
        "value": last_price,
        "as_of": datetime.now(timezone.utc).isoformat(),
        "source": "yfinance",
    }


def fetch_candles(ticker: str, lookback_days: int = 400) -> pd.DataFrame:
    """Fallback candle fetcher. Used mainly for VIX historical context."""
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=lookback_days)
    t = yf.Ticker(ticker)
    df = t.history(
        start=start.strftime("%Y-%m-%d"),
        end=end.strftime("%Y-%m-%d"),
        interval="1d",
        auto_adjust=False,
    )
    if df.empty:
        raise RuntimeError(f"no candle data for {ticker}")

    df = df.reset_index()
    df.columns = [c.lower() for c in df.columns]
    if "date" not in df.columns and "datetime" in df.columns:
        df = df.rename(columns={"datetime": "date"})
    df = df[["date", "open", "high", "low", "close", "volume"]]
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
    return df.sort_values("date").reset_index(drop=True)
