"""Intraday indicators derived directly from a live quote."""
from __future__ import annotations

from typing import Any


def day_change_pct(quote: dict[str, Any]) -> float:
    """Today's change vs previous close, as a fraction."""
    return float(quote.get("day_change_pct", 0.0))


def from_session_high(quote: dict[str, Any]) -> float:
    """Current price vs today's session high, as a fraction (negative)."""
    return float(quote.get("from_session_high", 0.0))
