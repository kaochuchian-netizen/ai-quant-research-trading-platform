#!/usr/bin/env python3
"""Validate AI-DEV-158 LINE runtime activation guard artifacts."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
from app.dashboard.dashboard_url_registry import get_tw_dashboard_url

PREVIEW_JSON = REPO_ROOT / "artifacts/runtime/line_four_batch_runtime_preview_latest.json"
TRACE_MD = REPO_ROOT / "artifacts/runtime/line_runtime_activation_trace_latest.md"
NEW_URL = get_tw_dashboard_url()
REQUIRED_WINDOWS = {"pre_open_0700", "intraday_1305", "pre_close_1335", "post_close_1500"}
FORBIDDEN_TERMS = [
    "/stock-ai-dashboard/index.html",
    "status:",
    "state:",
    "pipeline output available",
    "pipeline_type",
    "pipeline_run_id",
    "run_date",
    "run_time",
    "advisory only; no trading instruction",
    "advisory_only",
    "prediction review pending",
    "insufficient data",
    "【2330 台積電】",
    "C級",
    "B級",
    "收盤：",
    "技術：",
    "ADR：",
    "法人：",
    "主力：",
    "資券：",
    "新聞：",
    "籌碼：",
    "策略：",
]
STOCK_DETAIL_TERMS = ["今日最高價預測", "今日最低價預測", "信心分數", "評等", "動作"]


def load_json(path: Path, errors: list[str]) -> dict[str, Any]:
    if not path.exists():
        errors.append(f"missing preview JSON: {path}")
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"preview JSON parse failed: {exc}")
        return {}


def invalid_number(value: Any) -> bool:
    return isinstance(value, float) and (math.isnan(value) or math.isinf(value))


def validate(payload: dict[str, Any], trace_path: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if payload.get("schema_version") != "line_four_batch_runtime_preview_v1":
        errors.append("schema_version must be line_four_batch_runtime_preview_v1")
    if payload.get("task_id") != "AI-DEV-158":
        errors.append("task_id must be AI-DEV-158")
    if payload.get("is_actual_send") is not False:
        errors.append("top-level is_actual_send must be false")
    if payload.get("safety_mode") != "dry_run_preview_only":
        errors.append("top-level safety_mode must be dry_run_preview_only")
    if payload.get("dashboard_url") != NEW_URL:
        errors.append("top-level dashboard_url must use the four-window Dashboard URL")
    if not trace_path.exists():
        errors.append(f"runtime trace report missing: {trace_path}")

    windows = payload.get("windows")
    if not isinstance(windows, list):
        errors.append("windows must be a list")
        return errors, warnings
    seen = {str(window.get("window")) for window in windows if isinstance(window, dict)}
    missing = REQUIRED_WINDOWS - seen
    if missing:
        errors.append(f"missing required windows: {sorted(missing)}")

    for window in windows:
        if not isinstance(window, dict):
            errors.append("window entry must be an object")
            continue
        key = str(window.get("window"))
        message = str(window.get("message_body", ""))
        lowered = message.lower()
        if window.get("is_actual_send") is not False:
            errors.append(f"{key}: is_actual_send must be false")
        if window.get("safety_mode") != "dry_run_preview_only":
            errors.append(f"{key}: safety_mode must be dry_run_preview_only")
        if window.get("dashboard_url") != NEW_URL or NEW_URL not in message:
            errors.append(f"{key}: must use the four-window Dashboard URL")
        if "僅供研究參考，非交易指令" not in message:
            errors.append(f"{key}: missing research/no-trading wording")
        hits = [term for term in FORBIDDEN_TERMS if term.lower() in lowered]
        if hits:
            errors.append(f"{key}: forbidden content found: {hits}")
        stock_hits = [term for term in STOCK_DETAIL_TERMS if term in message]
        if stock_hits:
            errors.append(f"{key}: stock detail content found: {stock_hits}")
        if key == "pre_close_1335" and "收盤快照" not in message:
            errors.append("pre_close_1335 must contain 收盤快照")
        if key == "post_close_1500" and "盤後檢討" not in message:
            errors.append("post_close_1500 must contain 盤後檢討")
        check = window.get("forbidden_content_check", {})
        if isinstance(check, dict) and check.get("ok") is not True:
            errors.append(f"{key}: forbidden_content_check must be ok=true")

    def scan_numbers(obj: Any, path: str = "payload") -> None:
        if invalid_number(obj):
            errors.append(f"invalid number at {path}")
        elif isinstance(obj, dict):
            for k, v in obj.items():
                scan_numbers(v, f"{path}.{k}")
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                scan_numbers(v, f"{path}[{i}]")
    scan_numbers(payload)
    return errors, warnings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate LINE runtime activation guard preview.")
    parser.add_argument("--preview", default=str(PREVIEW_JSON))
    parser.add_argument("--trace", default=str(TRACE_MD))
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    errors: list[str] = []
    payload = load_json(Path(args.preview), errors)
    warnings: list[str] = []
    if payload:
        extra_errors, warnings = validate(payload, Path(args.trace))
        errors.extend(extra_errors)
    summary = {
        "ok": not errors,
        "task_id": "AI-DEV-158",
        "preview": args.preview,
        "trace": args.trace,
        "windows": sorted(REQUIRED_WINDOWS),
        "errors": errors,
        "warnings": warnings,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
