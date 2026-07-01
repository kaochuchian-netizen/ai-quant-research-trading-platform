#!/usr/bin/env python3
"""Unified Controlled LINE + Email + Dashboard Delivery Runtime V1."""

from __future__ import annotations

import argparse
import json
import os
import sys
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


DEFAULT_INPUT = Path("templates/unified_controlled_delivery_runtime_input.example.json")
SCHEMA_VERSION = "unified_controlled_delivery_runtime_v1"
SUMMARY_SCHEMA_VERSION = "unified_controlled_delivery_runtime_summary_v1"
TASK_ID = "AI-DEV-107"
APPROVED_STATUSES = {"approved", "APPROVED"}
CHANNELS = ["line", "email", "dashboard"]
DECISION_COMPLETED = "unified_controlled_delivery_runtime_completed"
DECISION_WARNINGS = "unified_controlled_delivery_runtime_completed_with_warnings"
DECISION_BLOCKED = "unified_delivery_blocked_pending_approval"
DECISION_READY = "unified_delivery_ready_pending_manual_tests"
DECISION_VALIDATION_FAILED = "validation_failed"
DECISION_RUNTIME_BLOCKED = "blocked"
EMAIL_ENV_NAMES = [
    "ORCH_MAIL_HOST",
    "ORCH_MAIL_PORT",
    "ORCH_MAIL_USER",
    "ORCH_MAIL_PASS",
    "ORCH_MAIL_FROM",
    "ORCH_MAIL_TO",
]
DEFAULT_MAIL_ENV_FILE = Path("~/.config/stock-ai-orchestrator/mail.env")
SIDE_EFFECTS_BASE = {
    "read_secrets": False,
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
    "modified_cron": False,
    "modified_systemd": False,
    "modified_timer": False,
    "modified_service": False,
    "modified_schedule_or_service": False,
}
SAFETY = {
    "controlled_delivery_runtime": True,
    "dry_run_default": True,
    "delivery_gate_required": True,
    "no_token_printing": True,
    "no_secret_logging": True,
    "no_secret_read": True,
    "no_line_push_by_default": True,
    "no_email_send_by_default": True,
    "no_dashboard_publish_by_default": True,
    "no_smtp_call_by_default": True,
    "no_gmail_api_call_by_default": True,
    "no_api_server_created": True,
    "no_persistent_store_writes": True,
    "no_portfolio_actions": True,
    "no_cron_modification": True,
    "no_systemd_modification": True,
    "no_timer_modification": True,
    "no_service_modification": True,
    "no_schedule_service_changes": True,
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


def stable_json(payload: Any, pretty: bool) -> str:
    text = json.dumps(payload, ensure_ascii=False, indent=2 if pretty else None, sort_keys=True)
    return f"{text}\n" if pretty else text


def now_taipei() -> str:
    return datetime.now(ZoneInfo("Asia/Taipei")).replace(microsecond=0).isoformat()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def parse_env_assignment(line: str) -> tuple[str, str] | None:
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    if line.startswith("export "):
        line = line[len("export "):].strip()
    if "=" not in line:
        return None
    key, value = line.split("=", 1)
    key = key.strip()
    value = value.strip().strip('"').strip("'")
    if key not in EMAIL_ENV_NAMES:
        return None
    return key, value


def load_mail_env_file(path: Path) -> dict[str, Any]:
    expanded = path.expanduser()
    exists = expanded.exists()
    loaded = False
    error_type = None
    if exists:
        try:
            for line in expanded.read_text(encoding="utf-8").splitlines():
                parsed = parse_env_assignment(line)
                if parsed is None:
                    continue
                key, value = parsed
                os.environ.setdefault(key, value)
            loaded = True
        except Exception as exc:  # pragma: no cover - local runtime failure path
            error_type = exc.__class__.__name__
    return {
        "attempted": True,
        "path": str(expanded),
        "exists": exists,
        "loaded": loaded,
        "error_type": error_type,
        "value_printed": False,
    }


def env_presence(names: list[str]) -> dict[str, Any]:
    present = [name for name in names if os.environ.get(name)]
    missing = [name for name in names if not os.environ.get(name)]
    return {
        "inspected": True,
        "value_printed": False,
        "required_env_names": names,
        "present_env_names": present,
        "missing_env_names": missing,
        "all_required_present": not missing,
    }


def gate_status(data: dict[str, Any]) -> dict[str, Any]:
    raw = as_dict(data.get("gate_status"))
    delivery_allowed = raw.get("delivery_allowed") is True or data.get("delivery_allowed") is True
    approval_status = str(raw.get("approval_status") or data.get("approval_status") or "pending_approval")
    approved = approval_status in APPROVED_STATUSES
    channels = as_dict(data.get("channels"))
    preconditions = {
        "delivery_allowed": delivery_allowed,
        "approval_status_approved": approved,
        "line_channel_enabled": as_dict(channels.get("line")).get("enabled") is True,
        "email_channel_enabled": as_dict(channels.get("email")).get("enabled") is True,
        "dashboard_channel_enabled": as_dict(channels.get("dashboard")).get("enabled") is True,
    }
    blockers = [key for key, value in preconditions.items() if value is not True]
    return {
        "delivery_allowed": delivery_allowed,
        "approval_status": approval_status,
        "approved": approved,
        "preconditions": preconditions,
        "gate_open": not blockers,
        "blocked_reasons": blockers,
    }


def channel_decisions(data: dict[str, Any], gate: dict[str, Any]) -> dict[str, dict[str, Any]]:
    channels = as_dict(data.get("channels"))
    decisions: dict[str, dict[str, Any]] = {}
    for channel in CHANNELS:
        config = as_dict(channels.get(channel))
        enabled = config.get("enabled") is True
        allowed = gate["delivery_allowed"] is True and gate["approved"] is True and enabled
        decisions[channel] = {
            "enabled": enabled,
            "delivery_allowed": allowed,
            "approval_status": gate["approval_status"],
            "approved": gate["approved"],
            "runtime_action_allowed": False,
            "blocked_reason": None if allowed else f"{channel}_gate_not_approved_or_disabled",
        }
    return decisions


def command_for_runtime(flag: str, output_name: str) -> str:
    return (
        "python3 scripts/orchestrator/unified_controlled_delivery_runtime.py "
        "--input templates/unified_controlled_delivery_runtime_input.example.json "
        f"--output /tmp/{output_name} "
        "--summary-output /tmp/unified_controlled_delivery_runtime_summary.json "
        f"--pretty {flag}"
    )


def email_test_command() -> str:
    return (
        "python3 scripts/orchestrator/controlled_email_runtime.py "
        "--input templates/unified_controlled_delivery_runtime_input.example.json "
        "--output /tmp/controlled_email_runtime_result.json "
        "--summary-output /tmp/controlled_email_runtime_summary.json "
        "--pretty --send-test-email"
    )


def dashboard_publish_command() -> str:
    return (
        "python3 scripts/orchestrator/private_static_dashboard_publish.py "
        "--input templates/dashboard_delivery_gate_result.example.json "
        "--output /tmp/private_static_dashboard_publish_result.json "
        "--pretty --publish --auto-browser-target"
    )


def scheduler_activation_command() -> str:
    return (
        "python3 scripts/orchestrator/production_scheduler_gate_runtime.py "
        "--input templates/production_scheduler_gate_runtime_input.example.json "
        "--output /tmp/production_scheduler_gate_runtime_result.json "
        "--summary-output /tmp/production_scheduler_gate_runtime_summary.json "
        "--window pre_open_0700 --pretty"
    )


def build_line_status(decisions: dict[str, dict[str, Any]], send_test_line: bool) -> dict[str, Any]:
    allowed = decisions["line"]["delivery_allowed"] is True
    return {
        "runtime": "scripts/orchestrator/controlled_line_runtime.py",
        "requested": send_test_line,
        "dry_run": not send_test_line,
        "gate_approved_for_manual_test": allowed,
        "send_attempted": False,
        "send_status": "blocked_pending_manual_confirmation"
        if send_test_line
        else "dry_run_not_sent",
        "requires_separate_user_confirmation": True,
        "note": "Unified runtime does not perform LINE push automatically.",
    }


def build_email_status(decisions: dict[str, dict[str, Any]], send_test_email: bool) -> dict[str, Any]:
    env_file = load_mail_env_file(DEFAULT_MAIL_ENV_FILE)
    presence = env_presence(EMAIL_ENV_NAMES)
    allowed = decisions["email"]["delivery_allowed"] is True
    return {
        "runtime": "scripts/orchestrator/controlled_email_runtime.py",
        "requested": send_test_email,
        "dry_run": not send_test_email,
        "gate_approved_for_manual_test": allowed,
        "mail_env_file": env_file,
        "runtime_settings_present": presence["all_required_present"],
        "runtime_settings_presence": presence,
        "send_attempted": False,
        "send_status": "blocked_pending_manual_confirmation"
        if send_test_email
        else "dry_run_not_sent",
        "requires_separate_user_confirmation": True,
        "note": "Unified runtime inspects env var presence only and does not print secret values.",
    }


def build_dashboard_status(decisions: dict[str, dict[str, Any]], publish_dashboard: bool, data: dict[str, Any]) -> dict[str, Any]:
    allowed = decisions["dashboard"]["delivery_allowed"] is True
    publish_path = str(as_dict(data.get("dashboard")).get("publish_path") or "/tmp/stock_ai_private_static_dashboard")
    return {
        "runtime": "scripts/orchestrator/private_static_dashboard_publish.py",
        "requested": publish_dashboard,
        "dry_run": not publish_dashboard,
        "gate_approved_for_manual_publish": allowed,
        "publish_attempted": False,
        "publish_status": "blocked_pending_manual_confirmation"
        if publish_dashboard
        else "dry_run_not_published",
        "requires_separate_user_confirmation": True,
        "private_static_publish_path": publish_path,
        "private_url_hint": f"file://{Path(publish_path).resolve()}/index.html",
    }


def build_summary(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "task_id": result.get("task_id"),
        "run_id": result.get("run_id"),
        "generated_at": result.get("generated_at"),
        "mode": result.get("mode"),
        "delivery_allowed": result.get("delivery_allowed"),
        "approval_status": result.get("approval_status"),
        "channels": deepcopy(result.get("channels")),
        "line_runtime_status": deepcopy(result.get("line_runtime_status")),
        "email_runtime_status": deepcopy(result.get("email_runtime_status")),
        "dashboard_runtime_status": deepcopy(result.get("dashboard_runtime_status")),
        "ok": result.get("ok"),
        "decision": result.get("decision"),
        "next_recommendation": result.get("next_recommendation"),
    }


def build_result(data: dict[str, Any], send_test_line: bool, send_test_email: bool, publish_dashboard: bool) -> dict[str, Any]:
    generated_at = str(data.get("generated_at") or now_taipei())
    run_id = str(data.get("run_id") or f"unified-controlled-delivery-runtime-{generated_at}")
    mode = str(data.get("mode") or "dry_run_no_send_no_publish")
    if send_test_line or send_test_email or publish_dashboard:
        mode = "manual_test_requested_pending_confirmation"
    gate = gate_status(data)
    decisions = channel_decisions(data, gate)
    line_status = build_line_status(decisions, send_test_line)
    email_status = build_email_status(decisions, send_test_email)
    dashboard_status = build_dashboard_status(decisions, publish_dashboard, data)
    side_effects = deepcopy(SIDE_EFFECTS_BASE)
    requested_real_action = send_test_line or send_test_email or publish_dashboard
    warnings = []
    if email_status["runtime_settings_present"] is not True:
        warnings.append("email_runtime_settings_missing_or_incomplete")
    if requested_real_action:
        decision = DECISION_READY if gate["gate_open"] else DECISION_BLOCKED
        next_recommendation = (
            "Stop here and obtain separate explicit user confirmation before running any real LINE, Email, Dashboard publish, or scheduler activation command."
        )
    elif gate["gate_open"]:
        decision = DECISION_WARNINGS if warnings else DECISION_COMPLETED
        next_recommendation = "Dry-run is complete. Run manual channel tests only after separate explicit confirmation."
    else:
        decision = DECISION_BLOCKED
        next_recommendation = "Keep unified delivery in dry-run/no-send/no-publish mode until all channel gates are approved."

    result = {
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "run_id": run_id,
        "generated_at": generated_at,
        "mode": mode,
        "gate_status": gate,
        "delivery_allowed": gate["delivery_allowed"],
        "approval_status": gate["approval_status"],
        "channels": decisions,
        "line_runtime_status": line_status,
        "email_runtime_status": email_status,
        "dashboard_runtime_status": dashboard_status,
        "dashboard_private_url_hint": dashboard_status["private_url_hint"],
        "dashboard_publish_path": dashboard_status["private_static_publish_path"],
        "line_test_command": command_for_runtime("--send-test-line", "unified_controlled_line_test_result.json"),
        "email_test_command": email_test_command(),
        "dashboard_publish_command": dashboard_publish_command(),
        "scheduler_activation_command": scheduler_activation_command(),
        "side_effects": side_effects,
        "safety": deepcopy(SAFETY),
        "warnings": warnings,
        "ok": True,
        "decision": decision,
        "next_recommendation": next_recommendation,
    }
    result["unified_controlled_delivery_runtime_summary"] = build_summary(result)
    return result


def write_json(payload: Any, output: Path, pretty: bool) -> str:
    output.parent.mkdir(parents=True, exist_ok=True)
    rendered = stable_json(payload, pretty)
    output.write_text(rendered, encoding="utf-8")
    return rendered


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Unified Controlled Delivery Runtime V1.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", required=True)
    parser.add_argument("--summary-output", required=True)
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--send-test-line", action="store_true")
    parser.add_argument("--send-test-email", action="store_true")
    parser.add_argument("--publish-dashboard", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build_result(load_json(Path(args.input)), args.send_test_line, args.send_test_email, args.publish_dashboard)
    rendered = write_json(result, Path(args.output), args.pretty)
    write_json(result["unified_controlled_delivery_runtime_summary"], Path(args.summary_output), args.pretty)
    sys.stdout.write(rendered)
    if not rendered.endswith("\n"):
        sys.stdout.write("\n")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
