#!/usr/bin/env python3
"""Validate Production Scheduler Runtime Gate Wiring V1 fixture results."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "production_scheduler_runtime_gate_wiring_v1"
SUMMARY_SCHEMA_VERSION = "production_scheduler_runtime_gate_wiring_summary_v1"
TASK_ID = "AI-DEV-100"
CONTRACT_NAME = "production_scheduler_runtime_gate_wiring"
CONTRACT_VERSION = "v1"
WINDOW_IDS = ["pre_open_0700", "intraday_1305", "pre_close_1335"]
WINDOW_TIMES = {"pre_open_0700": "07:00", "intraday_1305": "13:05", "pre_close_1335": "13:35"}
CURRENT_ENTRYPOINT = "/home/kaochuchian/stock-ai/run_stock_analysis.sh"
DECISIONS = {
    "production_scheduler_runtime_gate_wiring_completed",
    "production_scheduler_runtime_gate_wiring_completed_with_warnings",
    "runtime_wiring_blocked_pending_service_change_confirmation",
    "validation_failed",
    "blocked",
}
TOP_LEVEL = [
    "schema_version",
    "task_id",
    "run_id",
    "generated_at",
    "mode",
    "scheduler_inspection_summary",
    "production_scheduler_runtime_gate_wiring",
    "runtime_gate_wiring_summary",
    "validation_summary",
    "side_effects",
    "safety",
    "ok",
    "decision",
    "next_recommendation",
]
WIRING_FIELDS = [
    "wiring_id",
    "report_date",
    "runtime_mode",
    "source_integration_refs",
    "scheduler_windows",
    "contract_requirements",
    "activation_boundary",
    "rollback_plan",
]
WINDOW_FIELDS = [
    "scheduler_window_id",
    "local_time",
    "cron_expression",
    "pipeline_type",
    "pipeline_context",
    "current_entrypoint",
    "proposed_gate_entrypoint",
    "dry_run_command",
    "future_runtime_command",
    "delivery_gate_required",
    "approval_required",
    "manual_confirmation_required",
    "allowed_side_effects",
    "blocked_side_effects",
    "rollback_plan",
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
    "modified_github_remote",
    "external_side_effects_allowed",
]
SAFETY_TRUE = [
    "repo_only",
    "gated_dry_run_first",
    "advisory_only",
    "manual_confirmation_required",
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
    "no_cron_modification",
    "no_systemd_modification",
    "no_timer_modification",
    "no_service_modification",
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
FORBIDDEN_TRADING_TEXT = [
    re.compile(r"\b(buy|sell|short|long)\s+(now|today|at market|at open|at close)\b", re.IGNORECASE),
    re.compile(r"\b(place|submit|route|execute)\s+(an?\s+)?order\b", re.IGNORECASE),
    re.compile(r"\border\s+(now|immediately|ticket|instruction)\b", re.IGNORECASE),
]
FORBIDDEN_MUTATION_TEXT = [
    re.compile(r"\b(crontab\s+-e|systemctl\s+(enable|disable|start|stop|restart|daemon-reload))\b", re.IGNORECASE),
    re.compile(r"\b(send\s+email|push\s+line|deploy\s+dashboard|call\s+smtp|gmail api call)\b", re.IGNORECASE),
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


def validate_inspection(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    inspection = payload.get("scheduler_inspection_summary")
    if not isinstance(inspection, dict):
        return ["scheduler_inspection_summary must be an object"]
    entries = as_list(inspection.get("current_scheduler_entrypoints_found"))
    if len(entries) != 3:
        errors.append("scheduler_inspection_summary.current_scheduler_entrypoints_found must contain three entries")
    if [as_dict(entry).get("window_id") for entry in entries] != WINDOW_IDS:
        errors.append("scheduler_inspection_summary current entrypoints must be ordered by required scheduler windows")
    for entry in entries:
        item = as_dict(entry)
        if item.get("command") != CURRENT_ENTRYPOINT:
            errors.append(f"scheduler_inspection_summary.{item.get('window_id')}.command must match current entrypoint")
    if inspection.get("cron_inspection_status") != "completed_read_only":
        errors.append("scheduler_inspection_summary.cron_inspection_status must be completed_read_only")
    return errors


def validate_wiring(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    wiring = payload.get("production_scheduler_runtime_gate_wiring")
    if not isinstance(wiring, dict):
        return ["production_scheduler_runtime_gate_wiring must be an object"]
    for key in missing(wiring, WIRING_FIELDS):
        errors.append(f"production_scheduler_runtime_gate_wiring missing {key}")
    if not re.fullmatch(r"20\d{2}-\d{2}-\d{2}", str(wiring.get("report_date", ""))):
        errors.append("production_scheduler_runtime_gate_wiring.report_date must be YYYY-MM-DD")
    if wiring.get("runtime_mode") != "gated_dry_run_first_advisory_only":
        errors.append("production_scheduler_runtime_gate_wiring.runtime_mode is invalid")
    refs = as_dict(wiring.get("source_integration_refs"))
    if refs.get("source_schema_version") != "production_scheduler_delivery_gate_integration_v1":
        errors.append("source_integration_refs.source_schema_version must be production_scheduler_delivery_gate_integration_v1")
    if refs.get("source_schema_matched") is not True:
        errors.append("source_integration_refs.source_schema_matched must be true")
    if refs.get("source_ok") is not True:
        errors.append("source_integration_refs.source_ok must be true")
    windows = wiring.get("scheduler_windows")
    if not isinstance(windows, list):
        errors.append("production_scheduler_runtime_gate_wiring.scheduler_windows must be a list")
        windows = []
    if [as_dict(window).get("scheduler_window_id") for window in windows] != WINDOW_IDS:
        errors.append("scheduler_windows must model pre_open_0700, intraday_1305, pre_close_1335")
    for window in windows:
        entry = as_dict(window)
        window_id = str(entry.get("scheduler_window_id"))
        for key in missing(entry, WINDOW_FIELDS):
            errors.append(f"scheduler_windows.{window_id or 'unknown'} missing {key}")
        if entry.get("local_time") != WINDOW_TIMES.get(window_id):
            errors.append(f"scheduler_windows.{window_id}.local_time is invalid")
        if entry.get("current_entrypoint") != CURRENT_ENTRYPOINT:
            errors.append(f"scheduler_windows.{window_id}.current_entrypoint is invalid")
        if entry.get("proposed_gate_entrypoint") != "scripts/orchestrator/production_scheduler_runtime_gate_wiring_dry_run.py":
            errors.append(f"scheduler_windows.{window_id}.proposed_gate_entrypoint is invalid")
        if "production_scheduler_runtime_gate_wiring_dry_run.py" not in str(entry.get("dry_run_command", "")):
            errors.append(f"scheduler_windows.{window_id}.dry_run_command must use runtime wiring dry run helper")
        if "--require-manual-confirmation" not in str(entry.get("future_runtime_command", "")):
            errors.append(f"scheduler_windows.{window_id}.future_runtime_command must require manual confirmation")
        for key in ["delivery_gate_required", "approval_required", "manual_confirmation_required"]:
            if entry.get(key) is not True:
                errors.append(f"scheduler_windows.{window_id}.{key} must be true")
        blocked = set(as_list(entry.get("blocked_side_effects")))
        for action in ["cron_modification", "systemd_modification", "timer_modification", "service_modification"]:
            if action not in blocked:
                errors.append(f"scheduler_windows.{window_id}.blocked_side_effects missing {action}")
    boundary = as_dict(wiring.get("activation_boundary"))
    for key in [
        "actual_cron_change_allowed",
        "actual_systemd_change_allowed",
        "actual_timer_change_allowed",
        "actual_service_change_allowed",
    ]:
        if boundary.get(key) is not False:
            errors.append(f"activation_boundary.{key} must be false")
    if boundary.get("requires_new_explicit_confirmation") is not True:
        errors.append("activation_boundary.requires_new_explicit_confirmation must be true")
    return errors


def validate_summary(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    summary = payload.get("runtime_gate_wiring_summary")
    wiring = as_dict(payload.get("production_scheduler_runtime_gate_wiring"))
    if not isinstance(summary, dict):
        return ["runtime_gate_wiring_summary must be an object"]
    if summary.get("schema_version") != SUMMARY_SCHEMA_VERSION:
        errors.append("runtime_gate_wiring_summary.schema_version is invalid")
    for key in ["task_id", "run_id", "generated_at", "mode", "decision", "ok"]:
        if summary.get(key) != payload.get(key):
            errors.append(f"runtime_gate_wiring_summary.{key} must match top-level")
    for key in ["wiring_id", "report_date", "runtime_mode"]:
        if summary.get(key) != wiring.get(key):
            errors.append(f"runtime_gate_wiring_summary.{key} must match wiring")
    if summary.get("scheduler_window_ids") != WINDOW_IDS:
        errors.append("runtime_gate_wiring_summary.scheduler_window_ids is invalid")
    if summary.get("scheduler_window_count") != 3:
        errors.append("runtime_gate_wiring_summary.scheduler_window_count must be 3")
    if summary.get("manual_confirmation_required") is not True:
        errors.append("runtime_gate_wiring_summary.manual_confirmation_required must be true")
    if summary.get("actual_service_change_pending_explicit_confirmation") is not True:
        errors.append("runtime_gate_wiring_summary.actual_service_change_pending_explicit_confirmation must be true")
    for key in ["cron_modified", "systemd_modified", "timer_modified", "service_modified"]:
        if summary.get(key) is not False:
            errors.append(f"runtime_gate_wiring_summary.{key} must be false")
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
        "repo_only": True,
        "gated_dry_run_first": True,
        "advisory_only": True,
        "source_schema_matched": True,
        "source_result_ok": True,
        "scheduler_windows_present": True,
        "scheduler_window_count": 3,
        "all_windows_delivery_gate_required": True,
        "all_windows_approval_required": True,
        "all_windows_manual_confirmation_required": True,
        "all_window_entrypoints_dry_run": True,
        "all_future_runtime_commands_require_confirmation": True,
        "no_schedule_service_changes": True,
    }
    for key, value in expected.items():
        if validation.get(key) != value:
            errors.append(f"validation_summary.{key} is invalid")
    for key in ["blocked_side_effect_count", "allowed_side_effect_count"]:
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
    if payload.get("task_id") != TASK_ID:
        errors.append(f"task_id must be {TASK_ID}")
    if payload.get("mode") != "fixture_gated_dry_run":
        errors.append("mode must be fixture_gated_dry_run")
    if payload.get("decision") not in DECISIONS:
        errors.append("decision is invalid")
    if payload.get("ok") is not True and payload.get("decision") not in {"validation_failed", "blocked"}:
        errors.append("ok must be true for completed or pending-confirmation decisions")
    errors.extend(validate_inspection(payload))
    errors.extend(validate_wiring(payload))
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
        for pattern in FORBIDDEN_TRADING_TEXT:
            if pattern.search(text):
                errors.append(f"possible trading/order instruction detected: {text}")
        for pattern in FORBIDDEN_MUTATION_TEXT:
            if pattern.search(text):
                errors.append(f"possible forbidden live mutation command detected: {text}")
    summary = as_dict(payload.get("runtime_gate_wiring_summary"))
    validation = as_dict(payload.get("validation_summary"))
    return {
        "ok": not errors,
        "run_id": payload.get("run_id"),
        "decision": payload.get("decision"),
        "scheduler_window_ids": summary.get("scheduler_window_ids"),
        "current_entrypoints": summary.get("current_entrypoints"),
        "proposed_gate_entrypoints": summary.get("proposed_gate_entrypoints"),
        "manual_confirmation_required": summary.get("manual_confirmation_required"),
        "actual_service_change_pending_explicit_confirmation": summary.get(
            "actual_service_change_pending_explicit_confirmation"
        ),
        "deterministic_output": validation.get("deterministic_output"),
        "cron_modified": summary.get("cron_modified"),
        "systemd_modified": summary.get("systemd_modified"),
        "timer_modified": summary.get("timer_modified"),
        "service_modified": summary.get("service_modified"),
        "errors": errors,
        "side_effects": {key: False for key in SIDE_EFFECTS_FALSE},
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Production Scheduler Runtime Gate Wiring V1 result JSON.")
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
