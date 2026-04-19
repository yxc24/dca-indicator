"""Unit tests for pure indicator functions.

Run: python -m pytest tests/ -v
"""
from __future__ import annotations

import pandas as pd
import pytest

from src.indicators.drawdown import from_52w_high, mtd_drawdown
from src.indicators.intraday import day_change_pct, from_session_high
from src.indicators.ma import ma_deviation
from src.indicators.rsi import rsi_14


def _series(values):
    return pd.Series(values, dtype=float)


def _ohlc_df(closes, start="2026-01-01"):
    dates = pd.date_range(start=start, periods=len(closes), freq="B")
    return pd.DataFrame({
        "date": dates,
        "open": closes,
        "high": [c * 1.005 for c in closes],
        "low": [c * 0.995 for c in closes],
        "close": closes,
        "volume": [1_000_000] * len(closes),
    })


# ── RSI ─────────────────────────────────────────────────────────────
def test_rsi_uptrend_gives_high_value():
    closes = _series([100 + i for i in range(30)])
    rsi = rsi_14(closes)
    assert rsi > 70


def test_rsi_downtrend_gives_low_value():
    closes = _series([100 - i for i in range(30)])
    rsi = rsi_14(closes)
    assert rsi < 30


def test_rsi_insufficient_data_raises():
    with pytest.raises(ValueError):
        rsi_14(_series([100, 101, 102]))


# ── MA deviation ────────────────────────────────────────────────────
def test_ma_deviation_below_ma_is_negative():
    closes = _series([100] * 49 + [90])
    dev = ma_deviation(closes, period=50)
    assert dev < 0


def test_ma_deviation_above_ma_is_positive():
    closes = _series([100] * 49 + [110])
    dev = ma_deviation(closes, period=50)
    assert dev > 0


# ── Drawdown ────────────────────────────────────────────────────────
def test_mtd_drawdown_negative_when_down_from_peak():
    # First day of month is peak at 100, then drops
    df = _ohlc_df([100, 98, 95, 97], start="2026-04-01")
    dd = mtd_drawdown(df, as_of=df["date"].iloc[-1].date())
    assert dd == pytest.approx((97 - 100) / 100)


def test_from_52w_high_negative():
    closes = [100 + i for i in range(100)] + [150] + [140]  # 150 peak, 140 current
    df = _ohlc_df(closes)
    # high col = close * 1.005 so peak_high = 150.75
    result = from_52w_high(df)
    assert result < 0


# ── Intraday ────────────────────────────────────────────────────────
def test_day_change_pct():
    q = {"day_change_pct": -0.023}
    assert day_change_pct(q) == pytest.approx(-0.023)


def test_from_session_high():
    q = {"from_session_high": -0.012}
    assert from_session_high(q) == pytest.approx(-0.012)
