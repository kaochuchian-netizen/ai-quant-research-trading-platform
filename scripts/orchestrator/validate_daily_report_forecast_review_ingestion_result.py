#!/usr/bin/env python3
"""Validate Daily Report Forecast review ingestion result payloads.

This validator is structural and safety-focused. It does not call external
services, read production databases, send notifications, or run pipelines.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


INGESTION_VERSION = "daily_report_forecast_review_ingestion_v1"
RECORD_TYPE = "daily_report_forecast_prediction_review"

REQUIRED_TOP_LEVEL = [
    "schema_version",
    "ingestion_version",
    "run_id",
    "generated_at",
    "source_forecast_run_id",
    "source_forecast_version",
    "run_date",
    "timezone",
    "review_records",
    "aggregate_summary",
    "validation_status",
    "runtime_action_performed",
    "notification_sent",
    "production_pipeline_run",
    "safety",
]

REQUIRED_RECORD_FIELDS = [
    "record_id",
    "record_type",
    "record_status",
    "stock_id",
    "stock_name",
    "forecast_version",
    "source_forecast_run_id",
    "run_date",
    "timezone",
    "forecast_horizon",
    "forecast_target",
    "target_date",
    "review_window",
    "review_due",
    "forecast_snapshot",
    "actual_outcome",
    "evaluation_metrics",
    "source_metadata",
    "safety",
]

REQUIRED_SAFETY_TRUE = [
    "fixture_only",
    "advisory_only",
    "research_only",
    "no_trade",
    "no_order",
    "no_trading_instruction",
    "no_order_execution",
    "requires_human_review",
]

HORIZON_RULES = {
    "same_day": {
        "target": "same_day_high_low_interval",
        "window": "same_day_close",
        "snapshot_interval": "price_interval",
        "actual_values": ["actual_high", "actual_low", "actual_close", "actual_return", "actual_direction"],
    },
    "next_day": {
        "target": "next_day_high_low_interval",
        "window": "next_trading_day_close",
        "snapshot_interval": "price_interval",
        "actual_values": ["actual_high", "actual_low", "actual_close", "actual_return", "actual_direction"],
    },
    "one_month": {
        "target": "one_month_trend_interval",
        "window": "one_month_close",
        "snapshot_interval": "trend_interval",
        "actual_values": ["actual_return", "actual_trend", "actual_close"],
    },
}

SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{20,}"),
    re.compile(r"AIza[0-9A-Za-z_-]{20,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{20,}", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
]

FORBIDDEN_TRADING_TEXT = [
    re.compile(r"\b(buy|sell|short|long)\s+(now|today|at market|at open|at close)\b", re.IGNORECASE),
    re.compile(r"\b(place|submit|route|execute)\s+(an?\s+)?order\b", re.IGNORECASE),
    re.compile(r"\border\s+(now|immediately|ticket|instruction)\b", re.IGNORECASE),
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


def validate_safety(name: str, safety: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(safety, dict):
        return [f"{name}.safety must be an object"]
    for key in REQUIRED_SAFETY_TRUE:
        if safety.get(key) is not True:
            errors.append(f"{name}.safety.{key} must be true")
    for key in [
        "external_api_called",
        "notification_sent",
        "production_pipeline_run",
        "production_db_modified",
        "trading_or_order_run",
        "secrets_read_or_modified",
    ]:
        if key in safety and safety.get(key) is not False:
            errors.append(f"{name}.safety.{key} must be false")
    return errors


def validate_price_interval(name: str, interval: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(interval, dict):
        return [f"{name} must be an object"]
    for key in ["low", "high", "unit", "interval_method", "contains_reference_price"]:
        if key not in interval:
            errors.append(f"{name} missing {key}")
    low = interval.get("low")
    high = interval.get("high")
    if not isinstance(low, (int, float)) or not isinstance(high, (int, float)):
        errors.append(f"{name}.low/high must be numeric")
    elif low > high:
        errors.append(f"{name}.low must be <= high")
    return errors


def validate_trend_interval(name: str, interval: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(interval, dict):
        return [f"{name} must be an object"]
    for key in ["lower", "upper", "unit", "interval_method"]:
        if key not in interval:
            errors.append(f"{name} missing {key}")
    lower = interval.get("lower")
    upper = interval.get("upper")
    if isinstance(lower, (int, float)) and isinstance(upper, (int, float)) and lower > upper:
        errors.append(f"{name}.lower must be <= upper")
    return errors


def validate_forecast_snapshot(name: str, snapshot: Any, rule: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(snapshot, dict):
        return [f"{name} must be an object"]
    for key in ["forecast_type", "forecast_target", "confidence_score", "confidence_bucket", "basis", "review_due"]:
        if key not in snapshot:
            errors.append(f"{name} missing {key}")
    if snapshot.get("forecast_target") != rule["target"]:
        errors.append(f"{name}.forecast_target must be {rule['target']}")
    confidence = snapshot.get("confidence_score")
    if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
        errors.append(f"{name}.confidence_score must be between 0 and 1")
    if not isinstance(snapshot.get("basis"), list):
        errors.append(f"{name}.basis must be a list")
    if rule["snapshot_interval"] == "price_interval":
        errors.extend(validate_price_interval(f"{name}.price_interval", snapshot.get("price_interval")))
    else:
        if not snapshot.get("trend"):
            errors.append(f"{name}.trend is required")
        errors.extend(validate_trend_interval(f"{name}.trend_interval", snapshot.get("trend_interval")))
    return errors


def validate_actual_outcome(name: str, actual: Any, required_values: list[str]) -> list[str]:
    errors: list[str] = []
    if not isinstance(actual, dict):
        return [f"{name} must be an object"]
    if actual.get("outcome_status") != "pending":
        errors.append(f"{name}.outcome_status must be pending")
    if actual.get("source_status") != "not_collected":
        errors.append(f"{name}.source_status must be not_collected")
    if not actual.get("pending_reason"):
        errors.append(f"{name}.pending_reason is required")
    values = actual.get("values")
    if not isinstance(values, dict):
        errors.append(f"{name}.values must be an object")
    else:
        for key in required_values:
            if key not in values:
                errors.append(f"{name}.values missing {key}")
            elif values.get(key) is not None:
                errors.append(f"{name}.values.{key} must be null while pending")
    return errors


def validate_metrics(name: str, metrics: Any, confidence_bucket: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(metrics, dict):
        return [f"{name} must be an object"]
    for key in [
        "evaluation_status",
        "interval_hit",
        "high_inside_interval",
        "low_inside_interval",
        "direction_match",
        "trend_match",
        "absolute_error",
        "high_forecast_error",
        "low_forecast_error",
        "confidence_bucket",
        "calibration_bucket",
    ]:
        if key not in metrics:
            errors.append(f"{name} missing {key}")
    if metrics.get("evaluation_status") != "pending":
        errors.append(f"{name}.evaluation_status must be pending")
    for key in [
        "interval_hit",
        "high_inside_interval",
        "low_inside_interval",
        "direction_match",
        "trend_match",
        "absolute_error",
        "high_forecast_error",
        "low_forecast_error",
    ]:
        if key in metrics and metrics.get(key) is not None:
            errors.append(f"{name}.{key} must be null while pending")
    if metrics.get("confidence_bucket") != confidence_bucket:
        errors.append(f"{name}.confidence_bucket must match forecast_snapshot.confidence_bucket")
    if metrics.get("calibration_bucket") != "pending":
        errors.append(f"{name}.calibration_bucket must be pending")
    return errors


def validate_record(record: Any, index: int) -> list[str]:
    name = f"review_records[{index}]"
    errors: list[str] = []
    if not isinstance(record, dict):
        return [f"{name} must be an object"]
    for key in missing_keys(record, REQUIRED_RECORD_FIELDS):
        errors.append(f"{name} missing {key}")
    if record.get("record_type") != RECORD_TYPE:
        errors.append(f"{name}.record_type must be {RECORD_TYPE}")
    if record.get("record_status") != "pending_actual_outcome":
        errors.append(f"{name}.record_status must be pending_actual_outcome")
    if not str(record.get("stock_id", "")).strip():
        errors.append(f"{name}.stock_id is required")
    if not str(record.get("stock_name", "")).strip():
        errors.append(f"{name}.stock_name is required")
    if record.get("forecast_version") != "daily_report_forecast_v1":
        errors.append(f"{name}.forecast_version must be daily_report_forecast_v1")
    horizon = record.get("forecast_horizon")
    rule = HORIZON_RULES.get(str(horizon))
    if rule is None:
        errors.append(f"{name}.forecast_horizon is not recognized")
        rule = HORIZON_RULES["same_day"]
    if record.get("forecast_target") != rule["target"]:
        errors.append(f"{name}.forecast_target must be {rule['target']}")
    if record.get("review_window") != rule["window"]:
        errors.append(f"{name}.review_window must be {rule['window']}")
    if not record.get("target_date"):
        errors.append(f"{name}.target_date is required")
    if not record.get("review_due"):
        errors.append(f"{name}.review_due is required")
    snapshot = record.get("forecast_snapshot")
    errors.extend(validate_forecast_snapshot(f"{name}.forecast_snapshot", snapshot, rule))
    confidence_bucket = snapshot.get("confidence_bucket") if isinstance(snapshot, dict) else None
    errors.extend(validate_actual_outcome(f"{name}.actual_outcome", record.get("actual_outcome"), rule["actual_values"]))
    errors.extend(validate_metrics(f"{name}.evaluation_metrics", record.get("evaluation_metrics"), confidence_bucket))
    source_metadata = record.get("source_metadata")
    if not isinstance(source_metadata, dict):
        errors.append(f"{name}.source_metadata must be an object")
    else:
        for key in ["report_window", "generated_at", "data_cutoff", "signals_used", "original_prediction_review"]:
            if key not in source_metadata:
                errors.append(f"{name}.source_metadata missing {key}")
        if source_metadata.get("report_window") != "pre_open":
            errors.append(f"{name}.source_metadata.report_window must be pre_open")
    errors.extend(validate_safety(name, record.get("safety")))
    return errors


def validate_payload(payload: Any) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return {"ok": False, "errors": ["result root must be an object"]}
    for key in missing_keys(payload, REQUIRED_TOP_LEVEL):
        errors.append(f"missing top-level field: {key}")
    if payload.get("ingestion_version") != INGESTION_VERSION:
        errors.append(f"ingestion_version must be {INGESTION_VERSION}")
    if payload.get("source_forecast_version") != "daily_report_forecast_v1":
        errors.append("source_forecast_version must be daily_report_forecast_v1")
    for key in ["runtime_action_performed", "notification_sent", "production_pipeline_run"]:
        if payload.get(key) is not False:
            errors.append(f"{key} must be false")
    records = payload.get("review_records")
    if not isinstance(records, list) or not records:
        errors.append("review_records must be a non-empty list")
        records = []
    record_ids: set[str] = set()
    for index, record in enumerate(records):
        errors.extend(validate_record(record, index))
        if isinstance(record, dict):
            record_id = str(record.get("record_id", ""))
            if record_id in record_ids:
                errors.append(f"duplicate record_id: {record_id}")
            record_ids.add(record_id)
    summary = payload.get("aggregate_summary")
    if not isinstance(summary, dict):
        errors.append("aggregate_summary must be an object")
    else:
        stock_ids = {str(record.get("stock_id")) for record in records if isinstance(record, dict)}
        if summary.get("stock_count") != len(stock_ids):
            errors.append("aggregate_summary.stock_count must equal unique stock_id count")
        if summary.get("review_record_count") != len(records):
            errors.append("aggregate_summary.review_record_count must equal review_records length")
        pending = sum(1 for record in records if isinstance(record, dict) and record.get("record_status") == "pending_actual_outcome")
        if summary.get("pending_actual_outcome_count") != pending:
            errors.append("aggregate_summary.pending_actual_outcome_count must equal pending records")
        windows = summary.get("review_windows")
        if not isinstance(windows, list) or set(windows) != {rule["window"] for rule in HORIZON_RULES.values()}:
            errors.append("aggregate_summary.review_windows must include same_day, next_day, and one_month windows")
        if summary.get("fixture_only") is not True:
            errors.append("aggregate_summary.fixture_only must be true")
    status = payload.get("validation_status")
    if not isinstance(status, dict):
        errors.append("validation_status must be an object")
    elif not status.get("status"):
        errors.append("validation_status.status is required")
    errors.extend(validate_safety("result", payload.get("safety")))

    rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    for pattern in SECRET_PATTERNS:
        if pattern.search(rendered):
            errors.append(f"secret-like value detected: {pattern.pattern}")
            break
    for text in iter_strings(payload):
        for pattern in FORBIDDEN_TRADING_TEXT:
            if pattern.search(text):
                errors.append(f"possible trading/order instruction detected: {text}")

    return {
        "ok": not errors,
        "run_id": payload.get("run_id"),
        "run_date": payload.get("run_date"),
        "source_forecast_run_id": payload.get("source_forecast_run_id"),
        "review_record_count": len(records),
        "errors": errors,
        "side_effects": {
            "external_api_called": False,
            "notification_sent": False,
            "production_pipeline_run": False,
            "production_db_modified": False,
            "trading_or_order_run": False,
            "secrets_read_or_modified": False,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Daily Report Forecast review ingestion result JSON.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload, load_errors = load_json(Path(args.input))
    result = {"ok": False, "errors": load_errors} if payload is None else validate_payload(payload)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
