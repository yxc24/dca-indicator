"""Backtest the alert rules against historical data.

Usage:
    python -m src.backtest --start 2025-01-01 --end 2026-04-01 --ticker SPY

Produces:
    data/backtest_report.csv - one row per signal with forward performance
    Prints a summary to stdout.
"""
from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import asdict
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import yfinance as yf

from .config import load_config, setup_logging
from .engine.scorer import score_target
from .indicators.drawdown import from_52w_high, mtd_drawdown
from .indicators.ma import ma_deviation
from .indicators.rsi import rsi_14

logger = logging.getLogger(__name__)


def backtest(
    start: str,
    end: str,
    ticker: str = "SPY",
    rules_path: str = "rules.yaml",
) -> pd.DataFrame:
    import os
    os.environ.setdefault("RUN_MODE", "daily_final")

    cfg = load_config(rules_path=rules_path)

    # Download price history with a buffer for indicator warmup
    buffer_start = (pd.to_datetime(start) - pd.Timedelta(days=400)).strftime("%Y-%m-%d")

    prices = _fetch(ticker, buffer_start, end)
    vix = _fetch("^VIX", buffer_start, end)

    # Align VIX to price dates
    vix_close = vix.set_index("date")["close"]

    # Iterate through business days in the test window
    target = {"ticker": ticker, "name": ticker}
    signals: list[dict] = []

    test_dates = prices[prices["date"] >= pd.to_datetime(start)]["date"]

    for d in test_dates:
        # Snapshot up to and including day d
        hist = prices[prices["date"] <= d].copy()
        if len(hist) < 60:
            continue

        values: dict = {}
        errors: dict = {}

        # Global: VIX on that day
        try:
            if d in vix_close.index:
                values["vix"] = float(vix_close.loc[d])
            else:
                # use most recent available VIX
                vix_slice = vix_close[vix_close.index <= d]
                if not vix_slice.empty:
                    values["vix"] = float(vix_slice.iloc[-1])
        except Exception as e:
            errors["vix"] = str(e)

        # FGI historical data is not easily available; skip
        values["fgi"] = None

        # Per-target indicators
        try:
            values[f"{ticker}:rsi_14"] = rsi_14(hist["close"])
        except Exception as e:
            errors[f"{ticker}:rsi_14"] = str(e)
        try:
            values[f"{ticker}:ma50_deviation"] = ma_deviation(hist["close"], 50)
        except Exception as e:
            errors[f"{ticker}:ma50_deviation"] = str(e)
        try:
            values[f"{ticker}:mtd_drawdown"] = mtd_drawdown(hist, as_of=d.date())
        except Exception as e:
            errors[f"{ticker}:mtd_drawdown"] = str(e)
        try:
            values[f"{ticker}:from_52w_high"] = from_52w_high(hist)
        except Exception as e:
            errors[f"{ticker}:from_52w_high"] = str(e)

        result = score_target(target, values, errors, cfg)
        if result.level == "none":
            continue

        # Forward performance lookup
        close_d = float(hist["close"].iloc[-1])
        fwd = _forward_perf(prices, d, close_d, [5, 10, 20])

        signals.append({
            "date": d.date().isoformat(),
            "level": result.level,
            "score": result.total_score,
            "max_score": result.max_score,
            "triggered": ",".join(e.id for e in result.triggered),
            "close": close_d,
            **fwd,
        })

    df = pd.DataFrame(signals)
    if not df.empty:
        Path("data").mkdir(exist_ok=True)
        df.to_csv("data/backtest_report.csv", index=False)
    return df


def _fetch(ticker: str, start: str, end: str) -> pd.DataFrame:
    df = yf.Ticker(ticker).history(start=start, end=end, interval="1d", auto_adjust=False)
    df = df.reset_index()
    df.columns = [c.lower() for c in df.columns]
    if "date" not in df.columns and "datetime" in df.columns:
        df = df.rename(columns={"datetime": "date"})
    df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)
    return df[["date", "open", "high", "low", "close", "volume"]].sort_values("date").reset_index(drop=True)


def _forward_perf(prices: pd.DataFrame, as_of, close_now: float, horizons: list[int]) -> dict:
    out = {}
    future = prices[prices["date"] > as_of].reset_index(drop=True)
    for h in horizons:
        if len(future) >= h:
            close_fwd = float(future["close"].iloc[h - 1])
            out[f"ret_{h}d"] = (close_fwd - close_now) / close_now
        else:
            out[f"ret_{h}d"] = None
    return out


def print_summary(df: pd.DataFrame) -> None:
    if df.empty:
        print("No signals in the backtest window.")
        return

    print(f"\n{'='*60}")
    print(f"Total signals: {len(df)}")
    print(f"{'='*60}")
    for level in df["level"].unique():
        sub = df[df["level"] == level]
        print(f"\n[{level}]  count={len(sub)}")
        for h in (5, 10, 20):
            col = f"ret_{h}d"
            if col in sub.columns:
                avg = sub[col].dropna().mean()
                win = (sub[col].dropna() > 0).mean()
                print(f"  {h:2d}d forward return: avg={avg:+.2%}  win_rate={win:.0%}")

    print(f"\nReport saved: data/backtest_report.csv")


def main():
    setup_logging()
    p = argparse.ArgumentParser()
    p.add_argument("--start", required=True, help="YYYY-MM-DD")
    p.add_argument("--end", required=True, help="YYYY-MM-DD")
    p.add_argument("--ticker", default="SPY")
    p.add_argument("--rules", default="rules.yaml")
    args = p.parse_args()

    df = backtest(args.start, args.end, args.ticker, args.rules)
    print_summary(df)


if __name__ == "__main__":
    main()
