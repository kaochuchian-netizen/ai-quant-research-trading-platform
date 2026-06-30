#!/usr/bin/env python3
"""Build deterministic Production Scheduler Delivery Gate Integration V1 fixtures."""

from __future__ import annotations

import argparse
import json
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any


DEFAULT_INPUT = Path("templates/production_scheduler_delivery_gate_integration_input.example.json")
SCHEMA_VERSION = "production_scheduler_delivery_gate_integration_v1"
SUMMARY_SCHEMA_VERSION = "production_scheduler_delivery_gate_integration_summary_v1"
TASK_ID = "AI-DEV-099"
CONTRACT_NAME = "production_scheduler_delivery_gate_integration"
CONTRACT_VERSION = "v1"
SOURCE_SCHEMA_VERSION = "delivery_gate_audit_runtime_bridge_v1"
SCHEDULER_WINDOWS = [
    {
        "window_id": "pre_open_0700",
        "local_time": "07:00",
        "pipeline_context": "daily_pre_open_analysis",
    },
    {
        "window_id": "intraday_1305",
        "local_time": "13:05",
        "pipeline_context": "intraday_analysis_refresh",
    },
    {
        "window_id": "pre_close_1335",
        "local_time": "13:35",
        "pipeline_context": "pre_close_analysis_refresh",
    },
]
CHANNELS = ["email", "line", "dashboard"]
ALLOWED_ACTIONS = [
    "read_repo_fixture",
    "build_scheduler_delivery_gate_preview",
    "write_requested_json_outputs",
    "validate_fixture_contract",
]
BLOCKED_ACTIONS = [
    "cron_modification",
    "systemd_modification",
    "timer_modification",
    "service_modification",
    "email_send",
    "line_push",
    "dashboard_deploy",
    "api_server_creation",
    "smtp_call",
    "gmail_api_call",
    "market_data_call",
    "model_runtime_call",
    "production_db_write",
    "portfolio_action",
    "external_system_mutation",
]
SIDE_EFFECTS = {
    "read_secrets": False,
    "called_external_model_runtime": False,
    "called_market_data_runtime": False,
    "sent_notification": False,
    "sent_email": False,
    "called_smtp": False,
    "called_gmail_api": False,
    "sent_line_push": False,
    "called_line_api": False,
    "deployed_dashboard": False,
    "created_api_server": False,
    "placed_trade_order": False,
    "modified_portfolio": False,
    "wrote_persistent_store": False,
    "modified_schedule_or_service": False,
    "modified_cron": False,
    "modified_systemd": False,
    "modified_timer": False,
    "modified_service": False,
    "modified_github_remote": False,
    "external_side_effects_allowed": False,
}
SAFETY = {
    "repo_only": True,
    "fixture_only": True,
    "dry_run_only": True,
    "advisory_only": True,
    "preview_only": True,
    "no_external_model_calls": True,
    "no_market_data_calls": True,
    "no_delivery_actions": True,
    "no_email_send": True,
    "no_line_push": True,
    "no_dashboard_deploy": True,
    "no_smtp_call": True,
    "no_gmail_api_call": True,
    "no_api_server_created": True,
    "no_persistent_store_writes": True,
    "no_portfolio_actions": True,
    "no_cron_modification": True,
    "no_systemd_modification": True,
    "no_timer_modification": True,
    "no_service_modification": True,
    "no_schedule_service_changes": True,
    "external_side_effects_allowed": False,
    "dashboard_deploy": False,
    "api_server_created": False,
    "trading_instruction": False,
    "manual_confirmation_required": True,
}


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"input file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"input file is not valid JSON: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit("input JSON root must be an object")
    return data


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def repo_path(raw_path: Any) -> Path:
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise SystemExit("referenced fixture path must be a non-empty string")
    path = Path(raw_path)
    if path.is_absolute():
        raise SystemExit("referenced fixture path must be repo-relative")
    if ".." in path.parts:
        raise SystemExit("referenced fixture path must not contain parent traversal")
    return path


def stable_json(payload: Any, pretty: bool) -> str:
    text = json.dumps(payload, ensure_ascii=False, indent=2 if pretty else None, sort_keys=True)
    return f"{text}\n" if pretty else text


def slug(value: Any) -> str:
    text = str(value or "unknown").strip().lower()
    text = re.sub(r"[^a-z0-9._-]+", "-", text)
    return text.strip("-") or "unknown"


def bridge_refs(path: Path, bridge: dict[str, Any]) -> dict[str, Any]:
    audit = as_dict(bridge.get("delivery_gate_audit_log"))
    runtime_bridge = as_dict(bridge.get("runtime_bridge_plan"))
    return {
        "source_path": str(path),
        "source_schema_expected": SOURCE_SCHEMA_VERSION,
        "source_schema_version": bridge.get("schema_version"),
        "source_schema_matched": bridge.get("schema_version") == SOURCE_SCHEMA_VERSION,
        "source_task_id": bridge.get("task_id"),
        "source_run_id": bridge.get("run_id"),
        "source_generated_at": bridge.get("generated_at"),
        "source_mode": bridge.get("mode"),
        "source_ok": bridge.get("ok") is True,
        "source_decision": bridge.get("decision"),
        "audit_id": audit.get("audit_id"),
        "bridge_id": runtime_bridge.get("bridge_id"),
        "report_date": audit.get("report_date"),
        "review_id": audit.get("review_id"),
        "review_status": audit.get("review_status"),
        "delivery_allowed": audit.get("delivery_allowed") is True,
        "blocked_channels": deepcopy(audit.get("blocked_channels")),
        "ready_channels": deepcopy(audit.get("ready_channels")),
        "human_review_required": audit.get("human_review_required") is True,
        "external_side_effects_allowed": runtime_bridge.get("external_side_effects_allowed") is True,
    }


def window_entry(window: dict[str, str], refs: dict[str, Any]) -> dict[str, Any]:
    window_id = window["window_id"]
    dry_run_command = (
        "python3 scripts/orchestrator/production_scheduler_delivery_gate_integration_dry_run.py "
        "--input templates/production_scheduler_delivery_gate_integration_input.example.json "
        f"--output /tmp/{window_id}_scheduler_delivery_gate_preview.json "
        f"--summary-output /tmp/{window_id}_scheduler_delivery_gate_summary.json --pretty"
    )
    return {
        "window_id": window_id,
        "local_time": window["local_time"],
        "pipeline_context": window["pipeline_context"],
        "gate_required": True,
        "approval_required": True,
        "delivery_allowed": False,
        "channels_considered": deepcopy(CHANNELS),
        "channels_enabled": [],
        "blocked_reason": "fixture_mode_delivery_allowed_false_manual_confirmation_required",
        "dry_run_command": dry_run_command,
        "future_runtime_command": (
            f"production_scheduler --window {window_id} --delivery-gate-check --require-manual-confirmation"
        ),
        "delivery_gate_ref": {
            "audit_id": refs.get("audit_id"),
            "bridge_id": refs.get("bridge_id"),
            "source_run_id": refs.get("source_run_id"),
        },
    }


def build_integration(data: dict[str, Any], bridge_path: Path, bridge: dict[str, Any]) -> dict[str, Any]:
    refs = bridge_refs(bridge_path, bridge)
    report_date = str(data.get("report_date") or refs.get("report_date") or "2026-06-30")
    windows = [window_entry(window, refs) for window in SCHEDULER_WINDOWS]
    return {
        "scheduler_integration_id": f"production_scheduler_delivery_gate_integration_{slug(report_date)}",
        "report_date": report_date,
        "runtime_mode": "fixture_dry_run_preview_only",
        "scheduler_windows": windows,
        "gate_preconditions": [
            "delivery_gate_audit_runtime_bridge_fixture_loaded",
            "source_schema_matched",
            "source_result_ok",
            "gate_required_for_each_scheduler_window",
            "delivery_allowed_false_in_fixture_mode",
            "external_side_effects_allowed_false",
        ],
        "approval_preconditions": [
            "manual_confirmation_required_before_schedule_or_service_change",
            "approval_required_for_each_scheduler_window",
            "review_status_must_be_approved_before_future_runtime_delivery",
            "delivery_allowed_must_be_true_before_future_runtime_delivery",
        ],
        "delivery_gate_refs": refs,
        "allowed_actions": deepcopy(ALLOWED_ACTIONS),
        "blocked_actions": deepcopy(BLOCKED_ACTIONS),
        "dry_run_entrypoints": {
            "integration_preview": "scripts/orchestrator/production_scheduler_delivery_gate_integration_dry_run.py",
            "integration_validator": "scripts/orchestrator/validate_production_scheduler_delivery_gate_integration_result.py",
            "source_bridge_preview": "scripts/orchestrator/delivery_gate_audit_runtime_bridge_dry_run.py",
        },
        "future_runtime_entrypoints": {
            "pre_open_0700": "production_scheduler --window pre_open_0700 --delivery-gate-check --require-manual-confirmation",
            "intraday_1305": "production_scheduler --window intraday_1305 --delivery-gate-check --require-manual-confirmation",
            "pre_close_1335": "production_scheduler --window pre_close_1335 --delivery-gate-check --require-manual-confirmation",
        },
        "rollback_plan": [
            "Do not alter existing cron, systemd, timer, or service definitions during this task.",
            "If a future scheduler change is proposed, keep a reviewed revert patch before activation.",
            "Disable future runtime entrypoints first, then restore the prior scheduler definition after manual confirmation.",
            "Re-run fixture validation before any future activation request.",
        ],
        "manual_confirmation_required": True,
    }


def build_summary(result: dict[str, Any]) -> dict[str, Any]:
    integration = as_dict(result.get("scheduler_delivery_gate_integration"))
    validation = as_dict(result.get("validation_summary"))
    windows = as_list(integration.get("scheduler_windows"))
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "task_id": result.get("task_id"),
        "run_id": result.get("run_id"),
        "generated_at": result.get("generated_at"),
        "mode": result.get("mode"),
        "scheduler_integration_id": integration.get("scheduler_integration_id"),
        "report_date": integration.get("report_date"),
        "runtime_mode": integration.get("runtime_mode"),
        "scheduler_window_ids": [as_dict(window).get("window_id") for window in windows],
        "scheduler_window_count": len(windows),
        "delivery_allowed": all(as_dict(window).get("delivery_allowed") is True for window in windows),
        "manual_confirmation_required": integration.get("manual_confirmation_required"),
        "cron_modified": False,
        "systemd_modified": False,
        "timer_modified": False,
        "service_modified": False,
        "deterministic_output": validation.get("deterministic_output"),
        "ok": result.get("ok"),
        "decision": result.get("decision"),
        "safety": deepcopy(result.get("safety")),
    }


def build_result(data: dict[str, Any]) -> dict[str, Any]:
    bridge_path = repo_path(as_dict(data.get("input_sources")).get("delivery_gate_audit_runtime_bridge_result_path"))
    bridge = load_json(bridge_path)
    integration = build_integration(data, bridge_path, bridge)
    windows = as_list(integration.get("scheduler_windows"))
    refs = as_dict(integration.get("delivery_gate_refs"))
    validation_summary = {
        "contract_name": CONTRACT_NAME,
        "contract_version": CONTRACT_VERSION,
        "deterministic_output": True,
        "fixture_only": True,
        "dry_run_only": True,
        "preview_only": True,
        "advisory_only": True,
        "source_schema_matched": refs.get("source_schema_matched") is True,
        "source_result_ok": refs.get("source_ok") is True,
        "scheduler_windows_present": [as_dict(window).get("window_id") for window in windows]
        == [window["window_id"] for window in SCHEDULER_WINDOWS],
        "scheduler_window_count": len(windows),
        "all_windows_gate_required": all(as_dict(window).get("gate_required") is True for window in windows),
        "all_windows_approval_required": all(as_dict(window).get("approval_required") is True for window in windows),
        "all_windows_delivery_allowed_false": all(
            as_dict(window).get("delivery_allowed") is False for window in windows
        ),
        "all_window_entrypoints_dry_run": all("dry_run" in str(as_dict(window).get("dry_run_command")) for window in windows),
        "manual_confirmation_required": integration.get("manual_confirmation_required") is True,
        "external_side_effects_allowed": False,
        "no_delivery_actions": True,
        "no_schedule_service_changes": True,
        "blocked_action_count": len(as_list(integration.get("blocked_actions"))),
        "allowed_action_count": len(as_list(integration.get("allowed_actions"))),
    }
    ok = (
        validation_summary["source_schema_matched"]
        and validation_summary["source_result_ok"]
        and validation_summary["scheduler_windows_present"]
        and validation_summary["all_windows_gate_required"]
        and validation_summary["all_windows_approval_required"]
        and validation_summary["all_windows_delivery_allowed_false"]
        and validation_summary["all_window_entrypoints_dry_run"]
        and validation_summary["manual_confirmation_required"]
        and all(value is False for value in SIDE_EFFECTS.values())
    )
    if not ok:
        decision = "validation_failed"
    elif integration["manual_confirmation_required"]:
        decision = "production_scheduler_delivery_gate_blocked_pending_runtime_confirmation"
    else:
        decision = "production_scheduler_delivery_gate_integration_completed"
    result = {
        "schema_version": SCHEMA_VERSION,
        "task_id": data.get("task_id", TASK_ID),
        "run_id": data.get("run_id", "production-scheduler-delivery-gate-integration-fixture"),
        "generated_at": data.get("generated_at"),
        "mode": "fixture_dry_run",
        "scheduler_delivery_gate_integration": integration,
        "scheduler_delivery_gate_summary": {},
        "validation_summary": validation_summary,
        "side_effects": deepcopy(SIDE_EFFECTS),
        "safety": deepcopy(SAFETY),
        "ok": ok,
        "decision": decision,
        "next_recommendation": (
            "Keep production scheduler integration advisory-only until manual runtime confirmation; "
            "do not modify cron, systemd, timers, services, delivery channels, databases, or external systems."
        ),
    }
    result["scheduler_delivery_gate_summary"] = build_summary(result)
    return result


def write_json(payload: Any, output: Path, pretty: bool) -> str:
    output.parent.mkdir(parents=True, exist_ok=True)
    rendered = stable_json(payload, pretty)
    output.write_text(rendered, encoding="utf-8")
    return rendered


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Production Scheduler Delivery Gate Integration V1 fixture.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", required=True)
    parser.add_argument("--summary-output", required=True)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build_result(load_json(Path(args.input)))
    rendered = write_json(result, Path(args.output), args.pretty)
    write_json(result["scheduler_delivery_gate_summary"], Path(args.summary_output), args.pretty)
    sys.stdout.write(rendered)
    if not rendered.endswith("\n"):
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
