#!/usr/bin/env python3
"""Validate AI-DEV-157 LINE link-only notifications and PM-readable dashboard cards."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.reports.multi_window_formatter import DASHBOARD_URL_FALLBACK, format_window_report
from reports.line_short_formatter import format_line_short

HTML = ROOT / "templates/four_window_dashboard_route_preview.example.html"
LEGACY_SCRIPT = ROOT / "scripts/orchestrator/publish_four_window_dashboard_preview_v1.py"
WINDOWS = ["pre_open_0700", "intraday_1305", "pre_close_1335", "post_close_1500"]
FORBIDDEN_LINE = [
    "status:", "state:", "pipeline output available", "pipeline_type", "pipeline_run_id",
    "run_date", "run_time", "stock universe count", "advisory only; no trading instruction",
    "advisory_only", "insufficient data", "prediction review pending", "【2330 台積電】",
    "C級", "B級", "分", "收盤：", "技術：", "動能：", "ADR：", "法人：",
    "主力：", "資券：", "新聞：", "籌碼：", "策略：", "/stock-ai-dashboard/index.html",
]
FORBIDDEN_CARD = [
    "source_evidence", "latest_ohlcv_date", "read_mode", "source_type", "missing_fields",
    "local_analysis_context", "{'", "path':", '"path"', "data/historical/",
]
RAW_VALUES = ["bullish", "bearish", "uncertain", "medium_high"]
REQUIRED_CARD = [
    "預測摘要", "今日預測區間", "隔日預測區間", "1 個月趨勢", "3 個月趨勢",
    "信心分數", "方法", "deterministic baseline V1", "說明", "風險與資料品質",
    "重大新聞", "重大新聞資料待接", "偏多", "不明朗", "中高",
]
REGRESSION_MARKERS = [
    "單日檢討", "7 天滾動檢討", "產生時間", "資料品質摘要", "樣本數：9",
    "blocked_insufficient_sample", "Shadow tuning 門檻：30", "Formula change 門檻：100",
    "不代表穩定績效", "尚不可直接修改公式",
]


def line_outputs() -> dict[str, str]:
    outputs: dict[str, str] = {}
    for window in WINDOWS:
        report = format_window_report(window, "partial", "runtime dry-run summary", dashboard_url=DASHBOARD_URL_FALLBACK)
        outputs[window] = str(report["channel_reports"]["line"]["text"])
    outputs["legacy_short_formatter"] = format_line_short({"scheduler_window": "pre_open_0700"})
    return outputs


def stock_card_html(html: str) -> str:
    start = html.find('<section class="card"><h2>每日股價預測資料狀態</h2>')
    end = html.find('<section class="card"><h2>Forecast Calibration / 回測校準狀態</h2>', start)
    if start < 0 or end < 0:
        return ""
    return html[start:end]


def validate() -> dict[str, object]:
    errors: list[str] = []
    warnings: list[str] = []
    outputs = line_outputs()
    for window, text in outputs.items():
        if DASHBOARD_URL_FALLBACK not in text:
            errors.append(f"{window} LINE missing four-window Dashboard URL")
        if "僅供研究參考，非交易指令" not in text:
            errors.append(f"{window} LINE missing research-only wording")
        for forbidden in FORBIDDEN_LINE:
            if forbidden in text:
                errors.append(f"{window} LINE contains forbidden content: {forbidden}")
        if len(text) > 220:
            errors.append(f"{window} LINE too long: {len(text)}")
    if "收盤快照" not in outputs["pre_close_1335"]:
        errors.append("13:35 LINE must use close snapshot wording")
    if "盤後檢討" not in outputs["post_close_1500"]:
        errors.append("15:00 LINE must use prediction review wording")

    if not HTML.exists():
        errors.append(f"dashboard HTML missing: {HTML}")
        html = ""
    else:
        html = HTML.read_text(encoding="utf-8")
    cards = stock_card_html(html)
    if not cards:
        errors.append("stock card section missing")
    for marker in REQUIRED_CARD:
        if marker not in cards:
            errors.append(f"stock card missing PM-readable marker: {marker}")
    for forbidden in FORBIDDEN_CARD:
        if forbidden in cards:
            errors.append(f"stock card contains raw artifact/debug field: {forbidden}")
    for raw in RAW_VALUES:
        if re.search(rf">[^<]*\b{re.escape(raw)}\b[^<]*<", cards):
            errors.append(f"stock card displays raw enum value: {raw}")
    if "新聞情緒可用，重大標題待接" in cards and "重大新聞資料待接" not in cards:
        errors.append("news fallback wording inconsistent")
    for marker in REGRESSION_MARKERS:
        if marker not in html:
            errors.append(f"regression marker missing: {marker}")

    script_text = LEGACY_SCRIPT.read_text(encoding="utf-8") if LEGACY_SCRIPT.exists() else ""
    for marker in ["Legacy / Debug Landing", "不再作為正式投資決策主畫面", "四時段 Decision Intelligence Dashboard"]:
        if marker not in script_text:
            errors.append(f"legacy landing marker missing in publish script: {marker}")
    blocked_send_call = "send_line_" + "report("
    if blocked_send_call in script_text:
        errors.append("publish script must not send LINE")

    return {
        "ok": not errors,
        "task_id": "AI-DEV-157",
        "errors": errors,
        "warnings": warnings,
        "line_window_count": len(outputs),
        "dashboard_url": DASHBOARD_URL_FALLBACK,
        "notification_sent": False,
        "stock_card_checked": bool(cards),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    result = validate()
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
