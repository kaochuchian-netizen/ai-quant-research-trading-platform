#!/usr/bin/env python3
"""Read-only validator for prediction review storage research samples.

This script only reads JSON examples under orchestrator/templates/research_samples/
prediction_review_storage and performs structural validation. It does not write
files, call external services, touch databases, send notifications, or run any
production pipeline.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence


ROOT = Path(__file__).resolve().parents[2]
SAMPLE_DIR = ROOT / "orchestrator" / "templates" / "research_samples" / "prediction_review_storage"

FORECAST_FILE = SAMPLE_DIR / "forecast_to_review_record.example.json"
OUTCOME_FILE = SAMPLE_DIR / "actual_outcome_backfill.example.json"
INDEX_FILE = SAMPLE_DIR / "prediction_review_storage_index.example.json"

ALLOWED_LIFECYCLE_STATUSES = {
    "forecast_created",
    "review_record_created",
    "outcome_pending",
    "outcome_backfilled",
    "evaluated",
    "archived",
}

ALLOWED_DATA_STATUSES = {"sample", "research_only", "pending", "completed", "invalid"}
ALLOWED_BACKFILL_STATUSES = {"pending", "completed", "invalid"}


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path.name}: JSON root must be an object")
    return payload


def ensure_fields(payload: Dict[str, Any], required: Sequence[str], *, label: str) -> None:
    missing = [field for field in required if field not in payload]
    if missing:
        raise ValueError(f"{label}: missing required fields: {', '.join(missing)}")


def ensure_status(value: str, allowed: Iterable[str], *, label: str, field_name: str) -> None:
    if value not in allowed:
        allowed_text = ", ".join(sorted(allowed))
        raise ValueError(f"{label}: invalid {field_name}={value!r}; allowed: {allowed_text}")


def validate_forecast_record(payload: Dict[str, Any]) -> None:
    ensure_fields(
        payload,
        [
            "schema_version",
            "record_version",
            "record_id",
            "forecast_id",
            "review_id",
            "signal_id",
            "run_date",
            "stock_id",
            "forecast_window",
            "forecast_payload",
            "lifecycle_status",
            "data_status",
            "created_at",
            "source_type",
            "source_tier",
            "missing_data_policy",
            "notes",
        ],
        label=FORECAST_FILE.name,
    )
    ensure_status(payload["lifecycle_status"], ALLOWED_LIFECYCLE_STATUSES, label=FORECAST_FILE.name, field_name="lifecycle_status")
    ensure_status(payload["data_status"], ALLOWED_DATA_STATUSES, label=FORECAST_FILE.name, field_name="data_status")
    if payload["lifecycle_status"] != "review_record_created":
        raise ValueError(f"{FORECAST_FILE.name}: lifecycle_status should be review_record_created")
    if payload["data_status"] != "research_only":
        raise ValueError(f"{FORECAST_FILE.name}: data_status should be research_only")

    forecast_payload = payload["forecast_payload"]
    if not isinstance(forecast_payload, dict):
        raise ValueError(f"{FORECAST_FILE.name}: forecast_payload must be an object")
    ensure_fields(
        forecast_payload,
        [
            "forecast_type",
            "forecast_target",
            "predicted_direction",
            "predicted_range",
            "confidence",
            "evaluation_status",
            "source_pipeline_metadata",
        ],
        label=f"{FORECAST_FILE.name}.forecast_payload",
    )
    if forecast_payload["evaluation_status"] != "review_record_created":
        raise ValueError(f"{FORECAST_FILE.name}: forecast_payload.evaluation_status should be review_record_created")
    predicted_range = forecast_payload["predicted_range"]
    if not isinstance(predicted_range, dict):
        raise ValueError(f"{FORECAST_FILE.name}: forecast_payload.predicted_range must be an object")
    ensure_fields(predicted_range, ["low", "high", "unit"], label=f"{FORECAST_FILE.name}.forecast_payload.predicted_range")

    source_pipeline_metadata = forecast_payload["source_pipeline_metadata"]
    if not isinstance(source_pipeline_metadata, dict):
        raise ValueError(f"{FORECAST_FILE.name}: source_pipeline_metadata must be an object")
    ensure_fields(
        source_pipeline_metadata,
        ["pipeline_name", "pipeline_run_id", "source_schema_version"],
        label=f"{FORECAST_FILE.name}.forecast_payload.source_pipeline_metadata",
    )


def validate_outcome_record(payload: Dict[str, Any]) -> None:
    ensure_fields(
        payload,
        [
            "schema_version",
            "record_version",
            "record_id",
            "review_id",
            "forecast_id",
            "stock_id",
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
        ],
        label=OUTCOME_FILE.name,
    )
    ensure_status(payload["lifecycle_status"], ALLOWED_LIFECYCLE_STATUSES, label=OUTCOME_FILE.name, field_name="lifecycle_status")
    ensure_status(payload["data_status"], ALLOWED_DATA_STATUSES, label=OUTCOME_FILE.name, field_name="data_status")
    ensure_status(payload["backfill_status"], ALLOWED_BACKFILL_STATUSES, label=OUTCOME_FILE.name, field_name="backfill_status")
    if payload["lifecycle_status"] != "outcome_backfilled":
        raise ValueError(f"{OUTCOME_FILE.name}: lifecycle_status should be outcome_backfilled")
    if payload["backfill_status"] != "completed":
        raise ValueError(f"{OUTCOME_FILE.name}: backfill_status should be completed")
    if payload["data_status"] != "completed":
        raise ValueError(f"{OUTCOME_FILE.name}: data_status should be completed")

    actual_outcome = payload["actual_outcome"]
    if not isinstance(actual_outcome, dict):
        raise ValueError(f"{OUTCOME_FILE.name}: actual_outcome must be an object")
    ensure_fields(
        actual_outcome,
        [
            "actual_close",
            "actual_high",
            "actual_low",
            "actual_return",
            "actual_direction",
            "unit",
            "market_data_source",
            "captured_at",
        ],
        label=f"{OUTCOME_FILE.name}.actual_outcome",
    )

    pending_example = payload["pending_example"]
    if not isinstance(pending_example, dict):
        raise ValueError(f"{OUTCOME_FILE.name}: pending_example must be an object")
    ensure_fields(
        pending_example,
        ["backfill_status", "lifecycle_status", "data_status", "actual_outcome", "notes"],
        label=f"{OUTCOME_FILE.name}.pending_example",
    )
    ensure_status(
        pending_example["backfill_status"],
        ALLOWED_BACKFILL_STATUSES,
        label=f"{OUTCOME_FILE.name}.pending_example",
        field_name="backfill_status",
    )
    ensure_status(
        pending_example["lifecycle_status"],
        ALLOWED_LIFECYCLE_STATUSES,
        label=f"{OUTCOME_FILE.name}.pending_example",
        field_name="lifecycle_status",
    )
    ensure_status(
        pending_example["data_status"],
        ALLOWED_DATA_STATUSES,
        label=f"{OUTCOME_FILE.name}.pending_example",
        field_name="data_status",
    )
    if pending_example["backfill_status"] != "pending":
        raise ValueError(f"{OUTCOME_FILE.name}: pending_example.backfill_status should be pending")
    if pending_example["lifecycle_status"] != "outcome_pending":
        raise ValueError(f"{OUTCOME_FILE.name}: pending_example.lifecycle_status should be outcome_pending")

    backfill_policy = payload["backfill_policy"]
    if not isinstance(backfill_policy, dict):
        raise ValueError(f"{OUTCOME_FILE.name}: backfill_policy must be an object")
    ensure_fields(
        backfill_policy,
        ["pending_when_missing", "allow_manual_override", "holiday_policy", "suspended_trading_policy"],
        label=f"{OUTCOME_FILE.name}.backfill_policy",
    )


def validate_index_record(payload: Dict[str, Any]) -> None:
    ensure_fields(
        payload,
        [
            "schema_version",
            "record_version",
            "index_id",
            "generated_at",
            "storage_policy",
            "non_goals",
            "safety_boundaries",
            "records",
            "notes",
        ],
        label=INDEX_FILE.name,
    )
    storage_policy = payload["storage_policy"]
    if not isinstance(storage_policy, dict):
        raise ValueError(f"{INDEX_FILE.name}: storage_policy must be an object")
    ensure_fields(
        storage_policy,
        ["mode", "immutability", "enrichment_layer", "queryability"],
        label=f"{INDEX_FILE.name}.storage_policy",
    )
    if storage_policy["mode"] != "research_only":
        raise ValueError(f"{INDEX_FILE.name}: storage_policy.mode should be research_only")

    records = payload["records"]
    if not isinstance(records, list) or not records:
        raise ValueError(f"{INDEX_FILE.name}: records must be a non-empty array")

    required_record_ids = {
        "forecast-review-link-2330-example",
        "outcome-backfill-2330-example",
    }
    seen_record_ids = set()
    for entry in records:
        if not isinstance(entry, dict):
            raise ValueError(f"{INDEX_FILE.name}: each records entry must be an object")
        ensure_fields(entry, ["record_id", "record_type", "path", "lifecycle_status", "data_status"], label=f"{INDEX_FILE.name}.records[]")
        ensure_status(
            entry["lifecycle_status"],
            ALLOWED_LIFECYCLE_STATUSES,
            label=f"{INDEX_FILE.name}.records[]",
            field_name="lifecycle_status",
        )
        ensure_status(
            entry["data_status"],
            ALLOWED_DATA_STATUSES,
            label=f"{INDEX_FILE.name}.records[]",
            field_name="data_status",
        )
        seen_record_ids.add(entry["record_id"])

    missing = sorted(required_record_ids - seen_record_ids)
    if missing:
        raise ValueError(f"{INDEX_FILE.name}: missing linked record ids: {', '.join(missing)}")


def validate_file(path: Path, validator) -> Dict[str, Any]:
    payload = load_json(path)
    validator(payload)
    return {
        "file": path.name,
        "path": str(path.relative_to(ROOT)),
        "status": "ok",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate prediction review storage research samples.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print the JSON summary.")
    args = parser.parse_args()

    results: List[Dict[str, Any]] = []
    errors: List[str] = []

    checks = [
        (FORECAST_FILE, validate_forecast_record),
        (OUTCOME_FILE, validate_outcome_record),
        (INDEX_FILE, validate_index_record),
    ]
    for path, validator in checks:
        try:
            results.append(validate_file(path, validator))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{path.name}: {exc}")

    summary = {
        "ok": not errors,
        "sample_dir": str(SAMPLE_DIR.relative_to(ROOT)),
        "validated_files": results,
        "errors": errors,
        "policy": {
            "read_only": True,
            "write_db": False,
            "send_notifications": False,
            "run_production_pipeline": False,
            "use_credentials": False,
        },
    }

    if args.pretty:
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))

    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
