"""Wilder's RSI-14 indicator."""
from __future__ import annotations

import pandas as pd


def rsi_14(closes: pd.Series, period: int = 14) -> float:
    """Return the latest RSI-14 value computed on a pandas Series of closes.

    Uses Wilder's smoothing method (EWM with alpha = 1/period).
    Requires at least `period + 1` data points.

    Edge cases:
      - All gains, no losses -> RSI = 100
      - All losses, no gains -> RSI = 0
      - Flat market          -> RSI = 50
    """
    if len(closes) < period + 1:
        raise ValueError(f"need at least {period+1} closes, got {len(closes)}")

    delta = closes.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)

    avg_gain = gain.ewm(alpha=1.0 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, adjust=False).mean()

    latest_gain = float(avg_gain.iloc[-1])
    latest_loss = float(avg_loss.iloc[-1])

    if latest_loss == 0 and latest_gain == 0:
        return 50.0
    if latest_loss == 0:
        return 100.0
    if latest_gain == 0:
        return 0.0

    rs = latest_gain / latest_loss
    return float(100 - (100 / (1 + rs)))
