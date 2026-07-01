#!/usr/bin/env python3
"""Repo-side Production Scheduler Gate Runtime Activation V1."""

from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any


DEFAULT_INPUT = Path("templates/production_scheduler_gate_runtime_input.example.json")
SCHEMA_VERSION = "production_scheduler_gate_runtime_activation_v1"
SUMMARY_SCHEMA_VERSION = "production_scheduler_gate_runtime_summary_v1"
TASK_ID = "AI-DEV-101"
WINDOWS = {
    "pre_open_0700": {"local_time": "07:00", "pipeline_type": "pre_open"},
    "intraday_1305": {"local_time": "13:05", "pipeline_type": "intraday"},
    "pre_close_1335": {"local_time": "13:35", "pipeline_type": "pre_close"},
    "post_close_1500": {"local_time": "15:00", "pipeline_type": "post_close"},
}
CHANNELS = ["email", "line", "dashboard"]
APPROVED_STATUSES = {"approved", "APPROVED"}
DECISION_COMPLETED = "production_scheduler_gate_runtime_activation_completed"
DECISION_WARNINGS = "production_scheduler_gate_runtime_activation_completed_with_warnings"
DECISION_PENDING = "production_scheduler_gate_runtime_blocked_pending_approval"
DECISION_SERVICE_PENDING = "service_installation_blocked_pending_confirmation"
DECISION_FAILED = "validation_failed"

BLOCKED_ACTIONS = [
    "email_send",
    "line_push",
    "dashboard_deploy",
    "api_server_creation",
    "smtp_call",
    "gmail_api_call",
    "production_db_write",
    "persistent_store_write",
    "market_data_mutation",
    "external_model_call",
    "portfolio_action",
    "trading_instruction",
    "cron_installation",
    "systemd_installation",
    "timer_installation",
    "service_installation",
    "live_schedule_mutation",
]
ALLOWED_ACTIONS = [
    "read_repo_fixture",
    "read_gate_runtime_bridge_fixture",
    "evaluate_scheduler_window_gate",
    "write_requested_json_outputs",
    "print_clear_decision_output",
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
    "external_side_effects_allowed": False,
}
SAFETY = {
    "repo_only": True,
    "gated_runtime": True,
    "dry_run_default": True,
    "manual_confirmation_required_for_service_install": True,
    "no_external_model_calls": True,
    "no_market_data_mutation": True,
    "no_delivery_actions": True,
    "no_email_send": True,
    "no_line_push": True,
    "no_dashboard_deploy": True,
    "no_smtp_call": True,
    "no_gmail_api_call": True,
    "no_api_server_created": True,
    "no_persistent_store_writes": True,
    "no_portfolio_actions": True,
    "no_cron_installation": True,
    "no_systemd_installation": True,
    "no_timer_installation": True,
    "no_service_installation": True,
    "no_live_schedule_mutation": True,
    "external_side_effects_allowed": False,
    "dashboard_deploy": False,
    "api_server_created": False,
    "trading_instruction": False,
}


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"input file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"input file is not valid JSON: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit("input JSON root must be an object")
    return payload


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def repo_path(raw_path: Any) -> Path:
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise SystemExit("referenced fixture path must be a non-empty string")
    path = Path(raw_path)
    if path.is_absolute() or ".." in path.parts:
        raise SystemExit("referenced fixture path must be repo-relative and must not contain parent traversal")
    return path


def stable_json(payload: Any, pretty: bool) -> str:
    text = json.dumps(payload, ensure_ascii=False, indent=2 if pretty else None, sort_keys=True)
    return f"{text}\n" if pretty else text


def source_refs(path: Path, payload: dict[str, Any], expected_schema: str) -> dict[str, Any]:
    summary = as_dict(payload.get("runtime_gate_wiring_summary") or payload.get("scheduler_delivery_gate_summary"))
    return {
        "source_path": str(path),
        "source_schema_expected": expected_schema,
        "source_schema_version": payload.get("schema_version"),
        "source_schema_matched": payload.get("schema_version") == expected_schema,
        "source_task_id": payload.get("task_id"),
        "source_run_id": payload.get("run_id"),
        "source_generated_at": payload.get("generated_at"),
        "source_mode": payload.get("mode"),
        "source_ok": payload.get("ok") is True,
        "source_decision": payload.get("decision"),
        "source_delivery_allowed": summary.get("delivery_allowed") is True,
        "source_manual_confirmation_required": (
            summary.get("manual_confirmation_required") is True
            or summary.get("actual_service_change_pending_explicit_confirmation") is True
        ),
    }


def channel_decisions(
    delivery_allowed: bool, approval_status: str, approved: bool
) -> list[dict[str, Any]]:
    return [
        {
            "channel": channel,
            "delivery_allowed": False,
            "approval_status": approval_status,
            "approved": approved,
            "blocked": not (delivery_allowed and approved),
            "blocked_reason": (
                "delivery_allowed_false_or_approval_not_approved"
                if not (delivery_allowed and approved)
                else "delivery_still_disabled_by_runtime_safety_boundary"
            ),
        }
        for channel in CHANNELS
    ]


def build_result(data: dict[str, Any], window_id: str) -> dict[str, Any]:
    if window_id not in WINDOWS:
        raise SystemExit(f"unsupported scheduler window: {window_id}")

    sources = as_dict(data.get("input_sources"))
    delivery_path = repo_path(sources.get("production_scheduler_delivery_gate_integration_result_path"))
    wiring_path = repo_path(sources.get("production_scheduler_runtime_gate_wiring_result_path"))
    delivery_result = load_json(delivery_path)
    wiring_result = load_json(wiring_path)
    delivery_refs = source_refs(delivery_path, delivery_result, "production_scheduler_delivery_gate_integration_v1")
    wiring_refs = source_refs(wiring_path, wiring_result, "production_scheduler_runtime_gate_wiring_v1")

    runtime_gate = as_dict(data.get("runtime_gate"))
    delivery_allowed = bool(runtime_gate.get("delivery_allowed")) and delivery_refs["source_delivery_allowed"]
    approval_status = str(runtime_gate.get("approval_status") or "pending_approval")
    approved = approval_status in APPROVED_STATUSES
    mode = str(data.get("mode") or "dry_run_no_delivery")
    service_install_requested = bool(runtime_gate.get("service_install_requested"))
    window = WINDOWS[window_id]
    source_ok = delivery_refs["source_schema_matched"] and delivery_refs["source_ok"]
    wiring_ok = wiring_refs["source_schema_matched"] and wiring_refs["source_ok"]
    external_blocked = all(value is False for value in SIDE_EFFECTS.values())

    if not (source_ok and wiring_ok):
        decision = DECISION_FAILED
        ok = False
    elif service_install_requested:
        decision = DECISION_SERVICE_PENDING
        ok = True
    elif delivery_allowed and approved:
        decision = DECISION_WARNINGS if mode != "dry_run_no_delivery" else DECISION_COMPLETED
        ok = True
    else:
        decision = DECISION_PENDING
        ok = True

    gate_runtime_decision = {
        "runtime_id": f"production_scheduler_gate_runtime_{window_id}_20260630",
        "scheduler_window": window_id,
        "local_time": window["local_time"],
        "pipeline_type": window["pipeline_type"],
        "mode": mode,
        "dry_run": True,
        "delivery_allowed_input": bool(runtime_gate.get("delivery_allowed")),
        "delivery_allowed": delivery_allowed,
        "approval_status": approval_status,
        "approval_required": True,
        "approved": approved,
        "pipeline_execution_allowed": False,
        "delivery_execution_allowed": False,
        "service_install_requested": service_install_requested,
        "service_install_allowed": False,
        "delivery_gate_refs": delivery_refs,
        "runtime_wiring_refs": wiring_refs,
        "channel_decisions": channel_decisions(delivery_allowed, approval_status, approved),
        "blocked_reason": (
            "service_installation_requires_separate_explicit_confirmation"
            if service_install_requested
            else "delivery_allowed_false_or_approval_not_approved"
            if not (delivery_allowed and approved)
            else "approved_gate_observed_but_delivery_side_effects_remain_disabled_in_repo_runtime"
        ),
    }
    validation_summary = {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "task_id": TASK_ID,
        "deterministic_output": True,
        "scheduler_window_supported": True,
        "delivery_source_schema_matched": delivery_refs["source_schema_matched"],
        "delivery_source_ok": delivery_refs["source_ok"],
        "runtime_wiring_source_schema_matched": wiring_refs["source_schema_matched"],
        "runtime_wiring_source_ok": wiring_refs["source_ok"],
        "delivery_allowed_enforced": delivery_allowed is False,
        "approval_status_enforced": not approved,
        "delivery_actions_blocked": True,
        "service_installation_blocked": True,
        "external_side_effects_blocked": external_blocked,
    }
    result = {
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "run_id": data.get("run_id", f"production-scheduler-gate-runtime-{window_id}-fixture-20260630"),
        "generated_at": data.get("generated_at", "2026-06-30T12:30:00+08:00"),
        "mode": mode,
        "scheduler_window": window_id,
        "gate_runtime_decision": gate_runtime_decision,
        "delivery_allowed": delivery_allowed,
        "approval_status": approval_status,
        "channels": deepcopy(CHANNELS),
        "blocked_actions": deepcopy(BLOCKED_ACTIONS),
        "allowed_actions": deepcopy(ALLOWED_ACTIONS),
        "side_effects": deepcopy(SIDE_EFFECTS),
        "safety": deepcopy(SAFETY),
        "validation_summary": validation_summary,
        "ok": ok,
        "decision": decision,
        "next_recommendation": (
            "Keep scheduler runtime in dry-run/no-delivery mode. Service installation or live schedule mutation "
            "remains pending a separate explicit confirmation."
        ),
    }
    result["runtime_summary"] = build_summary(result)
    return result


def build_summary(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "task_id": result.get("task_id"),
        "run_id": result.get("run_id"),
        "generated_at": result.get("generated_at"),
        "mode": result.get("mode"),
        "scheduler_window": result.get("scheduler_window"),
        "decision": result.get("decision"),
        "delivery_allowed": result.get("delivery_allowed"),
        "approval_status": result.get("approval_status"),
        "channels": deepcopy(result.get("channels")),
        "blocked_actions": deepcopy(result.get("blocked_actions")),
        "allowed_actions": deepcopy(result.get("allowed_actions")),
        "deterministic_output": as_dict(result.get("validation_summary")).get("deterministic_output"),
        "cron_installed": False,
        "systemd_installed": False,
        "timer_installed": False,
        "service_installed": False,
        "live_schedule_mutated": False,
        "ok": result.get("ok"),
    }


def write_json(payload: Any, output: Path, pretty: bool) -> str:
    output.parent.mkdir(parents=True, exist_ok=True)
    rendered = stable_json(payload, pretty)
    output.write_text(rendered, encoding="utf-8")
    return rendered


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Production Scheduler Gate Runtime Activation V1.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", required=True)
    parser.add_argument("--summary-output", required=True)
    parser.add_argument("--window", required=True, choices=sorted(WINDOWS))
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build_result(load_json(Path(args.input)), args.window)
    rendered = write_json(result, Path(args.output), args.pretty)
    write_json(result["runtime_summary"], Path(args.summary_output), args.pretty)
    sys.stdout.write(rendered)
    if not rendered.endswith("\n"):
        sys.stdout.write("\n")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
