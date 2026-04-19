"""Send cards to Feishu via custom bot webhook (with signature)."""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import time

import requests

logger = logging.getLogger(__name__)


def _sign(secret: str, timestamp: int) -> str:
    """Feishu custom-bot signature algorithm."""
    string_to_sign = f"{timestamp}\n{secret}"
    hmac_code = hmac.new(
        string_to_sign.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()
    return base64.b64encode(hmac_code).decode("utf-8")


def send(
    webhook: str,
    payload: dict,
    sign_secret: str | None = None,
    timeout: int = 10,
) -> dict:
    """Post payload to Feishu webhook. Returns Feishu's response JSON."""
    if not webhook:
        raise ValueError("webhook URL is empty")

    body = dict(payload)  # shallow copy
    if sign_secret:
        ts = int(time.time())
        body["timestamp"] = str(ts)
        body["sign"] = _sign(sign_secret, ts)

    resp = requests.post(webhook, json=body, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()

    # Feishu: code 0 = success; anything else = error
    if data.get("code", 0) not in (0, None):
        raise RuntimeError(f"Feishu error {data.get('code')}: {data.get('msg')}")
    logger.info(f"Feishu notification sent: {data}")
    return data
