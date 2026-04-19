"""CNN Fear & Greed Index source.

Uses CNN's public data API directly (no scraping, no API key required).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import requests

logger = logging.getLogger(__name__)

CNN_API = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}


def fetch_fgi_latest(timeout: int = 10) -> dict[str, Any]:
    """Fetch the current CNN Fear & Greed Index value.

    Returns: {'value': 42.0, 'description': 'fear', 'as_of': '...', 'source': 'cnn_fgi'}
    """
    resp = requests.get(CNN_API, headers=HEADERS, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()

    # CNN response shape: { 'fear_and_greed': {'score': 42.3, 'rating': 'fear', 'timestamp': '...'} , ... }
    fg = data.get("fear_and_greed") or {}
    if "score" not in fg:
        raise RuntimeError(f"CNN F&G response missing 'score': {data}")

    return {
        "value": float(fg["score"]),
        "description": fg.get("rating", ""),
        "as_of": fg.get("timestamp") or datetime.now(timezone.utc).isoformat(),
        "source": "cnn_fgi",
    }
