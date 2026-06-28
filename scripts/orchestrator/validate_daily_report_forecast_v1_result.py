#!/usr/bin/env python3
"""Validate Daily Report Forecast V1 result payloads.

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


REQUIRED_TOP_LEVEL = [
    "schema_version",
    "run_id",
    "run_date",
    "timezone",
    "report_window",
    "forecast_version",
    "generated_at",
    "data_cutoff",
    "stocks",
    "aggregate_summary",
    "validation_status",
    "runtime_action_performed",
    "notification_sent",
    "production_pipeline_run",
    "safety",
]

REQUIRED_STOCK_FIELDS = [
    "stock_id",
    "stock_name",
    "reference_price",
    "same_day_forecast",
    "next_day_forecast",
    "one_month_trend_forecast",
    "signals_used",
    "prediction_review",
    "safety",
]

REQUIRED_SAFETY_TRUE = [
    "advisory_only",
    "research_only",
    "no_trade",
    "no_order",
    "no_trading_instruction",
    "no_order_execution",
    "requires_human_review",
]

REQUIRED_PRICE_INTERVAL = ["low", "high", "unit", "interval_method", "contains_reference_price"]
REQUIRED_REVIEW_FIELDS = [
    "review_status",
    "same_day_review_due",
    "next_day_review_due",
    "one_month_review_due",
    "actual_outcome",
    "evaluation_metrics",
    "review_notes",
]

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
    for key in ["external_api_called", "notification_sent", "production_pipeline_run"]:
        if key in safety and safety.get(key) is not False:
            errors.append(f"{name}.safety.{key} must be false")
    return errors


def validate_price_forecast(name: str, forecast: Any, expected_horizon: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(forecast, dict):
        return [f"{name} must be an object"]
    if forecast.get("horizon") != expected_horizon:
        errors.append(f"{name}.horizon must be {expected_horizon}")
    if forecast.get("forecast_type") != "high_low_interval":
        errors.append(f"{name}.forecast_type must be high_low_interval")
    interval = forecast.get("price_interval")
    if not isinstance(interval, dict):
        errors.append(f"{name}.price_interval must be an object")
    else:
        for key in REQUIRED_PRICE_INTERVAL:
            if key not in interval:
                errors.append(f"{name}.price_interval missing {key}")
        low = interval.get("low")
        high = interval.get("high")
        if not isinstance(low, (int, float)) or not isinstance(high, (int, float)):
            errors.append(f"{name}.price_interval low/high must be numeric")
        elif low > high:
            errors.append(f"{name}.price_interval low must be <= high")
        if interval.get("contains_reference_price") is not True:
            errors.append(f"{name}.price_interval.contains_reference_price must be true")
    confidence = forecast.get("confidence_score")
    if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
        errors.append(f"{name}.confidence_score must be between 0 and 1")
    if not forecast.get("confidence_bucket"):
        errors.append(f"{name}.confidence_bucket is required")
    if not isinstance(forecast.get("basis"), list) or not forecast.get("basis"):
        errors.append(f"{name}.basis must be a non-empty list")
    if not forecast.get("review_due"):
        errors.append(f"{name}.review_due is required")
    return errors


def validate_trend_forecast(name: str, forecast: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(forecast, dict):
        return [f"{name} must be an object"]
    if forecast.get("horizon") != "one_month":
        errors.append(f"{name}.horizon must be one_month")
    if forecast.get("forecast_type") != "trend_interval":
        errors.append(f"{name}.forecast_type must be trend_interval")
    if not forecast.get("trend"):
        errors.append(f"{name}.trend is required")
    confidence = forecast.get("confidence_score")
    if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
        errors.append(f"{name}.confidence_score must be between 0 and 1")
    interval = forecast.get("interval")
    if not isinstance(interval, dict):
        errors.append(f"{name}.interval must be an object")
    else:
        for key in ["lower", "upper", "unit", "interval_method"]:
            if key not in interval:
                errors.append(f"{name}.interval missing {key}")
        lower = interval.get("lower")
        upper = interval.get("upper")
        if isinstance(lower, (int, float)) and isinstance(upper, (int, float)) and lower > upper:
            errors.append(f"{name}.interval lower must be <= upper")
    if not isinstance(forecast.get("basis"), list) or not forecast.get("basis"):
        errors.append(f"{name}.basis must be a non-empty list")
    if not forecast.get("review_due"):
        errors.append(f"{name}.review_due is required")
    return errors


def validate_stock(stock: Any, index: int) -> list[str]:
    name = f"stocks[{index}]"
    errors: list[str] = []
    if not isinstance(stock, dict):
        return [f"{name} must be an object"]
    for key in missing_keys(stock, REQUIRED_STOCK_FIELDS):
        errors.append(f"{name} missing {key}")
    if not str(stock.get("stock_id", "")).strip():
        errors.append(f"{name}.stock_id is required")
    if not str(stock.get("stock_name", "")).strip():
        errors.append(f"{name}.stock_name is required")
    if not isinstance(stock.get("reference_price"), (int, float)) or stock.get("reference_price") <= 0:
        errors.append(f"{name}.reference_price must be a positive number")
    errors.extend(validate_price_forecast(f"{name}.same_day_forecast", stock.get("same_day_forecast"), "same_day"))
    errors.extend(validate_price_forecast(f"{name}.next_day_forecast", stock.get("next_day_forecast"), "next_day"))
    errors.extend(validate_trend_forecast(f"{name}.one_month_trend_forecast", stock.get("one_month_trend_forecast")))
    if not isinstance(stock.get("signals_used"), list) or not stock.get("signals_used"):
        errors.append(f"{name}.signals_used must be a non-empty list")
    review = stock.get("prediction_review")
    if not isinstance(review, dict):
        errors.append(f"{name}.prediction_review must be an object")
    else:
        for key in missing_keys(review, REQUIRED_REVIEW_FIELDS):
            errors.append(f"{name}.prediction_review missing {key}")
        if review.get("review_status") not in {"pending", "outcome_collected", "evaluation_completed"}:
            errors.append(f"{name}.prediction_review.review_status is not recognized")
        if not isinstance(review.get("actual_outcome"), dict):
            errors.append(f"{name}.prediction_review.actual_outcome must be an object")
        if not isinstance(review.get("evaluation_metrics"), dict):
            errors.append(f"{name}.prediction_review.evaluation_metrics must be an object")
    errors.extend(validate_safety(name, stock.get("safety")))
    return errors


def validate_payload(payload: Any) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return {"ok": False, "errors": ["result root must be an object"]}
    for key in missing_keys(payload, REQUIRED_TOP_LEVEL):
        errors.append(f"missing top-level field: {key}")
    if payload.get("report_window") != "pre_open":
        errors.append("report_window must be pre_open")
    if payload.get("forecast_version") != "daily_report_forecast_v1":
        errors.append("forecast_version must be daily_report_forecast_v1")
    for key in ["runtime_action_performed", "notification_sent", "production_pipeline_run"]:
        if payload.get(key) is not False:
            errors.append(f"{key} must be false")
    stocks = payload.get("stocks")
    if not isinstance(stocks, list) or not stocks:
        errors.append("stocks must be a non-empty list")
        stocks = []
    for index, stock in enumerate(stocks):
        errors.extend(validate_stock(stock, index))
    summary = payload.get("aggregate_summary")
    if not isinstance(summary, dict):
        errors.append("aggregate_summary must be an object")
    else:
        if summary.get("stock_count") != len(stocks):
            errors.append("aggregate_summary.stock_count must equal stocks length")
        if summary.get("forecast_count") != len(stocks) * 3:
            errors.append("aggregate_summary.forecast_count must equal stocks length * 3")
        avg = summary.get("average_confidence_score")
        if not isinstance(avg, (int, float)) or not 0 <= avg <= 1:
            errors.append("aggregate_summary.average_confidence_score must be between 0 and 1")
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
        "stock_count": len(stocks),
        "forecast_count": summary.get("forecast_count") if isinstance(summary, dict) else None,
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
    parser = argparse.ArgumentParser(description="Validate Daily Report Forecast V1 result JSON.")
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
