#!/usr/bin/env python3
"""Validate Daily Report Preview Index V1 fixture results."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "daily_report_preview_index_v1"
SOURCE_SCHEMA_VERSION = "daily_report_static_preview_export_v1"
DECISIONS = {
    "daily_report_preview_index_completed",
    "daily_report_preview_index_completed_with_warnings",
    "validation_failed",
    "blocked",
}
TOP_LEVEL = [
    "schema_version",
    "task_id",
    "run_id",
    "generated_at",
    "mode",
    "preview_index",
    "preview_entries",
    "preview_summary",
    "source_preview_export_summary",
    "validation_summary",
    "side_effects",
    "safety",
    "ok",
    "decision",
    "next_recommendation",
]
SIDE_EFFECTS_FALSE = [
    "read_secrets",
    "called_external_model_runtime",
    "called_market_data_runtime",
    "sent_notification",
    "placed_trade_order",
    "modified_portfolio",
    "wrote_persistent_store",
    "modified_schedule_or_service",
    "modified_github_remote",
    "sent_daily_report",
    "wrote_production_db",
]
SAFETY_TRUE = [
    "repo_only",
    "fixture_only",
    "preview_only",
    "advisory_only",
    "requires_human_review",
    "no_external_model_calls",
    "no_market_data_calls",
    "no_delivery_actions",
    "no_persistent_store_writes",
    "no_portfolio_actions",
    "no_schedule_service_changes",
]
ENTRY_KEYS = [
    "preview_id",
    "report_date",
    "title",
    "manifest_ref",
    "markdown_ref",
    "renderer_source_ref",
    "section_count",
    "advisory_only",
    "preview_only",
    "requires_human_review",
    "warnings",
    "validation_summary",
]
SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{20,}"),
    re.compile(r"AIza[0-9A-Za-z_-]{20,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{20,}", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\.env", re.IGNORECASE),
]
FORBIDDEN_LIVE_TERMS = ["shioaji", "production_db", "webhook", "broker"]
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


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def missing(data: Any, keys: list[str]) -> list[str]:
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


def validate_preview_index(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    index = payload.get("preview_index")
    entries = as_list(payload.get("preview_entries"))
    if not isinstance(index, dict):
        return ["preview_index must be an object"]
    for key in [
        "index_id",
        "source_preview_export_ref",
        "entry_count",
        "manifest_refs",
        "markdown_refs",
        "renderer_source_refs",
        "preview_ids",
        "dashboard_summary_ref",
    ]:
        if key not in index:
            errors.append(f"preview_index missing {key}")
    if index.get("entry_count") != len(entries):
        errors.append("preview_index.entry_count must match preview_entries length")
    for key in ["manifest_refs", "markdown_refs", "renderer_source_refs", "preview_ids"]:
        values = index.get(key)
        if not isinstance(values, list) or not values:
            errors.append(f"preview_index.{key} must be a non-empty list")
    if index.get("dashboard_summary_ref") != "embedded:preview_summary":
        errors.append("preview_index.dashboard_summary_ref must be embedded:preview_summary")
    return errors


def validate_preview_entries(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    entries = payload.get("preview_entries")
    if not isinstance(entries, list):
        return ["preview_entries must be a list"]
    if len(entries) != 1:
        errors.append("preview_entries must contain exactly one static preview export entry")
    for index, entry in enumerate(entries):
        prefix = f"preview_entries[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{prefix} must be an object")
            continue
        for key in ENTRY_KEYS:
            if key not in entry:
                errors.append(f"{prefix} missing {key}")
        for key in ["preview_id", "report_date", "title", "manifest_ref", "markdown_ref", "renderer_source_ref"]:
            if not isinstance(entry.get(key), str) or not entry.get(key):
                errors.append(f"{prefix}.{key} must be a non-empty string")
        if not re.fullmatch(r"20\d{2}-\d{2}-\d{2}", str(entry.get("report_date", ""))):
            errors.append(f"{prefix}.report_date must be YYYY-MM-DD")
        if not isinstance(entry.get("section_count"), int) or entry.get("section_count") <= 0:
            errors.append(f"{prefix}.section_count must be positive")
        for key in ["advisory_only", "preview_only", "requires_human_review"]:
            if entry.get(key) is not True:
                errors.append(f"{prefix}.{key} must be true")
        if not isinstance(entry.get("warnings"), list):
            errors.append(f"{prefix}.warnings must be a list")
        summary = entry.get("validation_summary")
        if not isinstance(summary, dict):
            errors.append(f"{prefix}.validation_summary must be an object")
            continue
        expected = {
            "source_schema_matched": True,
            "source_ok": True,
            "source_mode_fixture_dry_run": True,
            "manifest_ref_present": True,
            "markdown_ref_present": True,
            "renderer_source_ref_present": True,
        }
        for key, value in expected.items():
            if summary.get(key) != value:
                errors.append(f"{prefix}.validation_summary.{key} is invalid")
    return errors


def validate_preview_summary(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    summary = payload.get("preview_summary")
    entries = as_list(payload.get("preview_entries"))
    if not isinstance(summary, dict):
        return ["preview_summary must be an object"]
    for key in ["summary_title", "preview_count", "warning_count", "requires_human_review_count", "entries"]:
        if key not in summary:
            errors.append(f"preview_summary missing {key}")
    if summary.get("preview_count") != len(entries):
        errors.append("preview_summary.preview_count must match preview_entries length")
    if summary.get("requires_human_review_count") != len(entries):
        errors.append("preview_summary.requires_human_review_count must match review-required entries")
    summary_entries = summary.get("entries")
    if not isinstance(summary_entries, list) or len(summary_entries) != len(entries):
        errors.append("preview_summary.entries must match preview_entries length")
    return errors


def validate_source_summary(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    summary = payload.get("source_preview_export_summary")
    if not isinstance(summary, dict):
        return ["source_preview_export_summary must be an object"]
    expected = {
        "source_schema_version": SOURCE_SCHEMA_VERSION,
        "source_ok": True,
        "source_mode": "fixture_dry_run",
        "source_manifest_included": True,
        "source_markdown_included": True,
    }
    for key, value in expected.items():
        if summary.get(key) != value:
            errors.append(f"source_preview_export_summary.{key} is invalid")
    for key in ["source_path", "source_preview_id", "source_title"]:
        if not isinstance(summary.get(key), str) or not summary.get(key):
            errors.append(f"source_preview_export_summary.{key} must be a non-empty string")
    return errors


def validate_validation_summary(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    summary = payload.get("validation_summary")
    entries = as_list(payload.get("preview_entries"))
    if not isinstance(summary, dict):
        return ["validation_summary must be an object"]
    expected = {
        "source_schema_expected": SOURCE_SCHEMA_VERSION,
        "source_schema_matched": True,
        "source_ok": True,
        "source_mode_fixture_dry_run": True,
        "preview_entry_count": len(entries),
        "preview_entries_included": True,
        "preview_summary_included": True,
        "manifest_refs_present": True,
        "markdown_refs_present": True,
        "renderer_source_refs_present": True,
        "deterministic_output": True,
        "fixture_only": True,
    }
    for key, value in expected.items():
        if summary.get(key) != value:
            errors.append(f"validation_summary.{key} is invalid")
    if not isinstance(summary.get("section_count"), int) or summary.get("section_count") <= 0:
        errors.append("validation_summary.section_count must be positive")
    if not isinstance(summary.get("warnings"), list):
        errors.append("validation_summary.warnings must be a list")
    return errors


def validate_side_effects(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    side_effects = payload.get("side_effects")
    if not isinstance(side_effects, dict):
        return ["side_effects must be an object"]
    for key in SIDE_EFFECTS_FALSE:
        if side_effects.get(key) is not False:
            errors.append(f"side_effects.{key} must be false")
    return errors


def validate_safety(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    safety = payload.get("safety")
    if not isinstance(safety, dict):
        return ["safety must be an object"]
    for key in SAFETY_TRUE:
        if safety.get(key) is not True:
            errors.append(f"safety.{key} must be true")
    return errors


def validate_payload(payload: Any) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return {"ok": False, "errors": ["result root must be an object"]}
    for key in missing(payload, TOP_LEVEL):
        errors.append(f"missing top-level field: {key}")
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    if payload.get("mode") != "fixture_dry_run":
        errors.append("mode must be fixture_dry_run")
    if payload.get("decision") not in DECISIONS:
        errors.append("decision is invalid")
    if payload.get("ok") is not True and payload.get("decision") not in {"validation_failed", "blocked"}:
        errors.append("ok must be true for completed decisions")
    errors.extend(validate_preview_index(payload))
    errors.extend(validate_preview_entries(payload))
    errors.extend(validate_preview_summary(payload))
    errors.extend(validate_source_summary(payload))
    errors.extend(validate_validation_summary(payload))
    errors.extend(validate_side_effects(payload))
    errors.extend(validate_safety(payload))
    rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    for pattern in SECRET_PATTERNS:
        if pattern.search(rendered):
            errors.append(f"secret-like or private config text detected: {pattern.pattern}")
            break
    for text in iter_strings(payload):
        lowered = text.lower()
        for term in FORBIDDEN_LIVE_TERMS:
            if term in lowered:
                errors.append(f"forbidden live runtime source detected: {term}")
        for pattern in FORBIDDEN_TRADING_TEXT:
            if pattern.search(text):
                errors.append(f"possible trading/order instruction detected: {text}")
    validation = as_dict(payload.get("validation_summary"))
    return {
        "ok": not errors,
        "run_id": payload.get("run_id"),
        "decision": payload.get("decision"),
        "preview_entry_count": validation.get("preview_entry_count"),
        "deterministic_output": validation.get("deterministic_output"),
        "errors": errors,
        "side_effects": {key: False for key in SIDE_EFFECTS_FALSE},
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Daily Report Preview Index V1 result JSON.")
    parser.add_argument("path", nargs="?")
    parser.add_argument("--input", dest="input_path")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = args.input_path or args.path
    if not input_path:
        raise SystemExit("input path is required")
    payload, load_errors = load_json(Path(input_path))
    result = {"ok": False, "errors": load_errors} if payload is None else validate_payload(payload)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
