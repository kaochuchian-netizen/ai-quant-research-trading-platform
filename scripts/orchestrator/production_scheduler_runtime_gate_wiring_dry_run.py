#!/usr/bin/env python3
"""Build deterministic Production Scheduler Runtime Gate Wiring V1 artifacts."""

from __future__ import annotations

import argparse
import json
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any


DEFAULT_INPUT = Path("templates/production_scheduler_runtime_gate_wiring_input.example.json")
SCHEMA_VERSION = "production_scheduler_runtime_gate_wiring_v1"
SUMMARY_SCHEMA_VERSION = "production_scheduler_runtime_gate_wiring_summary_v1"
TASK_ID = "AI-DEV-100"
CONTRACT_NAME = "production_scheduler_runtime_gate_wiring"
CONTRACT_VERSION = "v1"
SOURCE_SCHEMA_VERSION = "production_scheduler_delivery_gate_integration_v1"
CURRENT_ENTRYPOINT = "/home/kaochuchian/stock-ai/run_stock_analysis.sh"
WINDOWS = [
    {
        "scheduler_window_id": "pre_open_0700",
        "local_time": "07:00",
        "cron_expression": "0 7 * * 1-5",
        "pipeline_type": "pre_open",
        "pipeline_context": "daily_pre_open_analysis",
    },
    {
        "scheduler_window_id": "intraday_1305",
        "local_time": "13:05",
        "cron_expression": "5 13 * * 1-5",
        "pipeline_type": "intraday",
        "pipeline_context": "intraday_analysis_refresh",
    },
    {
        "scheduler_window_id": "pre_close_1335",
        "local_time": "13:35",
        "cron_expression": "35 13 * * 1-5",
        "pipeline_type": "pre_close",
        "pipeline_context": "pre_close_analysis_refresh",
    },
]
ALLOWED_SIDE_EFFECTS = [
    "read_repo_fixture",
    "read_documented_scheduler_inspection_summary",
    "build_runtime_gate_wiring_preview",
    "write_requested_json_outputs",
    "validate_fixture_contract",
]
BLOCKED_SIDE_EFFECTS = [
    "cron_modification",
    "systemd_modification",
    "timer_modification",
    "service_modification",
    "schedule_service_change",
    "email_send",
    "line_push",
    "dashboard_deploy",
    "api_server_creation",
    "smtp_call",
    "gmail_api_call",
    "market_data_mutation",
    "model_runtime_call",
    "production_db_write",
    "persistent_store_write",
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
    "gated_dry_run_first": True,
    "advisory_only": True,
    "manual_confirmation_required": True,
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
    "no_cron_modification": True,
    "no_systemd_modification": True,
    "no_timer_modification": True,
    "no_service_modification": True,
    "no_schedule_service_changes": True,
    "external_side_effects_allowed": False,
    "dashboard_deploy": False,
    "api_server_created": False,
    "trading_instruction": False,
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


def source_refs(path: Path, source: dict[str, Any]) -> dict[str, Any]:
    integration = as_dict(source.get("scheduler_delivery_gate_integration"))
    summary = as_dict(source.get("scheduler_delivery_gate_summary"))
    return {
        "source_path": str(path),
        "source_schema_expected": SOURCE_SCHEMA_VERSION,
        "source_schema_version": source.get("schema_version"),
        "source_schema_matched": source.get("schema_version") == SOURCE_SCHEMA_VERSION,
        "source_task_id": source.get("task_id"),
        "source_run_id": source.get("run_id"),
        "source_generated_at": source.get("generated_at"),
        "source_mode": source.get("mode"),
        "source_ok": source.get("ok") is True,
        "source_decision": source.get("decision"),
        "source_scheduler_integration_id": integration.get("scheduler_integration_id"),
        "source_scheduler_window_ids": summary.get("scheduler_window_ids"),
        "source_delivery_allowed": summary.get("delivery_allowed") is True,
        "source_manual_confirmation_required": summary.get("manual_confirmation_required") is True,
    }


def inspection_summary(data: dict[str, Any]) -> dict[str, Any]:
    supplied = as_dict(data.get("scheduler_inspection_summary"))
    entries = as_list(supplied.get("current_scheduler_entrypoints_found"))
    return {
        "inspection_mode": "read_only_documented_fixture",
        "cron_inspection_status": "completed_read_only" if entries else "not_available",
        "systemd_inspection_status": supplied.get("systemd_inspection_status", "not_available"),
        "timer_inspection_status": supplied.get("timer_inspection_status", "not_available"),
        "service_inspection_status": supplied.get("service_inspection_status", "not_available"),
        "current_scheduler_entrypoints_found": deepcopy(entries),
        "inspected_repo_files": deepcopy(as_list(supplied.get("inspected_repo_files"))),
        "inspection_notes": deepcopy(as_list(supplied.get("inspection_notes"))),
        "inspection_warnings": [
            "No cron, systemd, timer, or service definitions are modified by this artifact.",
            "systemd and timer live state may require host-level inspection outside this sandbox before activation.",
        ],
    }


def window_wiring(window: dict[str, str], refs: dict[str, Any]) -> dict[str, Any]:
    window_id = window["scheduler_window_id"]
    dry_run_command = (
        "python3 scripts/orchestrator/production_scheduler_runtime_gate_wiring_dry_run.py "
        "--input templates/production_scheduler_runtime_gate_wiring_input.example.json "
        "--output /tmp/production_scheduler_runtime_gate_wiring_result.json "
        "--summary-output /tmp/production_scheduler_runtime_gate_wiring_summary.json --pretty"
    )
    return {
        "scheduler_window_id": window_id,
        "local_time": window["local_time"],
        "cron_expression": window["cron_expression"],
        "pipeline_type": window["pipeline_type"],
        "pipeline_context": window["pipeline_context"],
        "current_entrypoint": CURRENT_ENTRYPOINT,
        "proposed_gate_entrypoint": "scripts/orchestrator/production_scheduler_runtime_gate_wiring_dry_run.py",
        "dry_run_command": dry_run_command,
        "future_runtime_command": (
            f"production_scheduler_runtime_gate --window {window_id} "
            f"--pipeline {window['pipeline_type']} --delivery-gate-required "
            "--require-manual-confirmation"
        ),
        "delivery_gate_required": True,
        "approval_required": True,
        "manual_confirmation_required": True,
        "allowed_side_effects": deepcopy(ALLOWED_SIDE_EFFECTS),
        "blocked_side_effects": deepcopy(BLOCKED_SIDE_EFFECTS),
        "rollback_plan": [
            "Keep the current scheduler entrypoint unchanged until explicit service-change confirmation is granted.",
            "If future activation is approved, retain the prior crontab or service definition as the immediate rollback target.",
            "Revert the scheduler window to /home/kaochuchian/stock-ai/run_stock_analysis.sh if gate wiring activation fails.",
            "Re-run dry-run validation before and after any future scheduler service change proposal.",
        ],
        "delivery_gate_ref": {
            "source_scheduler_integration_id": refs.get("source_scheduler_integration_id"),
            "source_run_id": refs.get("source_run_id"),
            "source_decision": refs.get("source_decision"),
            "source_manual_confirmation_required": refs.get("source_manual_confirmation_required"),
        },
    }


def build_wiring(data: dict[str, Any], source_path: Path, source: dict[str, Any]) -> dict[str, Any]:
    refs = source_refs(source_path, source)
    report_date = str(data.get("report_date") or "2026-06-30")
    return {
        "wiring_id": f"production_scheduler_runtime_gate_wiring_{slug(report_date)}",
        "report_date": report_date,
        "runtime_mode": "gated_dry_run_first_advisory_only",
        "source_integration_refs": refs,
        "scheduler_windows": [window_wiring(window, refs) for window in WINDOWS],
        "contract_requirements": [
            "delivery_gate_required_for_each_scheduler_window",
            "manual_confirmation_required_for_any_scheduler_service_change",
            "dry_run_command_must_be_repo_only",
            "future_runtime_command_must_require_manual_confirmation",
            "no_cron_systemd_timer_service_mutation_in_this_task",
        ],
        "activation_boundary": {
            "actual_cron_change_allowed": False,
            "actual_systemd_change_allowed": False,
            "actual_timer_change_allowed": False,
            "actual_service_change_allowed": False,
            "requires_new_explicit_confirmation": True,
            "pending_confirmation_reason": "actual scheduler service mutation is outside AI-DEV-100 scope",
        },
        "rollback_plan": [
            "No rollback is required for this repo-only dry-run artifact because no live scheduler state is changed.",
            "For any future approved activation, snapshot existing scheduler definitions before applying changes.",
            "Use the prior run_stock_analysis.sh scheduler command as the first rollback target.",
            "Block delivery actions until the Delivery Gate and runtime wiring validators both pass.",
        ],
    }


def build_summary(result: dict[str, Any]) -> dict[str, Any]:
    wiring = as_dict(result.get("production_scheduler_runtime_gate_wiring"))
    validation = as_dict(result.get("validation_summary"))
    windows = as_list(wiring.get("scheduler_windows"))
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "task_id": result.get("task_id"),
        "run_id": result.get("run_id"),
        "generated_at": result.get("generated_at"),
        "mode": result.get("mode"),
        "wiring_id": wiring.get("wiring_id"),
        "report_date": wiring.get("report_date"),
        "runtime_mode": wiring.get("runtime_mode"),
        "scheduler_window_ids": [as_dict(window).get("scheduler_window_id") for window in windows],
        "scheduler_window_count": len(windows),
        "current_entrypoints": sorted(set(str(as_dict(window).get("current_entrypoint")) for window in windows)),
        "proposed_gate_entrypoints": sorted(
            set(str(as_dict(window).get("proposed_gate_entrypoint")) for window in windows)
        ),
        "manual_confirmation_required": True,
        "actual_service_change_pending_explicit_confirmation": True,
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
    source_path = repo_path(as_dict(data.get("input_sources")).get("production_scheduler_delivery_gate_integration_result_path"))
    source = load_json(source_path)
    wiring = build_wiring(data, source_path, source)
    windows = as_list(wiring.get("scheduler_windows"))
    refs = as_dict(wiring.get("source_integration_refs"))
    validation_summary = {
        "contract_name": CONTRACT_NAME,
        "contract_version": CONTRACT_VERSION,
        "deterministic_output": True,
        "repo_only": True,
        "gated_dry_run_first": True,
        "advisory_only": True,
        "source_schema_matched": refs.get("source_schema_matched") is True,
        "source_result_ok": refs.get("source_ok") is True,
        "scheduler_windows_present": [as_dict(window).get("scheduler_window_id") for window in windows]
        == [window["scheduler_window_id"] for window in WINDOWS],
        "scheduler_window_count": len(windows),
        "all_windows_delivery_gate_required": all(
            as_dict(window).get("delivery_gate_required") is True for window in windows
        ),
        "all_windows_approval_required": all(as_dict(window).get("approval_required") is True for window in windows),
        "all_windows_manual_confirmation_required": all(
            as_dict(window).get("manual_confirmation_required") is True for window in windows
        ),
        "all_window_entrypoints_dry_run": all("dry_run" in str(as_dict(window).get("dry_run_command")) for window in windows),
        "all_future_runtime_commands_require_confirmation": all(
            "--require-manual-confirmation" in str(as_dict(window).get("future_runtime_command")) for window in windows
        ),
        "no_schedule_service_changes": True,
        "blocked_side_effect_count": len(BLOCKED_SIDE_EFFECTS),
        "allowed_side_effect_count": len(ALLOWED_SIDE_EFFECTS),
    }
    ok = (
        validation_summary["source_schema_matched"]
        and validation_summary["source_result_ok"]
        and validation_summary["scheduler_windows_present"]
        and validation_summary["all_windows_delivery_gate_required"]
        and validation_summary["all_windows_approval_required"]
        and validation_summary["all_windows_manual_confirmation_required"]
        and validation_summary["all_window_entrypoints_dry_run"]
        and validation_summary["all_future_runtime_commands_require_confirmation"]
        and all(value is False for value in SIDE_EFFECTS.values())
    )
    decision = "runtime_wiring_blocked_pending_service_change_confirmation" if ok else "validation_failed"
    result = {
        "schema_version": SCHEMA_VERSION,
        "task_id": data.get("task_id", TASK_ID),
        "run_id": data.get("run_id", "production-scheduler-runtime-gate-wiring-fixture"),
        "generated_at": data.get("generated_at"),
        "mode": "fixture_gated_dry_run",
        "scheduler_inspection_summary": inspection_summary(data),
        "production_scheduler_runtime_gate_wiring": wiring,
        "runtime_gate_wiring_summary": {},
        "validation_summary": validation_summary,
        "side_effects": deepcopy(SIDE_EFFECTS),
        "safety": deepcopy(SAFETY),
        "ok": ok,
        "decision": decision,
        "next_recommendation": (
            "Keep the current scheduler unchanged. Request explicit confirmation before any cron, systemd, "
            "timer, or service mutation that activates the proposed runtime gate wiring."
        ),
    }
    result["runtime_gate_wiring_summary"] = build_summary(result)
    return result


def write_json(payload: Any, output: Path, pretty: bool) -> str:
    output.parent.mkdir(parents=True, exist_ok=True)
    rendered = stable_json(payload, pretty)
    output.write_text(rendered, encoding="utf-8")
    return rendered


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Production Scheduler Runtime Gate Wiring V1 fixture.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", required=True)
    parser.add_argument("--summary-output", required=True)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build_result(load_json(Path(args.input)))
    rendered = write_json(result, Path(args.output), args.pretty)
    write_json(result["runtime_gate_wiring_summary"], Path(args.summary_output), args.pretty)
    sys.stdout.write(rendered)
    if not rendered.endswith("\n"):
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
