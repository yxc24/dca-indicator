"""Moving-average-based indicators."""
from __future__ import annotations

import pandas as pd


def ma_deviation(closes: pd.Series, period: int = 50) -> float:
    """Percentage deviation of the latest close from an N-day simple moving average.

    Negative value = below MA (potential buying opportunity on dip).
    Positive value = above MA.
    """
    if len(closes) < period:
        raise ValueError(f"need at least {period} closes, got {len(closes)}")

    ma = closes.rolling(window=period).mean()
    latest_close = float(closes.iloc[-1])
    latest_ma = float(ma.iloc[-1])
    if latest_ma == 0 or pd.isna(latest_ma):
        raise ValueError("invalid MA value")
    return (latest_close - latest_ma) / latest_ma
