#!/usr/bin/env python3
"""Validate schema example JSON files without side effects."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


DEFAULT_EXAMPLES_DIR = "orchestrator/templates/schemas"
DEFAULT_REGISTRY_PATH = "orchestrator/templates/schema_registry.json"

REQUIRED_COMMON_FIELDS = [
    "schema_version",
    "entity_id",
    "entity_type",
    "as_of_date",
    "created_at",
    "source",
    "source_tier",
    "confidence",
    "data_quality",
    "missing_data_policy",
    "notes",
]

REQUIRED_DATA_QUALITY_FIELDS = [
    "freshness",
    "completeness",
    "source_count",
    "conflicting_sources",
    "requires_human_review",
    "legacy_record",
]

ALLOWED_SOURCE_TIERS = {
    "tier_1_official_filing",
    "tier_1_company_official",
    "tier_2_peer_and_industry_primary",
    "tier_2_management_interview",
    "tier_3_reputable_media",
    "tier_3_market_data",
    "tier_4_consensus_and_analyst",
    "tier_5_unverified_or_social",
}

ALLOWED_EVALUATION_STATUS = {
    "pending",
    "completed",
    "inconclusive",
    "not_reviewable",
}

ALLOWED_EVALUATION_WINDOWS = {
    "intraday",
    "same_day",
    "T+1",
    "5D",
    "20D",
    "1M",
    "quarter",
    "fy",
}

TYPE_REQUIRED_FIELDS = {
    "signal.example.json": ["signal_id", "stock_id", "signal_session", "signal_time", "signal_type"],
    "forecast.example.json": [
        "forecast_id",
        "forecast_horizon",
        "forecast_window",
        "forecast_type",
        "forecast_target",
        "forecast_value",
        "predicted_range",
        "actual_value_placeholder",
        "evaluation_status",
        "evaluation_window",
        "evaluation_metrics_expected",
        "model_version",
        "prompt_version",
        "confidence_calibration",
    ],
    "report_metadata.example.json": ["report_id", "report_type", "input_record_ids", "publication_status"],
    "prediction_review.example.json": [
        "review_id",
        "review_date",
        "review_horizon",
        "forecast_type",
        "forecast_target",
        "evaluation_status",
        "evaluation_window",
        "expected_outcome",
        "actual_outcome",
        "outcome_status",
        "error_metrics",
        "evaluation_metrics",
        "model_version",
        "prompt_version",
        "confidence_calibration",
    ],
    "company_intelligence.example.json": ["company_intel_id", "company_id", "event_type", "event_date"],
    "industry_intelligence.example.json": ["industry_intel_id", "industry_id", "topic", "summary"],
    "source_credibility.example.json": [
        "source_tiers",
        "analyst_target_price_handling_policy",
    ],
    "dashboard_payload.example.json": ["signal_summary", "source_quality_summary", "report_registry"],
    "email_report_payload.example.json": [
        "email_report_id",
        "report_id",
        "source_tier_summary",
        "notification_sent",
        "send_allowed",
    ],
}

REGISTRY_REQUIRED_ENTRY_FIELDS = [
    "schema_name",
    "schema_version",
    "example_path",
    "owner_area",
    "intended_usage",
    "production_status",
    "required_fields",
    "optional_fields",
    "validation_level",
    "allowed_consumers",
    "disallowed_consumers",
    "notes",
]

REQUIRED_REGISTRY_GOVERNANCE_FIELDS = [
    "schema_lifecycle",
    "versioning_policy",
    "source_policy_doc",
    "analyst_target_price_policy",
    "production_boundary",
]

PROHIBITED_REGISTRY_TERMS = [
    "production_enabled",
    "production-ready",
    "production ready",
    "trading_enabled",
    "trading-enabled",
    "order_enabled",
    "order-enabled",
    "auto_trade",
    "place_order",
    "send_line_report",
]

REQUIRED_DISALLOWED_CONSUMERS = {
    "production_pipeline",
    "notification_sender",
    "trading_execution",
    "order_execution",
}


def load_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        return None, str(exc)
    if not isinstance(data, dict):
        return None, "JSON root must be object"
    return data, None


def missing_fields(data: dict[str, Any], fields: list[str]) -> list[str]:
    return [field for field in fields if field not in data]


def validate_source(data: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    source = data.get("source")
    if not isinstance(source, list) or not source:
        return ["source must be a non-empty list"]
    for index, item in enumerate(source):
        if not isinstance(item, dict):
            reasons.append(f"source[{index}] must be an object")
            continue
        for field in ["source_id", "source_tier", "source_type", "publisher", "retrieved_at"]:
            if field not in item:
                reasons.append(f"source[{index}] missing field: {field}")
        source_tier = item.get("source_tier")
        if source_tier not in ALLOWED_SOURCE_TIERS:
            reasons.append(f"source[{index}] invalid source_tier: {source_tier}")
    return reasons


def validate_data_quality(data: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    data_quality = data.get("data_quality")
    if not isinstance(data_quality, dict):
        return ["data_quality must be an object"]
    for field in missing_fields(data_quality, REQUIRED_DATA_QUALITY_FIELDS):
        reasons.append(f"data_quality missing field: {field}")
    completeness = data_quality.get("completeness")
    if not isinstance(completeness, (int, float)) or not 0 <= completeness <= 1:
        reasons.append("data_quality.completeness must be a number between 0 and 1")
    return reasons


def validate_forecast_evaluation_fields(data: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if data.get("evaluation_status") not in ALLOWED_EVALUATION_STATUS:
        reasons.append(f"invalid evaluation_status: {data.get('evaluation_status')}")
    if data.get("evaluation_window") not in ALLOWED_EVALUATION_WINDOWS:
        reasons.append(f"invalid evaluation_window: {data.get('evaluation_window')}")
    if not isinstance(data.get("predicted_range"), dict):
        reasons.append("predicted_range must be an object")
    else:
        predicted_range = data["predicted_range"]
        for field in ["low", "high", "unit"]:
            if field not in predicted_range:
                reasons.append(f"predicted_range missing field: {field}")
        low = predicted_range.get("low")
        high = predicted_range.get("high")
        if isinstance(low, (int, float)) and isinstance(high, (int, float)) and low > high:
            reasons.append("predicted_range.low must be <= predicted_range.high")
    if not isinstance(data.get("actual_value_placeholder"), dict):
        reasons.append("actual_value_placeholder must be an object")
    if not isinstance(data.get("evaluation_metrics_expected"), list) or not data.get("evaluation_metrics_expected"):
        reasons.append("evaluation_metrics_expected must be a non-empty list")
    if not isinstance(data.get("model_version"), str) or not data.get("model_version"):
        reasons.append("model_version must be a non-empty string")
    if not isinstance(data.get("prompt_version"), str) or not data.get("prompt_version"):
        reasons.append("prompt_version must be a non-empty string")
    if not isinstance(data.get("confidence_calibration"), dict):
        reasons.append("confidence_calibration must be an object")
    return reasons


def validate_prediction_review_evaluation_fields(data: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if data.get("evaluation_status") not in ALLOWED_EVALUATION_STATUS:
        reasons.append(f"invalid evaluation_status: {data.get('evaluation_status')}")
    if data.get("evaluation_window") not in ALLOWED_EVALUATION_WINDOWS:
        reasons.append(f"invalid evaluation_window: {data.get('evaluation_window')}")
    expected = data.get("expected_outcome")
    if not isinstance(expected, dict):
        reasons.append("expected_outcome must be an object")
    elif not isinstance(expected.get("predicted_range"), dict):
        reasons.append("expected_outcome.predicted_range must be an object")
    actual = data.get("actual_outcome")
    if not isinstance(actual, dict):
        reasons.append("actual_outcome must be an object")
    else:
        for field in ["actual_low", "actual_high", "actual_close", "actual_direction"]:
            if field not in actual:
                reasons.append(f"actual_outcome missing field: {field}")
    if not isinstance(data.get("error_metrics"), dict):
        reasons.append("error_metrics must be an object")
    if not isinstance(data.get("evaluation_metrics"), dict):
        reasons.append("evaluation_metrics must be an object")
    if not isinstance(data.get("model_version"), str) or not data.get("model_version"):
        reasons.append("model_version must be a non-empty string")
    if not isinstance(data.get("prompt_version"), str) or not data.get("prompt_version"):
        reasons.append("prompt_version must be a non-empty string")
    if not isinstance(data.get("confidence_calibration"), dict):
        reasons.append("confidence_calibration must be an object")
    return reasons


def validate_example(path: Path) -> dict[str, Any]:
    data, error = load_json(path)
    reasons: list[str] = []
    if error:
        return {
            "path": str(path),
            "passed": False,
            "reasons": [error],
        }
    assert data is not None

    for field in missing_fields(data, REQUIRED_COMMON_FIELDS):
        reasons.append(f"missing common field: {field}")

    schema_version = data.get("schema_version")
    if not isinstance(schema_version, int):
        reasons.append("schema_version must be an integer")

    source_tier = data.get("source_tier")
    if source_tier not in ALLOWED_SOURCE_TIERS:
        reasons.append(f"invalid source_tier: {source_tier}")

    confidence = data.get("confidence")
    if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
        reasons.append("confidence must be a number between 0 and 1")

    missing_data_policy = data.get("missing_data_policy")
    if not isinstance(missing_data_policy, str) or not missing_data_policy:
        reasons.append("missing_data_policy must be a non-empty string")

    reasons.extend(validate_source(data))
    reasons.extend(validate_data_quality(data))

    for field in TYPE_REQUIRED_FIELDS.get(path.name, []):
        if field not in data:
            reasons.append(f"missing type-specific field: {field}")

    if path.name == "forecast.example.json":
        reasons.extend(validate_forecast_evaluation_fields(data))
    if path.name == "prediction_review.example.json":
        reasons.extend(validate_prediction_review_evaluation_fields(data))

    return {
        "path": str(path),
        "passed": not reasons,
        "reasons": reasons,
    }


def repo_relative(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def collect_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        result: list[str] = []
        for item in value.values():
            result.extend(collect_strings(item))
        return result
    if isinstance(value, list):
        result = []
        for item in value:
            result.extend(collect_strings(item))
        return result
    return []


def validate_registry(
    registry_path: Path,
    example_paths: list[Path],
    repo_root: Path,
) -> dict[str, Any]:
    data, error = load_json(registry_path)
    reasons: list[str] = []
    if error:
        return {
            "path": str(registry_path),
            "passed": False,
            "entry_count": 0,
            "registry_example_paths": [],
            "reasons": [error],
        }
    assert data is not None

    schema_version = data.get("schema_version")
    if not isinstance(schema_version, int):
        reasons.append("registry schema_version must be an integer")
    if data.get("production_status") != "research_planning_only":
        reasons.append("registry production_status must be research_planning_only")

    governance_policy = data.get("governance_policy")
    if not isinstance(governance_policy, dict):
        reasons.append("registry governance_policy must be an object")
    else:
        for field in REQUIRED_REGISTRY_GOVERNANCE_FIELDS:
            if field not in governance_policy:
                reasons.append(f"governance_policy missing field: {field}")

    entries = data.get("entries")
    if not isinstance(entries, list) or not entries:
        reasons.append("registry entries must be a non-empty list")
        entries = []

    expected_example_paths = {
        repo_relative(path, repo_root)
        for path in example_paths
    }
    registry_example_paths: set[str] = set()
    schema_names: set[str] = set()

    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            reasons.append(f"entries[{index}] must be an object")
            continue

        for field in REGISTRY_REQUIRED_ENTRY_FIELDS:
            if field not in entry:
                reasons.append(f"entries[{index}] missing field: {field}")

        schema_name = entry.get("schema_name")
        if not isinstance(schema_name, str) or not schema_name:
            reasons.append(f"entries[{index}] schema_name must be a non-empty string")
        elif schema_name in schema_names:
            reasons.append(f"duplicate schema_name: {schema_name}")
        else:
            schema_names.add(schema_name)

        if entry.get("production_status") != "research_planning_only":
            reasons.append(f"{schema_name or index}: production_status must be research_planning_only")

        entry_schema_version = entry.get("schema_version")
        if not isinstance(entry_schema_version, int):
            reasons.append(f"{schema_name or index}: schema_version must be an integer")

        example_path_value = entry.get("example_path")
        if not isinstance(example_path_value, str) or not example_path_value:
            reasons.append(f"{schema_name or index}: example_path must be a non-empty string")
            continue

        registry_example_paths.add(example_path_value)
        example_path = repo_root / example_path_value
        example_data, example_error = load_json(example_path)
        if example_error:
            reasons.append(f"{schema_name or index}: example_path invalid: {example_path_value}: {example_error}")
            continue
        assert example_data is not None

        if example_data.get("schema_version") != entry_schema_version:
            reasons.append(
                f"{schema_name or index}: registry schema_version does not match example schema_version"
            )

        required_fields = entry.get("required_fields")
        if not isinstance(required_fields, list) or not required_fields:
            reasons.append(f"{schema_name or index}: required_fields must be a non-empty list")
            required_fields = []
        for field in required_fields:
            if not isinstance(field, str) or not field:
                reasons.append(f"{schema_name or index}: required_fields contains invalid value")
            elif field not in example_data:
                reasons.append(f"{schema_name or index}: required field missing from example: {field}")

        for field in ["source_tier", "confidence", "data_quality", "missing_data_policy"]:
            if field not in required_fields:
                reasons.append(f"{schema_name or index}: required_fields must include {field}")

        optional_fields = entry.get("optional_fields")
        if not isinstance(optional_fields, list):
            reasons.append(f"{schema_name or index}: optional_fields must be a list")
        else:
            for field in optional_fields:
                if not isinstance(field, str) or not field:
                    reasons.append(f"{schema_name or index}: optional_fields contains invalid value")

        allowed_consumers = entry.get("allowed_consumers")
        if not isinstance(allowed_consumers, list):
            reasons.append(f"{schema_name or index}: allowed_consumers must be a list")

        disallowed_consumers = entry.get("disallowed_consumers")
        if not isinstance(disallowed_consumers, list):
            reasons.append(f"{schema_name or index}: disallowed_consumers must be a list")
            disallowed_consumers_set: set[str] = set()
        else:
            disallowed_consumers_set = {str(item) for item in disallowed_consumers}
        missing_disallowed = REQUIRED_DISALLOWED_CONSUMERS - disallowed_consumers_set
        for consumer in sorted(missing_disallowed):
            reasons.append(f"{schema_name or index}: disallowed_consumers missing {consumer}")

    missing_from_registry = sorted(expected_example_paths - registry_example_paths)
    extra_registry_paths = sorted(registry_example_paths - expected_example_paths)
    for path in missing_from_registry:
        reasons.append(f"example not registered: {path}")
    for path in extra_registry_paths:
        reasons.append(f"registry example_path has no matching example file: {path}")

    registry_strings = [text.lower() for text in collect_strings(data)]
    for term in PROHIBITED_REGISTRY_TERMS:
        if any(term in text for text in registry_strings):
            reasons.append(f"registry contains prohibited production/trading term: {term}")

    return {
        "path": str(registry_path),
        "passed": not reasons,
        "entry_count": len(entries),
        "registry_example_paths": sorted(registry_example_paths),
        "expected_example_paths": sorted(expected_example_paths),
        "reasons": reasons,
    }


def collect_example_paths(examples_dir: Path) -> list[Path]:
    if not examples_dir.exists():
        return []
    return sorted(path for path in examples_dir.glob("*.example.json") if path.is_file())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate investment schema example JSON files.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--examples-dir", default=DEFAULT_EXAMPLES_DIR)
    parser.add_argument("--registry-path", default=DEFAULT_REGISTRY_PATH)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    examples_dir = Path(args.examples_dir)
    if not examples_dir.is_absolute():
        examples_dir = repo_root / examples_dir
    registry_path = Path(args.registry_path)
    if not registry_path.is_absolute():
        registry_path = repo_root / registry_path

    paths = collect_example_paths(examples_dir)
    results = [validate_example(path) for path in paths]
    registry_result = validate_registry(registry_path, paths, repo_root)
    reasons: list[str] = []
    if not paths:
        reasons.append(f"no schema example files found: {examples_dir}")
    for result in results:
        reasons.extend(f"{result['path']}: {reason}" for reason in result["reasons"])
    reasons.extend(f"{registry_result['path']}: {reason}" for reason in registry_result["reasons"])

    output = {
        "ok": True,
        "passed": not reasons,
        "examples_dir": str(examples_dir),
        "registry_path": str(registry_path),
        "example_count": len(paths),
        "validated_files": [str(path) for path in paths],
        "registry": registry_result,
        "results": results,
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
