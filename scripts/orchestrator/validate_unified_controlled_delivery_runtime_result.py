#!/usr/bin/env python3
"""Validate Unified Controlled Delivery Runtime V1 results."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "unified_controlled_delivery_runtime_v1"
SUMMARY_SCHEMA_VERSION = "unified_controlled_delivery_runtime_summary_v1"
TASK_ID = "AI-DEV-107"
DECISIONS = {
    "unified_controlled_delivery_runtime_completed",
    "unified_controlled_delivery_runtime_completed_with_warnings",
    "unified_delivery_blocked_pending_approval",
    "unified_delivery_ready_pending_manual_tests",
    "validation_failed",
    "blocked",
}
TOP_LEVEL = [
    "schema_version",
    "task_id",
    "run_id",
    "generated_at",
    "mode",
    "gate_status",
    "delivery_allowed",
    "approval_status",
    "channels",
    "line_runtime_status",
    "email_runtime_status",
    "dashboard_runtime_status",
    "dashboard_private_url_hint",
    "dashboard_publish_path",
    "line_test_command",
    "email_test_command",
    "dashboard_publish_command",
    "scheduler_activation_command",
    "side_effects",
    "safety",
    "ok",
    "decision",
    "next_recommendation",
]
CHANNELS = ["line", "email", "dashboard"]
SIDE_EFFECTS_FALSE = [
    "read_secrets",
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
    "modified_cron",
    "modified_systemd",
    "modified_timer",
    "modified_service",
    "modified_schedule_or_service",
]
SAFETY_TRUE = [
    "controlled_delivery_runtime",
    "dry_run_default",
    "delivery_gate_required",
    "no_token_printing",
    "no_secret_logging",
    "no_secret_read",
    "no_line_push_by_default",
    "no_email_send_by_default",
    "no_dashboard_publish_by_default",
    "no_smtp_call_by_default",
    "no_gmail_api_call_by_default",
    "no_api_server_created",
    "no_persistent_store_writes",
    "no_portfolio_actions",
    "no_cron_modification",
    "no_systemd_modification",
    "no_timer_modification",
    "no_service_modification",
    "no_schedule_service_changes",
]
SAFETY_FALSE = ["trading_instruction"]
SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{20,}"),
    re.compile(r"AIza[0-9A-Za-z_-]{20,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{20,}", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
]
FORBIDDEN_TEXT = [
    re.compile(r"\b(buy|sell|short|long)\s+(now|today|at market|at open|at close)\b", re.IGNORECASE),
    re.compile(r"\b(place|submit|route|execute)\s+(an?\s+)?order\b", re.IGNORECASE),
]


def load_json(path: Path) -> tuple[Any | None, list[str]]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), []
    except Exception as exc:
        return None, [f"failed to read JSON: {exc}"]


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def iter_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        strings: list[str] = []
        for item in value:
            strings.extend(iter_strings(item))
        return strings
    if isinstance(value, dict):
        strings: list[str] = []
        for item in value.values():
            strings.extend(iter_strings(item))
        return strings
    return []


def missing(data: Any, keys: list[str]) -> list[str]:
    if not isinstance(data, dict):
        return keys
    return [key for key in keys if key not in data]


def validate_gate(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    gate = as_dict(payload.get("gate_status"))
    if gate.get("delivery_allowed") != payload.get("delivery_allowed"):
        errors.append("gate_status.delivery_allowed must match top-level delivery_allowed")
    if gate.get("approval_status") != payload.get("approval_status"):
        errors.append("gate_status.approval_status must match top-level approval_status")
    approved = payload.get("approval_status") in {"approved", "APPROVED"}
    if gate.get("approved") is not approved:
        errors.append("gate_status.approved must match approval_status")
    preconditions = as_dict(gate.get("preconditions"))
    if not isinstance(gate.get("blocked_reasons"), list):
        errors.append("gate_status.blocked_reasons must be a list")
    if gate.get("gate_open") is not all(value is True for value in preconditions.values()):
        errors.append("gate_status.gate_open must require every precondition")
    return errors


def validate_channels(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    channels = payload.get("channels")
    if not isinstance(channels, dict):
        return ["channels must be an object"]
    for channel in CHANNELS:
        item = as_dict(channels.get(channel))
        if not item:
            errors.append(f"channels.{channel} is required")
            continue
        if item.get("runtime_action_allowed") is not False:
            errors.append(f"channels.{channel}.runtime_action_allowed must be false")
        expected_allowed = (
            payload.get("delivery_allowed") is True
            and payload.get("approval_status") in {"approved", "APPROVED"}
            and item.get("enabled") is True
        )
        if item.get("delivery_allowed") is not expected_allowed:
            errors.append(f"channels.{channel}.delivery_allowed is invalid")
    return errors


def validate_runtime_status(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    line = as_dict(payload.get("line_runtime_status"))
    email = as_dict(payload.get("email_runtime_status"))
    dashboard = as_dict(payload.get("dashboard_runtime_status"))
    if line.get("send_attempted") is not False:
        errors.append("line_runtime_status.send_attempted must be false")
    if email.get("send_attempted") is not False:
        errors.append("email_runtime_status.send_attempted must be false")
    if dashboard.get("publish_attempted") is not False:
        errors.append("dashboard_runtime_status.publish_attempted must be false")
    for name, status in [("line", line), ("email", email), ("dashboard", dashboard)]:
        if status.get("requires_separate_user_confirmation") is not True:
            errors.append(f"{name}_runtime_status.requires_separate_user_confirmation must be true")
    presence = as_dict(email.get("runtime_settings_presence"))
    if presence.get("value_printed") is not False:
        errors.append("email_runtime_status.runtime_settings_presence.value_printed must be false")
    return errors


def validate_commands(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    expected = {
        "line_test_command": "--send-test-line",
        "email_test_command": "--send-test-email",
        "dashboard_publish_command": "private_static_dashboard_publish.py",
        "scheduler_activation_command": "production_scheduler_gate_runtime.py",
    }
    for key, needle in expected.items():
        value = str(payload.get(key) or "")
        if needle not in value:
            errors.append(f"{key} must include {needle}")
        if "STOCK_AI_LEGACY_PRODUCTION_APPROVED=1" in value:
            errors.append(f"{key} must not enable legacy production approval")
    return errors


def validate_side_effects(payload: dict[str, Any]) -> list[str]:
    side_effects = payload.get("side_effects")
    if not isinstance(side_effects, dict):
        return ["side_effects must be an object"]
    return [f"side_effects.{key} must be false" for key in SIDE_EFFECTS_FALSE if side_effects.get(key) is not False]


def validate_safety(payload: dict[str, Any]) -> list[str]:
    safety = payload.get("safety")
    if not isinstance(safety, dict):
        return ["safety must be an object"]
    errors: list[str] = []
    for key in SAFETY_TRUE:
        if safety.get(key) is not True:
            errors.append(f"safety.{key} must be true")
    for key in SAFETY_FALSE:
        if safety.get(key) is not False:
            errors.append(f"safety.{key} must be false")
    return errors


def validate_summary(payload: dict[str, Any]) -> list[str]:
    summary = as_dict(payload.get("unified_controlled_delivery_runtime_summary"))
    if not summary:
        return ["unified_controlled_delivery_runtime_summary must be an object"]
    errors: list[str] = []
    if summary.get("schema_version") != SUMMARY_SCHEMA_VERSION:
        errors.append("summary schema_version is invalid")
    for key in ["task_id", "run_id", "generated_at", "mode", "delivery_allowed", "approval_status", "ok", "decision"]:
        if summary.get(key) != payload.get(key):
            errors.append(f"summary.{key} must match top-level field")
    return errors


def validate_payload(payload: Any) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return {"ok": False, "decision": "validation_failed", "errors": ["result root must be an object"]}
    for key in missing(payload, TOP_LEVEL):
        errors.append(f"missing top-level field: {key}")
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    if payload.get("task_id") != TASK_ID:
        errors.append(f"task_id must be {TASK_ID}")
    if payload.get("decision") not in DECISIONS:
        errors.append("decision is invalid")
    if payload.get("ok") is not True:
        errors.append("ok must be true for a controlled dry-run result")
    if not str(payload.get("run_id", "")).strip():
        errors.append("run_id is required")
    if not str(payload.get("generated_at", "")).strip():
        errors.append("generated_at is required")
    if not str(payload.get("next_recommendation", "")).strip():
        errors.append("next_recommendation is required")
    errors.extend(validate_gate(payload))
    errors.extend(validate_channels(payload))
    errors.extend(validate_runtime_status(payload))
    errors.extend(validate_commands(payload))
    errors.extend(validate_side_effects(payload))
    errors.extend(validate_safety(payload))
    errors.extend(validate_summary(payload))
    rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    for pattern in SECRET_PATTERNS:
        if pattern.search(rendered):
            errors.append(f"secret-like text detected: {pattern.pattern}")
            break
    for text in iter_strings(payload):
        for pattern in FORBIDDEN_TEXT:
            if pattern.search(text):
                errors.append(f"possible trading/order instruction detected: {text}")
    return {
        "ok": not errors,
        "run_id": payload.get("run_id"),
        "decision": payload.get("decision"),
        "delivery_allowed": payload.get("delivery_allowed"),
        "approval_status": payload.get("approval_status"),
        "errors": errors,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Unified Controlled Delivery Runtime V1 result JSON.")
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
