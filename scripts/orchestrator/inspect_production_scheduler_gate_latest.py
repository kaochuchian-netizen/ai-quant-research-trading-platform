#!/usr/bin/env python3
"""Inspect latest Production Scheduler Gate runtime artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "production_scheduler_gate_observability_v1"
SUMMARY_SCHEMA_VERSION = "production_scheduler_gate_observability_summary_v1"
TASK_ID = "AI-DEV-103"
DEFAULT_GATE_RESULT = Path("/tmp/production_scheduler_gate_runtime_result.json")
DEFAULT_GATE_SUMMARY = Path("/tmp/production_scheduler_gate_runtime_summary.json")
DECISION_COMPLETED = "production_scheduler_gate_observability_completed"
DECISION_WARNINGS = "production_scheduler_gate_observability_completed_with_warnings"
DECISION_NOT_FOUND = "latest_gate_result_not_found"
DECISION_VALIDATION_FAILED = "validation_failed"

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
    "observability_only": True,
    "gated_runtime": True,
    "dry_run_default": True,
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


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().replace(microsecond=0).isoformat()


def load_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, "not_found"
    except json.JSONDecodeError as exc:
        return None, f"invalid_json: {exc}"
    except OSError as exc:
        return None, f"read_error: {exc}"
    if not isinstance(payload, dict):
        return None, "root_not_object"
    return payload, None


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def stable_json(payload: Any, pretty: bool) -> str:
    text = json.dumps(payload, ensure_ascii=False, indent=2 if pretty else None, sort_keys=True)
    return f"{text}\n" if pretty else text


def safe_side_effects(source: dict[str, Any] | None) -> dict[str, Any]:
    candidate = as_dict(source.get("side_effects")) if source else {}
    return {key: bool(candidate.get(key, False)) for key in SIDE_EFFECTS}


def safe_safety(source: dict[str, Any] | None) -> dict[str, Any]:
    candidate = as_dict(source.get("safety")) if source else {}
    safety = dict(SAFETY)
    for key in SAFETY:
        if key in candidate:
            safety[key] = candidate[key]
    return safety


def source_digest(payload: dict[str, Any] | None, path: Path, error: str | None) -> dict[str, Any]:
    return {
        "path": str(path),
        "found": payload is not None,
        "error": error,
        "schema_version": payload.get("schema_version") if payload else None,
        "task_id": payload.get("task_id") if payload else None,
        "run_id": payload.get("run_id") if payload else None,
        "generated_at": payload.get("generated_at") if payload else None,
        "mode": payload.get("mode") if payload else None,
        "scheduler_window": payload.get("scheduler_window") if payload else None,
        "decision": payload.get("decision") if payload else None,
        "ok": payload.get("ok") if payload else None,
    }


def build_result(gate_path: Path, summary_path: Path) -> dict[str, Any]:
    generated_at = now_iso()
    gate, gate_error = load_json(gate_path)
    summary, summary_error = load_json(summary_path)
    gate_decision = as_dict(gate.get("gate_runtime_decision")) if gate else {}
    warnings: list[str] = []

    if gate is None:
        decision = DECISION_NOT_FOUND if gate_error == "not_found" else DECISION_VALIDATION_FAILED
        ok = False
        observed_window = None
        delivery_allowed = False
        approval_status = "unknown"
        gate_runtime_decision: dict[str, Any] = {
            "source_found": False,
            "source_error": gate_error,
            "scheduler_window": None,
            "delivery_allowed": False,
            "approval_status": "unknown",
            "pipeline_execution_allowed": False,
            "delivery_execution_allowed": False,
        }
        next_recommendation = (
            "Wait for the next scheduled gated runtime, then rerun the inspection helper against the latest paths."
        )
    else:
        observed_window = gate.get("scheduler_window")
        delivery_allowed = gate.get("delivery_allowed") is True
        approval_status = str(gate.get("approval_status") or "unknown")
        gate_runtime_decision = {
            "source_found": True,
            "source_error": None,
            "runtime_run_id": gate.get("run_id"),
            "runtime_generated_at": gate.get("generated_at"),
            "scheduler_window": observed_window,
            "mode": gate.get("mode"),
            "delivery_allowed": delivery_allowed,
            "approval_status": approval_status,
            "runtime_decision": gate.get("decision"),
            "pipeline_execution_allowed": gate_decision.get("pipeline_execution_allowed") is True,
            "delivery_execution_allowed": gate_decision.get("delivery_execution_allowed") is True,
            "blocked_reason": gate_decision.get("blocked_reason"),
        }
        if summary is None:
            warnings.append(f"latest gate summary unavailable: {summary_error}")
        if delivery_allowed:
            warnings.append("latest gate runtime reports delivery_allowed=true")
        if gate_decision.get("pipeline_execution_allowed") is True:
            warnings.append("latest gate runtime reports pipeline_execution_allowed=true")
        if gate_decision.get("delivery_execution_allowed") is True:
            warnings.append("latest gate runtime reports delivery_execution_allowed=true")
        ok = not warnings
        decision = DECISION_WARNINGS if warnings else DECISION_COMPLETED
        next_recommendation = (
            "Review observed_scheduler_window, delivery_allowed, blocked_actions, side_effects, and safety after each "
            "scheduled run."
        )

    blocked_actions = as_list(gate.get("blocked_actions")) if gate else list(BLOCKED_ACTIONS)
    if not blocked_actions:
        blocked_actions = list(BLOCKED_ACTIONS)
    result = {
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "run_id": f"production-scheduler-gate-observability-{generated_at}",
        "generated_at": generated_at,
        "latest_timestamp": gate.get("generated_at") if gate else None,
        "mode": gate.get("mode") if gate else "read_only_observability",
        "observed_scheduler_window": observed_window,
        "latest_gate_result_path": str(gate_path),
        "latest_gate_summary_path": str(summary_path),
        "delivery_allowed": delivery_allowed,
        "approval_status": approval_status,
        "gate_runtime_decision": gate_runtime_decision,
        "blocked_actions": blocked_actions,
        "side_effects": safe_side_effects(gate),
        "safety": safe_safety(gate),
        "sources": {
            "latest_gate_result": source_digest(gate, gate_path, gate_error),
            "latest_gate_summary": source_digest(summary, summary_path, summary_error),
        },
        "warnings": warnings,
        "ok": ok,
        "decision": decision,
        "next_recommendation": next_recommendation,
    }
    result["observability_summary"] = build_summary(result)
    return result


def build_summary(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "task_id": result.get("task_id"),
        "run_id": result.get("run_id"),
        "generated_at": result.get("generated_at"),
        "latest_timestamp": result.get("latest_timestamp"),
        "mode": result.get("mode"),
        "observed_scheduler_window": result.get("observed_scheduler_window"),
        "latest_gate_result_path": result.get("latest_gate_result_path"),
        "latest_gate_summary_path": result.get("latest_gate_summary_path"),
        "delivery_allowed": result.get("delivery_allowed"),
        "approval_status": result.get("approval_status"),
        "decision": result.get("decision"),
        "ok": result.get("ok"),
        "warnings": result.get("warnings"),
        "blocked_actions_count": len(as_list(result.get("blocked_actions"))),
        "external_side_effects_allowed": as_dict(result.get("side_effects")).get("external_side_effects_allowed"),
        "no_delivery_actions": as_dict(result.get("safety")).get("no_delivery_actions"),
        "no_cron_installation": as_dict(result.get("safety")).get("no_cron_installation"),
        "no_systemd_installation": as_dict(result.get("safety")).get("no_systemd_installation"),
        "no_timer_installation": as_dict(result.get("safety")).get("no_timer_installation"),
        "no_service_installation": as_dict(result.get("safety")).get("no_service_installation"),
    }


def write_json(payload: Any, path: Path, pretty: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(payload, pretty), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect latest Production Scheduler Gate observability artifacts.")
    parser.add_argument("--latest-gate-result", default=str(DEFAULT_GATE_RESULT))
    parser.add_argument("--latest-gate-summary", default=str(DEFAULT_GATE_SUMMARY))
    parser.add_argument("--output", required=True)
    parser.add_argument("--summary-output", required=True)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build_result(Path(args.latest_gate_result), Path(args.latest_gate_summary))
    write_json(result, Path(args.output), args.pretty)
    write_json(result["observability_summary"], Path(args.summary_output), args.pretty)
    sys.stdout.write(stable_json(result, args.pretty))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
