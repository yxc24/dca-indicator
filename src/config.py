"""Load rules.yaml and environment variables into a single Config object."""
from __future__ import annotations

import os
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


@dataclass
class Config:
    rules: dict                              # parsed rules.yaml
    feishu_webhook: str | None
    feishu_sign_secret: str | None
    finnhub_api_key: str | None
    fred_api_key: str | None
    run_mode: str                            # "intraday" or "daily_final"
    state_path: Path
    rules_path: Path

    @property
    def targets(self) -> list[dict]:
        return self.rules["targets"]

    @property
    def indicators(self) -> list[dict]:
        return self.rules["indicators"]

    @property
    def thresholds(self) -> dict:
        return self.rules["thresholds"][self.run_mode]

    @property
    def cooldown(self) -> dict:
        return self.rules["cooldown"][self.run_mode]


def load_config(
    rules_path: str | Path = "rules.yaml",
    state_path: str | Path = "state.json",
) -> Config:
    rules_path = Path(rules_path)
    state_path = Path(state_path)

    if not rules_path.exists():
        raise FileNotFoundError(f"rules file not found: {rules_path}")

    with open(rules_path, "r", encoding="utf-8") as f:
        rules = yaml.safe_load(f)

    run_mode = os.environ.get("RUN_MODE", "intraday")
    if run_mode not in ("intraday", "daily_final"):
        raise ValueError(f"invalid RUN_MODE: {run_mode}")

    return Config(
        rules=rules,
        feishu_webhook=os.environ.get("FEISHU_WEBHOOK"),
        feishu_sign_secret=os.environ.get("FEISHU_SIGN_SECRET"),
        finnhub_api_key=os.environ.get("FINNHUB_API_KEY"),
        fred_api_key=os.environ.get("FRED_API_KEY"),
        run_mode=run_mode,
        state_path=state_path,
        rules_path=rules_path,
    )


def load_state(path: str | Path) -> dict:
    path = Path(path)
    if not path.exists():
        return {
            "last_run": None,
            "targets": {},
            "cached_indicators": {},
            "data_health": {},
        }
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(path: str | Path, state: dict) -> None:
    path = Path(path)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False, default=str)


def setup_logging() -> None:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
