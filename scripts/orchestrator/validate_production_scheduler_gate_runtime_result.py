#!/usr/bin/env python3
"""Validate Production Scheduler Gate Runtime Activation V1 results."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "production_scheduler_gate_runtime_activation_v1"
SUMMARY_SCHEMA_VERSION = "production_scheduler_gate_runtime_summary_v1"
TASK_ID = "AI-DEV-101"
WINDOWS = ["pre_open_0700", "intraday_1305", "pre_close_1335"]
CHANNELS = ["email", "line", "dashboard"]
DECISIONS = {
    "production_scheduler_gate_runtime_activation_completed",
    "production_scheduler_gate_runtime_activation_completed_with_warnings",
    "production_scheduler_gate_runtime_blocked_pending_approval",
    "service_installation_blocked_pending_confirmation",
    "validation_failed",
    "blocked",
}
TOP_LEVEL = [
    "schema_version",
    "task_id",
    "run_id",
    "generated_at",
    "mode",
    "scheduler_window",
    "gate_runtime_decision",
    "delivery_allowed",
    "approval_status",
    "channels",
    "blocked_actions",
    "allowed_actions",
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
    "modified_cron",
    "modified_systemd",
    "modified_timer",
    "modified_service",
    "external_side_effects_allowed",
]
SAFETY_TRUE = [
    "repo_only",
    "gated_runtime",
    "dry_run_default",
    "manual_confirmation_required_for_service_install",
    "no_external_model_calls",
    "no_market_data_mutation",
    "no_delivery_actions",
    "no_email_send",
    "no_line_push",
    "no_dashboard_deploy",
    "no_smtp_call",
    "no_gmail_api_call",
    "no_api_server_created",
    "no_persistent_store_writes",
    "no_portfolio_actions",
    "no_cron_installation",
    "no_systemd_installation",
    "no_timer_installation",
    "no_service_installation",
    "no_live_schedule_mutation",
]
SAFETY_FALSE = ["external_side_effects_allowed", "dashboard_deploy", "api_server_created", "trading_instruction"]
BLOCKED_REQUIRED = {
    "email_send",
    "line_push",
    "dashboard_deploy",
    "smtp_call",
    "gmail_api_call",
    "cron_installation",
    "systemd_installation",
    "timer_installation",
    "service_installation",
    "live_schedule_mutation",
}
SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{20,}", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
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


def validate_payload(payload: Any) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return {"ok": False, "errors": ["result root must be an object"], "decision": "validation_failed"}
    for key in missing(payload, TOP_LEVEL):
        errors.append(f"missing top-level field: {key}")
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    if payload.get("task_id") != TASK_ID:
        errors.append(f"task_id must be {TASK_ID}")
    if payload.get("scheduler_window") not in WINDOWS:
        errors.append("scheduler_window is invalid")
    if payload.get("mode") != "dry_run_no_delivery":
        errors.append("mode must be dry_run_no_delivery")
    if payload.get("decision") not in DECISIONS:
        errors.append("decision is invalid")
    if payload.get("ok") is not True and payload.get("decision") not in {"validation_failed", "blocked"}:
        errors.append("ok must be true unless validation failed")
    if payload.get("delivery_allowed") is not False:
        errors.append("delivery_allowed must remain false for default runtime activation")
    if payload.get("approval_status") != "pending_approval":
        errors.append("approval_status must be pending_approval in default fixture")
    if payload.get("channels") != CHANNELS:
        errors.append("channels must be email, line, dashboard")

    gate = as_dict(payload.get("gate_runtime_decision"))
    for key in [
        "runtime_id",
        "scheduler_window",
        "pipeline_type",
        "mode",
        "dry_run",
        "delivery_allowed",
        "approval_status",
        "approved",
        "pipeline_execution_allowed",
        "delivery_execution_allowed",
        "service_install_allowed",
        "delivery_gate_refs",
        "runtime_wiring_refs",
        "channel_decisions",
        "blocked_reason",
    ]:
        if key not in gate:
            errors.append(f"gate_runtime_decision missing {key}")
    if gate.get("scheduler_window") != payload.get("scheduler_window"):
        errors.append("gate_runtime_decision.scheduler_window must match top-level")
    for key in ["delivery_allowed", "approved", "pipeline_execution_allowed", "delivery_execution_allowed", "service_install_allowed"]:
        if gate.get(key) is not False:
            errors.append(f"gate_runtime_decision.{key} must be false")
    if gate.get("dry_run") is not True:
        errors.append("gate_runtime_decision.dry_run must be true")
    for source_key, schema in [
        ("delivery_gate_refs", "production_scheduler_delivery_gate_integration_v1"),
        ("runtime_wiring_refs", "production_scheduler_runtime_gate_wiring_v1"),
    ]:
        refs = as_dict(gate.get(source_key))
        if refs.get("source_schema_version") != schema:
            errors.append(f"gate_runtime_decision.{source_key}.source_schema_version must be {schema}")
        if refs.get("source_schema_matched") is not True:
            errors.append(f"gate_runtime_decision.{source_key}.source_schema_matched must be true")
        if refs.get("source_ok") is not True:
            errors.append(f"gate_runtime_decision.{source_key}.source_ok must be true")

    channel_decisions = as_list(gate.get("channel_decisions"))
    if [as_dict(item).get("channel") for item in channel_decisions] != CHANNELS:
        errors.append("gate_runtime_decision.channel_decisions must cover email, line, dashboard")
    for item in channel_decisions:
        entry = as_dict(item)
        if entry.get("delivery_allowed") is not False or entry.get("blocked") is not True:
            errors.append(f"channel {entry.get('channel')} must be blocked with delivery_allowed false")

    blocked_actions = set(as_list(payload.get("blocked_actions")))
    missing_blocked = sorted(BLOCKED_REQUIRED - blocked_actions)
    if missing_blocked:
        errors.append(f"blocked_actions missing required entries: {missing_blocked}")

    side_effects = as_dict(payload.get("side_effects"))
    for key in SIDE_EFFECTS_FALSE:
        if side_effects.get(key) is not False:
            errors.append(f"side_effects.{key} must be false")
    safety = as_dict(payload.get("safety"))
    for key in SAFETY_TRUE:
        if safety.get(key) is not True:
            errors.append(f"safety.{key} must be true")
    for key in SAFETY_FALSE:
        if safety.get(key) is not False:
            errors.append(f"safety.{key} must be false")

    summary = as_dict(payload.get("runtime_summary"))
    if summary:
        if summary.get("schema_version") != SUMMARY_SCHEMA_VERSION:
            errors.append("runtime_summary.schema_version is invalid")
        for key in ["run_id", "scheduler_window", "decision", "delivery_allowed", "approval_status", "ok"]:
            if summary.get(key) != payload.get(key):
                errors.append(f"runtime_summary.{key} must match top-level")
        for key in ["cron_installed", "systemd_installed", "timer_installed", "service_installed", "live_schedule_mutated"]:
            if summary.get(key) is not False:
                errors.append(f"runtime_summary.{key} must be false")

    rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    for pattern in SECRET_PATTERNS:
        if pattern.search(rendered):
            errors.append(f"secret-like text detected: {pattern.pattern}")
            break
    for text in iter_strings(payload):
        if re.search(r"\b(crontab\s+-e|systemctl\s+(enable|disable|start|stop|restart|daemon-reload))\b", text, re.I):
            errors.append(f"possible forbidden live service mutation command detected: {text}")
    return {
        "ok": not errors,
        "run_id": payload.get("run_id"),
        "decision": payload.get("decision"),
        "scheduler_window": payload.get("scheduler_window"),
        "delivery_allowed": payload.get("delivery_allowed"),
        "approval_status": payload.get("approval_status"),
        "channels": payload.get("channels"),
        "deterministic_output": as_dict(payload.get("validation_summary")).get("deterministic_output"),
        "cron_installed": summary.get("cron_installed"),
        "systemd_installed": summary.get("systemd_installed"),
        "timer_installed": summary.get("timer_installed"),
        "service_installed": summary.get("service_installed"),
        "live_schedule_mutated": summary.get("live_schedule_mutated"),
        "errors": errors,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Production Scheduler Gate Runtime Activation V1 result JSON.")
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
