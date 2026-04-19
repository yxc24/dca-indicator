"""Drawdown indicators: MTD drawdown and from 52-week high."""
from __future__ import annotations

from datetime import date, datetime

import pandas as pd


def mtd_drawdown(df: pd.DataFrame, as_of: date | None = None) -> float:
    """Month-to-date drawdown: current close vs the highest close of this month.

    Returns negative value (e.g. -0.042 = 4.2% below MTD peak).
    """
    if df.empty:
        raise ValueError("empty dataframe")
    if as_of is None:
        as_of = df["date"].iloc[-1].date() if hasattr(df["date"].iloc[-1], "date") else df["date"].iloc[-1]

    # Normalize to date for comparison
    df = df.copy()
    df["_d"] = pd.to_datetime(df["date"]).dt.date

    month_start = as_of.replace(day=1)
    mtd = df[df["_d"] >= month_start]
    if mtd.empty:
        return 0.0

    peak = float(mtd["close"].max())
    current = float(mtd["close"].iloc[-1])
    if peak == 0:
        return 0.0
    return (current - peak) / peak


def from_52w_high(df: pd.DataFrame) -> float:
    """Distance from the trailing 52-week high as a fraction.

    Returns negative value (e.g. -0.068 = 6.8% below 52w high).
    """
    if df.empty:
        raise ValueError("empty dataframe")
    # Use at most the last 252 trading days (~1 year)
    recent = df.tail(252)
    peak = float(recent["high"].max())
    current = float(df["close"].iloc[-1])
    if peak == 0:
        return 0.0
    return (current - peak) / peak
