"""Composite VIX fetcher: yfinance primary, FRED fallback.

This module is kept thin so main.py can simply call `fetch_vix()` without
worrying about which source to use.
"""
from __future__ import annotations

import logging
from typing import Any

from . import yfinance_src
from .fred_src import FredSource

logger = logging.getLogger(__name__)


def fetch_vix(fred_api_key: str | None = None) -> dict[str, Any]:
    """Try yfinance first; fall back to FRED on failure."""
    try:
        result = yfinance_src.fetch_vix_latest()
        logger.info(f"VIX from yfinance: {result['value']:.2f}")
        return result
    except Exception as e:
        logger.warning(f"yfinance VIX failed: {e}; falling back to FRED")

    if not fred_api_key:
        raise RuntimeError("yfinance VIX failed and no FRED_API_KEY configured")

    fred = FredSource(api_key=fred_api_key)
    result = fred.fetch_vix_latest()
    logger.info(f"VIX from FRED: {result['value']:.2f}")
    return result
