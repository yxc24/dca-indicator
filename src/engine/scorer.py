"""Scoring engine.

Takes the computed indicator values and the rules config, evaluates every
trigger expression safely via `asteval`, and produces a ScoreResult.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from asteval import Interpreter

logger = logging.getLogger(__name__)


@dataclass
class IndicatorEval:
    id: str
    value: float | None
    triggered: bool
    weight: int
    description: str
    trigger_expr: str
    error: str | None = None


@dataclass
class ScoreResult:
    target: str
    target_name: str
    run_mode: str
    as_of: str
    total_score: int
    max_score: int
    level: str                         # "none" | "alert" | "watch" | "strong_buy"
    triggered: list[IndicatorEval] = field(default_factory=list)
    not_triggered: list[IndicatorEval] = field(default_factory=list)
    errors: list[IndicatorEval] = field(default_factory=list)

    def has_signal(self) -> bool:
        return self.level != "none"


def _eval_trigger(expr: str, value: float | None) -> bool:
    """Safely evaluate a trigger expression like 'value < 30' or 'value > 25'."""
    if value is None:
        return False
    aeval = Interpreter()
    aeval.symtable["value"] = value
    try:
        result = aeval(expr)
        return bool(result)
    except Exception as e:
        logger.warning(f"trigger eval error for '{expr}' with value={value}: {e}")
        return False


def score_target(
    target: dict,
    indicator_values: dict[str, float | None],
    indicator_errors: dict[str, str],
    cfg,
) -> ScoreResult:
    """Score a single target against all applicable indicators."""
    triggered: list[IndicatorEval] = []
    not_triggered: list[IndicatorEval] = []
    errors_list: list[IndicatorEval] = []

    total_score = 0
    max_score = 0

    for ind_cfg in cfg.indicators:
        # skip indicators restricted to other modes
        only_modes = ind_cfg.get("only_modes")
        if only_modes and cfg.run_mode not in only_modes:
            continue

        ind_id = ind_cfg["id"]
        scope = ind_cfg.get("scope", "per_target")
        weight = int(ind_cfg.get("weight", 1))
        expr = ind_cfg["trigger"]
        desc = ind_cfg.get("description", ind_id)

        # lookup key: global indicators by id; per-target by "target:id"
        key = ind_id if scope == "global" else f"{target['ticker']}:{ind_id}"

        max_score += weight

        if key in indicator_errors:
            errors_list.append(IndicatorEval(
                id=ind_id, value=None, triggered=False,
                weight=weight, description=desc, trigger_expr=expr,
                error=indicator_errors[key],
            ))
            continue

        value = indicator_values.get(key)
        fired = _eval_trigger(expr, value)
        ev = IndicatorEval(
            id=ind_id, value=value, triggered=fired,
            weight=weight, description=desc, trigger_expr=expr,
        )
        if fired:
            total_score += weight
            triggered.append(ev)
        else:
            not_triggered.append(ev)

    level = _determine_level(total_score, cfg)

    return ScoreResult(
        target=target["ticker"],
        target_name=target.get("name", target["ticker"]),
        run_mode=cfg.run_mode,
        as_of=datetime.now(timezone.utc).isoformat(),
        total_score=total_score,
        max_score=max_score,
        level=level,
        triggered=triggered,
        not_triggered=not_triggered,
        errors=errors_list,
    )


def _determine_level(score: int, cfg) -> str:
    thr = cfg.thresholds
    if cfg.run_mode == "intraday":
        return "alert" if score >= int(thr.get("alert", 3)) else "none"
    # daily_final
    if score >= int(thr.get("strong_buy", 4)):
        return "strong_buy"
    if score >= int(thr.get("watch", 3)):
        return "watch"
    return "none"
