#!/usr/bin/env python3
"""Validate a scheduled GitHub Issue activation preflight result."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REQUIRED_FIELDS = [
    "schema_version",
    "run_id",
    "generated_at",
    "scheduler_activation_requested",
    "scheduler_enabled",
    "activation_ready",
    "decision",
    "proposed_cadence",
    "max_issues_per_run",
    "lock_policy",
    "idempotency_policy",
    "state_paths_proposed",
    "log_paths_proposed",
    "required_labels",
    "blocked_labels",
    "allowed_task_classes",
    "blocked_task_classes",
    "required_operator_approvals_for_AI_DEV_061",
    "rollback_plan_summary",
    "safety_confirmation",
    "runtime_action_performed",
    "github_issue_mutated",
    "daemon_or_background_service_created",
    "cron_systemd_timer_modified",
    "next_step_recommendation",
    "expected_AI_DEV_061_command",
    "errors",
    "warnings",
]
DECISIONS = {"approved_for_next_stage", "rejected", "needs_manual_review"}
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
SECRET_VALUE_PATTERNS = [
    re.compile(r"ghp_[A-Za-z0-9_]+"),
    re.compile(r"github_pat_[A-Za-z0-9_]+"),
    re.compile(r"sk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]+"),
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?i)(api[_-]?key|access[_-]?token|password)\s*[:=]\s*[^\s,}\"']+"),
]


def load_json(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, [f"failed to parse JSON result: {exc}"]
    if not isinstance(data, dict):
        return None, ["result root must be a JSON object"]
    return data, []


def flatten_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def require_false(data: dict[str, Any], field: str, errors: list[str]) -> None:
    if data.get(field) is not False:
        errors.append(f"{field} must be false")


def require_list(data: dict[str, Any], field: str, expected: list[str], errors: list[str]) -> None:
    value = data.get(field)
    if not isinstance(value, list):
        errors.append(f"{field} must be a list")
        return
    missing = [item for item in expected if item not in value]
    if missing:
        errors.append(f"{field} missing required values: " + ", ".join(missing))


def validate_result(data: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    for field in REQUIRED_FIELDS:
        if field not in data:
            errors.append(f"missing required field: {field}")

    decision = str(data.get("decision", ""))
    activation_ready = data.get("activation_ready")
    if decision not in DECISIONS:
        errors.append("decision must be approved_for_next_stage, rejected, or needs_manual_review")
    if not isinstance(activation_ready, bool):
        errors.append("activation_ready must be boolean")
    if decision == "approved_for_next_stage" and activation_ready is not True:
        errors.append("approved_for_next_stage requires activation_ready=true")
    if decision in {"rejected", "needs_manual_review"} and activation_ready is not False:
        errors.append("rejected or needs_manual_review requires activation_ready=false")

    if data.get("scheduler_enabled") is not False:
        errors.append("scheduler_enabled must be false")
    for field in [
        "runtime_action_performed",
        "github_issue_mutated",
        "daemon_or_background_service_created",
        "cron_systemd_timer_modified",
    ]:
        require_false(data, field, errors)

    if data.get("scheduler_activation_requested") is not True:
        errors.append("scheduler_activation_requested must be true in template/result artifacts")
    if data.get("proposed_cadence") not in {"15m", "30m", "5m"}:
        errors.append("proposed_cadence must be a recognized string")
    if decision == "approved_for_next_stage" and data.get("proposed_cadence") != "30m":
        errors.append("approved preflight must use recommended 30m cadence")
    if decision == "approved_for_next_stage" and data.get("max_issues_per_run") != 1:
        errors.append("approved preflight must use max_issues_per_run=1")
    if not isinstance(data.get("max_issues_per_run"), int):
        errors.append("max_issues_per_run must be integer")

    lock_policy = data.get("lock_policy")
    if not isinstance(lock_policy, dict):
        errors.append("lock_policy must be an object")
        lock_policy = {}
    if decision == "approved_for_next_stage":
        if lock_policy.get("single_active_task") is not True:
            errors.append("approved preflight requires single_active_task=true")
        if not str(lock_policy.get("lock_path", "")).startswith("/home/kaochuchian/.local/state/stock-ai-orchestrator/"):
            errors.append("approved preflight lock_path must be under orchestrator state")
        if lock_policy.get("stale_lock_requires_manual_review") is not True:
            errors.append("approved preflight requires stale_lock_requires_manual_review=true")

    idempotency_policy = data.get("idempotency_policy")
    if not isinstance(idempotency_policy, dict):
        errors.append("idempotency_policy must be an object")
        idempotency_policy = {}
    if decision == "approved_for_next_stage":
        if idempotency_policy.get("key_format") != "scheduled-pickup-v1|issue_number|issue_url|task_class|normalized_required_labels":
            errors.append("approved preflight idempotency key_format mismatch")
        if idempotency_policy.get("exclude_issue_body_text") is not True:
            errors.append("approved preflight must exclude Issue body text from idempotency")

    for field in ["state_paths_proposed", "log_paths_proposed", "errors", "warnings"]:
        if not isinstance(data.get(field), list):
            errors.append(f"{field} must be a list")
    if decision == "approved_for_next_stage":
        for path in data.get("state_paths_proposed", []) + data.get("log_paths_proposed", []):
            if not isinstance(path, str) or not path.startswith("/home/kaochuchian/.local/state/stock-ai-orchestrator/"):
                errors.append("approved preflight paths must be under orchestrator state")

    require_list(data, "required_labels", REQUIRED_LABELS, errors)
    require_list(data, "blocked_labels", BLOCKED_LABELS, errors)
    require_list(data, "allowed_task_classes", ALLOWED_TASK_CLASSES, errors)
    require_list(data, "blocked_task_classes", BLOCKED_TASK_CLASSES, errors)
    require_list(data, "required_operator_approvals_for_AI_DEV_061", REQUIRED_APPROVALS, errors)

    if not data.get("rollback_plan_summary"):
        errors.append("rollback_plan_summary must be present")
    if not data.get("safety_confirmation"):
        errors.append("safety_confirmation must be present")
    if not data.get("next_step_recommendation"):
        errors.append("next_step_recommendation must be present")
    if decision == "approved_for_next_stage":
        command = data.get("expected_AI_DEV_061_command")
        if not isinstance(command, str) or "github_issue_scheduled_pickup_dry_run.py" not in command or "--once" not in command:
            errors.append("approved preflight expected command must reference scheduled pickup dry-run helper with --once")
    elif data.get("expected_AI_DEV_061_command") is not None:
        errors.append("non-approved preflight expected command must be null")

    text = flatten_text(data)
    value_hit_patterns = [pattern.pattern for pattern in SECRET_VALUE_PATTERNS if pattern.search(text)]
    if value_hit_patterns:
        errors.append("result appears to include sensitive values")

    return {
        "ok": not errors,
        "run_id": data.get("run_id"),
        "activation_ready": activation_ready,
        "decision": decision or None,
        "scheduler_enabled": data.get("scheduler_enabled"),
        "proposed_cadence": data.get("proposed_cadence"),
        "max_issues_per_run": data.get("max_issues_per_run"),
        "errors": errors,
        "warnings": warnings,
        "values_included_or_printed": bool(value_hit_patterns),
        "value_hit_patterns": value_hit_patterns,
        "side_effects": {
            "runtime_action_performed": False,
            "github_issue_mutated": False,
            "daemon_or_background_service_created": False,
            "cron_systemd_timer_modified": False,
            "schedule_enabled": False,
            "notification_sent": False,
            "production_db_modified": False,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a scheduled activation preflight result JSON file.")
    parser.add_argument("--input", default="templates/github_issue_scheduled_activation_preflight_result.example.json")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    data, load_errors = load_json(Path(args.input))
    if data is None:
        result = {
            "ok": False,
            "run_id": None,
            "activation_ready": None,
            "decision": None,
            "scheduler_enabled": None,
            "proposed_cadence": None,
            "max_issues_per_run": None,
            "errors": load_errors,
            "warnings": [],
            "values_included_or_printed": False,
            "value_hit_patterns": [],
        }
    else:
        result = validate_result(data)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
