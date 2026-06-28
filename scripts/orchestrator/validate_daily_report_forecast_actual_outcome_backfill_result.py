#!/usr/bin/env python3
"""Validate Daily Report Forecast actual outcome backfill result payloads."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "daily_report_forecast_actual_outcome_backfill_evaluation_v1"
DECISIONS = {
    "backfill_evaluation_completed",
    "partial_pending_actuals",
    "no_evaluable_records",
    "validation_failed",
    "blocked",
}
REQUIRED_TOP_LEVEL = [
    "schema_version",
    "task_id",
    "run_id",
    "generated_at",
    "mode",
    "input_summary",
    "backfill_summary",
    "evaluation_summary",
    "records",
    "metrics",
    "side_effects",
    "safety",
    "ok",
    "decision",
    "next_recommendation",
]
REQUIRED_SIDE_EFFECTS_FALSE = [
    "read_secrets",
    "called_external_ai_runtime",
    "called_market_data_runtime",
    "sent_notification",
    "placed_trade_order",
    "modified_production_db",
    "modified_cron_systemd_timer",
    "modified_n8n",
    "mutated_github_issue",
]
REQUIRED_BUCKETS = ["0-20", "21-40", "41-60", "61-80", "81-100", "unknown"]
FORBIDDEN_SOURCE_TERMS = [
    "broker",
    "shioaji",
    "production_db",
    "yfinance",
    "gemini",
    "openai",
    "dify",
]
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


def missing_keys(data: Any, keys: list[str]) -> list[str]:
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
    for key in REQUIRED_SIDE_EFFECTS_FALSE:
        if side_effects.get(key) is not False:
            errors.append(f"side_effects.{key} must be false")
    return errors


def validate_record(record: Any, index: int) -> list[str]:
    errors: list[str] = []
    name = f"records[{index}]"
    if not isinstance(record, dict):
        return [f"{name} must be an object"]
    for key in ["record_id", "stock_id", "horizon", "status"]:
        if not record.get(key):
            errors.append(f"{name}.{key} is required")
    horizon = record.get("horizon")
    status = record.get("status")
    if horizon not in {"same_day", "next_day", "one_month"}:
        errors.append(f"{name}.horizon is invalid")
    if status not in {"pending_actual_outcome", "actual_outcome_available", "evaluated"}:
        errors.append(f"{name}.status is invalid")
    if status == "evaluated":
        if horizon in {"same_day", "next_day"}:
            for key in ["actual_high", "actual_low", "actual_close"]:
                if not isinstance(record.get(key), (int, float)):
                    errors.append(f"{name}.{key} must be numeric when evaluated")
        if horizon == "one_month":
            for key in ["actual_window_high", "actual_window_low", "actual_return_pct", "actual_trend"]:
                if key not in record:
                    errors.append(f"{name}.{key} is required when evaluated")
            if record.get("actual_trend") not in {"up", "flat", "down", "unknown"}:
                errors.append(f"{name}.actual_trend is invalid")
        metrics = record.get("evaluation_metrics")
        if not isinstance(metrics, dict):
            errors.append(f"{name}.evaluation_metrics must be an object when evaluated")
        else:
            for key in [
                "interval_hit",
                "high_interval_hit",
                "low_interval_hit",
                "close_in_interval",
                "direction_hit",
                "absolute_error",
                "absolute_error_pct",
                "range_width_pct",
                "confidence_bucket",
                "evaluation_status",
            ]:
                if key not in metrics:
                    errors.append(f"{name}.evaluation_metrics missing {key}")
            if metrics.get("evaluation_status") != "evaluated":
                errors.append(f"{name}.evaluation_metrics.evaluation_status must be evaluated")
    if status == "pending_actual_outcome" and not record.get("pending_reason"):
        errors.append(f"{name}.pending_reason is required while pending")
    return errors


def validate_metrics(payload: dict[str, Any], records: list[Any]) -> list[str]:
    errors: list[str] = []
    metrics = payload.get("metrics")
    if not isinstance(metrics, dict):
        return ["metrics must be an object"]
    total = len(records)
    evaluated = sum(1 for record in records if isinstance(record, dict) and record.get("status") == "evaluated")
    pending = sum(1 for record in records if isinstance(record, dict) and record.get("status") == "pending_actual_outcome")
    if metrics.get("total_records") != total:
        errors.append("metrics.total_records must equal records length")
    if metrics.get("evaluated_records") != evaluated:
        errors.append("metrics.evaluated_records must equal evaluated records")
    if metrics.get("pending_records") != pending:
        errors.append("metrics.pending_records must equal pending records")
    if evaluated + pending != total:
        errors.append("evaluated_records + pending_records must equal total_records")
    buckets = metrics.get("confidence_bucket_metrics")
    if not isinstance(buckets, dict):
        errors.append("metrics.confidence_bucket_metrics must be an object")
    else:
        for bucket in REQUIRED_BUCKETS:
            bucket_data = buckets.get(bucket)
            if not isinstance(bucket_data, dict):
                errors.append(f"metrics.confidence_bucket_metrics.{bucket} must be an object")
                continue
            for key in ["total_records", "evaluated_records", "interval_hit_rate", "direction_hit_rate", "mean_absolute_error_pct"]:
                if key not in bucket_data:
                    errors.append(f"metrics.confidence_bucket_metrics.{bucket} missing {key}")
    summary = payload.get("backfill_summary")
    if not isinstance(summary, dict):
        errors.append("backfill_summary must be an object")
    else:
        for key in ["total_records", "evaluated_records", "pending_records"]:
            if summary.get(key) != metrics.get(key):
                errors.append(f"backfill_summary.{key} must match metrics.{key}")
    return errors


def validate_payload(payload: Any) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return {"ok": False, "errors": ["result root must be an object"]}
    for key in missing_keys(payload, REQUIRED_TOP_LEVEL):
        errors.append(f"missing top-level field: {key}")
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    if payload.get("decision") not in DECISIONS:
        errors.append("decision is invalid")
    errors.extend(validate_side_effects(payload))
    records = payload.get("records")
    if not isinstance(records, list):
        errors.append("records must be a list")
        records = []
    if not records and payload.get("decision") != "no_evaluable_records":
        errors.append("records cannot be empty unless decision is no_evaluable_records")
    for index, record in enumerate(records):
        errors.extend(validate_record(record, index))
    errors.extend(validate_metrics(payload, records))
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
    return {
        "ok": not errors,
        "run_id": payload.get("run_id"),
        "decision": payload.get("decision"),
        "total_records": len(records),
        "evaluated_records": sum(1 for record in records if isinstance(record, dict) and record.get("status") == "evaluated"),
        "pending_records": sum(1 for record in records if isinstance(record, dict) and record.get("status") == "pending_actual_outcome"),
        "errors": errors,
        "side_effects": {key: False for key in REQUIRED_SIDE_EFFECTS_FALSE},
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Daily Report Forecast actual outcome backfill result JSON.")
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
