#!/usr/bin/env python3
"""Validate Controlled LINE Runtime Reactivation V1 results."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "controlled_line_runtime_reactivation_v1"
SUMMARY_SCHEMA_VERSION = "controlled_line_runtime_summary_v1"
TASK_ID = "AI-DEV-106"
DECISIONS = {
    "controlled_line_runtime_reactivation_completed",
    "controlled_line_runtime_reactivation_completed_with_test_push",
    "line_push_blocked_by_gate",
    "line_push_test_failed",
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
    "line_runtime_status",
    "delivery_allowed",
    "approval_status",
    "line_channel_enabled",
    "push_attempted",
    "push_status",
    "test_message_sent",
    "secret_safety",
    "side_effects",
    "safety",
    "ok",
    "decision",
    "next_recommendation",
]
SIDE_EFFECTS_FALSE_ALWAYS = [
    "sent_email",
    "called_smtp",
    "called_gmail_api",
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
SIDE_EFFECTS_RUNTIME_TRUE_ALLOWED = [
    "read_secrets",
    "sent_notification",
    "sent_line_push",
    "called_line_api",
]
SAFETY_TRUE = [
    "controlled_line_runtime",
    "dry_run_default",
    "delivery_gate_required",
    "no_token_printing",
    "no_secret_logging",
    "no_email_send",
    "no_dashboard_deploy",
    "no_smtp_call",
    "no_gmail_api_call",
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
SECRET_FALSE = [
    "token_printed",
    "secret_logged",
    "secret_values_in_result",
    "dry_run_reads_runtime_secrets",
]
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
    delivery_allowed = payload.get("delivery_allowed")
    approval_status = payload.get("approval_status")
    line_channel_enabled = payload.get("line_channel_enabled")
    if gate.get("delivery_allowed") != delivery_allowed:
        errors.append("gate_status.delivery_allowed must match top-level delivery_allowed")
    if gate.get("approval_status") != approval_status:
        errors.append("gate_status.approval_status must match top-level approval_status")
    if gate.get("line_channel_enabled") != line_channel_enabled:
        errors.append("gate_status.line_channel_enabled must match top-level line_channel_enabled")
    approved = approval_status in {"approved", "APPROVED"}
    if gate.get("approved") is not approved:
        errors.append("gate_status.approved must match approval_status")
    preconditions = as_dict(gate.get("preconditions"))
    expected = {
        "delivery_allowed": delivery_allowed is True,
        "approval_status_approved": approved,
        "line_channel_enabled": line_channel_enabled is True,
    }
    for key, value in expected.items():
        if preconditions.get(key) is not value:
            errors.append(f"gate_status.preconditions.{key} is invalid")
    if gate.get("gate_open") is not all(expected.values()):
        errors.append("gate_status.gate_open must require all preconditions")
    return errors


def validate_runtime(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    runtime = as_dict(payload.get("line_runtime_status"))
    if not str(runtime.get("runtime_id", "")).strip():
        errors.append("line_runtime_status.runtime_id is required")
    if runtime.get("one_shot_test_only") is not True:
        errors.append("line_runtime_status.one_shot_test_only must be true")
    if runtime.get("formal_scheduler_delivery_activation") is not False:
        errors.append("line_runtime_status.formal_scheduler_delivery_activation must be false")
    if runtime.get("send_test_line_requested") is True and runtime.get("dry_run") is not False:
        errors.append("send-test mode must not be marked dry_run")
    if runtime.get("send_test_line_requested") is not True and runtime.get("dry_run") is not True:
        errors.append("default mode must be dry_run")
    attempt = as_dict(runtime.get("runtime_attempt"))
    if attempt.get("attempted") != payload.get("push_attempted"):
        errors.append("runtime_attempt.attempted must match push_attempted")
    if attempt.get("message_marked_as_test") is not True:
        errors.append("runtime_attempt.message_marked_as_test must be true")
    return errors


def validate_status(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    decision = payload.get("decision")
    push_status = payload.get("push_status")
    push_attempted = payload.get("push_attempted")
    test_message_sent = payload.get("test_message_sent")
    gate_open = as_dict(payload.get("gate_status")).get("gate_open") is True
    send_requested = as_dict(payload.get("line_runtime_status")).get("send_test_line_requested") is True
    valid_push_status = {"dry_run_not_sent", "blocked_by_gate", "sent", "failed"}
    if push_status not in valid_push_status:
        errors.append("push_status is invalid")
    if decision not in DECISIONS:
        errors.append("decision is invalid")
    if test_message_sent is True and push_status != "sent":
        errors.append("test_message_sent true requires push_status sent")
    if push_status == "sent" and not (send_requested and gate_open and push_attempted):
        errors.append("sent push requires send request, open gate, and attempted push")
    if push_status == "blocked_by_gate" and gate_open:
        errors.append("blocked_by_gate requires a closed gate")
    if not send_requested and push_attempted is not False:
        errors.append("dry-run mode must not attempt push")
    if not send_requested and test_message_sent is not False:
        errors.append("dry-run mode must not send test message")
    if decision == "controlled_line_runtime_reactivation_completed_with_test_push" and push_status != "sent":
        errors.append("completed_with_test_push requires push_status sent")
    if decision == "line_push_test_failed" and push_status != "failed":
        errors.append("line_push_test_failed requires push_status failed")
    if payload.get("ok") is not True and decision != "line_push_test_failed":
        errors.append("ok false is only valid for line_push_test_failed in runtime result")
    return errors


def validate_secret_safety(payload: dict[str, Any]) -> list[str]:
    secret = payload.get("secret_safety")
    if not isinstance(secret, dict):
        return ["secret_safety must be an object"]
    errors = [f"secret_safety.{key} must be false" for key in SECRET_FALSE if secret.get(key) is not False]
    if secret.get("failure_details_redacted") is not True:
        errors.append("secret_safety.failure_details_redacted must be true")
    return errors


def validate_side_effects(payload: dict[str, Any]) -> list[str]:
    side_effects = payload.get("side_effects")
    if not isinstance(side_effects, dict):
        return ["side_effects must be an object"]
    errors = [f"side_effects.{key} must be false" for key in SIDE_EFFECTS_FALSE_ALWAYS if side_effects.get(key) is not False]
    push_attempted = payload.get("push_attempted") is True
    test_sent = payload.get("test_message_sent") is True
    for key in SIDE_EFFECTS_RUNTIME_TRUE_ALLOWED:
        expected = push_attempted if key in {"read_secrets", "called_line_api", "sent_notification"} else test_sent
        if side_effects.get(key) is not expected:
            errors.append(f"side_effects.{key} must be {str(expected).lower()}")
    return errors


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
    summary = as_dict(payload.get("controlled_line_runtime_summary"))
    if not summary:
        return ["controlled_line_runtime_summary must be an object"]
    errors: list[str] = []
    if summary.get("schema_version") != SUMMARY_SCHEMA_VERSION:
        errors.append("controlled_line_runtime_summary.schema_version is invalid")
    for key in [
        "task_id",
        "run_id",
        "generated_at",
        "mode",
        "delivery_allowed",
        "approval_status",
        "line_channel_enabled",
        "push_attempted",
        "push_status",
        "test_message_sent",
        "ok",
        "decision",
        "next_recommendation",
    ]:
        if summary.get(key) != payload.get(key):
            errors.append(f"controlled_line_runtime_summary.{key} must match top-level field")
    return errors


def validate_payload(payload: Any) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return {"ok": False, "errors": ["result root must be an object"]}
    for key in missing(payload, TOP_LEVEL):
        errors.append(f"missing top-level field: {key}")
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    if payload.get("task_id") != TASK_ID:
        errors.append(f"task_id must be {TASK_ID}")
    if not str(payload.get("run_id", "")).strip():
        errors.append("run_id is required")
    if not str(payload.get("generated_at", "")).strip():
        errors.append("generated_at is required")
    if not str(payload.get("next_recommendation", "")).strip():
        errors.append("next_recommendation is required")
    errors.extend(validate_gate(payload))
    errors.extend(validate_runtime(payload))
    errors.extend(validate_status(payload))
    errors.extend(validate_secret_safety(payload))
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
        "line_channel_enabled": payload.get("line_channel_enabled"),
        "push_attempted": payload.get("push_attempted"),
        "push_status": payload.get("push_status"),
        "test_message_sent": payload.get("test_message_sent"),
        "errors": errors,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Controlled LINE Runtime Reactivation V1 result JSON.")
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
