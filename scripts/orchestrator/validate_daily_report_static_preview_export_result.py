#!/usr/bin/env python3
"""Validate Daily Report Static Preview Export V1 fixture results."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "daily_report_static_preview_export_v1"
RENDERER_SCHEMA_VERSION = "daily_report_renderer_contract_v1"
DECISIONS = {
    "daily_report_static_preview_export_completed",
    "daily_report_static_preview_export_completed_with_warnings",
    "validation_failed",
    "blocked",
}
TOP_LEVEL = [
    "schema_version",
    "task_id",
    "run_id",
    "generated_at",
    "mode",
    "preview_package",
    "preview_manifest",
    "preview_files",
    "renderer_source_summary",
    "report_sections",
    "markdown_preview",
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
    "advisory_only",
    "preview_only",
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


def validate_preview_package(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    package = payload.get("preview_package")
    if not isinstance(package, dict):
        return ["preview_package must be an object"]
    for key in [
        "package_id",
        "preview_id",
        "export_title",
        "renderer_result_path",
        "artifact_count",
        "artifact_names",
        "intended_consumers",
        "delivery_authorized",
    ]:
        if key not in package:
            errors.append(f"preview_package missing {key}")
    if package.get("delivery_authorized") is not False:
        errors.append("preview_package.delivery_authorized must be false")
    if package.get("artifact_count") != 6:
        errors.append("preview_package.artifact_count must be 6")
    return errors


def validate_renderer_source_summary(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    summary = payload.get("renderer_source_summary")
    if not isinstance(summary, dict):
        return ["renderer_source_summary must be an object"]
    expected = {
        "source_schema_version": RENDERER_SCHEMA_VERSION,
        "source_ok": True,
        "source_mode": "fixture_dry_run",
        "source_markdown_included": True,
        "source_render_payload_included": True,
    }
    for key, value in expected.items():
        if summary.get(key) != value:
            errors.append(f"renderer_source_summary.{key} is invalid")
    if not isinstance(summary.get("source_path"), str) or not summary.get("source_path"):
        errors.append("renderer_source_summary.source_path must be a non-empty string")
    return errors


def validate_report_sections(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    sections = payload.get("report_sections")
    if not isinstance(sections, list):
        return ["report_sections must be a list"]
    if len(sections) != 2:
        errors.append("report_sections must contain forecast review and intelligence sections")
    expected_order = ["forecast_review", "daily_report_intelligence"]
    actual_order: list[Any] = []
    for index, section in enumerate(sections):
        prefix = f"report_sections[{index}]"
        if not isinstance(section, dict):
            errors.append(f"{prefix} must be an object")
            continue
        actual_order.append(section.get("section_id"))
        for key in [
            "index",
            "section_id",
            "title",
            "placement",
            "priority",
            "source_refs",
            "advisory_only",
            "requires_human_review",
            "markdown_char_count",
            "machine_readable_included",
        ]:
            if key not in section:
                errors.append(f"{prefix} missing {key}")
        if section.get("index") != index + 1:
            errors.append(f"{prefix}.index is invalid")
        if not isinstance(section.get("source_refs"), list) or not section.get("source_refs"):
            errors.append(f"{prefix}.source_refs must be a non-empty list")
        if section.get("advisory_only") is not True:
            errors.append(f"{prefix}.advisory_only must be true")
        if section.get("requires_human_review") is not True:
            errors.append(f"{prefix}.requires_human_review must be true")
        if section.get("machine_readable_included") is not True:
            errors.append(f"{prefix}.machine_readable_included must be true")
        if not isinstance(section.get("markdown_char_count"), int) or section.get("markdown_char_count") <= 0:
            errors.append(f"{prefix}.markdown_char_count must be positive")
    if actual_order != expected_order:
        errors.append("report_sections order must preserve forecast_review then daily_report_intelligence")
    return errors


def validate_preview_manifest(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    manifest = payload.get("preview_manifest")
    if not isinstance(manifest, dict):
        return ["preview_manifest must be an object"]
    for key in [
        "schema_version",
        "manifest_id",
        "preview_id",
        "package_id",
        "generated_at",
        "mode",
        "renderer_source",
        "artifacts",
        "section_index",
        "validation_summary",
        "safety",
        "delivery_authorized",
        "external_runtime_authorized",
    ]:
        if key not in manifest:
            errors.append(f"preview_manifest missing {key}")
    if manifest.get("schema_version") != "daily_report_static_preview_manifest_v1":
        errors.append("preview_manifest.schema_version is invalid")
    if manifest.get("mode") != "fixture_dry_run":
        errors.append("preview_manifest.mode must be fixture_dry_run")
    if manifest.get("delivery_authorized") is not False:
        errors.append("preview_manifest.delivery_authorized must be false")
    if manifest.get("external_runtime_authorized") is not False:
        errors.append("preview_manifest.external_runtime_authorized must be false")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        errors.append("preview_manifest.artifacts must be an object")
    else:
        for name in [
            "manifest_json",
            "result_json",
            "markdown_preview",
            "section_index",
            "validation_summary",
            "safety_summary",
        ]:
            artifact = artifacts.get(name)
            if not isinstance(artifact, dict):
                errors.append(f"preview_manifest.artifacts.{name} must be an object")
                continue
            if not artifact.get("path"):
                errors.append(f"preview_manifest.artifacts.{name}.path must be present")
            if name in {"manifest_json", "result_json"}:
                if artifact.get("sha256_scope") != "omitted_for_self_referential_artifact":
                    errors.append(f"preview_manifest.artifacts.{name}.sha256_scope is invalid")
                continue
            if not isinstance(artifact.get("sha256"), str) or len(artifact.get("sha256", "")) != 64:
                errors.append(f"preview_manifest.artifacts.{name}.sha256 must be a sha256 hex string")
    if manifest.get("section_index") != payload.get("report_sections"):
        errors.append("preview_manifest.section_index must match report_sections")
    return errors


def validate_validation_summary(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    summary = payload.get("validation_summary")
    if not isinstance(summary, dict):
        return ["validation_summary must be an object"]
    expected = {
        "source_schema_matched": True,
        "source_ok": True,
        "source_mode_fixture_dry_run": True,
        "preview_manifest_included": True,
        "markdown_preview_included": True,
        "section_index_included": True,
        "section_count": 2,
        "source_section_order_preserved": True,
        "validation_summary_included": True,
        "safety_summary_included": True,
        "deterministic_output": True,
        "fixture_only": True,
    }
    for key, value in expected.items():
        if summary.get(key) != value:
            errors.append(f"validation_summary.{key} is invalid")
    if summary.get("source_schema_expected") != RENDERER_SCHEMA_VERSION:
        errors.append("validation_summary.source_schema_expected is invalid")
    if not isinstance(summary.get("warnings"), list):
        errors.append("validation_summary.warnings must be a list")
    return errors


def validate_preview_files(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    files = payload.get("preview_files")
    if not isinstance(files, dict):
        return ["preview_files must be an object"]
    for key in [
        "result_json",
        "manifest_json",
        "markdown_preview",
        "section_index",
        "validation_summary",
        "safety_summary",
    ]:
        if key not in files or not files.get(key):
            errors.append(f"preview_files.{key} must be present")
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
    if not isinstance(payload.get("markdown_preview"), str) or not payload.get("markdown_preview", "").strip():
        errors.append("markdown_preview must be a non-empty string")
    if "Static preview package only" not in str(payload.get("markdown_preview")):
        errors.append("markdown_preview must include static preview warning")
    errors.extend(validate_preview_package(payload))
    errors.extend(validate_preview_manifest(payload))
    errors.extend(validate_preview_files(payload))
    errors.extend(validate_renderer_source_summary(payload))
    errors.extend(validate_report_sections(payload))
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
    validation = payload.get("validation_summary") if isinstance(payload.get("validation_summary"), dict) else {}
    return {
        "ok": not errors,
        "run_id": payload.get("run_id"),
        "decision": payload.get("decision"),
        "section_count": validation.get("section_count"),
        "deterministic_output": validation.get("deterministic_output"),
        "errors": errors,
        "side_effects": {key: False for key in SIDE_EFFECTS_FALSE},
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Daily Report Static Preview Export V1 result JSON.")
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
