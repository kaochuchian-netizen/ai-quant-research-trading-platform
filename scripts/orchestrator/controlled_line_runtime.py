#!/usr/bin/env python3
"""Controlled LINE Runtime Reactivation V1."""

from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEFAULT_INPUT = Path("templates/controlled_line_runtime_input.example.json")
SCHEMA_VERSION = "controlled_line_runtime_reactivation_v1"
SUMMARY_SCHEMA_VERSION = "controlled_line_runtime_summary_v1"
TASK_ID = "AI-DEV-106"
APPROVED_STATUSES = {"approved", "APPROVED"}
DECISION_COMPLETED = "controlled_line_runtime_reactivation_completed"
DECISION_COMPLETED_WITH_TEST = "controlled_line_runtime_reactivation_completed_with_test_push"
DECISION_BLOCKED_BY_GATE = "line_push_blocked_by_gate"
DECISION_TEST_FAILED = "line_push_test_failed"
DECISION_VALIDATION_FAILED = "validation_failed"
DECISION_BLOCKED = "blocked"
TEST_PREFIX = "[Stock AI Controlled LINE Runtime Test]"
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
    "controlled_line_runtime": True,
    "dry_run_default": True,
    "delivery_gate_required": True,
    "no_token_printing": True,
    "no_secret_logging": True,
    "no_email_send": True,
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


def stable_json(payload: Any, pretty: bool) -> str:
    text = json.dumps(payload, ensure_ascii=False, indent=2 if pretty else None, sort_keys=True)
    return f"{text}\n" if pretty else text


def now_taipei() -> str:
    return datetime.now(ZoneInfo("Asia/Taipei")).replace(microsecond=0).isoformat()


def gate_status(data: dict[str, Any]) -> dict[str, Any]:
    gate = as_dict(data.get("gate_status"))
    delivery_allowed = gate.get("delivery_allowed") is True or data.get("delivery_allowed") is True
    approval_status = str(
        gate.get("approval_status")
        or gate.get("review_status")
        or data.get("approval_status")
        or data.get("review_status")
        or "pending_approval"
    )
    line_channel_enabled = gate.get("line_channel_enabled") is True or data.get("line_channel_enabled") is True
    approved = approval_status in APPROVED_STATUSES
    preconditions = {
        "delivery_allowed": delivery_allowed,
        "approval_status_approved": approved,
        "line_channel_enabled": line_channel_enabled,
    }
    blockers = [key for key, value in preconditions.items() if value is not True]
    return {
        "delivery_allowed": delivery_allowed,
        "approval_status": approval_status,
        "line_channel_enabled": line_channel_enabled,
        "approved": approved,
        "preconditions": preconditions,
        "gate_open": not blockers,
        "blocked_reasons": blockers,
    }


def build_test_message(data: dict[str, Any], run_id: str, generated_at: str) -> str:
    raw_message = str(data.get("test_message") or "").strip()
    if raw_message:
        body = raw_message
    else:
        body = "This is a controlled one-shot LINE runtime test. No trading action is authorized."
    if not body.startswith(TEST_PREFIX):
        body = f"{TEST_PREFIX}\n{body}"
    return f"{body}\nrun_id: {run_id}\ngenerated_at: {generated_at}"


def execute_test_push(message: str) -> dict[str, Any]:
    try:
        from reports.line_report_sender import send_line_report as line_sender

        status_codes = line_sender(message)
    except Exception as exc:  # pragma: no cover - real runtime failure path
        return {
            "ok": False,
            "error_type": exc.__class__.__name__,
            "recipient_count": 0,
            "status_code_counts": {},
        }

    counts: dict[str, int] = {}
    recipient_count = 0
    for item in status_codes or []:
        recipient_count += 1
        status_code = str(item[1]) if isinstance(item, (list, tuple)) and len(item) >= 2 else "unknown"
        counts[status_code] = counts.get(status_code, 0) + 1
    return {
        "ok": True,
        "error_type": None,
        "recipient_count": recipient_count,
        "status_code_counts": counts,
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
        "line_channel_enabled": result.get("line_channel_enabled"),
        "push_attempted": result.get("push_attempted"),
        "push_status": result.get("push_status"),
        "test_message_sent": result.get("test_message_sent"),
        "ok": result.get("ok"),
        "decision": result.get("decision"),
        "next_recommendation": result.get("next_recommendation"),
    }


def build_result(data: dict[str, Any], send_test_line: bool) -> dict[str, Any]:
    generated_at = str(data.get("generated_at") or now_taipei())
    run_id = str(data.get("run_id") or f"controlled-line-runtime-{generated_at}")
    mode = "controlled_test_push" if send_test_line else str(data.get("mode") or "dry_run_no_send")
    gate = gate_status(data)
    gate_open = gate["gate_open"]
    push_attempted = False
    push_status = "dry_run_not_sent"
    test_message_sent = False
    runtime_attempt: dict[str, Any] = {
        "attempted": False,
        "error_type": None,
        "recipient_count": 0,
        "status_code_counts": {},
        "message_marked_as_test": True,
    }
    side_effects = deepcopy(SIDE_EFFECTS_BASE)

    if send_test_line and not gate_open:
        push_status = "blocked_by_gate"
        decision = DECISION_BLOCKED_BY_GATE
        ok = True
        next_recommendation = "Do not run a LINE test push until delivery_allowed, approval_status, and line_channel_enabled are all approved."
    elif send_test_line:
        push_attempted = True
        runtime_attempt["attempted"] = True
        side_effects["read_secrets"] = True
        side_effects["sent_notification"] = True
        side_effects["called_line_api"] = True
        test_message = build_test_message(data, run_id, generated_at)
        runtime_attempt.update(execute_test_push(test_message))
        if runtime_attempt["ok"]:
            side_effects["sent_line_push"] = True
            push_status = "sent"
            test_message_sent = True
            decision = DECISION_COMPLETED_WITH_TEST
            ok = True
            next_recommendation = "Controlled LINE test push completed. Formal scheduler delivery still requires separate explicit confirmation."
        else:
            push_status = "failed"
            decision = DECISION_TEST_FAILED
            ok = False
            next_recommendation = "Review non-secret LINE runtime configuration and retry only after confirming the gate remains approved."
    else:
        decision = DECISION_COMPLETED if gate_open else DECISION_BLOCKED_BY_GATE
        ok = True
        next_recommendation = (
            "Gate is approved for a controlled one-shot test. Run the documented --send-test-line command only after explicit confirmation."
            if gate_open
            else "Keep LINE runtime in dry-run/no-send mode until all delivery gate preconditions are approved."
        )

    line_runtime_status = {
        "runtime_id": f"controlled_line_runtime_{run_id}",
        "dry_run": not send_test_line,
        "send_test_line_requested": send_test_line,
        "one_shot_test_only": True,
        "formal_scheduler_delivery_activation": False,
        "gate_open": gate_open,
        "blocked_reasons": deepcopy(gate["blocked_reasons"]),
        "runtime_attempt": runtime_attempt,
    }
    secret_safety = {
        "token_printed": False,
        "secret_logged": False,
        "secret_values_in_result": False,
        "dry_run_reads_runtime_secrets": False,
        "send_mode_uses_existing_configured_environment": send_test_line,
        "failure_details_redacted": True,
    }
    result = {
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "run_id": run_id,
        "generated_at": generated_at,
        "mode": mode,
        "gate_status": gate,
        "line_runtime_status": line_runtime_status,
        "delivery_allowed": gate["delivery_allowed"],
        "approval_status": gate["approval_status"],
        "line_channel_enabled": gate["line_channel_enabled"],
        "push_attempted": push_attempted,
        "push_status": push_status,
        "test_message_sent": test_message_sent,
        "secret_safety": secret_safety,
        "side_effects": side_effects,
        "safety": deepcopy(SAFETY),
        "ok": ok,
        "decision": decision,
        "next_recommendation": next_recommendation,
    }
    result["controlled_line_runtime_summary"] = build_summary(result)
    return result


def write_json(payload: Any, output: Path, pretty: bool) -> str:
    output.parent.mkdir(parents=True, exist_ok=True)
    rendered = stable_json(payload, pretty)
    output.write_text(rendered, encoding="utf-8")
    return rendered


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Controlled LINE Runtime Reactivation V1.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", required=True)
    parser.add_argument("--summary-output", required=True)
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument(
        "--send-test-line",
        action="store_true",
        help="Send exactly one controlled LINE test message after gate preconditions pass.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = build_result(load_json(Path(args.input)), args.send_test_line)
    rendered = write_json(result, Path(args.output), args.pretty)
    write_json(result["controlled_line_runtime_summary"], Path(args.summary_output), args.pretty)
    sys.stdout.write(rendered)
    if not rendered.endswith("\n"):
        sys.stdout.write("\n")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
