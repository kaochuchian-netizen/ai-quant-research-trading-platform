#!/usr/bin/env python3
"""Summarize prediction review research samples without side effects."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
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

    linked_ids = {
        "forecast_id_match": forecast.get("forecast_id") == outcome.get("forecast_id"),
        "review_id_match": forecast.get("review_id") == outcome.get("review_id"),
        "stock_id_match": forecast.get("stock_id") == outcome.get("stock_id"),
        "record_id_match": any(
            isinstance(item, dict) and item.get("record_id") == forecast.get("record_id") for item in records
        )
        and any(
            isinstance(item, dict) and item.get("record_id") == outcome.get("record_id") for item in records
        ),
    }

    top_level_records = [
        {
            "record_type": "forecast_to_review_record",
            "path": str(FORECAST_PATH.relative_to(ROOT)),
            "record_id": forecast.get("record_id"),
            "lifecycle_status": forecast.get("lifecycle_status"),
            "data_status": forecast.get("data_status"),
            "source_tier": forecast.get("source_tier"),
        },
        {
            "record_type": "actual_outcome_backfill",
            "path": str(OUTCOME_PATH.relative_to(ROOT)),
            "record_id": outcome.get("record_id"),
            "lifecycle_status": outcome.get("lifecycle_status"),
            "data_status": outcome.get("data_status"),
            "source_tier": outcome.get("source_tier"),
        },
        {
            "record_type": "prediction_review_storage_index",
            "path": str(INDEX_PATH.relative_to(ROOT)),
            "record_id": index.get("index_id"),
            "lifecycle_status": "index_only",
            "data_status": "research_only",
            "source_tier": "metadata_index",
        },
    ]

    summary = {
        "sample_dir": str(SAMPLE_DIR.relative_to(ROOT)),
        "top_level_record_count": len(top_level_records),
        "loaded_record_count": len(top_level_records),
        "lifecycle_counts": dict(lifecycle_counts),
        "data_status_counts": dict(data_status_counts),
        "backfill_status_counts": dict(backfill_status_counts),
        "storage_policy_mode": storage_policy.get("mode"),
        "storage_policy_queryability": storage_policy.get("queryability"),
        "forecast": {
            "forecast_id": forecast.get("forecast_id"),
            "review_id": forecast.get("review_id"),
            "stock_id": forecast.get("stock_id"),
            "stock_name": forecast.get("stock_name"),
            "forecast_window": forecast.get("forecast_window"),
            "forecast_type": forecast_payload.get("forecast_type"),
            "forecast_target": forecast_payload.get("forecast_target"),
            "lifecycle_status": forecast.get("lifecycle_status"),
            "data_status": forecast.get("data_status"),
        },
        "outcome": {
            "record_id": outcome.get("record_id"),
            "backfill_status": outcome.get("backfill_status"),
            "lifecycle_status": outcome.get("lifecycle_status"),
            "data_status": outcome.get("data_status"),
            "actual_direction": actual_outcome.get("actual_direction"),
            "actual_close": actual_outcome.get("actual_close"),
            "pending_example_status": pending_example.get("backfill_status"),
        },
        "linkage": linked_ids,
        "records": top_level_records,
        "index_record_ids": [item.get("record_id") for item in records if isinstance(item, dict)],
        "notes": [
            "Research-only sample loader summary.",
            "No production database, notification, scheduler, or trading side effects.",
        ],
    }
    return summary, []


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize prediction review research samples.")
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
        "summary": summary,
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
