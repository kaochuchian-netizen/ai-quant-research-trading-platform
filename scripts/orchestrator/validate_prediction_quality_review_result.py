#!/usr/bin/env python3
"""Validate Prediction Quality Review + Daily Improvement result payloads."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "prediction_quality_review_daily_improvement_v1"
DECISIONS = {
    "quality_review_completed",
    "quality_review_completed_with_insufficient_data",
    "no_evaluated_records",
    "validation_failed",
    "blocked",
}
TOP_LEVEL = [
    "schema_version",
    "task_id",
    "run_id",
    "generated_at",
    "mode",
    "input_summary",
    "quality_review_summary",
    "horizon_reviews",
    "confidence_calibration",
    "error_patterns",
    "daily_improvement_recommendations",
    "next_forecast_tuning_hints",
    "side_effects",
    "safety",
    "ok",
    "decision",
    "next_recommendation",
]
SIDE_EFFECTS_FALSE = [
    "read_secrets",
    "called_external_ai_runtime",
    "called_market_data_runtime",
    "sent_notification",
    "placed_trade_order",
    "modified_production_db",
    "modified_cron_systemd_timer",
    "modified_n8n",
    "mutated_github_issue",
    "modified_forecast_runtime_weights",
]
HORIZONS = {"same_day", "next_day", "one_month"}
GRADES = {"A", "B", "C", "D", "Insufficient Data"}
CALIBRATION = {"well_calibrated", "overconfident", "underconfident", "insufficient_data"}
SEVERITY = {"low", "medium", "high"}
FORBIDDEN_SOURCE_TERMS = ["broker", "shioaji", "production_db", "yfinance", "gemini", "openai", "dify"]
SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{20,}"),
    re.compile(r"AIza[0-9A-Za-z_-]{20,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{20,}", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\.env", re.IGNORECASE),
]


def load_json(path: Path) -> tuple[Any | None, list[str]]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), []
    except Exception as exc:
        return None, [f"failed to read JSON: {exc}"]


def missing(data: Any, keys: list[str]) -> list[str]:
    if not isinstance(data, dict):
        return keys
    return [key for key in keys if key not in data]


def iter_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            result.extend(iter_strings(item))
        return result
    if isinstance(value, dict):
        result: list[str] = []
        for item in value.values():
            result.extend(iter_strings(item))
        return result
    return []


def validate_side_effects(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    side_effects = payload.get("side_effects")
    if not isinstance(side_effects, dict):
        return ["side_effects must be an object"]
    for key in SIDE_EFFECTS_FALSE:
        if side_effects.get(key) is not False:
            errors.append(f"side_effects.{key} must be false")
    return errors


def validate_summary(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    summary = payload.get("quality_review_summary")
    if not isinstance(summary, dict):
        return ["quality_review_summary must be an object"]
    for key in ["total_records", "evaluated_records", "pending_records", "overall_quality_grade", "overall_quality_status"]:
        if key not in summary:
            errors.append(f"quality_review_summary missing {key}")
    if summary.get("overall_quality_grade") not in GRADES:
        errors.append("quality_review_summary.overall_quality_grade is invalid")
    if payload.get("decision") == "no_evaluated_records" and summary.get("evaluated_records") != 0:
        errors.append("no_evaluated_records decision requires evaluated_records = 0")
    if payload.get("decision") == "quality_review_completed" and not (summary.get("evaluated_records", 0) >= 1):
        errors.append("quality_review_completed requires at least 1 evaluated record")
    return errors


def validate_horizon_reviews(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    reviews = payload.get("horizon_reviews")
    if not isinstance(reviews, list):
        return ["horizon_reviews must be a list"]
    for index, review in enumerate(reviews):
        name = f"horizon_reviews[{index}]"
        if not isinstance(review, dict):
            errors.append(f"{name} must be an object")
            continue
        for key in [
            "horizon",
            "total_records",
            "evaluated_records",
            "pending_records",
            "interval_hit_rate",
            "high_interval_hit_rate",
            "low_interval_hit_rate",
            "direction_hit_rate",
            "mean_absolute_error_pct",
            "median_absolute_error_pct",
            "max_absolute_error_pct",
            "pending_rate",
            "quality_grade",
            "quality_status",
        ]:
            if key not in review:
                errors.append(f"{name} missing {key}")
        if review.get("horizon") not in HORIZONS:
            errors.append(f"{name}.horizon is invalid")
        if review.get("quality_grade") not in GRADES:
            errors.append(f"{name}.quality_grade is invalid")
        if review.get("evaluated_records", 0) + review.get("pending_records", 0) != review.get("total_records"):
            errors.append(f"{name} evaluated + pending must equal total")
    return errors


def validate_calibration(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    items = payload.get("confidence_calibration")
    if not isinstance(items, list):
        return ["confidence_calibration must be a list"]
    for index, item in enumerate(items):
        name = f"confidence_calibration[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{name} must be an object")
            continue
        for key in ["bucket", "record_count", "evaluated_count", "interval_hit_rate", "direction_hit_rate", "mean_absolute_error_pct", "calibration_status"]:
            if key not in item:
                errors.append(f"{name} missing {key}")
        if item.get("calibration_status") not in CALIBRATION:
            errors.append(f"{name}.calibration_status is invalid")
    return errors


def validate_error_patterns(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    patterns = payload.get("error_patterns")
    if not isinstance(patterns, list):
        return ["error_patterns must be a list"]
    for index, item in enumerate(patterns):
        name = f"error_patterns[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{name} must be an object")
            continue
        for key in ["pattern", "count", "affected_horizons", "severity", "example_record_ids", "recommendation"]:
            if key not in item:
                errors.append(f"{name} missing {key}")
        if item.get("severity") not in SEVERITY:
            errors.append(f"{name}.severity is invalid")
        if not isinstance(item.get("affected_horizons"), list):
            errors.append(f"{name}.affected_horizons must be a list")
        if not isinstance(item.get("example_record_ids"), list):
            errors.append(f"{name}.example_record_ids must be a list")
    return errors


def validate_recommendations(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    items = payload.get("daily_improvement_recommendations")
    if not isinstance(items, list):
        return ["daily_improvement_recommendations must be a list"]
    for index, item in enumerate(items):
        name = f"daily_improvement_recommendations[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{name} must be an object")
            continue
        for key in [
            "recommendation_id",
            "priority",
            "target_horizon",
            "reason",
            "expected_effect",
            "safe_to_apply_automatically",
            "requires_human_review",
        ]:
            if key not in item:
                errors.append(f"{name} missing {key}")
        if item.get("safe_to_apply_automatically") is not False:
            errors.append(f"{name}.safe_to_apply_automatically must be false")
        if item.get("requires_human_review") is not True:
            errors.append(f"{name}.requires_human_review must be true")
    for section in ["next_forecast_tuning_hints"]:
        hints = payload.get(section)
        if not isinstance(hints, list):
            errors.append(f"{section} must be a list")
            continue
        for index, hint in enumerate(hints):
            if not isinstance(hint, dict):
                errors.append(f"{section}[{index}] must be an object")
                continue
            if hint.get("safe_to_apply_automatically") is not False:
                errors.append(f"{section}[{index}].safe_to_apply_automatically must be false")
            if hint.get("requires_human_review") is not True:
                errors.append(f"{section}[{index}].requires_human_review must be true")
    return errors


def validate_safety(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    safety = payload.get("safety")
    if not isinstance(safety, dict):
        return ["safety must be an object"]
    if safety.get("forecast_runtime_weights_modified") is not False:
        errors.append("safety.forecast_runtime_weights_modified must be false")
    return errors


def validate_payload(payload: Any) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return {"ok": False, "errors": ["result root must be an object"]}
    for key in missing(payload, TOP_LEVEL):
        errors.append(f"missing top-level field: {key}")
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    if payload.get("decision") not in DECISIONS:
        errors.append("decision is invalid")
    errors.extend(validate_side_effects(payload))
    errors.extend(validate_summary(payload))
    errors.extend(validate_horizon_reviews(payload))
    errors.extend(validate_calibration(payload))
    errors.extend(validate_error_patterns(payload))
    errors.extend(validate_recommendations(payload))
    errors.extend(validate_safety(payload))
    rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    for pattern in SECRET_PATTERNS:
        if pattern.search(rendered):
            errors.append(f"secret-like or private config text detected: {pattern.pattern}")
            break
    for text in iter_strings(payload):
        lowered = text.lower()
        for term in FORBIDDEN_SOURCE_TERMS:
            if term in lowered:
                errors.append(f"forbidden live runtime source detected: {term}")
    summary = payload.get("quality_review_summary") if isinstance(payload.get("quality_review_summary"), dict) else {}
    return {
        "ok": not errors,
        "run_id": payload.get("run_id"),
        "decision": payload.get("decision"),
        "total_records": summary.get("total_records"),
        "evaluated_records": summary.get("evaluated_records"),
        "pending_records": summary.get("pending_records"),
        "overall_quality_grade": summary.get("overall_quality_grade"),
        "overall_quality_status": summary.get("overall_quality_status"),
        "errors": errors,
        "side_effects": {key: False for key in SIDE_EFFECTS_FALSE},
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Prediction Quality Review result JSON.")
    parser.add_argument("path", nargs="?")
    parser.add_argument("--input", dest="input_path")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = args.input_path or args.path
    if not input_path:
        raise SystemExit("input path is required")
    payload, load_errors = load_json(Path(input_path))
    result = {"ok": False, "errors": load_errors} if payload is None else validate_payload(payload)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
