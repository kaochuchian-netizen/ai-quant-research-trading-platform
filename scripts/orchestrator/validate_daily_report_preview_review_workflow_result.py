#!/usr/bin/env python3
"""Validate Daily Report Preview Review Workflow V1 fixture results."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "daily_report_preview_review_workflow_v1"
SOURCE_SCHEMA_VERSION = "daily_report_dashboard_static_page_v1"
SUPPORTED_REVIEW_STATUSES = {"pending_review", "approved", "rejected", "needs_revision"}
DECISIONS = {
    "daily_report_preview_review_workflow_completed",
    "daily_report_preview_review_workflow_completed_with_warnings",
    "validation_failed",
    "blocked",
}
TOP_LEVEL = [
    "schema_version",
    "task_id",
    "run_id",
    "generated_at",
    "mode",
    "preview_review_workflow",
    "review_status",
    "approval_gate",
    "delivery_allowed",
    "reviewer_notes",
    "source_dashboard_static_page_summary",
    "validation_summary",
    "side_effects",
    "safety",
    "ok",
    "decision",
    "next_recommendation",
]
WORKFLOW_KEYS = [
    "review_id",
    "preview_id",
    "report_date",
    "review_status",
    "reviewer",
    "reviewer_notes",
    "approval_gate",
    "approved_at",
    "rejected_at",
    "revision_requested_at",
    "revision_notes",
    "source_dashboard_page_ref",
    "manifest_ref",
    "markdown_ref",
    "warning_badges",
    "requires_human_review",
    "delivery_allowed",
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
    "deployed_dashboard",
    "created_api_server",
]
SAFETY_TRUE = [
    "repo_only",
    "fixture_only",
    "preview_only",
    "advisory_only",
    "no_external_model_calls",
    "no_market_data_calls",
    "no_delivery_actions",
    "no_persistent_store_writes",
    "no_portfolio_actions",
    "no_schedule_service_changes",
]
SAFETY_FALSE = ["dashboard_deploy", "api_server_created"]
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


def validate_workflow(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    workflow = payload.get("preview_review_workflow")
    if not isinstance(workflow, dict):
        return ["preview_review_workflow must be an object"]
    for key in missing(workflow, WORKFLOW_KEYS):
        errors.append(f"preview_review_workflow missing {key}")
    status = workflow.get("review_status")
    delivery_allowed = workflow.get("delivery_allowed")
    if status not in SUPPORTED_REVIEW_STATUSES:
        errors.append("preview_review_workflow.review_status is invalid")
    if payload.get("review_status") != status:
        errors.append("review_status must match preview_review_workflow.review_status")
    if payload.get("delivery_allowed") != delivery_allowed:
        errors.append("delivery_allowed must match preview_review_workflow.delivery_allowed")
    if delivery_allowed is not (status == "approved"):
        errors.append("delivery_allowed must be true only when review_status is approved")
    for key in ["review_id", "preview_id", "report_date", "reviewer", "source_dashboard_page_ref", "manifest_ref", "markdown_ref"]:
        if not isinstance(workflow.get(key), str) or not workflow.get(key):
            errors.append(f"preview_review_workflow.{key} must be a non-empty string")
    if not re.fullmatch(r"20\d{2}-\d{2}-\d{2}", str(workflow.get("report_date", ""))):
        errors.append("preview_review_workflow.report_date must be YYYY-MM-DD")
    if not isinstance(workflow.get("reviewer_notes"), list):
        errors.append("preview_review_workflow.reviewer_notes must be a list")
    if payload.get("reviewer_notes") != workflow.get("reviewer_notes"):
        errors.append("reviewer_notes must match preview_review_workflow.reviewer_notes")
    if not isinstance(workflow.get("revision_notes"), list):
        errors.append("preview_review_workflow.revision_notes must be a list")
    if not isinstance(workflow.get("warning_badges"), list):
        errors.append("preview_review_workflow.warning_badges must be a list")
    if not isinstance(workflow.get("requires_human_review"), bool):
        errors.append("preview_review_workflow.requires_human_review must be boolean")
    timestamp_expectations = {
        "approved_at": status == "approved",
        "rejected_at": status == "rejected",
        "revision_requested_at": status == "needs_revision",
    }
    for key, should_have_value in timestamp_expectations.items():
        value = workflow.get(key)
        if should_have_value and not isinstance(value, str):
            errors.append(f"preview_review_workflow.{key} must be set for {status}")
        if not should_have_value and value is not None:
            errors.append(f"preview_review_workflow.{key} must be null for {status}")
    return errors


def validate_approval_gate(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    workflow = as_dict(payload.get("preview_review_workflow"))
    gate = payload.get("approval_gate")
    if not isinstance(gate, dict):
        return ["approval_gate must be an object"]
    if gate != workflow.get("approval_gate"):
        errors.append("approval_gate must match preview_review_workflow.approval_gate")
    expected = {
        "required_review_status": "approved",
        "current_review_status": workflow.get("review_status"),
        "delivery_allowed": workflow.get("delivery_allowed"),
        "gate_open": workflow.get("delivery_allowed"),
    }
    for key, value in expected.items():
        if gate.get(key) != value:
            errors.append(f"approval_gate.{key} is invalid")
    if not isinstance(gate.get("gate_id"), str) or not gate.get("gate_id"):
        errors.append("approval_gate.gate_id must be a non-empty string")
    if gate.get("requires_human_review") != workflow.get("requires_human_review"):
        errors.append("approval_gate.requires_human_review must match workflow")
    return errors


def validate_source_summary(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    summary = payload.get("source_dashboard_static_page_summary")
    workflow = as_dict(payload.get("preview_review_workflow"))
    if not isinstance(summary, dict):
        return ["source_dashboard_static_page_summary must be an object"]
    expected = {
        "source_schema_version": SOURCE_SCHEMA_VERSION,
        "source_ok": True,
        "source_mode": "fixture_dry_run",
        "source_preview_id": workflow.get("preview_id"),
        "source_report_date": workflow.get("report_date"),
        "source_manifest_ref": workflow.get("manifest_ref"),
        "source_markdown_ref": workflow.get("markdown_ref"),
    }
    for key, value in expected.items():
        if summary.get(key) != value:
            errors.append(f"source_dashboard_static_page_summary.{key} is invalid")
    for key in ["source_path", "source_page_id", "source_run_id"]:
        if not isinstance(summary.get(key), str) or not summary.get(key):
            errors.append(f"source_dashboard_static_page_summary.{key} must be a non-empty string")
    return errors


def validate_validation_summary(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    summary = payload.get("validation_summary")
    workflow = as_dict(payload.get("preview_review_workflow"))
    if not isinstance(summary, dict):
        return ["validation_summary must be an object"]
    expected = {
        "source_schema_expected": SOURCE_SCHEMA_VERSION,
        "source_schema_matched": True,
        "source_ok": True,
        "source_mode_fixture_dry_run": True,
        "supported_review_status": True,
        "approval_gate_included": True,
        "approval_gate_enforced": True,
        "delivery_allowed_policy_enforced": True,
        "reviewer_notes_included": True,
        "warning_badges_included": True,
        "source_refs_present": True,
        "deterministic_output": True,
        "fixture_only": True,
    }
    for key, value in expected.items():
        if summary.get(key) != value:
            errors.append(f"validation_summary.{key} is invalid")
    if not isinstance(summary.get("warnings"), list):
        errors.append("validation_summary.warnings must be a list")
    if len(as_list(summary.get("warnings"))) != len(as_list(workflow.get("warning_badges"))):
        errors.append("validation_summary.warnings must match warning_badges count")
    return errors


def validate_side_effects(payload: dict[str, Any]) -> list[str]:
    side_effects = payload.get("side_effects")
    if not isinstance(side_effects, dict):
        return ["side_effects must be an object"]
    return [
        f"side_effects.{key} must be false"
        for key in SIDE_EFFECTS_FALSE
        if side_effects.get(key) is not False
    ]


def validate_safety(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    safety = payload.get("safety")
    if not isinstance(safety, dict):
        return ["safety must be an object"]
    for key in SAFETY_TRUE:
        if safety.get(key) is not True:
            errors.append(f"safety.{key} must be true")
    for key in SAFETY_FALSE:
        if safety.get(key) is not False:
            errors.append(f"safety.{key} must be false")
    if safety.get("delivery_allowed") != payload.get("delivery_allowed"):
        errors.append("safety.delivery_allowed must match top-level delivery_allowed")
    return errors


def validate_payload(payload: Any) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return {"ok": False, "errors": ["result root must be an object"]}
    for key in missing(payload, TOP_LEVEL):
        errors.append(f"missing top-level field: {key}")
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    if payload.get("task_id") != "AI-DEV-089":
        errors.append("task_id must be AI-DEV-089")
    if payload.get("mode") != "fixture_dry_run":
        errors.append("mode must be fixture_dry_run")
    if payload.get("decision") not in DECISIONS:
        errors.append("decision is invalid")
    if payload.get("ok") is not True and payload.get("decision") not in {"validation_failed", "blocked"}:
        errors.append("ok must be true for completed decisions")
    errors.extend(validate_workflow(payload))
    errors.extend(validate_approval_gate(payload))
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
        "review_status": payload.get("review_status"),
        "delivery_allowed": payload.get("delivery_allowed"),
        "deterministic_output": validation.get("deterministic_output"),
        "errors": errors,
        "side_effects": {key: False for key in SIDE_EFFECTS_FALSE},
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Daily Report Preview Review Workflow V1 result JSON.")
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
