#!/usr/bin/env python3
"""Validate schema example JSON files without side effects."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


DEFAULT_EXAMPLES_DIR = "orchestrator/templates/schemas"

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

TYPE_REQUIRED_FIELDS = {
    "signal.example.json": ["signal_id", "stock_id", "signal_session", "signal_time", "signal_type"],
    "forecast.example.json": ["forecast_id", "forecast_horizon", "forecast_target", "forecast_value"],
    "report_metadata.example.json": ["report_id", "report_type", "input_record_ids", "publication_status"],
    "prediction_review.example.json": ["review_id", "review_date", "expected_outcome", "actual_outcome"],
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

    return {
        "path": str(path),
        "passed": not reasons,
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
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    examples_dir = Path(args.examples_dir)
    if not examples_dir.is_absolute():
        examples_dir = repo_root / examples_dir

    paths = collect_example_paths(examples_dir)
    results = [validate_example(path) for path in paths]
    reasons: list[str] = []
    if not paths:
        reasons.append(f"no schema example files found: {examples_dir}")
    for result in results:
        reasons.extend(f"{result['path']}: {reason}" for reason in result["reasons"])

    output = {
        "ok": True,
        "passed": not reasons,
        "examples_dir": str(examples_dir),
        "example_count": len(paths),
        "validated_files": [str(path) for path in paths],
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
