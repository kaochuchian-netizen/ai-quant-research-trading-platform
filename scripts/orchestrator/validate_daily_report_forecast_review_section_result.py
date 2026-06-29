#!/usr/bin/env python3
"""Validate Daily Report Forecast Review Section V1 fixture results."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "daily_report_forecast_review_section_v1"
SOURCE_SCHEMA_VERSION = "dashboard_prediction_review_report_export_v1"
DECISIONS = {
    "forecast_review_section_completed",
    "forecast_review_section_completed_with_insufficient_data",
    "no_report_sections",
    "validation_failed",
    "blocked",
}
TOP_LEVEL = [
    "schema_version",
    "task_id",
    "run_id",
    "generated_at",
    "mode",
    "source_summary",
    "daily_report_section",
    "validation_summary",
    "side_effects",
    "safety",
    "ok",
    "decision",
    "next_recommendation",
]
SIDE_EFFECTS_FALSE = [
    "read_secrets",
    "called_external_ai_runtime",
    "called_market_data_runtime",
    "sent_notification",
    "placed_trade_order",
    "modified_production_db",
    "modified_cron_systemd_timer",
    "modified_n8n",
    "mutated_github_issue",
    "modified_github_remote",
    "modified_forecast_runtime_weights",
    "rendered_runtime_report",
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
FORBIDDEN_SOURCE_TERMS = ["broker", "shioaji", "production_db", "yfinance", "gemini", "openai", "dify"]
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


def validate_source_summary(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    source = payload.get("source_summary")
    if not isinstance(source, dict):
        return ["source_summary must be an object"]
    if source.get("source_schema_version") != SOURCE_SCHEMA_VERSION:
        errors.append(f"source_summary.source_schema_version must be {SOURCE_SCHEMA_VERSION}")
    if source.get("source_section_count") is None or source.get("source_section_count") < 0:
        errors.append("source_summary.source_section_count must be a non-negative number")
    if payload.get("decision") != "no_report_sections" and source.get("source_section_count", 0) <= 0:
        errors.append("source_summary.source_section_count must be positive")
    return errors


def validate_section(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    section = payload.get("daily_report_section")
    if not isinstance(section, dict):
        return ["daily_report_section must be an object"]
    for key in [
        "section_id",
        "section_type",
        "title",
        "placement",
        "priority",
        "render_mode",
        "markdown",
        "machine_readable",
        "badges",
        "source_refs",
        "advisory_only",
        "requires_human_review",
    ]:
        if key not in section:
            errors.append(f"daily_report_section missing {key}")
    if section.get("section_type") != "forecast_review":
        errors.append("daily_report_section.section_type must be forecast_review")
    if section.get("render_mode") != "static_markdown_with_machine_readable_payload":
        errors.append("daily_report_section.render_mode must be static_markdown_with_machine_readable_payload")
    if not isinstance(section.get("markdown"), str) or not section.get("markdown", "").strip():
        errors.append("daily_report_section.markdown must be a non-empty string")
    if section.get("advisory_only") is not True:
        errors.append("daily_report_section.advisory_only must be true")
    if section.get("requires_human_review") is not True:
        errors.append("daily_report_section.requires_human_review must be true")
    machine = section.get("machine_readable")
    if not isinstance(machine, dict):
        errors.append("daily_report_section.machine_readable must be an object")
        machine = {}
    if machine.get("source_schema_version") != SOURCE_SCHEMA_VERSION:
        errors.append("daily_report_section.machine_readable.source_schema_version must match source export")
    source_sections = machine.get("source_sections")
    if not isinstance(source_sections, list):
        errors.append("daily_report_section.machine_readable.source_sections must be a list")
        source_sections = []
    if payload.get("decision") != "no_report_sections" and not source_sections:
        errors.append("daily_report_section.machine_readable.source_sections cannot be empty")
    for index, item in enumerate(source_sections):
        if not isinstance(item, dict):
            errors.append(f"source_sections[{index}] must be an object")
            continue
        for key in ["source_section_id", "title", "priority", "machine_readable", "source_refs", "advisory_only"]:
            if key not in item:
                errors.append(f"source_sections[{index}] missing {key}")
        if item.get("advisory_only") is not True:
            errors.append(f"source_sections[{index}].advisory_only must be true")
    badges = section.get("badges")
    if not isinstance(badges, dict):
        errors.append("daily_report_section.badges must be an object")
    else:
        for key in ["fixture_only", "advisory_only", "requires_human_review"]:
            if badges.get(key) is not True:
                errors.append(f"daily_report_section.badges.{key} must be true")
    return errors


def validate_validation_summary(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    summary = payload.get("validation_summary")
    if not isinstance(summary, dict):
        return ["validation_summary must be an object"]
    if summary.get("source_schema_expected") != SOURCE_SCHEMA_VERSION:
        errors.append("validation_summary.source_schema_expected is invalid")
    if summary.get("source_schema_matched") is not True:
        errors.append("validation_summary.source_schema_matched must be true")
    if summary.get("markdown_included") is not True:
        errors.append("validation_summary.markdown_included must be true")
    if summary.get("machine_readable_included") is not True:
        errors.append("validation_summary.machine_readable_included must be true")
    if payload.get("decision") != "no_report_sections" and summary.get("static_report_section_ready") is not True:
        errors.append("validation_summary.static_report_section_ready must be true")
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
    expected = {
        "fixture_only": True,
        "repo_only": True,
        "advisory_only": True,
        "requires_human_review": True,
        "no_trading": True,
        "no_notification": True,
        "no_production_db_write": True,
        "no_runtime_weight_change": True,
        "static_report_contract_only": True,
    }
    for key, value in expected.items():
        if safety.get(key) is not value:
            errors.append(f"safety.{key} must be {str(value).lower()}")
    return errors


def validate_payload(payload: Any) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return {"ok": False, "errors": ["result root must be an object"]}
    for key in missing(payload, TOP_LEVEL):
        errors.append(f"missing top-level field: {key}")
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    if payload.get("decision") not in DECISIONS:
        errors.append("decision is invalid")
    if payload.get("mode") != "fixture_dry_run":
        errors.append("mode must be fixture_dry_run")
    if payload.get("ok") is not True and payload.get("decision") != "no_report_sections":
        errors.append("ok must be true for completed section decisions")
    errors.extend(validate_source_summary(payload))
    errors.extend(validate_section(payload))
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
        for term in FORBIDDEN_SOURCE_TERMS:
            if term in lowered:
                errors.append(f"forbidden live runtime source detected: {term}")
        for pattern in FORBIDDEN_TRADING_TEXT:
            if pattern.search(text):
                errors.append(f"possible trading/order instruction detected: {text}")
    source = payload.get("source_summary") if isinstance(payload.get("source_summary"), dict) else {}
    validation = payload.get("validation_summary") if isinstance(payload.get("validation_summary"), dict) else {}
    return {
        "ok": not errors,
        "run_id": payload.get("run_id"),
        "decision": payload.get("decision"),
        "source_section_count": source.get("source_section_count"),
        "section_count": validation.get("section_count"),
        "errors": errors,
        "side_effects": {key: False for key in SIDE_EFFECTS_FALSE},
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Daily Report Forecast Review Section V1 result JSON.")
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
