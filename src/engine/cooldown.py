"""Cooldown / dedupe engine for notifications."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from .market_hours import ET, current_trading_date_et

logger = logging.getLogger(__name__)


def should_notify(state: dict, result, cfg) -> tuple[bool, str]:
    """Return (allow, reason)."""
    target_state = state.setdefault("targets", {}).setdefault(result.target, {})
    now = datetime.now(timezone.utc)

    if cfg.run_mode == "intraday":
        return _intraday_decision(target_state, result, cfg, now)
    return _daily_decision(target_state, result, cfg, now)


def _intraday_decision(target_state, result, cfg, now) -> tuple[bool, str]:
    last = target_state.get("last_intraday")
    if not last:
        return True, "no previous intraday signal"

    cd = cfg.cooldown
    last_ts = datetime.fromisoformat(last["ts"])
    last_date = last.get("trading_date")
    today = current_trading_date_et(now).isoformat()

    if cd.get("cross_session_reset", True) and last_date != today:
        return True, f"new trading session (prev {last_date})"

    if cd.get("score_upgrade_allowed", True) and result.total_score > last["score"]:
        return True, f"score upgraded {last['score']} -> {result.total_score}"

    cooldown_sec = int(cd.get("same_score_hours", 4)) * 3600
    elapsed = (now - last_ts).total_seconds()
    if elapsed < cooldown_sec:
        return False, f"in cooldown ({int(elapsed/60)}m of {cooldown_sec//60}m)"
    return True, "cooldown elapsed"


def _daily_decision(target_state, result, cfg, now) -> tuple[bool, str]:
    last = target_state.get("last_daily")
    if not last:
        return True, "no previous daily signal"

    cd = cfg.cooldown
    cooldown_days = int(cd.get("same_level_days", 3))
    last_ts = datetime.fromisoformat(last["ts"])

    if result.level != last["level"]:
        return True, f"level changed {last['level']} -> {result.level}"

    elapsed_days = (now - last_ts).total_seconds() / 86400
    if elapsed_days < cooldown_days:
        return False, f"in cooldown ({elapsed_days:.1f}d of {cooldown_days}d)"
    return True, "cooldown elapsed"


def register(state: dict, result) -> None:
    """Record this notification as having been sent."""
    target_state = state.setdefault("targets", {}).setdefault(result.target, {})
    now = datetime.now(timezone.utc)
    record = {
        "ts": now.isoformat(),
        "trading_date": current_trading_date_et(now).isoformat(),
        "score": result.total_score,
        "max_score": result.max_score,
        "level": result.level,
        "triggered_ids": [e.id for e in result.triggered],
    }
    if result.run_mode == "intraday":
        target_state["last_intraday"] = record
    else:
        target_state["last_daily"] = record
