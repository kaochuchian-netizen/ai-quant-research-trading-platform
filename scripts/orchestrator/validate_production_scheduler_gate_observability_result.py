#!/usr/bin/env python3
"""Validate Production Scheduler Gate Observability V1 results."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "production_scheduler_gate_observability_v1"
SUMMARY_SCHEMA_VERSION = "production_scheduler_gate_observability_summary_v1"
TASK_ID = "AI-DEV-103"
DECISIONS = {
    "production_scheduler_gate_observability_completed",
    "production_scheduler_gate_observability_completed_with_warnings",
    "latest_gate_result_not_found",
    "validation_failed",
    "blocked",
}
WINDOWS = {"pre_open_0700", "intraday_1305", "pre_close_1335", None}
TOP_LEVEL = [
    "schema_version",
    "task_id",
    "run_id",
    "generated_at",
    "mode",
    "observed_scheduler_window",
    "latest_gate_result_path",
    "latest_gate_summary_path",
    "delivery_allowed",
    "approval_status",
    "gate_runtime_decision",
    "blocked_actions",
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
    "observability_only",
    "gated_runtime",
    "dry_run_default",
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
    "production_db_write",
    "persistent_store_write",
    "portfolio_action",
    "trading_instruction",
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
FORBIDDEN_TEXT = [
    re.compile(r"STOCK_AI_LEGACY_PRODUCTION_APPROVED=1"),
    re.compile(r"main\.py\s+--production-approved"),
    re.compile(r"run_pipeline\.py\s+pre_open\s+--production-approved"),
    re.compile(r"\bsystemctl\s+(enable|disable|start|stop|restart|daemon-reload)\b", re.I),
    re.compile(r"\bcrontab\s+-e\b", re.I),
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

    for key in TOP_LEVEL:
        if key not in payload:
            errors.append(f"missing top-level field: {key}")
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    if payload.get("task_id") != TASK_ID:
        errors.append(f"task_id must be {TASK_ID}")
    if payload.get("decision") not in DECISIONS:
        errors.append("decision is invalid")
    if payload.get("observed_scheduler_window") not in WINDOWS:
        errors.append("observed_scheduler_window is invalid")
    if not isinstance(payload.get("latest_gate_result_path"), str) or not payload.get("latest_gate_result_path"):
        errors.append("latest_gate_result_path must be a non-empty string")
    if not isinstance(payload.get("latest_gate_summary_path"), str) or not payload.get("latest_gate_summary_path"):
        errors.append("latest_gate_summary_path must be a non-empty string")
    if payload.get("delivery_allowed") is not False:
        errors.append("delivery_allowed must remain false for observability artifacts")

    gate = as_dict(payload.get("gate_runtime_decision"))
    for key in [
        "source_found",
        "source_error",
        "scheduler_window",
        "delivery_allowed",
        "approval_status",
        "pipeline_execution_allowed",
        "delivery_execution_allowed",
    ]:
        if key not in gate:
            errors.append(f"gate_runtime_decision missing {key}")
    if gate.get("scheduler_window") != payload.get("observed_scheduler_window"):
        errors.append("gate_runtime_decision.scheduler_window must match observed_scheduler_window")
    for key in ["delivery_allowed", "pipeline_execution_allowed", "delivery_execution_allowed"]:
        if gate.get(key) is not False:
            errors.append(f"gate_runtime_decision.{key} must be false")

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

    if payload.get("decision") == "latest_gate_result_not_found":
        if as_dict(as_dict(payload.get("sources")).get("latest_gate_result")).get("found") is not False:
            errors.append("latest_gate_result_not_found requires sources.latest_gate_result.found=false")
    elif payload.get("ok") is not True and payload.get("decision") != "validation_failed":
        errors.append("ok must be true unless latest gate result is missing or validation failed")

    summary = as_dict(payload.get("observability_summary"))
    if summary:
        if summary.get("schema_version") != SUMMARY_SCHEMA_VERSION:
            errors.append("observability_summary.schema_version is invalid")
        for key in [
            "run_id",
            "generated_at",
            "latest_timestamp",
            "mode",
            "observed_scheduler_window",
            "latest_gate_result_path",
            "latest_gate_summary_path",
            "delivery_allowed",
            "approval_status",
            "decision",
            "ok",
        ]:
            if summary.get(key) != payload.get(key):
                errors.append(f"observability_summary.{key} must match top-level")
        for key in ["no_delivery_actions", "no_cron_installation", "no_systemd_installation", "no_timer_installation", "no_service_installation"]:
            if summary.get(key) is not True:
                errors.append(f"observability_summary.{key} must be true")

    rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    for pattern in SECRET_PATTERNS:
        if pattern.search(rendered):
            errors.append(f"secret-like text detected: {pattern.pattern}")
            break
    for text in iter_strings(payload):
        for pattern in FORBIDDEN_TEXT:
            if pattern.search(text):
                errors.append(f"forbidden command text detected: {text}")
                break

    return {
        "ok": not errors,
        "artifact_ok": payload.get("ok"),
        "schema_version": payload.get("schema_version"),
        "task_id": payload.get("task_id"),
        "run_id": payload.get("run_id"),
        "decision": payload.get("decision"),
        "observed_scheduler_window": payload.get("observed_scheduler_window"),
        "latest_gate_result_path": payload.get("latest_gate_result_path"),
        "latest_gate_summary_path": payload.get("latest_gate_summary_path"),
        "delivery_allowed": payload.get("delivery_allowed"),
        "approval_status": payload.get("approval_status"),
        "errors": errors,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Production Scheduler Gate Observability V1 result JSON.")
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
