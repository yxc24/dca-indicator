"""FRED (Federal Reserve Economic Data) source.

Used as backup for VIX when yfinance fails. FRED is authoritative
but daily-only (not intraday), so it's a decent fallback for daily
checks but not ideal for intraday.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fredapi import Fred

logger = logging.getLogger(__name__)


class FredSource:
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("FRED_API_KEY is required")
        self.client = Fred(api_key=api_key)

    def fetch_vix_latest(self) -> dict[str, Any]:
        """Latest daily VIX close."""
        # VIXCLS = CBOE Volatility Index: VIX (daily)
        series = self.client.get_series("VIXCLS")
        series = series.dropna()
        if series.empty:
            raise RuntimeError("FRED VIX series is empty")

        last_value = float(series.iloc[-1])
        last_date = series.index[-1].to_pydatetime()
        return {
            "value": last_value,
            "as_of": last_date.replace(tzinfo=timezone.utc).isoformat(),
            "source": "fred",
        }
