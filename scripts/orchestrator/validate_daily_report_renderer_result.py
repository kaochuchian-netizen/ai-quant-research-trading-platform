#!/usr/bin/env python3
"""Validate Daily Report Renderer Contract V1 fixture results."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "daily_report_renderer_contract_v1"
RESEARCH_PACK_SCHEMA_VERSION = "daily_report_research_pack_v1"
DECISIONS = {
    "daily_report_renderer_completed",
    "daily_report_renderer_completed_with_warnings",
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
    "render_payload",
    "report_title",
    "report_date",
    "report_sections",
    "markdown",
    "section_order",
    "risk_and_limitations",
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
]
SAFETY_TRUE = [
    "repo_only",
    "fixture_only",
    "advisory_only",
    "requires_human_review",
    "no_external_model_calls",
    "no_market_data_calls",
    "no_delivery_actions",
    "no_persistent_store_writes",
    "no_portfolio_actions",
    "no_schedule_service_changes",
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
FORBIDDEN_RUNTIME_TERMS = ["broker", "shioaji", "production_db", "yfinance", "webhook"]
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


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


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
    summary = payload.get("source_summary")
    if not isinstance(summary, dict):
        return ["source_summary must be an object"]
    expected = {
        "source_schema_version": RESEARCH_PACK_SCHEMA_VERSION,
        "source_ok": True,
        "source_credibility_metadata_preserved": True,
    }
    for key, value in expected.items():
        if summary.get(key) != value:
            errors.append(f"source_summary.{key} is invalid")
    if not isinstance(summary.get("source_path"), str) or not summary.get("source_path"):
        errors.append("source_summary.source_path must be a non-empty string")
    return errors


def validate_section_metadata(section: Any, prefix: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(section, dict):
        return [f"{prefix} must be an object"]
    for key in [
        "section_id",
        "title",
        "placement",
        "priority",
        "source_refs",
        "advisory_only",
        "requires_human_review",
    ]:
        if key not in section:
            errors.append(f"{prefix} missing {key}")
    if not isinstance(section.get("source_refs"), list) or not section.get("source_refs"):
        errors.append(f"{prefix}.source_refs must be a non-empty list")
    if section.get("advisory_only") is not True:
        errors.append(f"{prefix}.advisory_only must be true")
    if section.get("requires_human_review") is not True:
        errors.append(f"{prefix}.requires_human_review must be true")
    return errors


def validate_report_sections(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    sections = payload.get("report_sections")
    if not isinstance(sections, list):
        return ["report_sections must be a list"]
    if len(sections) != 2:
        errors.append("report_sections must contain forecast review and intelligence sections")
    for index, section in enumerate(sections):
        prefix = f"report_sections[{index}]"
        errors.extend(validate_section_metadata(section, prefix))
        if isinstance(section, dict):
            if section.get("render_mode") != "static_markdown_with_machine_readable_payload":
                errors.append(f"{prefix}.render_mode is invalid")
            if not isinstance(section.get("markdown"), str) or not section.get("markdown", "").strip():
                errors.append(f"{prefix}.markdown must be a non-empty string")
            if not isinstance(section.get("machine_readable"), dict):
                errors.append(f"{prefix}.machine_readable must be an object")
    section_order = payload.get("section_order")
    if not isinstance(section_order, list) or not section_order:
        errors.append("section_order must be a non-empty list")
        section_order = []
    actual_order = [section.get("section_id") for section in sections if isinstance(section, dict)]
    if section_order != actual_order:
        errors.append("section_order must match report_sections order")
    if actual_order != ["forecast_review", "daily_report_intelligence"]:
        errors.append("section_order must preserve forecast_review then daily_report_intelligence")
    return errors


def validate_render_payload(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    render_payload = payload.get("render_payload")
    if not isinstance(render_payload, dict):
        return ["render_payload must be an object"]
    for key in [
        "payload_id",
        "render_mode",
        "intended_report_slot",
        "report_title",
        "report_date",
        "section_order",
        "sections",
        "source_credibility_summary",
        "source_refs",
        "advisory_only",
        "requires_human_review",
    ]:
        if key not in render_payload:
            errors.append(f"render_payload missing {key}")
    if render_payload.get("render_mode") != "static_markdown_with_machine_readable_payload":
        errors.append("render_payload.render_mode is invalid")
    if render_payload.get("report_title") != payload.get("report_title"):
        errors.append("render_payload.report_title must match report_title")
    if render_payload.get("report_date") != payload.get("report_date"):
        errors.append("render_payload.report_date must match report_date")
    if render_payload.get("section_order") != payload.get("section_order"):
        errors.append("render_payload.section_order must match section_order")
    if render_payload.get("advisory_only") is not True:
        errors.append("render_payload.advisory_only must be true")
    if render_payload.get("requires_human_review") is not True:
        errors.append("render_payload.requires_human_review must be true")
    sections = render_payload.get("sections")
    if not isinstance(sections, list):
        errors.append("render_payload.sections must be a list")
    else:
        for index, section in enumerate(sections):
            errors.extend(validate_section_metadata(section, f"render_payload.sections[{index}]"))
    credibility = render_payload.get("source_credibility_summary")
    if not isinstance(credibility, dict):
        errors.append("render_payload.source_credibility_summary must be an object")
    else:
        if credibility.get("metadata_preserved") is not True:
            errors.append("render_payload.source_credibility_summary.metadata_preserved must be true")
        if credibility.get("advisory_only") is not True or credibility.get("requires_human_review") is not True:
            errors.append("render_payload.source_credibility_summary must be advisory-only and require human review")
    return errors


def validate_validation_summary(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    summary = payload.get("validation_summary")
    if not isinstance(summary, dict):
        return ["validation_summary must be an object"]
    expected = {
        "source_schema_matched": True,
        "source_ok": True,
        "section_count": 2,
        "section_order_preserved": True,
        "section_metadata_included": True,
        "source_refs_preserved": True,
        "source_credibility_metadata_preserved": True,
        "risk_and_limitations_preserved": True,
        "markdown_included": True,
        "machine_readable_render_payload_included": True,
        "deterministic_output": True,
        "fixture_only": True,
    }
    for key, value in expected.items():
        if summary.get(key) != value:
            errors.append(f"validation_summary.{key} is invalid")
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
    if not isinstance(payload.get("report_title"), str) or not payload.get("report_title"):
        errors.append("report_title must be a non-empty string")
    if not isinstance(payload.get("report_date"), str) or not payload.get("report_date"):
        errors.append("report_date must be a non-empty string")
    if not isinstance(payload.get("markdown"), str) or not payload.get("markdown", "").strip():
        errors.append("markdown must be a non-empty string")
    if "Requires human review" not in str(payload.get("markdown")):
        errors.append("markdown must preserve human-review warning")
    errors.extend(validate_source_summary(payload))
    errors.extend(validate_render_payload(payload))
    errors.extend(validate_report_sections(payload))
    if not isinstance(payload.get("risk_and_limitations"), list) or not payload.get("risk_and_limitations"):
        errors.append("risk_and_limitations must be a non-empty list")
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
        for term in FORBIDDEN_RUNTIME_TERMS:
            if term in lowered:
                errors.append(f"forbidden live runtime source detected: {term}")
        for pattern in FORBIDDEN_TRADING_TEXT:
            if pattern.search(text):
                errors.append(f"possible trading/order instruction detected: {text}")
    validation = payload.get("validation_summary") if isinstance(payload.get("validation_summary"), dict) else {}
    return {
        "ok": not errors,
        "run_id": payload.get("run_id"),
        "decision": payload.get("decision"),
        "section_order": payload.get("section_order"),
        "deterministic_output": validation.get("deterministic_output"),
        "errors": errors,
        "side_effects": {key: False for key in SIDE_EFFECTS_FALSE},
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Daily Report Renderer Contract V1 result JSON.")
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
