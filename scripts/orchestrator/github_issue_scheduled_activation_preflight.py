#!/usr/bin/env python3
"""Preflight GitHub Issue scheduled auto-pickup activation proposal.

This helper validates a proposed activation package. It never enables a
schedule, never mutates cron/systemd/timers/GitHub Actions, never mutates
GitHub Issues, and never performs runtime actions.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REQUIRED_LABELS = ["ai-dev", "gcp-pickup", "auto-run", "repo-only"]
BLOCKED_LABELS = ["manual-review", "blocked", "runtime", "production", "secret", "notification", "trading", "n8n", "dify"]
ALLOWED_TASK_CLASSES = ["docs_only", "template_only", "validator_only", "repo_side_contract", "test_or_validation_helper"]
BLOCKED_TASK_CLASSES = [
    "runtime_action",
    "production_pipeline",
    "secret_handling",
    "notification_send",
    "n8n_control",
    "Dify_runtime_call",
    "OpenAI_API_call",
    "trading_or_order",
    "production_DB_mutation",
    "cron_systemd_timer_change",
    "daemon_background_service",
]
REQUIRED_APPROVALS = [
    "approve_30m_initial_cadence",
    "approve_max_issues_per_run_1",
    "approve_single_active_task_lock",
    "approve_idempotency_state_path",
    "approve_read_only_issue_discovery",
    "approve_no_issue_mutation",
    "approve_no_comment_back",
    "approve_no_runtime_action",
    "approve_no_production_pipeline",
    "approve_rollback_disable_procedure",
]
DEFAULT_STATE_PATHS = [
    "/home/kaochuchian/.local/state/stock-ai-orchestrator/github_issue_scheduled_pickup_latest.json",
    "/home/kaochuchian/.local/state/stock-ai-orchestrator/github_issue_scheduled_pickup_idempotency.json",
    "/home/kaochuchian/.local/state/stock-ai-orchestrator/archive/github_issue_scheduled_pickup/",
]
DEFAULT_LOG_PATHS = [
    "/home/kaochuchian/.local/state/stock-ai-orchestrator/logs/github_issue_scheduled_pickup.log",
]
EXPECTED_COMMAND = (
    "python3 scripts/orchestrator/github_issue_scheduled_pickup_dry_run.py "
    "--input /home/kaochuchian/.local/state/stock-ai-orchestrator/github_issue_scheduled_pickup_request.json "
    "--output /home/kaochuchian/.local/state/stock-ai-orchestrator/github_issue_scheduled_pickup_latest.json "
    "--pretty --once"
)
SAFETY_CONFIRMATION = (
    "Preflight only. Scheduler remains disabled. No runtime action, GitHub Issue mutation, daemon, "
    "schedule, background service, cron/systemd/timer/GitHub Actions schedule mutation, branch, PR from "
    "Issue content, merge from Issue content, notification, Dify, OpenAI, n8n, trading, production "
    "pipeline, or production database action was performed."
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, [f"failed to parse JSON preflight request: {exc}"]
    if not isinstance(data, dict):
        return None, ["preflight request root must be a JSON object"]
    return data, []


def as_list_of_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str)]


def validate_request(request: dict[str, Any]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if request.get("scheduler_activation_requested") is not True:
        errors.append("scheduler_activation_requested must be true for activation preflight")
    if request.get("proposed_cadence") not in {"15m", "30m"}:
        errors.append("proposed_cadence must be 15m or 30m")
    if request.get("proposed_cadence") == "15m":
        warnings.append("30m is the recommended first production cadence; 15m should be reviewed after dry-run stability")
    if request.get("max_issues_per_run") != 1:
        errors.append("recommended first activation requires max_issues_per_run=1")

    lock_policy = request.get("lock_policy", {})
    if not isinstance(lock_policy, dict):
        errors.append("lock_policy must be an object")
        lock_policy = {}
    if lock_policy.get("single_active_task") is not True:
        errors.append("single_active_task lock policy must be enabled")
    if not str(lock_policy.get("lock_path", "")).startswith("/home/kaochuchian/.local/state/stock-ai-orchestrator/"):
        errors.append("lock_path must be under the orchestrator state directory")
    if lock_policy.get("stale_lock_requires_manual_review") is not True:
        errors.append("stale locks must require manual review")

    idempotency_policy = request.get("idempotency_policy", {})
    if not isinstance(idempotency_policy, dict):
        errors.append("idempotency_policy must be an object")
        idempotency_policy = {}
    expected_key_format = "scheduled-pickup-v1|issue_number|issue_url|task_class|normalized_required_labels"
    if idempotency_policy.get("key_format") != expected_key_format:
        errors.append("idempotency key_format must match scheduled-pickup-v1 contract")
    if not str(idempotency_policy.get("state_path", "")).startswith("/home/kaochuchian/.local/state/stock-ai-orchestrator/"):
        errors.append("idempotency state_path must be under the orchestrator state directory")
    if idempotency_policy.get("exclude_issue_body_text") is not True:
        errors.append("idempotency policy must exclude Issue body text")

    state_paths = as_list_of_strings(request.get("state_paths_proposed"))
    log_paths = as_list_of_strings(request.get("log_paths_proposed"))
    if len(state_paths) < 2:
        errors.append("state_paths_proposed must include latest result and idempotency state paths")
    if not log_paths:
        errors.append("log_paths_proposed must include a sanitized log path")
    for path in state_paths + log_paths:
        if not path.startswith("/home/kaochuchian/.local/state/stock-ai-orchestrator/"):
            errors.append("state and log paths must be under the orchestrator state directory")

    approvals = set(as_list_of_strings(request.get("required_operator_approvals_for_AI_DEV_061")))
    missing_approvals = [approval for approval in REQUIRED_APPROVALS if approval not in approvals]
    if missing_approvals:
        errors.append("missing required operator approvals for AI-DEV-061: " + ", ".join(missing_approvals))
    return errors, warnings


def build_result(request: dict[str, Any], load_errors: list[str] | None = None) -> dict[str, Any]:
    run_id = str(request.get("run_id") or "scheduled-activation-preflight-invalid")
    proposed_cadence = str(request.get("proposed_cadence", ""))
    max_issues_per_run = request.get("max_issues_per_run")
    lock_policy = request.get("lock_policy") if isinstance(request.get("lock_policy"), dict) else {}
    idempotency_policy = request.get("idempotency_policy") if isinstance(request.get("idempotency_policy"), dict) else {}
    state_paths = as_list_of_strings(request.get("state_paths_proposed")) or DEFAULT_STATE_PATHS
    log_paths = as_list_of_strings(request.get("log_paths_proposed")) or DEFAULT_LOG_PATHS
    errors, warnings = validate_request(request)
    if load_errors:
        errors.extend(load_errors)

    activation_ready = not errors
    if activation_ready:
        decision = "approved_for_next_stage"
        rollback = (
            "Disable the reviewed scheduler entry, verify it is inactive, preserve sanitized logs/state for audit, "
            "and do not mutate Issues or runtime systems during rollback."
        )
        next_step = (
            "AI-DEV-061 may enable the reviewed schedule only after explicit operator approval of cadence, lock, "
            "idempotency, read-only permissions, logging, rollback, and no-mutation boundaries."
        )
        expected_command: str | None = EXPECTED_COMMAND
    elif errors:
        decision = "rejected"
        rollback = "Rejected preflight. Do not enable a scheduler until cadence, max issues, lock, idempotency, state, logs, and approvals are corrected."
        next_step = "Fix the preflight request and rerun before AI-DEV-061."
        expected_command = None
    else:
        decision = "needs_manual_review"
        rollback = "Manual review required before any schedule activation."
        next_step = "Resolve warnings and obtain explicit operator approval before AI-DEV-061."
        expected_command = None

    return {
        "schema_version": "1.0.0",
        "run_id": run_id,
        "generated_at": utc_now(),
        "scheduler_activation_requested": bool(request.get("scheduler_activation_requested")),
        "scheduler_enabled": False,
        "activation_ready": activation_ready,
        "decision": decision,
        "proposed_cadence": proposed_cadence,
        "max_issues_per_run": max_issues_per_run,
        "lock_policy": lock_policy,
        "idempotency_policy": idempotency_policy,
        "state_paths_proposed": state_paths,
        "log_paths_proposed": log_paths,
        "required_labels": REQUIRED_LABELS,
        "blocked_labels": BLOCKED_LABELS,
        "allowed_task_classes": ALLOWED_TASK_CLASSES,
        "blocked_task_classes": BLOCKED_TASK_CLASSES,
        "required_operator_approvals_for_AI_DEV_061": REQUIRED_APPROVALS,
        "rollback_plan_summary": rollback,
        "safety_confirmation": SAFETY_CONFIRMATION,
        "runtime_action_performed": False,
        "github_issue_mutated": False,
        "daemon_or_background_service_created": False,
        "cron_systemd_timer_modified": False,
        "next_step_recommendation": next_step,
        "expected_AI_DEV_061_command": expected_command,
        "errors": errors,
        "warnings": warnings,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Preflight a scheduled GitHub Issue pickup activation proposal.")
    parser.add_argument("--input", required=True, help="Sanitized preflight request JSON.")
    parser.add_argument("--output", required=True)
    parser.add_argument("--once", action="store_true", help="Required guard; this helper never schedules or polls.")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.once:
        result = build_result(
            {
                "run_id": "scheduled-activation-preflight-invalid",
                "scheduler_activation_requested": False,
                "proposed_cadence": "",
                "max_issues_per_run": None,
                "lock_policy": {},
                "idempotency_policy": {},
            },
            ["--once is required; schedule, daemon, and polling modes are not implemented"],
        )
    else:
        request, load_errors = load_json(Path(args.input))
        result = build_result({}, load_errors) if request is None else build_result(request)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {
        "ok": result.get("decision") in {"approved_for_next_stage", "rejected", "needs_manual_review"},
        "output": str(output_path),
        "run_id": result.get("run_id"),
        "activation_ready": result.get("activation_ready"),
        "decision": result.get("decision"),
        "scheduler_enabled": result.get("scheduler_enabled"),
        "proposed_cadence": result.get("proposed_cadence"),
        "max_issues_per_run": result.get("max_issues_per_run"),
        "side_effects": {
            "runtime_action_performed": False,
            "github_issue_mutated": False,
            "daemon_or_background_service_created": False,
            "cron_systemd_timer_modified": False,
            "schedule_enabled": False,
        },
    }
    json.dump(summary, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    return 0 if summary["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
