#!/usr/bin/env python3
"""Validate LINE Delivery Gate Contract V1 fixture results."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "line_delivery_gate_contract_v1"
SUMMARY_SCHEMA_VERSION = "line_delivery_gate_summary_v1"
CONTRACT_NAME = "line_delivery_gate"
CONTRACT_VERSION = "v1"
DECISIONS = {
    "line_delivery_gate_contract_completed",
    "line_delivery_gate_contract_completed_with_warnings",
    "line_delivery_blocked_pending_approval",
    "validation_failed",
    "blocked",
}
TOP_LEVEL = [
    "schema_version",
    "task_id",
    "run_id",
    "generated_at",
    "mode",
    "line_delivery_gate",
    "line_delivery_summary",
    "validation_summary",
    "side_effects",
    "safety",
    "ok",
    "decision",
    "next_recommendation",
]
LINE_GATE_FIELDS = [
    "line_delivery_id",
    "payload_id",
    "report_date",
    "review_id",
    "review_status",
    "approval_gate",
    "delivery_allowed",
    "line_channel_enabled",
    "preview_only",
    "recipient_policy",
    "message_preview",
    "link_preview",
    "delivery_blockers",
    "warning_badges",
    "human_review_required",
    "advisory_disclaimer",
    "push_intent",
    "push_status",
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
    "no_line_push",
    "no_line_api_call",
    "no_email_send",
    "no_smtp_call",
    "no_gmail_api_call",
    "no_dashboard_deploy",
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


def validate_line_delivery_gate(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    gate_payload = payload.get("line_delivery_gate")
    if not isinstance(gate_payload, dict):
        return ["line_delivery_gate must be an object"]
    for key in missing(gate_payload, LINE_GATE_FIELDS):
        errors.append(f"line_delivery_gate missing {key}")
    if not re.fullmatch(r"20\d{2}-\d{2}-\d{2}", str(gate_payload.get("report_date", ""))):
        errors.append("line_delivery_gate.report_date must be YYYY-MM-DD")
    for key in ["line_delivery_id", "payload_id", "review_id", "review_status", "advisory_disclaimer"]:
        if not str(gate_payload.get(key, "")).strip():
            errors.append(f"line_delivery_gate.{key} is required")
    review_status = gate_payload.get("review_status")
    delivery_allowed = gate_payload.get("delivery_allowed")
    line_channel_enabled = gate_payload.get("line_channel_enabled")
    expected_allowed = review_status == "approved"
    if delivery_allowed is not expected_allowed:
        errors.append("line_delivery_gate.delivery_allowed must be true only when review_status is approved")
    if line_channel_enabled is not (delivery_allowed is True and review_status == "approved"):
        errors.append("line_delivery_gate.line_channel_enabled must require delivery_allowed true and approved review")
    if gate_payload.get("preview_only") is not True:
        errors.append("line_delivery_gate.preview_only must be true")
    if gate_payload.get("push_status") != "not_sent":
        errors.append("line_delivery_gate.push_status must remain not_sent")
    if gate_payload.get("push_intent") != "preview_only_no_push":
        errors.append("line_delivery_gate.push_intent must be preview_only_no_push")
    gate = as_dict(gate_payload.get("approval_gate"))
    if gate.get("required_review_status") != "approved":
        errors.append("line_delivery_gate.approval_gate.required_review_status must be approved")
    if gate.get("current_review_status") != review_status:
        errors.append("line_delivery_gate.approval_gate.current_review_status must match review_status")
    if gate.get("approval_required") is not True:
        errors.append("line_delivery_gate.approval_gate.approval_required must be true")
    if gate.get("delivery_allowed") != delivery_allowed or gate.get("gate_open") != delivery_allowed:
        errors.append("line_delivery_gate.approval_gate must match delivery_allowed")
    recipient_policy = as_dict(gate_payload.get("recipient_policy"))
    if recipient_policy.get("recipients_resolved") is not False:
        errors.append("line_delivery_gate.recipient_policy.recipients_resolved must be false")
    if recipient_policy.get("recipient_count") != 0:
        errors.append("line_delivery_gate.recipient_policy.recipient_count must be 0")
    if recipient_policy.get("allow_external_recipients") is not False:
        errors.append("line_delivery_gate.recipient_policy.allow_external_recipients must be false")
    message_preview = as_dict(gate_payload.get("message_preview"))
    if message_preview.get("contains_full_line_message") is not False:
        errors.append("line_delivery_gate.message_preview.contains_full_line_message must be false")
    link_preview = as_dict(gate_payload.get("link_preview"))
    if link_preview.get("links_resolved") is not False:
        errors.append("line_delivery_gate.link_preview.links_resolved must be false")
    if link_preview.get("link_count") != 0:
        errors.append("line_delivery_gate.link_preview.link_count must be 0")
    if link_preview.get("allow_external_links") is not False:
        errors.append("line_delivery_gate.link_preview.allow_external_links must be false")
    if not isinstance(gate_payload.get("delivery_blockers"), list):
        errors.append("line_delivery_gate.delivery_blockers must be a list")
    if not isinstance(gate_payload.get("warning_badges"), list):
        errors.append("line_delivery_gate.warning_badges must be a list")
    if not isinstance(gate_payload.get("human_review_required"), bool):
        errors.append("line_delivery_gate.human_review_required must be boolean")
    blockers = as_list(gate_payload.get("delivery_blockers"))
    if delivery_allowed is False and "approval_gate_closed" not in blockers:
        errors.append("line_delivery_gate.delivery_blockers must include approval_gate_closed when blocked")
    if line_channel_enabled is False and "line_channel_disabled" not in blockers:
        errors.append("line_delivery_gate.delivery_blockers must include line_channel_disabled when disabled")
    if "fixture_mode_no_line_push" not in blockers:
        errors.append("line_delivery_gate.delivery_blockers must include fixture_mode_no_line_push")
    if "fixture_mode_no_line_api_call" not in blockers:
        errors.append("line_delivery_gate.delivery_blockers must include fixture_mode_no_line_api_call")
    return errors


def validate_summary(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    summary = payload.get("line_delivery_summary")
    gate = as_dict(payload.get("line_delivery_gate"))
    if not isinstance(summary, dict):
        return ["line_delivery_summary must be an object"]
    if summary.get("schema_version") != SUMMARY_SCHEMA_VERSION:
        errors.append("line_delivery_summary.schema_version is invalid")
    for key in [
        "line_delivery_id",
        "payload_id",
        "report_date",
        "review_id",
        "review_status",
        "delivery_allowed",
        "line_channel_enabled",
        "preview_only",
        "push_status",
        "push_intent",
        "human_review_required",
    ]:
        if summary.get(key) != gate.get(key):
            errors.append(f"line_delivery_summary.{key} must match line_delivery_gate")
    if summary.get("recipient_count") != as_dict(gate.get("recipient_policy")).get("recipient_count"):
        errors.append("line_delivery_summary.recipient_count must match recipient_policy")
    if summary.get("link_count") != as_dict(gate.get("link_preview")).get("link_count"):
        errors.append("line_delivery_summary.link_count must match link_preview")
    if summary.get("warning_badge_count") != len(as_list(gate.get("warning_badges"))):
        errors.append("line_delivery_summary.warning_badge_count must match warning_badges")
    if summary.get("delivery_blocker_count") != len(as_list(gate.get("delivery_blockers"))):
        errors.append("line_delivery_summary.delivery_blocker_count must match delivery_blockers")
    return errors


def validate_validation_summary(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    summary = payload.get("validation_summary")
    if not isinstance(summary, dict):
        return ["validation_summary must be an object"]
    expected = {
        "contract_name": CONTRACT_NAME,
        "contract_version": CONTRACT_VERSION,
        "deterministic_output": True,
        "fixture_only": True,
        "preview_only": True,
        "source_schema_matched": True,
        "source_ok": True,
        "approval_gate_required": True,
        "delivery_allowed_policy_enforced": True,
        "line_channel_policy_enforced": True,
        "push_status_not_sent": True,
        "push_intent_preview_only": True,
        "recipients_unresolved": True,
        "links_unresolved": True,
    }
    for key, value in expected.items():
        if summary.get(key) != value:
            errors.append(f"validation_summary.{key} is invalid")
    for key in ["warning_count", "delivery_blocker_count"]:
        if not isinstance(summary.get(key), int) or summary.get(key, -1) < 0:
            errors.append(f"validation_summary.{key} must be a non-negative integer")
    if not isinstance(summary.get("warnings"), list):
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
    if payload.get("task_id") != "AI-DEV-095":
        errors.append("task_id must be AI-DEV-095")
    if payload.get("mode") != "fixture_dry_run":
        errors.append("mode must be fixture_dry_run")
    if payload.get("decision") not in DECISIONS:
        errors.append("decision is invalid")
    if payload.get("ok") is not True and payload.get("decision") not in {"validation_failed", "blocked"}:
        errors.append("ok must be true for completed decisions")
    errors.extend(validate_line_delivery_gate(payload))
    errors.extend(validate_summary(payload))
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
    gate = as_dict(payload.get("line_delivery_gate"))
    validation = as_dict(payload.get("validation_summary"))
    return {
        "ok": not errors,
        "run_id": payload.get("run_id"),
        "decision": payload.get("decision"),
        "delivery_allowed": gate.get("delivery_allowed"),
        "line_channel_enabled": gate.get("line_channel_enabled"),
        "push_status": gate.get("push_status"),
        "review_status": gate.get("review_status"),
        "deterministic_output": validation.get("deterministic_output"),
        "errors": errors,
        "side_effects": {key: False for key in SIDE_EFFECTS_FALSE},
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate LINE Delivery Gate Contract V1 result JSON.")
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
