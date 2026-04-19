"""Finnhub data source: real-time quotes and historical daily candles.

Finnhub free tier:
  - 60 API calls / minute
  - Real-time US stock quotes (NYSE/NASDAQ)
  - Historical candles (daily/weekly/monthly)
  - No credit card required to sign up
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import finnhub
import pandas as pd

logger = logging.getLogger(__name__)


class FinnhubSource:
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("FINNHUB_API_KEY is required")
        self.client = finnhub.Client(api_key=api_key)

    def fetch_quote(self, ticker: str) -> dict[str, Any]:
        """Real-time quote.

        Returns dict with:
          value (current), high (session), low (session), open, prev_close,
          day_change_pct, from_session_high, as_of (unix ts), source
        """
        q = self.client.quote(ticker)
        # Finnhub quote response keys:
        #   c = current, h = high (today), l = low (today),
        #   o = open, pc = previous close, t = unix timestamp
        if not q or q.get("c") in (0, None):
            raise RuntimeError(f"finnhub quote empty for {ticker}: {q}")

        current = float(q["c"])
        prev_close = float(q["pc"])
        session_high = float(q["h"])

        return {
            "ticker": ticker,
            "value": current,
            "current": current,
            "high": session_high,
            "low": float(q["l"]),
            "open": float(q["o"]),
            "prev_close": prev_close,
            "day_change_pct": (current - prev_close) / prev_close if prev_close else 0.0,
            "from_session_high": (current - session_high) / session_high if session_high else 0.0,
            "as_of": datetime.fromtimestamp(q["t"], tz=timezone.utc).isoformat() if q.get("t") else None,
            "source": "finnhub",
        }

    def fetch_candles(
        self,
        ticker: str,
        lookback_days: int = 400,
        resolution: str = "D",
    ) -> pd.DataFrame:
        """Daily OHLCV candles.

        Returns DataFrame with columns: date, open, high, low, close, volume
        sorted ascending by date.

        NOTE: Finnhub's free tier /stock/candle endpoint has been restricted
        to premium plans for US stocks since 2024. This method uses
        yfinance as a fallback for candles only; quotes still go through Finnhub.
        """
        # Prefer yfinance for historical candles because Finnhub free tier
        # restricted /stock/candle for US equities.
        import yfinance as yf

        end = datetime.now(timezone.utc)
        start = end - timedelta(days=lookback_days)

        ticker_obj = yf.Ticker(ticker)
        df = ticker_obj.history(
            start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
            interval="1d",
            auto_adjust=False,
        )
        if df.empty:
            raise RuntimeError(f"no candle data for {ticker}")

        df = df.reset_index()
        df.columns = [c.lower() for c in df.columns]
        # yfinance returns 'date' or 'datetime' depending on version
        if "date" not in df.columns and "datetime" in df.columns:
            df = df.rename(columns={"datetime": "date"})
        df = df[["date", "open", "high", "low", "close", "volume"]]
        df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
        return df.sort_values("date").reset_index(drop=True)
