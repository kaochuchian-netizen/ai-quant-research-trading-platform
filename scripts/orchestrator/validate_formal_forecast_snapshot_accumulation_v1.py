#!/usr/bin/env python3
"""Validate formal forecast snapshot accumulation artifacts for AI-DEV-155."""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
INDEX_JSON = ROOT / "artifacts/archive/formal_forecast_snapshots/index/formal_forecast_snapshot_index_latest.json"
DASHBOARD_HTML = ROOT / "templates/four_window_dashboard_route_preview.example.html"
PUBLISHED_URL = "http://35.201.242.167/stock-ai-dashboard/dashboard/decision-intelligence/four-window-preview/index.html"
SECRET_PATTERNS = [r"Authorization:\s*Bearer\s+[A-Za-z0-9._~+/=-]+", r"api[_-]?key\s*[:=]\s*[^\s\"']+", r"token\s*[:=]\s*[^\s\"']+", r"BEGIN (?:RSA |OPENSSH )?PRIVATE KEY", r"\.env"]


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
    def handle_data(self, data: str) -> None:
        if data.strip():
            self.parts.append(data.strip())
    @property
    def text(self) -> str:
        return " ".join(self.parts)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def no_nan(value: Any, path: str, errors: list[str]) -> None:
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        errors.append(f"NaN/Infinity at {path}")
    elif isinstance(value, dict):
        for k, v in value.items():
            no_nan(v, f"{path}.{k}", errors)
    elif isinstance(value, list):
        for i, v in enumerate(value):
            no_nan(v, f"{path}[{i}]", errors)


def scan_secret_patterns(text: str) -> list[str]:
    hits: list[str] = []
    for pattern in SECRET_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            hits.append(pattern)
    return hits


def html_text(source: str) -> str:
    parser = TextExtractor()
    parser.feed(source)
    return parser.text


def fetch_published() -> str:
    with urlopen(PUBLISHED_URL, timeout=10) as resp:  # nosec: public dashboard validation only
        return resp.read().decode("utf-8", errors="replace")


def validate_index(errors: list[str], warnings: list[str]) -> dict[str, Any] | None:
    if not INDEX_JSON.exists():
        errors.append(f"missing snapshot index: {rel(INDEX_JSON)}")
        return None
    index = read_json(INDEX_JSON)
    if index.get("artifact_type") != "formal_forecast_snapshot_index":
        errors.append("snapshot index artifact_type must be formal_forecast_snapshot_index")
    for key in ["snapshot_count", "prediction_snapshot_count", "actual_outcome_snapshot_count", "review_snapshot_count", "eligible_same_day_sample_count", "eligible_next_day_sample_count"]:
        value = index.get(key)
        if not isinstance(value, int) or value < 0:
            errors.append(f"{key} must be non-negative integer")
    progress = index.get("calibration_gate_progress") if isinstance(index.get("calibration_gate_progress"), dict) else {}
    if progress.get("ready_for_shadow_tuning_threshold") != 30:
        errors.append("ready_for_shadow_tuning_threshold must be 30")
    if progress.get("ready_for_formula_change_threshold") != 100:
        errors.append("ready_for_formula_change_threshold must be 100")
    eligible = progress.get("current_eligible_sample_count")
    gate = progress.get("current_gate_status")
    if isinstance(eligible, int):
        if eligible < 30 and gate == "ready_for_shadow_tuning":
            errors.append("gate cannot be ready_for_shadow_tuning when eligible sample count < 30")
        if eligible < 100 and gate == "ready_for_formula_change":
            errors.append("gate cannot be ready_for_formula_change when eligible sample count < 100")
    else:
        errors.append("current_eligible_sample_count must be integer")
    no_nan(index, "snapshot_index", errors)
    if not any("next-day" in str(item).lower() or "next_day" in str(item).lower() for item in index.get("limitations", [])):
        errors.append("index limitations must explicitly mention missing next-day outcomes")
    return index


def validate_snapshot_files(index: dict[str, Any] | None, errors: list[str]) -> None:
    if not index:
        return
    for row in index.get("snapshots", []):
        if not isinstance(row, dict):
            errors.append("snapshot row must be object")
            continue
        pred_path = row.get("prediction_snapshot_path")
        if pred_path:
            path = ROOT / str(pred_path)
            if not path.exists():
                errors.append(f"missing prediction snapshot: {pred_path}")
            else:
                pred = read_json(path)
                if pred.get("is_example") is True:
                    errors.append(f"prediction snapshot must not be example: {pred_path}")
                meta = pred.get("snapshot_metadata") if isinstance(pred.get("snapshot_metadata"), dict) else {}
                if meta.get("is_fake_backfilled_forecast") is not False:
                    errors.append(f"prediction snapshot must explicitly forbid fake backfilled forecasts: {pred_path}")
        actual_path = row.get("actual_outcome_snapshot_path")
        if actual_path:
            actual = read_json(ROOT / str(actual_path))
            if actual.get("artifact_type") != "formal_actual_outcome_snapshot":
                errors.append(f"actual snapshot artifact_type mismatch: {actual_path}")
            if "is_backfilled_actual" not in actual:
                errors.append(f"actual snapshot must explicitly mark is_backfilled_actual: {actual_path}")
        review_path = row.get("review_snapshot_path")
        if review_path:
            review = read_json(ROOT / str(review_path))
            if review.get("fake_hit_rate_generated") is not False:
                errors.append(f"review snapshot must not generate fake hit rate: {review_path}")
            for stock in review.get("stocks", []):
                if not isinstance(stock, dict):
                    continue
                if stock.get("next_day_interval_result") is None and "next_day_actual_outcome_unavailable" not in stock.get("insufficient_data_reasons", []):
                    errors.append(f"{review_path} {stock.get('stock_id')}: missing next-day outcome must be explicit")
                no_nan(stock, f"{review_path}.{stock.get('stock_id')}", errors)


def validate_dashboard(errors: list[str], warnings: list[str], *, published: bool) -> None:
    if published:
        try:
            source = fetch_published()
        except Exception as exc:
            errors.append(f"published dashboard fetch failed: {exc}")
            return
    else:
        if not DASHBOARD_HTML.exists():
            errors.append(f"missing dashboard html: {rel(DASHBOARD_HTML)}")
            return
        source = DASHBOARD_HTML.read_text(encoding="utf-8")
    text = html_text(source)
    required = [
        "Forecast Snapshot Accumulation / 預測樣本累積進度",
        "已歸檔 prediction snapshots",
        "可評估 same-day samples",
        "Shadow tuning 門檻：30",
        "Formula change 門檻：100",
        "blocked_insufficient_sample",
        "樣本數不足時不可直接調整公式",
    ]
    for phrase in required:
        if phrase not in text:
            errors.append(f"dashboard missing required snapshot wording: {phrase}")
    hits = scan_secret_patterns(source)
    if hits:
        errors.append("dashboard contains forbidden secret-like pattern")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--published", action="store_true", help="Validate the public published dashboard URL instead of local preview HTML.")
    args = parser.parse_args()
    errors: list[str] = []
    warnings: list[str] = []
    index = validate_index(errors, warnings)
    validate_snapshot_files(index, errors)
    validate_dashboard(errors, warnings, published=args.published)
    result = {
        "ok": not errors,
        "schema_version": "formal_forecast_snapshot_accumulation_validator_v1",
        "index_path": rel(INDEX_JSON),
        "published_dashboard_checked": args.published,
        "snapshot_count": index.get("snapshot_count") if index else None,
        "prediction_snapshot_count": index.get("prediction_snapshot_count") if index else None,
        "actual_outcome_snapshot_count": index.get("actual_outcome_snapshot_count") if index else None,
        "review_snapshot_count": index.get("review_snapshot_count") if index else None,
        "eligible_same_day_sample_count": index.get("eligible_same_day_sample_count") if index else None,
        "eligible_next_day_sample_count": index.get("eligible_next_day_sample_count") if index else None,
        "current_gate_status": (index.get("calibration_gate_progress") or {}).get("current_gate_status") if index else None,
        "errors": errors,
        "warnings": warnings,
        "side_effects": {"files_modified": False, "db_write": False, "notification_sent": False, "production_pipeline_executed": False},
    }
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
