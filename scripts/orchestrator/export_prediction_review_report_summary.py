#!/usr/bin/env python3
"""Export a research-only prediction review report summary without side effects."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SAMPLE_DIR = ROOT / "orchestrator" / "templates" / "research_samples" / "prediction_review_storage"

FORECAST_PATH = SAMPLE_DIR / "forecast_to_review_record.example.json"
OUTCOME_PATH = SAMPLE_DIR / "actual_outcome_backfill.example.json"
INDEX_PATH = SAMPLE_DIR / "prediction_review_storage_index.example.json"

REQUIRED_FORECAST_FIELDS = [
    "schema_version",
    "record_version",
    "record_id",
    "forecast_id",
    "review_id",
    "signal_id",
    "run_date",
    "stock_id",
    "stock_name",
    "entity_type",
    "forecast_window",
    "forecast_payload",
    "lifecycle_status",
    "data_status",
    "created_at",
    "source_type",
    "source_tier",
    "pending_policy",
    "missing_data_policy",
    "notes",
]

REQUIRED_OUTCOME_FIELDS = [
    "schema_version",
    "record_version",
    "record_id",
    "review_id",
    "forecast_id",
    "stock_id",
    "stock_name",
    "outcome_window",
    "backfill_status",
    "lifecycle_status",
    "data_status",
    "updated_at",
    "backfill_timestamp",
    "actual_outcome",
    "pending_example",
    "backfill_policy",
    "missing_data_policy",
    "source_type",
    "source_tier",
    "notes",
]

REQUIRED_INDEX_FIELDS = [
    "schema_version",
    "record_version",
    "index_id",
    "generated_at",
    "storage_policy",
    "non_goals",
    "safety_boundaries",
    "records",
    "notes",
]


def load_object(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be object: {path}")
    return data


def ensure_required(data: dict[str, Any], fields: list[str], label: str) -> list[str]:
    return [f"{label} missing field: {field}" for field in fields if field not in data]


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


def date_only(value: str) -> str:
    return value.split("T", 1)[0] if "T" in value else value


def load_bundle() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[str]]:
    reasons: list[str] = []
    try:
        forecast = load_object(FORECAST_PATH)
    except Exception as exc:  # noqa: BLE001
        reasons.append(f"forecast sample load failed: {exc}")
        forecast = {}
    try:
        outcome = load_object(OUTCOME_PATH)
    except Exception as exc:  # noqa: BLE001
        reasons.append(f"actual outcome sample load failed: {exc}")
        outcome = {}
    try:
        index = load_object(INDEX_PATH)
    except Exception as exc:  # noqa: BLE001
        reasons.append(f"storage index sample load failed: {exc}")
        index = {}
    return forecast, outcome, index, reasons


def summarize(forecast: dict[str, Any], outcome: dict[str, Any], index: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    reasons: list[str] = []
    reasons.extend(ensure_required(forecast, REQUIRED_FORECAST_FIELDS, "forecast_to_review_record"))
    reasons.extend(ensure_required(outcome, REQUIRED_OUTCOME_FIELDS, "actual_outcome_backfill"))
    reasons.extend(ensure_required(index, REQUIRED_INDEX_FIELDS, "prediction_review_storage_index"))
    if reasons:
        return {}, reasons

    forecast_payload = forecast.get("forecast_payload")
    if not isinstance(forecast_payload, dict):
        reasons.append("forecast.forecast_payload must be an object")
        forecast_payload = {}

    forecast_window = forecast.get("forecast_window")
    if not isinstance(forecast_window, dict):
        reasons.append("forecast.forecast_window must be an object")
        forecast_window = {}

    outcome_window = outcome.get("outcome_window")
    if not isinstance(outcome_window, dict):
        reasons.append("outcome.outcome_window must be an object")
        outcome_window = {}

    actual_outcome = outcome.get("actual_outcome")
    if not isinstance(actual_outcome, dict):
        reasons.append("outcome.actual_outcome must be an object")
        actual_outcome = {}

    pending_example = outcome.get("pending_example")
    if not isinstance(pending_example, dict):
        reasons.append("outcome.pending_example must be an object")
        pending_example = {}

    storage_policy = index.get("storage_policy")
    if not isinstance(storage_policy, dict):
        reasons.append("index.storage_policy must be an object")
        storage_policy = {}

    records = index.get("records")
    if not isinstance(records, list):
        reasons.append("index.records must be a list")
        records = []

    if reasons:
        return {}, reasons

    forecast_range = forecast_payload.get("predicted_range")
    if not isinstance(forecast_range, dict):
        reasons.append("forecast.forecast_payload.predicted_range must be an object")
        forecast_range = {}

    forecast_confidence = float(forecast_payload.get("confidence", 0.0))
    predicted_low = float(forecast_range.get("low", 0.0))
    predicted_high = float(forecast_range.get("high", 0.0))
    actual_low = float(actual_outcome.get("actual_low", 0.0))
    actual_high = float(actual_outcome.get("actual_high", 0.0))
    actual_close = float(actual_outcome.get("actual_close", 0.0))
    predicted_midpoint = (predicted_low + predicted_high) / 2 if predicted_high or predicted_low else 0.0

    predicted_direction = str(forecast_payload.get("predicted_direction", ""))
    actual_direction = str(actual_outcome.get("actual_direction", ""))
    direction_match = predicted_direction == actual_direction
    interval_hit = actual_low >= predicted_low and actual_high <= predicted_high

    lifecycle_counts = Counter(
        [
            str(forecast.get("lifecycle_status")),
            str(outcome.get("lifecycle_status")),
            str(pending_example.get("lifecycle_status")),
        ]
    )
    data_status_counts = Counter(
        [
            str(forecast.get("data_status")),
            str(outcome.get("data_status")),
            str(pending_example.get("data_status")),
        ]
    )
    backfill_status_counts = Counter(
        [
            str(outcome.get("backfill_status")),
            str(pending_example.get("backfill_status")),
        ]
    )
    source_tier_summary = Counter(
        [
            str(forecast.get("source_tier")),
            str(outcome.get("source_tier")),
            "metadata_index",
        ]
    )

    completed_review_id = str(forecast.get("review_id"))
    pending_review_id = f"{forecast.get('review_id')}-pending-example"
    completed_metric_count = 1
    pending_metric_count = 1

    summary = {
        "schema_version": int(forecast.get("schema_version", 1)),
        "report_type": "forecast_review",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "source_type": "research_samples",
            "source_scope": "research_only",
            "source_bundle": str(SAMPLE_DIR.relative_to(ROOT)),
            "source_files": [
                str(FORECAST_PATH.relative_to(ROOT)),
                str(OUTCOME_PATH.relative_to(ROOT)),
                str(INDEX_PATH.relative_to(ROOT)),
            ],
            "source_record_ids": [
                str(forecast.get("record_id")),
                str(outcome.get("record_id")),
                str(index.get("index_id")),
            ],
            "source_tier_summary": dict(source_tier_summary),
        },
        "safety_mode": "research_only",
        "record_summary": {
            "sample_file_count": 3,
            "logical_record_count": 3,
            "forecast_review_record_count": 1,
            "actual_outcome_record_count": 1,
            "storage_index_record_count": 1,
            "completed_outcome_count": 1,
            "pending_outcome_count": 1,
            "record_ids": [
                str(forecast.get("record_id")),
                str(outcome.get("record_id")),
                str(index.get("index_id")),
            ],
            "review_ids": [completed_review_id, pending_review_id],
        },
        "forecast_quality_summary": {
            "forecast_id": forecast.get("forecast_id"),
            "review_id": completed_review_id,
            "forecast_type": forecast_payload.get("forecast_type"),
            "forecast_target": forecast_payload.get("forecast_target"),
            "forecast_window": forecast_window,
            "forecast_confidence": forecast_confidence,
            "forecast_confidence_bucket": confidence_bucket(forecast_confidence),
            "evaluation_status": forecast_payload.get("evaluation_status"),
            "completed_review_count": completed_metric_count,
            "pending_review_count": pending_metric_count,
            "review_completion_rate": completed_metric_count / (completed_metric_count + pending_metric_count),
        },
        "pending_outcome_summary": {
            "pending_review_id": pending_review_id,
            "pending_count": 1,
            "pending_state": pending_example.get("lifecycle_status"),
            "pending_data_status": pending_example.get("data_status"),
            "pending_backfill_status": pending_example.get("backfill_status"),
            "missing_data_policy": forecast.get("missing_data_policy"),
            "pending_policy": forecast.get("pending_policy"),
            "backfill_policy": outcome.get("backfill_policy"),
        },
        "metric_summary": {
            "completed_metric_count": completed_metric_count,
            "direction_match_count": int(direction_match),
            "direction_match_rate": 1.0 if direction_match else 0.0,
            "interval_hit_count": int(interval_hit),
            "interval_hit_rate": 1.0 if interval_hit else 0.0,
            "average_absolute_error": abs(actual_close - predicted_midpoint),
            "high_forecast_error": actual_high - predicted_high,
            "low_forecast_error": actual_low - predicted_low,
            "actual_direction": actual_direction,
            "predicted_direction": predicted_direction,
        },
        "confidence_summary": {
            "forecast_confidence": forecast_confidence,
            "forecast_confidence_bucket": confidence_bucket(forecast_confidence),
            "bucket_counts": {
                confidence_bucket(forecast_confidence): completed_metric_count,
                "pending_unscored": pending_metric_count,
            },
            "calibration_notes": [
                "Research-only example uses one completed outcome and one pending outcome.",
                "Confidence should be treated as an illustrative research metric, not a trading signal.",
            ],
        },
        "stock_summary": {
            "stock_count": 1,
            "stocks": [
                {
                    "stock_id": forecast.get("stock_id"),
                    "stock_name": forecast.get("stock_name"),
                    "entity_type": forecast.get("entity_type"),
                    "source_tier": forecast.get("source_tier"),
                }
            ],
        },
        "window_summary": {
            "run_date": forecast.get("run_date"),
            "forecast_window": forecast_window,
            "outcome_window": outcome_window,
            "forecast_horizon": forecast_window.get("horizon"),
            "window_type": forecast_window.get("window_type"),
            "backfill_timestamp": outcome.get("backfill_timestamp"),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "data_quality_summary": {
            "data_quality_status": "research_only",
            "data_status_counts": dict(data_status_counts),
            "lifecycle_counts": dict(lifecycle_counts),
            "backfill_status_counts": dict(backfill_status_counts),
            "missing_data_policy": forecast.get("missing_data_policy"),
            "pending_policy": forecast.get("pending_policy"),
            "backfill_policy": outcome.get("backfill_policy"),
            "quality_notes": [
                "The bundle is intentionally research-only and read-only.",
                "Pending outcomes are preserved instead of being inferred.",
                "Analyst target prices and broker ratings remain metadata only.",
            ],
        },
        "dashboard_cards": [
            {
                "card_id": "total_records",
                "title": "Total Records",
                "value": 3,
                "unit": "records",
                "status": "research_only",
                "description": "Total research-only sample files represented in the export bundle.",
                "drilldown_key": "record_summary.sample_file_count",
            },
            {
                "card_id": "completed_outcomes",
                "title": "Completed Outcomes",
                "value": 1,
                "unit": "records",
                "status": "completed",
                "description": "Completed actual outcome example count.",
                "drilldown_key": "record_summary.completed_outcome_count",
            },
            {
                "card_id": "pending_outcomes",
                "title": "Pending Outcomes",
                "value": 1,
                "unit": "records",
                "status": "pending",
                "description": "Pending actual outcome example count preserved for backfill planning.",
                "drilldown_key": "pending_outcome_summary.pending_count",
            },
            {
                "card_id": "direction_match_rate",
                "title": "Direction Match Rate",
                "value": 1.0 if direction_match else 0.0,
                "unit": "rate",
                "status": "completed" if direction_match else "mixed",
                "description": "Share of completed examples where forecast direction matched actual direction.",
                "drilldown_key": "metric_summary.direction_match_rate",
            },
            {
                "card_id": "interval_hit_rate",
                "title": "Interval Hit Rate",
                "value": 1.0 if interval_hit else 0.0,
                "unit": "rate",
                "status": "completed" if interval_hit else "mixed",
                "description": "Share of completed examples where the actual range stayed within the forecast interval.",
                "drilldown_key": "metric_summary.interval_hit_rate",
            },
            {
                "card_id": "average_absolute_error",
                "title": "Average Absolute Error",
                "value": abs(actual_close - predicted_midpoint),
                "unit": "TWD",
                "status": "completed",
                "description": "Average absolute error derived from the completed forecast example.",
                "drilldown_key": "metric_summary.average_absolute_error",
            },
            {
                "card_id": "data_quality_status",
                "title": "Data Quality Status",
                "value": "research_only",
                "unit": "mode",
                "status": "research_only",
                "description": "Research-only bundle status and read-only safety boundary.",
                "drilldown_key": "data_quality_summary.data_quality_status",
            },
            {
                "card_id": "safety_mode",
                "title": "Safety Mode",
                "value": "research_only",
                "unit": "mode",
                "status": "research_only",
                "description": "Confirms the export is read-only and does not touch production systems.",
                "drilldown_key": "safety_mode",
            },
        ],
        "email_report_sections": [
            {
                "section_id": "executive_summary",
                "title": "Executive Summary",
                "priority": 1,
                "summary": "Research-only prediction review summary for the AI-DEV-018 storage bundle.",
                "bullets": [
                    "One completed forecast review example is available.",
                    "One pending outcome example is preserved for backfill planning.",
                    "The bundle remains read-only and does not connect to production delivery.",
                ],
                "metrics": {
                    "completed_outcomes": 1,
                    "pending_outcomes": 1,
                },
            },
            {
                "section_id": "forecast_quality",
                "title": "Forecast Quality",
                "priority": 2,
                "summary": "The completed example shows a matched direction and interval hit.",
                "bullets": [
                    f"Forecast type: {forecast_payload.get('forecast_type')}",
                    f"Forecast target: {forecast_payload.get('forecast_target')}",
                ],
                "metrics": {
                    "forecast_confidence_bucket": confidence_bucket(forecast_confidence),
                    "direction_match_rate": 1.0 if direction_match else 0.0,
                    "interval_hit_rate": 1.0 if interval_hit else 0.0,
                },
            },
            {
                "section_id": "pending_outcomes",
                "title": "Pending Outcomes",
                "priority": 3,
                "summary": "The pending example is preserved explicitly instead of being inferred.",
                "bullets": [
                    f"Pending review id: {pending_review_id}",
                    f"Pending state: {pending_example.get('lifecycle_status')}",
                ],
                "metrics": {
                    "pending_count": 1,
                    "pending_backfill_status": pending_example.get("backfill_status"),
                },
            },
            {
                "section_id": "data_quality",
                "title": "Data Quality",
                "priority": 4,
                "summary": "The bundle is research-only and carries explicit missing-data handling.",
                "bullets": [
                    "No external API, database, or notification call is made.",
                    "Pending outcomes remain pending until backfilled.",
                ],
                "metrics": {
                    "data_quality_status": "research_only",
                    "data_status_completed": data_status_counts.get("completed", 0),
                    "data_status_pending": data_status_counts.get("pending", 0),
                },
            },
            {
                "section_id": "methodology_notes",
                "title": "Methodology Notes",
                "priority": 5,
                "summary": "Metrics are derived from the research-only storage examples.",
                "bullets": [
                    "Missing outcomes remain pending instead of being fabricated.",
                    "Analyst target prices and broker ratings remain metadata only.",
                ],
                "metrics": {
                    "completed_metric_count": completed_metric_count,
                    "pending_metric_count": pending_metric_count,
                },
            },
            {
                "section_id": "limitations",
                "title": "Limitations",
                "priority": 6,
                "summary": "This preview is not a trading recommendation or production artifact.",
                "bullets": [
                    "Read-only research artifact.",
                    "Does not write files, databases, or production data.",
                    "Does not send LINE, email, or any notification.",
                    "Does not authorize trading or order placement.",
                ],
                "metrics": {
                    "safety_mode": "research_only",
                },
            },
        ],
        "next_actions": [
            "Use the summary contract as a reference for future dashboard preview work.",
            "Keep the storage and review layers separate until a controlled migration is approved.",
            "Extend with future sample sets before considering any production integration.",
        ],
        "limitations": [
            "Read-only research artifact.",
            "Does not write files, databases, or production data.",
            "Does not send LINE, email, or any notification.",
            "Does not authorize trading or order placement.",
            "Analyst target prices and broker ratings remain low-priority metadata only.",
        ],
        "validation_summary": {
            "checked_files": [
                str(FORECAST_PATH.relative_to(ROOT)),
                str(OUTCOME_PATH.relative_to(ROOT)),
                str(INDEX_PATH.relative_to(ROOT)),
            ],
            "lifecycle_counts": dict(lifecycle_counts),
            "data_status_counts": dict(data_status_counts),
            "backfill_status_counts": dict(backfill_status_counts),
            "source_tier_summary": dict(source_tier_summary),
            "read_only": True,
        },
    }

    return summary, []


def main() -> int:
    parser = argparse.ArgumentParser(description="Export a prediction review report summary from research samples.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    if repo_root != ROOT:
        # Keep the prototype constrained to the repository checkout.
        pass

    forecast, outcome, index, load_reasons = load_bundle()
    summary, summary_reasons = summarize(forecast, outcome, index)
    reasons = load_reasons + summary_reasons

    output = {
        "ok": True,
        "passed": not reasons,
        "sample_dir": str(SAMPLE_DIR.relative_to(ROOT)),
        "files": {
            "forecast_to_review_record": str(FORECAST_PATH.relative_to(ROOT)),
            "actual_outcome_backfill": str(OUTCOME_PATH.relative_to(ROOT)),
            "prediction_review_storage_index": str(INDEX_PATH.relative_to(ROOT)),
        },
        **summary,
        "report_summary": summary,
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

    print(json.dumps(output, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0 if output["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
