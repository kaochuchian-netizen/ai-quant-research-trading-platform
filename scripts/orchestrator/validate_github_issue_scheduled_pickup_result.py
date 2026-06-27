#!/usr/bin/env python3
"""Validate a scheduled GitHub Issue pickup dry-run result artifact."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REQUIRED_TOP_LEVEL_FIELDS = [
    "schema_version",
    "run_id",
    "generated_at",
    "dry_run",
    "scheduler_enabled",
    "runtime_action_performed",
    "github_issue_mutated",
    "daemon_or_background_service_created",
    "source",
    "total_issues_seen",
    "eligible_count",
    "rejected_count",
    "needs_manual_review_count",
    "candidate_issue_numbers",
    "candidates",
    "rejected",
    "idempotency_keys",
    "next_step_recommendation",
    "safety_confirmation",
    "errors",
    "warnings",
]
REQUIRED_ISSUE_FIELDS = [
    "issue_number",
    "issue_url",
    "title",
    "labels_seen",
    "eligible",
    "decision",
    "task_class",
    "required_labels_present",
    "blocked_terms_detected",
    "idempotency_key",
    "sanitized_summary",
    "proposed_runner_command",
    "execute_repo_only_allowed",
    "manual_approval_required",
]
DECISIONS = {"accepted", "rejected", "needs_manual_review"}
TASK_CLASSES = {
    "docs_only",
    "template_only",
    "validator_only",
    "repo_side_contract",
    "test_or_validation_helper",
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
    "needs_manual_review",
    "invalid_fixture",
}
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


def validate_issue_record(record: Any, bucket: str, errors: list[str]) -> None:
    if not isinstance(record, dict):
        errors.append(f"{bucket} entries must be objects")
        return
    for field in REQUIRED_ISSUE_FIELDS:
        if field not in record:
            errors.append(f"{bucket} entry missing required field: {field}")
    decision = str(record.get("decision", ""))
    task_class = str(record.get("task_class", ""))
    if record.get("issue_number") is not None and not isinstance(record.get("issue_number"), int):
        errors.append(f"{bucket}.issue_number must be integer or null")
    issue_url = str(record.get("issue_url", ""))
    if record.get("issue_number") is not None and not issue_url.startswith("https://github.com/"):
        errors.append(f"{bucket}.issue_url must be a GitHub URL")
    if not isinstance(record.get("labels_seen"), list):
        errors.append(f"{bucket}.labels_seen must be a list")
    if decision not in DECISIONS:
        errors.append(f"{bucket}.decision is not recognized")
    if task_class not in TASK_CLASSES:
        errors.append(f"{bucket}.task_class is not recognized")
    if not isinstance(record.get("required_labels_present"), bool):
        errors.append(f"{bucket}.required_labels_present must be boolean")
    if not isinstance(record.get("blocked_terms_detected"), list):
        errors.append(f"{bucket}.blocked_terms_detected must be a list")
    if not str(record.get("idempotency_key", "")).startswith("scheduled-pickup-v1|"):
        errors.append(f"{bucket}.idempotency_key must start with scheduled-pickup-v1|")
    if record.get("execute_repo_only_allowed") is not False:
        errors.append(f"{bucket}.execute_repo_only_allowed must be false")
    if record.get("manual_approval_required") is not True:
        errors.append(f"{bucket}.manual_approval_required must be true")
    if bucket == "candidates":
        if record.get("eligible") is not True:
            errors.append("candidate entries must have eligible=true")
        if decision != "accepted":
            errors.append("candidate entries must have decision=accepted")
        command = record.get("proposed_runner_command")
        if not isinstance(command, str) or "github_issue_auto_runner.py" not in command or "--once" not in command:
            errors.append("candidate proposed_runner_command must reference github_issue_auto_runner.py with --once")
    if bucket == "rejected":
        if record.get("eligible") is not False:
            errors.append("rejected entries must have eligible=false")
        if decision not in {"rejected", "needs_manual_review"}:
            errors.append("rejected bucket entries must be rejected or needs_manual_review")
        if record.get("proposed_runner_command") is not None:
            errors.append("rejected proposed_runner_command must be null")


def validate_result(data: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    for field in REQUIRED_TOP_LEVEL_FIELDS:
        if field not in data:
            errors.append(f"missing required field: {field}")

    if data.get("dry_run") is not True:
        errors.append("dry_run must be true")
    if data.get("scheduler_enabled") is not False:
        errors.append("scheduler_enabled must be false")
    for field in ["runtime_action_performed", "github_issue_mutated", "daemon_or_background_service_created"]:
        require_false(data, field, errors)
    if data.get("source") not in {"fixture", "live_read"}:
        errors.append("source must be fixture or live_read")
    if data.get("source") == "live_read":
        warnings.append("live_read source is allowed only for read-only reports; AI-DEV-059 templates use fixture")

    for field in ["total_issues_seen", "eligible_count", "rejected_count", "needs_manual_review_count"]:
        if not isinstance(data.get(field), int) or data.get(field) < 0:
            errors.append(f"{field} must be a non-negative integer")
    for field in ["candidate_issue_numbers", "candidates", "rejected", "idempotency_keys", "errors", "warnings"]:
        if not isinstance(data.get(field), list):
            errors.append(f"{field} must be a list")

    candidates = data.get("candidates", [])
    rejected = data.get("rejected", [])
    if isinstance(candidates, list):
        for record in candidates:
            validate_issue_record(record, "candidates", errors)
    if isinstance(rejected, list):
        for record in rejected:
            validate_issue_record(record, "rejected", errors)

    if isinstance(candidates, list) and data.get("eligible_count") != len(candidates):
        errors.append("eligible_count must equal number of candidates")
    if isinstance(rejected, list):
        rejected_count = sum(1 for record in rejected if isinstance(record, dict) and record.get("decision") == "rejected")
        manual_count = sum(1 for record in rejected if isinstance(record, dict) and record.get("decision") == "needs_manual_review")
        if data.get("rejected_count") != rejected_count:
            errors.append("rejected_count must equal rejected entries with decision=rejected")
        if data.get("needs_manual_review_count") != manual_count:
            errors.append("needs_manual_review_count must equal rejected bucket entries with decision=needs_manual_review")
    if isinstance(candidates, list) and isinstance(rejected, list):
        if data.get("total_issues_seen") != len(candidates) + len(rejected):
            errors.append("total_issues_seen must equal candidates plus rejected entries")

    candidate_numbers = data.get("candidate_issue_numbers", [])
    if isinstance(candidate_numbers, list) and isinstance(candidates, list):
        expected_numbers = [record.get("issue_number") for record in candidates if isinstance(record, dict)]
        if candidate_numbers != expected_numbers:
            errors.append("candidate_issue_numbers must match candidate issue_number order")
    idempotency_keys = data.get("idempotency_keys", [])
    if isinstance(idempotency_keys, list) and isinstance(candidates, list):
        expected_keys = [record.get("idempotency_key") for record in candidates if isinstance(record, dict)]
        if idempotency_keys != expected_keys:
            errors.append("idempotency_keys must match accepted candidate keys")

    if not data.get("next_step_recommendation"):
        errors.append("next_step_recommendation must be present")
    if not data.get("safety_confirmation"):
        errors.append("safety_confirmation must be present")

    text = flatten_text(data)
    value_hit_patterns = [pattern.pattern for pattern in SECRET_VALUE_PATTERNS if pattern.search(text)]
    if value_hit_patterns:
        errors.append("result appears to include sensitive values")

    return {
        "ok": not errors,
        "run_id": data.get("run_id"),
        "source": data.get("source"),
        "total_issues_seen": data.get("total_issues_seen"),
        "eligible_count": data.get("eligible_count"),
        "rejected_count": data.get("rejected_count"),
        "needs_manual_review_count": data.get("needs_manual_review_count"),
        "errors": errors,
        "warnings": warnings,
        "values_included_or_printed": bool(value_hit_patterns),
        "value_hit_patterns": value_hit_patterns,
        "side_effects": {
            "runtime_action_performed": False,
            "github_issue_mutated": False,
            "daemon_or_background_service_created": False,
            "branch_created": False,
            "pr_created": False,
            "merge_performed": False,
            "notification_sent": False,
            "production_db_modified": False,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a scheduled GitHub Issue pickup dry-run result.")
    parser.add_argument("--input", default="templates/github_issue_scheduled_pickup_result.example.json")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    data, load_errors = load_json(Path(args.input))
    if data is None:
        result = {
            "ok": False,
            "run_id": None,
            "source": None,
            "total_issues_seen": None,
            "eligible_count": None,
            "rejected_count": None,
            "needs_manual_review_count": None,
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
