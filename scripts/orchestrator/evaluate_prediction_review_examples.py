#!/usr/bin/env python3
"""Evaluate forecast and prediction review examples without side effects."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


DEFAULT_FORECAST_PATH = "orchestrator/templates/schemas/forecast.example.json"
DEFAULT_REVIEW_PATH = "orchestrator/templates/schemas/prediction_review.example.json"


def load_object(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be object: {path}")
    return data


def confidence_bucket(confidence: float) -> str:
    if confidence >= 0.8:
        return "0.80-1.00"
    if confidence >= 0.7:
        return "0.70-0.79"
    if confidence >= 0.6:
        return "0.60-0.69"
    if confidence >= 0.4:
        return "0.40-0.59"
    return "0.00-0.39"


def validate_required(data: dict[str, Any], fields: list[str], label: str) -> list[str]:
    return [f"{label} missing field: {field}" for field in fields if field not in data]


def evaluate(forecast: dict[str, Any], review: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    reasons: list[str] = []
    reasons.extend(
        validate_required(
            forecast,
            [
                "forecast_id",
                "forecast_direction",
                "predicted_range",
                "evaluation_status",
                "evaluation_window",
                "confidence",
                "model_version",
                "prompt_version",
            ],
            "forecast",
        )
    )
    reasons.extend(
        validate_required(
            review,
            [
                "forecast_id",
                "evaluation_status",
                "evaluation_window",
                "expected_outcome",
                "actual_outcome",
                "error_metrics",
                "model_version",
                "prompt_version",
            ],
            "prediction_review",
        )
    )
    if reasons:
        return {}, reasons

    if forecast["forecast_id"] != review["forecast_id"]:
        reasons.append("forecast_id mismatch")

    predicted_range = forecast.get("predicted_range")
    if not isinstance(predicted_range, dict):
        reasons.append("forecast.predicted_range must be an object")
        predicted_range = {}
    actual_outcome = review.get("actual_outcome")
    if not isinstance(actual_outcome, dict):
        reasons.append("prediction_review.actual_outcome must be an object")
        actual_outcome = {}

    low = predicted_range.get("low")
    high = predicted_range.get("high")
    actual_low = actual_outcome.get("actual_low")
    actual_high = actual_outcome.get("actual_high")
    actual_close = actual_outcome.get("actual_close")
    actual_direction = actual_outcome.get("actual_direction")
    numeric_values = [low, high, actual_low, actual_high, actual_close]
    if not all(isinstance(value, (int, float)) for value in numeric_values):
        reasons.append("forecast/review numeric range fields must all be numbers")
    if isinstance(low, (int, float)) and isinstance(high, (int, float)) and low > high:
        reasons.append("forecast.predicted_range.low must be <= high")
    if reasons:
        return {}, reasons

    assert isinstance(low, (int, float))
    assert isinstance(high, (int, float))
    assert isinstance(actual_low, (int, float))
    assert isinstance(actual_high, (int, float))
    assert isinstance(actual_close, (int, float))

    direction_match = forecast.get("forecast_direction") == actual_direction
    interval_hit = actual_low >= low and actual_high <= high
    absolute_error = 0.0 if interval_hit else min(abs(actual_low - low), abs(actual_high - high))
    high_forecast_error = actual_high - high
    low_forecast_error = actual_low - low
    confidence = forecast.get("confidence")
    if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
        reasons.append("forecast.confidence must be a number between 0 and 1")
        return {}, reasons

    result = {
        "forecast_id": forecast["forecast_id"],
        "evaluation_status": review["evaluation_status"],
        "evaluation_window": review["evaluation_window"],
        "metrics": {
            "direction_match": direction_match,
            "interval_hit": interval_hit,
            "absolute_error": absolute_error,
            "high_forecast_error": high_forecast_error,
            "low_forecast_error": low_forecast_error,
            "confidence_bucket": confidence_bucket(float(confidence)),
        },
        "metadata": {
            "model_version": forecast["model_version"],
            "prompt_version": forecast["prompt_version"],
            "review_model_version": review["model_version"],
            "review_prompt_version": review["prompt_version"],
        },
    }
    return result, []


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate forecast/review example JSON files.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--forecast-path", default=DEFAULT_FORECAST_PATH)
    parser.add_argument("--review-path", default=DEFAULT_REVIEW_PATH)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def resolve_path(repo_root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else repo_root / path


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    forecast_path = resolve_path(repo_root, args.forecast_path)
    review_path = resolve_path(repo_root, args.review_path)
    reasons: list[str] = []
    result: dict[str, Any] | None = None

    try:
        forecast = load_object(forecast_path)
        review = load_object(review_path)
        result, reasons = evaluate(forecast, review)
    except Exception as exc:
        reasons = [str(exc)]

    output = {
        "ok": True,
        "passed": not reasons,
        "forecast_path": str(forecast_path),
        "review_path": str(review_path),
        "evaluation": result,
        "reasons": reasons,
        "side_effects": {
            "files_modified": False,
            "runtime_queue_modified": False,
            "database_modified": False,
            "production_data_modified": False,
            "external_api_called": False,
            "notification_sent": False,
            "trading_execution_run": False,
            "production_pipeline_run": False,
            "scheduler_modified": False,
            "secrets_read_or_modified": False,
        },
    }
    json.dump(output, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    return 0 if output["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
