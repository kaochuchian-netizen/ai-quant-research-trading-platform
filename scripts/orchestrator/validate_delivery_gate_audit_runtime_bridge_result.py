#!/usr/bin/env python3
"""Validate Delivery Gate Audit + Runtime Bridge V1 fixture results."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "delivery_gate_audit_runtime_bridge_v1"
SUMMARY_SCHEMA_VERSION = "delivery_gate_audit_runtime_bridge_summary_v1"
CONTRACT_NAME = "delivery_gate_audit_runtime_bridge"
CONTRACT_VERSION = "v1"
CHANNELS = ["email", "line", "dashboard"]
DECISIONS = {
    "delivery_gate_audit_runtime_bridge_completed",
    "delivery_gate_audit_runtime_bridge_completed_with_warnings",
    "delivery_gate_runtime_bridge_blocked_pending_approval",
    "validation_failed",
    "blocked",
}
TOP_LEVEL = [
    "schema_version",
    "task_id",
    "run_id",
    "generated_at",
    "mode",
    "delivery_gate_audit_log",
    "runtime_bridge_plan",
    "delivery_gate_audit_runtime_bridge_summary",
    "validation_summary",
    "side_effects",
    "safety",
    "ok",
    "decision",
    "next_recommendation",
]
AUDIT_FIELDS = [
    "audit_id",
    "report_date",
    "payload_id",
    "review_id",
    "review_status",
    "approval_gate",
    "delivery_allowed",
    "final_delivery_decision",
    "channel_audit_entries",
    "blocked_channels",
    "ready_channels",
    "human_review_required",
    "audit_decision",
    "audit_notes",
]
BRIDGE_FIELDS = [
    "bridge_id",
    "bridge_mode",
    "allowed_channels",
    "blocked_channels",
    "runtime_preconditions",
    "channel_bridge_specs",
    "dry_run_entrypoints",
    "required_runtime_flags",
    "required_approval_fields",
    "safety_guards",
    "external_side_effects_allowed",
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
    "external_side_effects_allowed",
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
SAFETY_FALSE = ["external_side_effects_allowed", "dashboard_deploy", "api_server_created", "trading_instruction"]
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


def validate_audit_log(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    audit = payload.get("delivery_gate_audit_log")
    if not isinstance(audit, dict):
        return ["delivery_gate_audit_log must be an object"]
    for key in missing(audit, AUDIT_FIELDS):
        errors.append(f"delivery_gate_audit_log missing {key}")
    if not re.fullmatch(r"20\d{2}-\d{2}-\d{2}", str(audit.get("report_date", ""))):
        errors.append("delivery_gate_audit_log.report_date must be YYYY-MM-DD")
    entries = audit.get("channel_audit_entries")
    if not isinstance(entries, dict):
        errors.append("delivery_gate_audit_log.channel_audit_entries must be an object")
        entries = {}
    if set(entries.keys()) != set(CHANNELS):
        errors.append("delivery_gate_audit_log.channel_audit_entries must include email, line, dashboard")
    for channel in CHANNELS:
        entry = as_dict(entries.get(channel))
        if entry.get("channel") != channel:
            errors.append(f"channel_audit_entries.{channel}.channel must match key")
        if not isinstance(entry.get("blocked"), bool):
            errors.append(f"channel_audit_entries.{channel}.blocked must be boolean")
        if not isinstance(entry.get("ready_for_runtime_bridge"), bool):
            errors.append(f"channel_audit_entries.{channel}.ready_for_runtime_bridge must be boolean")
        if entry.get("blocked") is (entry.get("ready_for_runtime_bridge") is True):
            errors.append(f"channel_audit_entries.{channel}.blocked must inverse ready_for_runtime_bridge")
        if not isinstance(entry.get("blockers"), list):
            errors.append(f"channel_audit_entries.{channel}.blockers must be a list")
    blocked = [channel for channel in CHANNELS if as_dict(entries.get(channel)).get("blocked") is True]
    ready = [channel for channel in CHANNELS if as_dict(entries.get(channel)).get("blocked") is False]
    if audit.get("blocked_channels") != blocked:
        errors.append("delivery_gate_audit_log.blocked_channels must match channel audit entries")
    if audit.get("ready_channels") != ready:
        errors.append("delivery_gate_audit_log.ready_channels must match channel audit entries")
    if audit.get("delivery_allowed") is not (len(blocked) == 0):
        errors.append("delivery_gate_audit_log.delivery_allowed must require no blocked channels")
    if blocked and audit.get("audit_decision") != "blocked_pending_approval":
        errors.append("delivery_gate_audit_log.audit_decision must be blocked_pending_approval when blocked")
    if blocked and audit.get("human_review_required") is not True:
        errors.append("delivery_gate_audit_log.human_review_required must be true when blocked")
    return errors


def validate_bridge_plan(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    audit = as_dict(payload.get("delivery_gate_audit_log"))
    bridge = payload.get("runtime_bridge_plan")
    if not isinstance(bridge, dict):
        return ["runtime_bridge_plan must be an object"]
    for key in missing(bridge, BRIDGE_FIELDS):
        errors.append(f"runtime_bridge_plan missing {key}")
    if bridge.get("bridge_mode") != "dry_run_gated_preview_only":
        errors.append("runtime_bridge_plan.bridge_mode must be dry_run_gated_preview_only")
    if bridge.get("allowed_channels") != audit.get("ready_channels"):
        errors.append("runtime_bridge_plan.allowed_channels must match audit ready_channels")
    if bridge.get("blocked_channels") != audit.get("blocked_channels"):
        errors.append("runtime_bridge_plan.blocked_channels must match audit blocked_channels")
    if bridge.get("external_side_effects_allowed") is not False:
        errors.append("runtime_bridge_plan.external_side_effects_allowed must be false")
    entrypoints = bridge.get("dry_run_entrypoints")
    if not isinstance(entrypoints, dict):
        errors.append("runtime_bridge_plan.dry_run_entrypoints must be an object")
        entrypoints = {}
    if set(entrypoints.keys()) != set(CHANNELS):
        errors.append("runtime_bridge_plan.dry_run_entrypoints must include email, line, dashboard")
    for channel in CHANNELS:
        value = str(entrypoints.get(channel, ""))
        if "dry_run" not in value or not value.startswith("scripts/orchestrator/"):
            errors.append(f"runtime_bridge_plan.dry_run_entrypoints.{channel} must be dry-run orchestrator path")
    specs = bridge.get("channel_bridge_specs")
    if not isinstance(specs, dict):
        errors.append("runtime_bridge_plan.channel_bridge_specs must be an object")
        specs = {}
    if set(specs.keys()) != set(CHANNELS):
        errors.append("runtime_bridge_plan.channel_bridge_specs must include email, line, dashboard")
    for channel in CHANNELS:
        spec = as_dict(specs.get(channel))
        if spec.get("channel") != channel:
            errors.append(f"channel_bridge_specs.{channel}.channel must match key")
        if spec.get("external_side_effects_allowed") is not False:
            errors.append(f"channel_bridge_specs.{channel}.external_side_effects_allowed must be false")
        if spec.get("allowed_runtime_action") is not None:
            errors.append(f"channel_bridge_specs.{channel}.allowed_runtime_action must be null")
        if not str(spec.get("dry_run_entrypoint", "")).startswith("scripts/orchestrator/"):
            errors.append(f"channel_bridge_specs.{channel}.dry_run_entrypoint must be an orchestrator script")
    return errors


def validate_summary(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    summary = payload.get("delivery_gate_audit_runtime_bridge_summary")
    audit = as_dict(payload.get("delivery_gate_audit_log"))
    bridge = as_dict(payload.get("runtime_bridge_plan"))
    if not isinstance(summary, dict):
        return ["delivery_gate_audit_runtime_bridge_summary must be an object"]
    if summary.get("schema_version") != SUMMARY_SCHEMA_VERSION:
        errors.append("delivery_gate_audit_runtime_bridge_summary.schema_version is invalid")
    for key in [
        "audit_id",
        "report_date",
        "payload_id",
        "review_id",
        "review_status",
        "delivery_allowed",
        "final_delivery_decision",
        "audit_decision",
        "blocked_channels",
        "ready_channels",
        "human_review_required",
    ]:
        if summary.get(key) != audit.get(key):
            errors.append(f"delivery_gate_audit_runtime_bridge_summary.{key} must match audit log")
    for key in ["bridge_id", "bridge_mode", "external_side_effects_allowed"]:
        if summary.get(key) != bridge.get(key):
            errors.append(f"delivery_gate_audit_runtime_bridge_summary.{key} must match bridge plan")
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
        "runtime_bridge_dry_run_only": True,
        "runtime_entrypoints_dry_run_only": True,
        "external_side_effects_allowed": False,
        "no_delivery_actions": True,
    }
    for key, value in expected.items():
        if validation.get(key) != value:
            errors.append(f"validation_summary.{key} is invalid")
    for key in ["warning_count", "blocked_channel_count", "ready_channel_count"]:
        if not isinstance(validation.get(key), int) or validation.get(key, -1) < 0:
            errors.append(f"validation_summary.{key} must be a non-negative integer")
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
    if payload.get("task_id") != "AI-DEV-098":
        errors.append("task_id must be AI-DEV-098")
    if payload.get("mode") != "fixture_dry_run":
        errors.append("mode must be fixture_dry_run")
    if payload.get("decision") not in DECISIONS:
        errors.append("decision is invalid")
    if payload.get("ok") is not True and payload.get("decision") not in {"validation_failed", "blocked"}:
        errors.append("ok must be true for completed decisions")
    errors.extend(validate_audit_log(payload))
    errors.extend(validate_bridge_plan(payload))
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
    audit = as_dict(payload.get("delivery_gate_audit_log"))
    bridge = as_dict(payload.get("runtime_bridge_plan"))
    validation = as_dict(payload.get("validation_summary"))
    return {
        "ok": not errors,
        "run_id": payload.get("run_id"),
        "decision": payload.get("decision"),
        "delivery_allowed": audit.get("delivery_allowed"),
        "final_delivery_decision": audit.get("final_delivery_decision"),
        "external_side_effects_allowed": bridge.get("external_side_effects_allowed"),
        "bridge_mode": bridge.get("bridge_mode"),
        "blocked_channels": audit.get("blocked_channels"),
        "ready_channels": audit.get("ready_channels"),
        "deterministic_output": validation.get("deterministic_output"),
        "errors": errors,
        "side_effects": {key: False for key in SIDE_EFFECTS_FALSE},
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Delivery Gate Audit + Runtime Bridge V1 result JSON.")
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
