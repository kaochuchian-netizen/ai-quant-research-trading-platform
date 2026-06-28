#!/usr/bin/env python3
"""Generate a fixture-only prediction quality review result.

The helper consumes an AI-DEV-072-compatible evaluation result and emits a
sanitized quality review artifact. It does not call external services, modify
forecast runtime weights, send notifications, trade, or write production data.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_INPUT = Path("templates/prediction_quality_review_input.example.json")
SCHEMA_VERSION = "prediction_quality_review_daily_improvement_v1"
HORIZONS = ["same_day", "next_day", "one_month"]
BUCKETS = ["0-20", "21-40", "41-60", "61-80", "81-100", "unknown"]
SIDE_EFFECTS = {
    "read_secrets": False,
    "called_external_ai_runtime": False,
    "called_market_data_runtime": False,
    "sent_notification": False,
    "placed_trade_order": False,
    "modified_production_db": False,
    "modified_cron_systemd_timer": False,
    "modified_n8n": False,
    "mutated_github_issue": False,
    "modified_forecast_runtime_weights": False,
}


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"input file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"input file is not valid JSON: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit("input JSON root must be an object")
    return data


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def mean(values: list[float]) -> float | None:
    return round(statistics.mean(values), 6) if values else None


def median(values: list[float]) -> float | None:
    return round(statistics.median(values), 6) if values else None


def max_value(values: list[float]) -> float | None:
    return round(max(values), 6) if values else None


def rate(records: list[dict[str, Any]], metric: str) -> float | None:
    values = [record.get("evaluation_metrics", {}).get(metric) for record in records]
    booleans = [value for value in values if isinstance(value, bool)]
    if not booleans:
        return None
    return round(sum(1 for value in booleans if value) / len(booleans), 6)


def evaluated_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [record for record in records if record.get("status") == "evaluated"]


def pending_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [record for record in records if record.get("status") == "pending_actual_outcome"]


def quality_grade(interval_hit_rate: float | None, mean_error: float | None, evaluated_count: int, minimum: int) -> str:
    if evaluated_count < minimum:
        return "Insufficient Data"
    interval = interval_hit_rate if interval_hit_rate is not None else 0.0
    error = mean_error if mean_error is not None else 1.0
    if interval >= 0.75 and error <= 0.03:
        return "A"
    if interval >= 0.60 and error <= 0.05:
        return "B"
    if interval >= 0.45:
        return "C"
    return "D"


def quality_status(grade: str, pending_rate: float) -> str:
    if grade == "Insufficient Data":
        return "insufficient_data"
    if pending_rate >= 0.40:
        return "coverage_limited"
    if grade in {"A", "B"}:
        return "acceptable"
    return "needs_review"


def horizon_review(horizon: str, records: list[dict[str, Any]], minimum: int) -> dict[str, Any]:
    horizon_records = [record for record in records if record.get("horizon") == horizon]
    evaluated = evaluated_records(horizon_records)
    pending = pending_records(horizon_records)
    abs_errors = [
        metric
        for record in evaluated
        if isinstance((metric := record.get("evaluation_metrics", {}).get("absolute_error_pct")), (int, float))
    ]
    interval_hit_rate = rate(evaluated, "interval_hit")
    mean_error = mean(abs_errors)
    pending_rate = round(len(pending) / len(horizon_records), 6) if horizon_records else None
    grade = quality_grade(interval_hit_rate, mean_error, len(evaluated), minimum)
    return {
        "horizon": horizon,
        "total_records": len(horizon_records),
        "evaluated_records": len(evaluated),
        "pending_records": len(pending),
        "interval_hit_rate": interval_hit_rate,
        "high_interval_hit_rate": rate(evaluated, "high_interval_hit"),
        "low_interval_hit_rate": rate(evaluated, "low_interval_hit"),
        "direction_hit_rate": rate(evaluated, "direction_hit"),
        "mean_absolute_error_pct": mean_error,
        "median_absolute_error_pct": median(abs_errors),
        "max_absolute_error_pct": max_value(abs_errors),
        "pending_rate": pending_rate,
        "quality_grade": grade,
        "quality_status": quality_status(grade, pending_rate or 0.0),
    }


def calibration_status(bucket: str, evaluated_count: int, hit_rate: float | None, minimum: int) -> str:
    if evaluated_count < minimum or hit_rate is None:
        return "insufficient_data"
    if bucket in {"61-80", "81-100"} and hit_rate < 0.60:
        return "overconfident"
    if bucket in {"0-20", "21-40"} and hit_rate >= 0.60:
        return "underconfident"
    return "well_calibrated"


def confidence_calibration(records: list[dict[str, Any]], minimum: int) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for bucket in BUCKETS:
        bucket_records = [
            record
            for record in records
            if record.get("evaluation_metrics", {}).get("confidence_bucket") == bucket
        ]
        evaluated = evaluated_records(bucket_records)
        abs_errors = [
            metric
            for record in evaluated
            if isinstance((metric := record.get("evaluation_metrics", {}).get("absolute_error_pct")), (int, float))
        ]
        hit_rate = rate(evaluated, "interval_hit")
        result.append({
            "bucket": bucket,
            "record_count": len(bucket_records),
            "evaluated_count": len(evaluated),
            "interval_hit_rate": hit_rate,
            "direction_hit_rate": rate(evaluated, "direction_hit"),
            "mean_absolute_error_pct": mean(abs_errors),
            "calibration_status": calibration_status(bucket, len(evaluated), hit_rate, minimum),
        })
    return result


def pattern_record(
    pattern: str,
    records: list[dict[str, Any]],
    recommendation: str,
) -> dict[str, Any] | None:
    if not records:
        return None
    horizons = sorted({str(record.get("horizon")) for record in records})
    count = len(records)
    severity = "high" if count >= 3 else "medium" if count == 2 else "low"
    return {
        "pattern": pattern,
        "count": count,
        "affected_horizons": horizons,
        "severity": severity,
        "example_record_ids": [str(record.get("record_id")) for record in records[:3]],
        "recommendation": recommendation,
    }


def error_patterns(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {
        "high_forecast_too_low": [],
        "high_forecast_too_high": [],
        "low_forecast_too_low": [],
        "low_forecast_too_high": [],
        "range_too_narrow": [],
        "range_too_wide": [],
        "trend_mismatch": [],
        "missing_actuals": [],
        "confidence_mismatch": [],
    }
    for record in records:
        metrics = record.get("evaluation_metrics", {})
        forecast_interval = record.get("forecast", {}).get("price_interval", {})
        forecast_low = number(forecast_interval.get("low"))
        forecast_high = number(forecast_interval.get("high"))
        actual_high = number(record.get("actual_high") or record.get("actual_window_high"))
        actual_low = number(record.get("actual_low") or record.get("actual_window_low"))
        range_width = number(metrics.get("range_width_pct"))
        if record.get("status") == "pending_actual_outcome":
            groups["missing_actuals"].append(record)
            continue
        if forecast_high is not None and actual_high is not None:
            if actual_high > forecast_high:
                groups["high_forecast_too_low"].append(record)
            elif actual_high < forecast_high * 0.97:
                groups["high_forecast_too_high"].append(record)
        if forecast_low is not None and actual_low is not None:
            if actual_low < forecast_low:
                groups["low_forecast_too_high"].append(record)
            elif actual_low > forecast_low * 1.03:
                groups["low_forecast_too_low"].append(record)
        if range_width is not None:
            if range_width < 0.03 and metrics.get("interval_hit") is False:
                groups["range_too_narrow"].append(record)
            elif range_width > 0.08:
                groups["range_too_wide"].append(record)
        if metrics.get("direction_hit") is False:
            groups["trend_mismatch"].append(record)
        bucket = metrics.get("confidence_bucket")
        if bucket in {"61-80", "81-100"} and metrics.get("interval_hit") is False:
            groups["confidence_mismatch"].append(record)
        if bucket in {"0-20", "21-40"} and metrics.get("interval_hit") is True:
            groups["confidence_mismatch"].append(record)
    recommendations = {
        "high_forecast_too_low": "Review upside interval cap assumptions for affected horizons.",
        "high_forecast_too_high": "Review whether upside intervals are too generous for affected horizons.",
        "low_forecast_too_low": "Review whether downside intervals are too conservative.",
        "low_forecast_too_high": "Widen or recalibrate downside interval assumptions.",
        "range_too_narrow": "Increase interval width when misses cluster near both bounds.",
        "range_too_wide": "Separate wide exploratory ranges from quality-scored interval forecasts.",
        "trend_mismatch": "Review signal weights for directional one-month forecasts.",
        "missing_actuals": "Increase fixture or future actuals coverage before strong quality conclusions.",
        "confidence_mismatch": "Review confidence assignment against realized hit rates.",
    }
    return [
        pattern
        for key in groups
        if (pattern := pattern_record(key, groups[key], recommendations[key])) is not None
    ]


def recommendation(
    recommendation_id: str,
    priority: str,
    target_horizon: str,
    reason: str,
    expected_effect: str,
) -> dict[str, Any]:
    return {
        "recommendation_id": recommendation_id,
        "priority": priority,
        "target_horizon": target_horizon,
        "reason": reason,
        "expected_effect": expected_effect,
        "safe_to_apply_automatically": False,
        "requires_human_review": True,
    }


def daily_recommendations(horizon_reviews: list[dict[str, Any]], patterns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    pending_heavy = [review for review in horizon_reviews if (review.get("pending_rate") or 0) > 0]
    if pending_heavy:
        result.append(recommendation(
            "increase_actuals_coverage_before_quality_conclusion",
            "high",
            "all",
            "Some records remain pending, so quality conclusions are coverage-limited.",
            "Improves evaluated sample size and reduces misleading quality grades.",
        ))
    if any(pattern.get("pattern") == "range_too_narrow" for pattern in patterns):
        result.append(recommendation(
            "increase_interval_width_for_same_day",
            "medium",
            "same_day",
            "Interval misses suggest range width may be too narrow.",
            "Improves interval coverage while preserving review-only behavior.",
        ))
    if any(pattern.get("pattern") == "range_too_wide" for pattern in patterns):
        result.append(recommendation(
            "separate_one_month_trend_from_short_term_interval",
            "medium",
            "one_month",
            "Wide one-month ranges should be reviewed separately from short-term interval quality.",
            "Keeps trend quality interpretation distinct from daily high-low interval scoring.",
        ))
    if any(pattern.get("pattern") == "trend_mismatch" for pattern in patterns):
        result.append(recommendation(
            "review_signal_weights_for_direction_miss",
            "high",
            "one_month",
            "Directional misses indicate signal weighting needs review.",
            "Improves future manual tuning discussion without changing runtime weights.",
        ))
    if not result:
        result.append(recommendation(
            "continue_collecting_evaluated_records",
            "medium",
            "all",
            "Current fixture sample is too small for a strong conclusion.",
            "Builds enough history for calibration and dashboard reporting.",
        ))
    return result


def tuning_hints(horizon_reviews: list[dict[str, Any]], calibrations: list[dict[str, Any]], patterns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    hints: list[dict[str, Any]] = []
    for review in horizon_reviews:
        if review.get("quality_grade") == "Insufficient Data":
            hints.append({
                "hint_id": f"collect_more_{review['horizon']}_records",
                "target_horizon": review["horizon"],
                "hint": "Collect more evaluated records before changing forecast behavior.",
                "rationale": "Evaluated sample is below the configured strong-conclusion threshold.",
                "safe_to_apply_automatically": False,
                "requires_human_review": True,
            })
    for calibration in calibrations:
        if calibration.get("calibration_status") in {"overconfident", "underconfident"}:
            hints.append({
                "hint_id": f"review_confidence_bucket_{calibration['bucket']}",
                "target_horizon": "all",
                "hint": "Review confidence bucket assignment against realized hit rates.",
                "rationale": f"Bucket {calibration['bucket']} is {calibration['calibration_status']}.",
                "safe_to_apply_automatically": False,
                "requires_human_review": True,
            })
    if any(pattern.get("pattern") == "missing_actuals" for pattern in patterns):
        hints.append({
            "hint_id": "prioritize_actual_outcome_coverage",
            "target_horizon": "all",
            "hint": "Prioritize actual outcome coverage before tuning forecast scoring.",
            "rationale": "Missing actuals reduce quality-review reliability.",
            "safe_to_apply_automatically": False,
            "requires_human_review": True,
        })
    return hints


def overall_summary(records: list[dict[str, Any]], horizon_reviews: list[dict[str, Any]], minimum: int) -> dict[str, Any]:
    evaluated = evaluated_records(records)
    pending = pending_records(records)
    abs_errors = [
        metric
        for record in evaluated
        if isinstance((metric := record.get("evaluation_metrics", {}).get("absolute_error_pct")), (int, float))
    ]
    interval_hit_rate = rate(evaluated, "interval_hit")
    mean_error = mean(abs_errors)
    grade = quality_grade(interval_hit_rate, mean_error, len(evaluated), minimum)
    return {
        "total_records": len(records),
        "evaluated_records": len(evaluated),
        "pending_records": len(pending),
        "overall_interval_hit_rate": interval_hit_rate,
        "overall_direction_hit_rate": rate(evaluated, "direction_hit"),
        "overall_mean_absolute_error_pct": mean_error,
        "overall_quality_grade": grade,
        "overall_quality_status": quality_status(grade, round(len(pending) / len(records), 6) if records else 0.0),
        "horizon_count": len(horizon_reviews),
        "minimum_records_for_strong_conclusion": minimum,
    }


def decision(summary: dict[str, Any]) -> str:
    if summary["evaluated_records"] == 0:
        return "no_evaluated_records"
    if summary["overall_quality_grade"] == "Insufficient Data":
        return "quality_review_completed_with_insufficient_data"
    return "quality_review_completed"


def build_result(data: dict[str, Any]) -> dict[str, Any]:
    source = data.get("source_evaluation_result")
    if not isinstance(source, dict):
        source = {}
    records = [record for record in source.get("records", []) if isinstance(record, dict)]
    config = data.get("review_config") if isinstance(data.get("review_config"), dict) else {}
    supported_horizons = config.get("supported_horizons") if isinstance(config.get("supported_horizons"), list) else HORIZONS
    minimum = int(config.get("minimum_records_for_strong_conclusion", 5))
    horizon_reviews = [horizon_review(str(horizon), records, minimum) for horizon in supported_horizons]
    calibrations = confidence_calibration(records, minimum)
    patterns = error_patterns(records)
    recommendations = daily_recommendations(horizon_reviews, patterns)
    hints = tuning_hints(horizon_reviews, calibrations, patterns)
    summary = overall_summary(records, horizon_reviews, minimum)
    result_decision = decision(summary)
    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": data.get("task_id", "AI-DEV-073"),
        "run_id": data.get("run_id", "prediction-quality-review-fixture"),
        "generated_at": data.get("generated_at") or now_iso(),
        "mode": "fixture_dry_run",
        "input_summary": {
            "source_schema_version": source.get("schema_version"),
            "source_run_id": source.get("run_id"),
            "source_decision": source.get("decision"),
            "review_window_days": config.get("review_window_days"),
            "supported_horizons": supported_horizons,
            "source_side_effects": deepcopy(source.get("side_effects", {})),
        },
        "quality_review_summary": summary,
        "horizon_reviews": horizon_reviews,
        "confidence_calibration": calibrations,
        "error_patterns": patterns,
        "daily_improvement_recommendations": recommendations,
        "next_forecast_tuning_hints": hints,
        "side_effects": deepcopy(SIDE_EFFECTS),
        "safety": {
            "fixture_only": True,
            "repo_only": True,
            "advisory_only": True,
            "research_only": True,
            "no_external_market_data": True,
            "no_external_ai_runtime": True,
            "no_notification": True,
            "no_trade": True,
            "no_order": True,
            "no_production_db": True,
            "forecast_runtime_weights_modified": False,
        },
        "ok": result_decision in {
            "quality_review_completed",
            "quality_review_completed_with_insufficient_data",
            "no_evaluated_records",
        },
        "decision": result_decision,
        "next_recommendation": "AI-DEV-074 Dashboard-ready Prediction Review Summary + Report Export V1",
    }


def write_result(result: dict[str, Any], output: Path, pretty: bool) -> str:
    rendered = json.dumps(result, ensure_ascii=False, indent=2 if pretty else None, sort_keys=True)
    if pretty:
        rendered += "\n"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    return rendered


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate fixture-only prediction quality review result.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", required=True)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build_result(load_json(Path(args.input)))
    rendered = write_result(result, Path(args.output), args.pretty)
    sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
