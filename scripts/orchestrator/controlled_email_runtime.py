#!/usr/bin/env python3
"""Controlled one-shot Email runtime for orchestrator delivery tests."""

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


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.orchestrator.notify_stage_report import (  # noqa: E402
    ENV_FROM,
    ENV_HOST,
    ENV_PASS,
    ENV_PORT,
    ENV_TO,
    ENV_USER,
    build_message,
    load_env_file,
    load_mail_config,
    send_message,
)


DEFAULT_INPUT = Path("templates/unified_controlled_delivery_runtime_input.example.json")
DEFAULT_ENV_FILE = Path("~/.config/stock-ai-orchestrator/mail.env")
SCHEMA_VERSION = "controlled_email_runtime_v1"
SUMMARY_SCHEMA_VERSION = "controlled_email_runtime_summary_v1"
TASK_ID = "AI-DEV-109"
APPROVED_STATUSES = {"approved", "APPROVED"}
EMAIL_ENV_NAMES = [ENV_HOST, ENV_PORT, ENV_USER, ENV_PASS, ENV_FROM, ENV_TO]
TEST_PREFIX = "[Stock AI Controlled Email Runtime Test]"
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
    "controlled_email_runtime": True,
    "dry_run_default": True,
    "delivery_gate_required": True,
    "no_token_printing": True,
    "no_secret_logging": True,
    "no_line_push": True,
    "no_dashboard_deploy": True,
    "no_gmail_api_call": True,
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


def gate_status(data: dict[str, Any]) -> dict[str, Any]:
    raw = as_dict(data.get("gate_status"))
    channels = as_dict(data.get("channels"))
    email = as_dict(channels.get("email"))
    delivery_allowed = raw.get("delivery_allowed") is True or data.get("delivery_allowed") is True
    approval_status = str(raw.get("approval_status") or data.get("approval_status") or "pending_approval")
    email_channel_enabled = email.get("enabled") is True or raw.get("email_channel_enabled") is True
    approved = approval_status in APPROVED_STATUSES
    preconditions = {
        "delivery_allowed": delivery_allowed,
        "approval_status_approved": approved,
        "email_channel_enabled": email_channel_enabled,
    }
    blockers = [key for key, value in preconditions.items() if value is not True]
    return {
        "delivery_allowed": delivery_allowed,
        "approval_status": approval_status,
        "email_channel_enabled": email_channel_enabled,
        "approved": approved,
        "preconditions": preconditions,
        "gate_open": not blockers,
        "blocked_reasons": blockers,
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


def maybe_load_env_file(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {
            "attempted": False,
            "path": None,
            "exists": False,
            "loaded": False,
            "error_type": None,
            "value_printed": False,
        }
    expanded = path.expanduser()
    exists = expanded.exists()
    loaded = False
    error_type = None
    if exists:
        try:
            load_env_file(expanded)
            loaded = True
        except Exception as exc:  # pragma: no cover - runtime environment path
            error_type = exc.__class__.__name__
    return {
        "attempted": True,
        "path": str(expanded),
        "exists": exists,
        "loaded": loaded,
        "error_type": error_type,
        "value_printed": False,
    }


def build_test_body(data: dict[str, Any], run_id: str, generated_at: str) -> str:
    raw = str(data.get("test_message") or "").strip()
    body = raw or "Controlled one-shot email runtime test. No trading action is authorized."
    if not body.startswith(TEST_PREFIX):
        body = f"{TEST_PREFIX}\n{body}"
    return f"{body}\nrun_id: {run_id}\ngenerated_at: {generated_at}"


def execute_test_email(data: dict[str, Any], run_id: str, generated_at: str) -> dict[str, Any]:
    try:
        config = load_mail_config()
        subject = f"{TEST_PREFIX} {generated_at}"
        message = build_message(config, subject, build_test_body(data, run_id, generated_at))
        send_message(config, message)
    except Exception as exc:  # pragma: no cover - real SMTP failure path
        return {"ok": False, "error_type": exc.__class__.__name__}
    return {"ok": True, "error_type": None}


def build_summary(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": SUMMARY_SCHEMA_VERSION,
        "task_id": result.get("task_id"),
        "run_id": result.get("run_id"),
        "generated_at": result.get("generated_at"),
        "mode": result.get("mode"),
        "delivery_allowed": result.get("delivery_allowed"),
        "approval_status": result.get("approval_status"),
        "email_channel_enabled": result.get("email_channel_enabled"),
        "send_attempted": result.get("send_attempted"),
        "send_status": result.get("send_status"),
        "test_message_sent": result.get("test_message_sent"),
        "ok": result.get("ok"),
        "decision": result.get("decision"),
    }


def build_result(data: dict[str, Any], send_test_email: bool, env_file: Path | None) -> dict[str, Any]:
    generated_at = str(data.get("generated_at") or now_taipei())
    run_id = str(data.get("run_id") or f"controlled-email-runtime-{generated_at}")
    mode = "controlled_test_email" if send_test_email else "dry_run_no_send"
    loaded_env = maybe_load_env_file(env_file)
    presence = env_presence(EMAIL_ENV_NAMES)
    gate = gate_status(data)
    side_effects = deepcopy(SIDE_EFFECTS_BASE)
    send_attempted = False
    test_message_sent = False
    runtime_attempt = {"attempted": False, "ok": False, "error_type": None}

    if send_test_email and not gate["gate_open"]:
        send_status = "blocked_by_gate"
        decision = "email_send_blocked_by_gate"
        ok = True
    elif send_test_email and not presence["all_required_present"]:
        send_status = "blocked_missing_runtime_settings"
        decision = "email_send_blocked_missing_runtime_settings"
        ok = True
    elif send_test_email:
        send_attempted = True
        runtime_attempt["attempted"] = True
        side_effects["read_secrets"] = True
        side_effects["sent_notification"] = True
        side_effects["called_smtp"] = True
        runtime_attempt.update(execute_test_email(data, run_id, generated_at))
        if runtime_attempt["ok"]:
            side_effects["sent_email"] = True
            send_status = "sent"
            test_message_sent = True
            decision = "controlled_email_runtime_completed_with_test_send"
            ok = True
        else:
            send_status = "failed"
            decision = "email_send_test_failed"
            ok = False
    else:
        send_status = "dry_run_not_sent"
        decision = "controlled_email_runtime_completed" if gate["gate_open"] else "email_send_blocked_by_gate"
        ok = True

    result = {
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "run_id": run_id,
        "generated_at": generated_at,
        "mode": mode,
        "gate_status": gate,
        "mail_env_file": loaded_env,
        "runtime_settings_presence": presence,
        "delivery_allowed": gate["delivery_allowed"],
        "approval_status": gate["approval_status"],
        "email_channel_enabled": gate["email_channel_enabled"],
        "send_requested": send_test_email,
        "send_attempted": send_attempted,
        "send_status": send_status,
        "test_message_sent": test_message_sent,
        "runtime_attempt": runtime_attempt,
        "secret_safety": {
            "secret_values_in_result": False,
            "secret_logged": False,
            "value_printed": False,
            "failure_details_redacted": True,
        },
        "side_effects": side_effects,
        "safety": deepcopy(SAFETY),
        "ok": ok,
        "decision": decision,
        "next_recommendation": "Formal scheduler delivery still requires separate explicit confirmation.",
    }
    result["controlled_email_runtime_summary"] = build_summary(result)
    return result


def write_json(payload: Any, output: Path, pretty: bool) -> str:
    output.parent.mkdir(parents=True, exist_ok=True)
    rendered = stable_json(payload, pretty)
    output.write_text(rendered, encoding="utf-8")
    return rendered


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a controlled one-shot Email runtime test.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", required=True)
    parser.add_argument("--summary-output", required=True)
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--env-file", default=str(DEFAULT_ENV_FILE))
    parser.add_argument("--no-env-file", action="store_true")
    parser.add_argument("--send-test-email", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    env_file = None if args.no_env_file else Path(args.env_file)
    result = build_result(load_json(Path(args.input)), args.send_test_email, env_file)
    rendered = write_json(result, Path(args.output), args.pretty)
    write_json(result["controlled_email_runtime_summary"], Path(args.summary_output), args.pretty)
    sys.stdout.write(rendered)
    if not rendered.endswith("\n"):
        sys.stdout.write("\n")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
