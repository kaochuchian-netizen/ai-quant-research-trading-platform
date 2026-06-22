#!/usr/bin/env python3
"""Read-only actual outcome backfill prototype for research samples.

This prototype reads the AI-DEV-018 prediction review storage samples and
prints a JSON summary for actual outcome backfill planning. It does not write
files, touch databases, call external services, read credentials, send
notifications, or run production pipelines.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SAMPLE_DIR = ROOT / "orchestrator" / "templates" / "research_samples" / "prediction_review_storage"

FORECAST_PATH = SAMPLE_DIR / "forecast_to_review_record.example.json"
OUTCOME_PATH = SAMPLE_DIR / "actual_outcome_backfill.example.json"
INDEX_PATH = SAMPLE_DIR / "prediction_review_storage_index.example.json"

ALLOWED_BACKFILL_STATUSES = {
    "pending",
    "completed",
    "missing_market_data",
    "non_trading_day",
    "suspended",
    "invalid_window",
    "not_due",
}

ALLOWED_DATA_QUALITY_FLAGS = {
    "sample_data_only",
    "research_only",
    "missing_actual_close",
    "missing_actual_high",
    "missing_actual_low",
    "missing_actual_return",
    "window_not_elapsed",
    "manual_review_required",
}

ACTUAL_OUTCOME_FIELDS = [
    "actual_close",
    "actual_high",
    "actual_low",
    "actual_return",
    "actual_direction",
    "unit",
    "market_data_source",
    "captured_at",
]


def load_object(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be object: {path}")
    return data


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


def require_mapping(value: Any, label: str, reasons: list[str]) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    reasons.append(f"{label} must be an object")
    return {}


def date_part(value: Any) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    return value.split("T", 1)[0]


def parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def missing_actual_fields(actual_outcome: dict[str, Any] | None) -> list[str]:
    if not actual_outcome:
        return ACTUAL_OUTCOME_FIELDS.copy()
    return [field for field in ACTUAL_OUTCOME_FIELDS if actual_outcome.get(field) is None]


def quality_flags_for_candidate(
    *,
    status: str,
    actual_outcome: dict[str, Any] | None,
    data_status: str,
    source_type: str,
) -> list[str]:
    flags = {"sample_data_only", "research_only"}
    missing_fields = set(missing_actual_fields(actual_outcome))
    flag_by_field = {
        "actual_close": "missing_actual_close",
        "actual_high": "missing_actual_high",
        "actual_low": "missing_actual_low",
        "actual_return": "missing_actual_return",
    }
    for field_name, flag_name in flag_by_field.items():
        if field_name in missing_fields:
            flags.add(flag_name)
    if status in {"pending", "not_due"}:
        flags.add("window_not_elapsed")
    if status in {"missing_market_data", "non_trading_day", "suspended", "invalid_window"}:
        flags.add("manual_review_required")
    if data_status not in {"completed", "pending", "research_only"}:
        flags.add("manual_review_required")
    if source_type != "research_example":
        flags.add("manual_review_required")
    return sorted(flags)


def ensure_allowed_statuses(candidates: list[dict[str, Any]]) -> list[str]:
    reasons: list[str] = []
    for candidate in candidates:
        status = str(candidate.get("backfill_status"))
        if status not in ALLOWED_BACKFILL_STATUSES:
            reasons.append(f"invalid backfill_status for {candidate.get('candidate_id')}: {status}")
        for flag in candidate.get("data_quality_flags", []):
            if flag not in ALLOWED_DATA_QUALITY_FLAGS:
                reasons.append(f"invalid data_quality_flag for {candidate.get('candidate_id')}: {flag}")
    return reasons


def summarize(
    forecast: dict[str, Any],
    outcome: dict[str, Any],
    index: dict[str, Any],
    *,
    dry_run: bool,
) -> tuple[dict[str, Any], list[str]]:
    reasons: list[str] = []
    forecast_window = require_mapping(forecast.get("forecast_window"), "forecast.forecast_window", reasons)
    outcome_window = require_mapping(outcome.get("outcome_window"), "outcome.outcome_window", reasons)
    actual_outcome = require_mapping(outcome.get("actual_outcome"), "outcome.actual_outcome", reasons)
    pending_example = require_mapping(outcome.get("pending_example"), "outcome.pending_example", reasons)
    backfill_policy = require_mapping(outcome.get("backfill_policy"), "outcome.backfill_policy", reasons)
    storage_policy = require_mapping(index.get("storage_policy"), "index.storage_policy", reasons)
    records = index.get("records")
    if not isinstance(records, list):
        reasons.append("index.records must be a list")
        records = []

    if reasons:
        return {}, reasons

    completed_candidate = {
        "candidate_id": str(outcome.get("record_id")),
        "record_type": "actual_outcome_backfill",
        "forecast_id": outcome.get("forecast_id"),
        "review_id": outcome.get("review_id"),
        "stock_id": outcome.get("stock_id"),
        "stock_name": outcome.get("stock_name"),
        "forecast_window": forecast_window,
        "outcome_window": outcome_window,
        "backfill_status": str(outcome.get("backfill_status")),
        "lifecycle_status": outcome.get("lifecycle_status"),
        "data_status": str(outcome.get("data_status")),
        "actual_outcome": actual_outcome,
        "data_quality_flags": quality_flags_for_candidate(
            status=str(outcome.get("backfill_status")),
            actual_outcome=actual_outcome,
            data_status=str(outcome.get("data_status")),
            source_type=str(outcome.get("source_type")),
        ),
        "evaluable": str(outcome.get("backfill_status")) == "completed",
    }
    pending_candidate = {
        "candidate_id": f"{outcome.get('record_id')}-pending-example",
        "record_type": "pending_actual_outcome_example",
        "forecast_id": outcome.get("forecast_id"),
        "review_id": f"{outcome.get('review_id')}-pending-example",
        "stock_id": outcome.get("stock_id"),
        "stock_name": outcome.get("stock_name"),
        "forecast_window": forecast_window,
        "outcome_window": outcome_window,
        "backfill_status": str(pending_example.get("backfill_status")),
        "lifecycle_status": pending_example.get("lifecycle_status"),
        "data_status": str(pending_example.get("data_status")),
        "actual_outcome": None,
        "data_quality_flags": quality_flags_for_candidate(
            status=str(pending_example.get("backfill_status")),
            actual_outcome=None,
            data_status=str(pending_example.get("data_status")),
            source_type=str(outcome.get("source_type")),
        ),
        "evaluable": False,
    }
    candidates = [completed_candidate, pending_candidate]
    reasons.extend(ensure_allowed_statuses(candidates))

    forecast_created_at = parse_datetime(forecast.get("created_at"))
    outcome_captured_at = parse_datetime(actual_outcome.get("captured_at"))
    backfill_timestamp = parse_datetime(outcome.get("backfill_timestamp"))
    forecast_before_outcome = (
        forecast_created_at is not None
        and outcome_captured_at is not None
        and forecast_created_at < outcome_captured_at
    )
    forecast_before_backfill = (
        forecast_created_at is not None
        and backfill_timestamp is not None
        and forecast_created_at < backfill_timestamp
    )

    backfill_status_counts = Counter(str(candidate["backfill_status"]) for candidate in candidates)
    all_flags = sorted({flag for candidate in candidates for flag in candidate["data_quality_flags"]})
    missing_field_counts = Counter(
        field
        for candidate in candidates
        for field in missing_actual_fields(candidate.get("actual_outcome"))
        if field in {"actual_close", "actual_high", "actual_low", "actual_return"}
    )
    evaluable_records = [candidate for candidate in candidates if candidate["evaluable"]]
    non_evaluable_records = [candidate for candidate in candidates if not candidate["evaluable"]]

    summary = {
        "schema_version": 1,
        "operation": "actual_outcome_backfill_dry_run" if dry_run else "actual_outcome_backfill_read_only_prototype",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "safety_mode": "research_only_read_only",
        "input_records": {
            "sample_dir": str(SAMPLE_DIR.relative_to(ROOT)),
            "source_files": [
                str(FORECAST_PATH.relative_to(ROOT)),
                str(OUTCOME_PATH.relative_to(ROOT)),
                str(INDEX_PATH.relative_to(ROOT)),
            ],
            "indexed_record_count": len(records),
            "storage_policy_mode": storage_policy.get("mode"),
            "forecast_record_id": forecast.get("record_id"),
            "outcome_record_id": outcome.get("record_id"),
            "index_id": index.get("index_id"),
        },
        "backfill_candidates": candidates,
        "backfill_status_counts": dict(sorted(backfill_status_counts.items())),
        "window_alignment_summary": {
            "forecast_window": forecast_window,
            "outcome_window": outcome_window,
            "window_start_match": forecast_window.get("start_date") == outcome_window.get("start_date"),
            "window_end_match": forecast_window.get("end_date") == outcome_window.get("end_date"),
            "window_type_match": forecast_window.get("window_type") == outcome_window.get("window_type"),
            "horizon_match": forecast_window.get("horizon") == outcome_window.get("horizon"),
            "aligned": forecast_window == outcome_window,
            "forecast_run_date": forecast.get("run_date"),
            "forecast_start_after_run_date": bool(
                date_part(forecast_window.get("start_date")) and date_part(forecast.get("run_date"))
                and str(forecast_window.get("start_date")) >= str(forecast.get("run_date"))
            ),
        },
        "actual_outcome_summary": {
            "completed_record_count": backfill_status_counts.get("completed", 0),
            "pending_record_count": backfill_status_counts.get("pending", 0),
            "evaluable_record_count": len(evaluable_records),
            "non_evaluable_record_count": len(non_evaluable_records),
            "completed_actual_fields_present": [
                field for field in ACTUAL_OUTCOME_FIELDS if actual_outcome.get(field) is not None
            ],
            "actual_direction_values": sorted(
                {
                    str(candidate["actual_outcome"].get("actual_direction"))
                    for candidate in candidates
                    if isinstance(candidate.get("actual_outcome"), dict)
                    and candidate["actual_outcome"].get("actual_direction") is not None
                }
            ),
        },
        "missing_data_summary": {
            "missing_actual_field_counts": dict(sorted(missing_field_counts.items())),
            "pending_is_failure": False,
            "pending_policy": forecast.get("pending_policy"),
            "missing_data_policy": outcome.get("missing_data_policy"),
            "holiday_policy": backfill_policy.get("holiday_policy"),
            "suspended_trading_policy": backfill_policy.get("suspended_trading_policy"),
        },
        "data_quality_flags": all_flags,
        "governance_summary": {
            "dry_run": dry_run,
            "dry_run_first_required": True,
            "db_mutation_allowed": False,
            "production_file_mutation_allowed": False,
            "external_service_calls_allowed": False,
            "notification_delivery_allowed": False,
            "schema_compatibility_check": {
                "forecast_window_present": bool(forecast_window),
                "outcome_window_present": bool(outcome_window),
                "actual_outcome_fields_checked": ACTUAL_OUTCOME_FIELDS,
                "allowed_backfill_statuses": sorted(ALLOWED_BACKFILL_STATUSES),
                "allowed_data_quality_flags": sorted(ALLOWED_DATA_QUALITY_FLAGS),
            },
            "audit_summary": {
                "candidate_count": len(candidates),
                "evaluable_record_count": len(evaluable_records),
                "non_evaluable_record_count": len(non_evaluable_records),
                "backfill_status_counts": dict(sorted(backfill_status_counts.items())),
                "data_quality_flags": all_flags,
                "pending_is_failure": False,
            },
            "rollback_policy": "no_op_for_research_samples",
            "no_op_policy": "dry_run_outputs_stdout_only_and_does_not_mutate_state",
        },
        "lookahead_bias_controls": {
            "forecast_snapshot_immutable": storage_policy.get("immutability") == "forecast_snapshot_immutable",
            "forecast_created_at": forecast.get("created_at"),
            "actual_captured_at": actual_outcome.get("captured_at"),
            "backfill_timestamp": outcome.get("backfill_timestamp"),
            "forecast_before_actual_capture": forecast_before_outcome,
            "forecast_before_backfill": forecast_before_backfill,
            "outcomes_do_not_mutate_forecast_payload": True,
            "pending_outcomes_not_inferred": True,
        },
        "evaluable_records": evaluable_records,
        "non_evaluable_records": non_evaluable_records,
        "next_actions": [
            "Keep this prototype read-only until an explicit DB migration task is approved.",
            "Extend samples for missing market data, holidays, suspended trading, invalid windows, and not-due windows.",
            "Add controlled trading-calendar integration only after external-service and production boundaries are approved.",
        ],
        "limitations": [
            "Research-only sample data; no external market data is fetched.",
            "Trading-day, holiday, and suspension handling is policy-only in this prototype.",
            "Pending outcomes are non-evaluable and do not count as failures.",
            "This output is not an investment recommendation, trading signal, production report, or notification payload.",
        ],
    }
    return summary, reasons


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize actual outcome backfill candidates from research samples.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Emit explicit dry-run governance metadata; still read-only and stdout-only.",
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    if repo_root != ROOT:
        # Keep the prototype constrained to this checkout. The argument is
        # accepted for consistency with sibling validators.
        pass

    forecast, outcome, index, load_reasons = load_bundle()
    summary, summary_reasons = summarize(forecast, outcome, index, dry_run=args.dry_run)
    reasons = load_reasons + summary_reasons
    output = {
        "ok": True,
        "passed": not reasons,
        **summary,
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
            "investment_advice_generated": False,
        },
    }
    print(json.dumps(output, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0 if output["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
