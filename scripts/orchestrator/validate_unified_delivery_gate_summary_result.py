#!/usr/bin/env python3
"""Validate Unified Delivery Gate Summary V1 fixture results."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "unified_delivery_gate_summary_v1"
SUMMARY_SCHEMA_VERSION = "unified_delivery_gate_summary_only_v1"
CONTRACT_NAME = "unified_delivery_gate_summary"
CONTRACT_VERSION = "v1"
CHANNELS = ["email", "line", "dashboard"]
DECISIONS = {
    "unified_delivery_gate_summary_completed",
    "unified_delivery_gate_summary_completed_with_warnings",
    "unified_delivery_blocked_pending_approval",
    "validation_failed",
    "blocked",
}
TOP_LEVEL = [
    "schema_version",
    "task_id",
    "run_id",
    "generated_at",
    "mode",
    "unified_delivery_gate_summary",
    "delivery_readiness_summary",
    "validation_summary",
    "side_effects",
    "safety",
    "ok",
    "decision",
    "next_recommendation",
]
SUMMARY_FIELDS = [
    "summary_id",
    "report_date",
    "payload_id",
    "review_id",
    "review_status",
    "approval_gate",
    "delivery_allowed",
    "channels",
    "channel_statuses",
    "blocked_channels",
    "ready_channels",
    "delivery_blockers",
    "warning_badges",
    "human_review_required",
    "advisory_disclaimer",
    "final_delivery_decision",
]
CHANNEL_STATUS_FIELDS = [
    "channel",
    "source",
    "status",
    "review_status",
    "approval_gate_open",
    "delivery_allowed",
    "channel_enabled",
    "approved_and_enabled",
    "blocked",
    "delivery_blockers",
    "warning_badge_count",
    "human_review_required",
    "action_status",
]
SIDE_EFFECTS_FALSE = [
    "read_secrets",
    "called_external_model_runtime",
    "called_market_data_runtime",
    "sent_notification",
    "sent_email",
    "called_smtp",
    "called_gmail_api",
    "sent_line_push",
    "called_line_api",
    "deployed_dashboard",
    "created_api_server",
    "placed_trade_order",
    "modified_portfolio",
    "wrote_persistent_store",
    "modified_schedule_or_service",
    "modified_github_remote",
]
SAFETY_TRUE = [
    "repo_only",
    "fixture_only",
    "advisory_only",
    "preview_only",
    "no_external_model_calls",
    "no_market_data_calls",
    "no_delivery_actions",
    "no_email_send",
    "no_line_push",
    "no_dashboard_deploy",
    "no_smtp_call",
    "no_gmail_api_call",
    "no_api_server_created",
    "no_persistent_store_writes",
    "no_portfolio_actions",
    "no_schedule_service_changes",
]
SAFETY_FALSE = ["dashboard_deploy", "api_server_created", "trading_instruction"]
SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{20,}"),
    re.compile(r"AIza[0-9A-Za-z_-]{20,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{20,}", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
]
FORBIDDEN_RUNTIME_TERMS = ["shioaji", "production_db", "webhook", "broker"]
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


def validate_channel_statuses(summary: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    statuses = summary.get("channel_statuses")
    if not isinstance(statuses, dict):
        return ["unified_delivery_gate_summary.channel_statuses must be an object"]
    if set(statuses.keys()) != set(CHANNELS):
        errors.append("unified_delivery_gate_summary.channel_statuses must include email, line, dashboard")
    for channel in CHANNELS:
        status = statuses.get(channel)
        if not isinstance(status, dict):
            errors.append(f"channel_statuses.{channel} must be an object")
            continue
        for key in missing(status, CHANNEL_STATUS_FIELDS):
            errors.append(f"channel_statuses.{channel} missing {key}")
        if status.get("channel") != channel:
            errors.append(f"channel_statuses.{channel}.channel must match key")
        if status.get("status") not in {"ready", "blocked"}:
            errors.append(f"channel_statuses.{channel}.status is invalid")
        expected_ready = (
            status.get("review_status") == "approved"
            and status.get("approval_gate_open") is True
            and status.get("delivery_allowed") is True
            and status.get("channel_enabled") is True
            and as_dict(status.get("source")).get("source_ok") is True
            and as_dict(status.get("source")).get("source_schema_matched") is True
        )
        if status.get("approved_and_enabled") is not expected_ready:
            errors.append(f"channel_statuses.{channel}.approved_and_enabled policy is invalid")
        if status.get("blocked") is (status.get("approved_and_enabled") is True):
            errors.append(f"channel_statuses.{channel}.blocked must be inverse of approved_and_enabled")
        if status.get("status") != ("ready" if expected_ready else "blocked"):
            errors.append(f"channel_statuses.{channel}.status must match approved_and_enabled")
        if not isinstance(status.get("delivery_blockers"), list):
            errors.append(f"channel_statuses.{channel}.delivery_blockers must be a list")
        if not isinstance(status.get("warning_badge_count"), int) or status.get("warning_badge_count", -1) < 0:
            errors.append(f"channel_statuses.{channel}.warning_badge_count must be a non-negative integer")
    return errors


def validate_unified_summary(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    summary = payload.get("unified_delivery_gate_summary")
    if not isinstance(summary, dict):
        return ["unified_delivery_gate_summary must be an object"]
    for key in missing(summary, SUMMARY_FIELDS):
        errors.append(f"unified_delivery_gate_summary missing {key}")
    if not re.fullmatch(r"20\d{2}-\d{2}-\d{2}", str(summary.get("report_date", ""))):
        errors.append("unified_delivery_gate_summary.report_date must be YYYY-MM-DD")
    for key in ["summary_id", "payload_id", "review_id", "review_status", "advisory_disclaimer"]:
        if not str(summary.get(key, "")).strip():
            errors.append(f"unified_delivery_gate_summary.{key} is required")
    if summary.get("channels") != CHANNELS:
        errors.append("unified_delivery_gate_summary.channels must be email, line, dashboard")
    errors.extend(validate_channel_statuses(summary))
    statuses = as_dict(summary.get("channel_statuses"))
    ready_channels = [channel for channel in CHANNELS if as_dict(statuses.get(channel)).get("approved_and_enabled") is True]
    blocked_channels = [channel for channel in CHANNELS if as_dict(statuses.get(channel)).get("approved_and_enabled") is not True]
    if summary.get("ready_channels") != ready_channels:
        errors.append("unified_delivery_gate_summary.ready_channels must match channel statuses")
    if summary.get("blocked_channels") != blocked_channels:
        errors.append("unified_delivery_gate_summary.blocked_channels must match channel statuses")
    expected_allowed = len(ready_channels) == len(CHANNELS)
    if summary.get("delivery_allowed") is not expected_allowed:
        errors.append("unified_delivery_gate_summary.delivery_allowed must require all source gates approved and enabled")
    gate = as_dict(summary.get("approval_gate"))
    if gate.get("required_review_status") != "approved":
        errors.append("unified_delivery_gate_summary.approval_gate.required_review_status must be approved")
    if gate.get("approval_required") is not True:
        errors.append("unified_delivery_gate_summary.approval_gate.approval_required must be true")
    if gate.get("gate_open") is not expected_allowed or gate.get("delivery_allowed") is not expected_allowed:
        errors.append("unified_delivery_gate_summary.approval_gate must match delivery_allowed")
    if gate.get("all_source_gates_approved_and_enabled") is not expected_allowed:
        errors.append("unified_delivery_gate_summary.approval_gate all-source policy is invalid")
    if blocked_channels and summary.get("final_delivery_decision") != "blocked_pending_approval":
        errors.append("unified_delivery_gate_summary.final_delivery_decision must be blocked_pending_approval when any channel is blocked")
    if not blocked_channels and summary.get("final_delivery_decision") not in {
        "approved_preview_only",
        "approved_with_warnings_preview_only",
    }:
        errors.append("unified_delivery_gate_summary.final_delivery_decision is invalid")
    if not isinstance(summary.get("delivery_blockers"), list):
        errors.append("unified_delivery_gate_summary.delivery_blockers must be a list")
    if not isinstance(summary.get("warning_badges"), list):
        errors.append("unified_delivery_gate_summary.warning_badges must be a list")
    if not isinstance(summary.get("human_review_required"), bool):
        errors.append("unified_delivery_gate_summary.human_review_required must be boolean")
    if blocked_channels and summary.get("human_review_required") is not True:
        errors.append("unified_delivery_gate_summary.human_review_required must be true when blocked")
    return errors


def validate_readiness_summary(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    readiness = payload.get("delivery_readiness_summary")
    summary = as_dict(payload.get("unified_delivery_gate_summary"))
    if not isinstance(readiness, dict):
        return ["delivery_readiness_summary must be an object"]
    if readiness.get("schema_version") != SUMMARY_SCHEMA_VERSION:
        errors.append("delivery_readiness_summary.schema_version is invalid")
    for key in [
        "summary_id",
        "report_date",
        "payload_id",
        "review_id",
        "review_status",
        "delivery_allowed",
        "final_delivery_decision",
        "blocked_channels",
        "ready_channels",
        "human_review_required",
    ]:
        if readiness.get(key) != summary.get(key):
            errors.append(f"delivery_readiness_summary.{key} must match unified_delivery_gate_summary")
    if readiness.get("channel_count") != len(as_list(summary.get("channels"))):
        errors.append("delivery_readiness_summary.channel_count must match channels")
    if readiness.get("blocked_channel_count") != len(as_list(summary.get("blocked_channels"))):
        errors.append("delivery_readiness_summary.blocked_channel_count must match blocked_channels")
    if readiness.get("ready_channel_count") != len(as_list(summary.get("ready_channels"))):
        errors.append("delivery_readiness_summary.ready_channel_count must match ready_channels")
    if readiness.get("delivery_blocker_count") != len(as_list(summary.get("delivery_blockers"))):
        errors.append("delivery_readiness_summary.delivery_blocker_count must match delivery_blockers")
    if readiness.get("warning_badge_count") != len(as_list(summary.get("warning_badges"))):
        errors.append("delivery_readiness_summary.warning_badge_count must match warning_badges")
    return errors


def validate_validation_summary(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    validation = payload.get("validation_summary")
    if not isinstance(validation, dict):
        return ["validation_summary must be an object"]
    expected = {
        "contract_name": CONTRACT_NAME,
        "contract_version": CONTRACT_VERSION,
        "deterministic_output": True,
        "fixture_only": True,
        "preview_only": True,
        "advisory_only": True,
        "required_channels_present": True,
        "source_schemas_matched": True,
        "source_results_ok": True,
        "approval_gate_required": True,
        "delivery_allowed_policy_enforced": True,
        "blocked_requires_pending_approval": True,
        "no_delivery_actions": True,
    }
    for key, value in expected.items():
        if validation.get(key) != value:
            errors.append(f"validation_summary.{key} is invalid")
    for key in ["warning_count", "delivery_blocker_count", "blocked_channel_count", "ready_channel_count"]:
        if not isinstance(validation.get(key), int) or validation.get(key, -1) < 0:
            errors.append(f"validation_summary.{key} must be a non-negative integer")
    if not isinstance(validation.get("warnings"), list):
        errors.append("validation_summary.warnings must be a list")
    return errors


def validate_side_effects(payload: dict[str, Any]) -> list[str]:
    side_effects = payload.get("side_effects")
    if not isinstance(side_effects, dict):
        return ["side_effects must be an object"]
    return [f"side_effects.{key} must be false" for key in SIDE_EFFECTS_FALSE if side_effects.get(key) is not False]


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
    return errors


def validate_payload(payload: Any) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return {"ok": False, "errors": ["result root must be an object"]}
    for key in missing(payload, TOP_LEVEL):
        errors.append(f"missing top-level field: {key}")
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    if payload.get("task_id") != "AI-DEV-097":
        errors.append("task_id must be AI-DEV-097")
    if payload.get("mode") != "fixture_dry_run":
        errors.append("mode must be fixture_dry_run")
    if payload.get("decision") not in DECISIONS:
        errors.append("decision is invalid")
    if payload.get("ok") is not True and payload.get("decision") not in {"validation_failed", "blocked"}:
        errors.append("ok must be true for completed decisions")
    errors.extend(validate_unified_summary(payload))
    errors.extend(validate_readiness_summary(payload))
    errors.extend(validate_validation_summary(payload))
    errors.extend(validate_side_effects(payload))
    errors.extend(validate_safety(payload))
    rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    for pattern in SECRET_PATTERNS:
        if pattern.search(rendered):
            errors.append(f"secret-like text detected: {pattern.pattern}")
            break
    for text in iter_strings(payload):
        lowered = text.lower()
        for term in FORBIDDEN_RUNTIME_TERMS:
            if term in lowered:
                errors.append(f"forbidden live runtime source detected: {term}")
        for pattern in FORBIDDEN_TRADING_TEXT:
            if pattern.search(text):
                errors.append(f"possible trading/order instruction detected: {text}")
    summary = as_dict(payload.get("unified_delivery_gate_summary"))
    validation = as_dict(payload.get("validation_summary"))
    return {
        "ok": not errors,
        "run_id": payload.get("run_id"),
        "decision": payload.get("decision"),
        "delivery_allowed": summary.get("delivery_allowed"),
        "final_delivery_decision": summary.get("final_delivery_decision"),
        "blocked_channels": summary.get("blocked_channels"),
        "ready_channels": summary.get("ready_channels"),
        "deterministic_output": validation.get("deterministic_output"),
        "errors": errors,
        "side_effects": {key: False for key in SIDE_EFFECTS_FALSE},
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Unified Delivery Gate Summary V1 result JSON.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload, load_errors = load_json(Path(args.input))
    result = {"ok": False, "errors": load_errors, "decision": "validation_failed"} if load_errors else validate_payload(payload)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
