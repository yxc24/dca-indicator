"""Main orchestrator.

Flow:
  1. Load config and state
  2. If intraday mode & market closed → exit cleanly
  3. Auto-switch to daily_final if we're in the post-close 30-90min window
  4. Fetch all required data (with fallbacks)
  5. Compute all indicators (cache slow ones for 24h)
  6. Score every target
  7. Check cooldown → send Feishu notification if allowed
  8. Persist updated state
"""
from __future__ import annotations

import logging
import os
import sys
import traceback
from datetime import datetime, timedelta, timezone
from typing import Any

from .config import load_config, load_state, save_state, setup_logging
from .engine import cooldown as cooldown_engine
from .engine import market_hours
from .engine.scorer import score_target
from .indicators.drawdown import from_52w_high, mtd_drawdown
from .indicators.ma import ma_deviation
from .indicators.rsi import rsi_14
from .notify import feishu
from .notify.templates import build_health_warning_card, build_signal_card
from .sources import fgi_src, yfinance_src
from .sources.finnhub_src import FinnhubSource
from .sources.vix_composite import fetch_vix

logger = logging.getLogger(__name__)


def run() -> int:
    setup_logging()
    cfg = load_config()
    state = load_state(cfg.state_path)

    # Auto-promote to daily_final if we're at the post-close final window
    if cfg.run_mode == "intraday" and market_hours.is_post_close_final_run():
        logger.info("Post-close final window detected → switching to daily_final mode")
        os.environ["RUN_MODE"] = "daily_final"
        cfg = load_config()

    # Skip if intraday mode and market not in window (e.g., US holiday)
    post_close = int(cfg.rules.get("market", {}).get("post_close_buffer_hours", 1))
    if cfg.run_mode == "intraday" and not market_hours.is_us_market_open_window(
        post_close_hours=post_close
    ):
        logger.info("Not in US market hours / holiday. Skipping.")
        _update_last_run(state)
        save_state(cfg.state_path, state)
        return 0

    # ── Fetch data ──────────────────────────────────────────────────────
    indicator_values: dict[str, float | None] = {}
    indicator_errors: dict[str, str] = {}
    data_health: dict[str, str] = {}

    # Global: VIX
    try:
        vix = fetch_vix(fred_api_key=cfg.fred_api_key)
        indicator_values["vix"] = vix["value"]
        data_health["vix"] = f"ok ({vix['source']})"
    except Exception as e:
        logger.exception("VIX fetch failed")
        indicator_errors["vix"] = str(e)
        data_health["vix"] = f"FAILED: {e}"

    # Global: Fear & Greed
    try:
        fgi = fgi_src.fetch_fgi_latest()
        indicator_values["fgi"] = fgi["value"]
        data_health["cnn_fgi"] = "ok"
    except Exception as e:
        logger.exception("FGI fetch failed")
        indicator_errors["fgi"] = str(e)
        data_health["cnn_fgi"] = f"FAILED: {e}"

    # Per-target: Finnhub quote + candle-derived indicators
    finnhub = None
    if cfg.finnhub_api_key:
        try:
            finnhub = FinnhubSource(api_key=cfg.finnhub_api_key)
        except Exception as e:
            logger.exception("Finnhub init failed")
            data_health["finnhub"] = f"FAILED: {e}"

    for target in cfg.targets:
        ticker = target["ticker"]
        _compute_target_indicators(
            ticker, finnhub, cfg, state,
            indicator_values, indicator_errors, data_health,
        )

    # ── Score & notify ─────────────────────────────────────────────────
    state.setdefault("data_health", {}).update(data_health)

    sent_any = False
    for target in cfg.targets:
        result = score_target(target, indicator_values, indicator_errors, cfg)
        logger.info(
            f"[{result.target}] score={result.total_score}/{result.max_score} "
            f"level={result.level} mode={result.run_mode}"
        )

        if not result.has_signal():
            continue

        allow, reason = cooldown_engine.should_notify(state, result, cfg)
        if not allow:
            logger.info(f"[{result.target}] suppressed by cooldown: {reason}")
            continue

        logger.info(f"[{result.target}] sending notification: {reason}")
        if cfg.feishu_webhook:
            try:
                card = build_signal_card(result)
                feishu.send(cfg.feishu_webhook, card, cfg.feishu_sign_secret)
                cooldown_engine.register(state, result)
                sent_any = True
            except Exception as e:
                logger.exception(f"failed to send Feishu notification for {result.target}")
                data_health["feishu"] = f"FAILED: {e}"
        else:
            logger.warning("FEISHU_WEBHOOK not configured; would have sent signal")
            cooldown_engine.register(state, result)

    # ── Data health warning ────────────────────────────────────────────
    failed = [k for k, v in data_health.items() if v.startswith("FAILED")]
    if failed and cfg.rules.get("data_health", {}).get("warn_on_all_sources_fail", True):
        _maybe_send_health_warning(cfg, state, failed, data_health)

    _update_last_run(state)
    save_state(cfg.state_path, state)
    logger.info(f"Run complete. sent_any={sent_any}")
    return 0


def _compute_target_indicators(
    ticker: str, finnhub, cfg, state,
    values: dict, errors: dict, health: dict,
) -> None:
    """Compute all per-target indicators for a given ticker."""
    cache = state.setdefault("cached_indicators", {}).setdefault(ticker, {})

    # Live quote (intraday only)
    if cfg.run_mode == "intraday":
        if finnhub:
            try:
                quote = finnhub.fetch_quote(ticker)
                values[f"{ticker}:day_change_pct"] = quote["day_change_pct"]
                values[f"{ticker}:from_session_high"] = quote["from_session_high"]
                health["finnhub"] = "ok"
            except Exception as e:
                logger.exception(f"Finnhub quote failed for {ticker}")
                errors[f"{ticker}:day_change_pct"] = str(e)
                errors[f"{ticker}:from_session_high"] = str(e)
                health["finnhub"] = f"FAILED: {e}"
        else:
            errors[f"{ticker}:day_change_pct"] = "no Finnhub API key"
            errors[f"{ticker}:from_session_high"] = "no Finnhub API key"

    # Slow indicators: cache for 24h based on candle data
    need_refresh = _cache_is_stale(cache.get("_candle_cached_at"), hours=24)

    if need_refresh:
        try:
            df = yfinance_src.fetch_candles(ticker, lookback_days=400)
            try:
                cache["rsi_14"] = rsi_14(df["close"])
            except Exception as e:
                cache["rsi_14_error"] = str(e)
            try:
                cache["ma50_deviation"] = ma_deviation(df["close"], period=50)
            except Exception as e:
                cache["ma50_deviation_error"] = str(e)
            try:
                cache["mtd_drawdown"] = mtd_drawdown(df)
            except Exception as e:
                cache["mtd_drawdown_error"] = str(e)
            try:
                cache["from_52w_high"] = from_52w_high(df)
            except Exception as e:
                cache["from_52w_high_error"] = str(e)

            cache["_candle_cached_at"] = datetime.now(timezone.utc).isoformat()
            health[f"candles_{ticker}"] = "ok (refreshed)"
        except Exception as e:
            logger.exception(f"candle refresh failed for {ticker}")
            health[f"candles_{ticker}"] = f"FAILED: {e}"

    # Copy cached values into the scoring map
    for ind in ("rsi_14", "ma50_deviation", "mtd_drawdown", "from_52w_high"):
        key = f"{ticker}:{ind}"
        if ind in cache:
            values[key] = cache[ind]
        elif f"{ind}_error" in cache:
            errors[key] = cache[f"{ind}_error"]


def _cache_is_stale(iso_ts: str | None, hours: int = 24) -> bool:
    if not iso_ts:
        return True
    try:
        t = datetime.fromisoformat(iso_ts)
        return datetime.now(timezone.utc) - t > timedelta(hours=hours)
    except Exception:
        return True


def _update_last_run(state: dict) -> None:
    state["last_run"] = datetime.now(timezone.utc).isoformat()


def _maybe_send_health_warning(cfg, state, failed: list[str], details: dict) -> None:
    """Send a health warning at most once per day."""
    last_warning = state.get("last_health_warning")
    now = datetime.now(timezone.utc)
    if last_warning:
        try:
            last_ts = datetime.fromisoformat(last_warning)
            if (now - last_ts).total_seconds() < 24 * 3600:
                return  # already warned in the last 24h
        except Exception:
            pass

    if not cfg.feishu_webhook:
        logger.warning(f"Data health failed but no webhook: {failed}")
        return

    try:
        card = build_health_warning_card(failed, details)
        feishu.send(cfg.feishu_webhook, card, cfg.feishu_sign_secret)
        state["last_health_warning"] = now.isoformat()
    except Exception:
        logger.exception("failed to send health warning")


if __name__ == "__main__":
    try:
        sys.exit(run())
    except Exception:
        traceback.print_exc()
        sys.exit(1)
