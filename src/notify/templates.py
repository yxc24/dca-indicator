"""Feishu interactive card templates."""
from __future__ import annotations

from datetime import datetime

import pytz

ET = pytz.timezone("America/New_York")
MYT = pytz.timezone("Asia/Kuala_Lumpur")


_LEVEL_META = {
    "alert":      {"title": "【盘中关注】",   "color": "orange"},
    "watch":      {"title": "【收盘关注】",   "color": "orange"},
    "strong_buy": {"title": "【强买点信号】", "color": "green"},
}


def build_signal_card(result) -> dict:
    meta = _LEVEL_META.get(result.level, {"title": "【信号】", "color": "blue"})

    now_et = datetime.fromisoformat(result.as_of).astimezone(ET)
    now_myt = datetime.fromisoformat(result.as_of).astimezone(MYT)

    # Header text
    header_text = (
        f"{meta['title']} {result.target_name} ({result.target})  "
        f"{result.total_score}/{result.max_score}"
    )

    # Build elements
    elements: list[dict] = []

    # Summary block
    summary_lines = [
        f"**评分**: {result.total_score} / {result.max_score}",
        f"**模式**: {result.run_mode}",
        f"**美东**: {now_et.strftime('%Y-%m-%d %H:%M')}",
        f"**MYT**: {now_myt.strftime('%Y-%m-%d %H:%M')}",
    ]
    elements.append({
        "tag": "div",
        "text": {"tag": "lark_md", "content": "\n".join(summary_lines)},
    })
    elements.append({"tag": "hr"})

    # Triggered indicators
    if result.triggered:
        lines = ["**✅ 已触发**"]
        for ev in result.triggered:
            v = _fmt_value(ev.value)
            lines.append(f"- **{ev.description}**  `值 = {v}`  (权重 {ev.weight})")
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": "\n".join(lines)},
        })

    # Not triggered
    if result.not_triggered:
        lines = ["**◻️ 未触发**"]
        for ev in result.not_triggered:
            v = _fmt_value(ev.value)
            lines.append(f"- {ev.description}  `值 = {v}`")
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": "\n".join(lines)},
        })

    # Errors
    if result.errors:
        lines = ["**⚠️ 数据异常**"]
        for ev in result.errors:
            lines.append(f"- {ev.description}: {ev.error}")
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": "\n".join(lines)},
        })

    elements.append({"tag": "hr"})
    elements.append({
        "tag": "note",
        "elements": [{
            "tag": "plain_text",
            "content": "DCA Indicator · 自动化择时预警",
        }],
    })

    return {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": header_text},
                "template": meta["color"],
            },
            "elements": elements,
        },
    }


def build_health_warning_card(failed_sources: list[str], details: dict | None = None) -> dict:
    details = details or {}
    lines = [
        "**❌ 数据源异常**",
        "",
        "以下数据源获取失败：",
    ]
    for src in failed_sources:
        lines.append(f"- `{src}`: {details.get(src, 'unknown error')}")

    return {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": "⚠️ DCA Indicator 数据告警"},
                "template": "red",
            },
            "elements": [{
                "tag": "div",
                "text": {"tag": "lark_md", "content": "\n".join(lines)},
            }],
        },
    }


def _fmt_value(v) -> str:
    if v is None:
        return "N/A"
    try:
        v = float(v)
    except Exception:
        return str(v)
    # percent-like values tend to be between -1 and 1
    if -1 < v < 1 and v != 0:
        return f"{v*100:.2f}%"
    return f"{v:.2f}"
