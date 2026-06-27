#!/usr/bin/env python3
"""Validate a sanitized GitHub Issue auto-runner v1 result artifact."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REQUIRED_FIELDS = [
    "schema_version",
    "issue_number",
    "issue_url",
    "title",
    "labels_seen",
    "eligible",
    "decision",
    "task_class",
    "required_labels_present",
    "blocked_terms_detected",
    "dry_run",
    "execute_repo_only",
    "mutation_performed",
    "runtime_action_performed",
    "github_issue_mutated",
    "branch_created",
    "pr_created",
    "pr_url",
    "merged",
    "merge_commit",
    "files_changed",
    "validations_run",
    "sanitized_summary",
    "next_step_recommendation",
    "safety_confirmation",
    "errors",
    "warnings",
]

DECISIONS = {"accepted", "rejected", "needs_manual_review", "executed_repo_only"}
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


def validate_result(data: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    for field in REQUIRED_FIELDS:
        if field not in data:
            errors.append(f"missing required field: {field}")

    decision = str(data.get("decision", ""))
    task_class = str(data.get("task_class", ""))
    eligible = data.get("eligible")
    execute_repo_only = data.get("execute_repo_only")

    if not isinstance(data.get("issue_number"), int):
        errors.append("issue_number must be an integer")
    if not str(data.get("issue_url", "")).startswith("https://github.com/"):
        errors.append("issue_url must be a GitHub URL")
    if decision not in DECISIONS:
        errors.append("decision must be accepted, rejected, needs_manual_review, or executed_repo_only")
    if task_class not in TASK_CLASSES:
        errors.append("task_class is not recognized")
    if not isinstance(eligible, bool):
        errors.append("eligible must be boolean")
    if decision in {"accepted", "executed_repo_only"} and eligible is not True:
        errors.append("accepted/executed_repo_only results must have eligible=true")
    if decision in {"rejected", "needs_manual_review"} and eligible is not False:
        errors.append("rejected/manual review results must have eligible=false")
    if decision == "executed_repo_only" and execute_repo_only is not True:
        errors.append("executed_repo_only decision requires execute_repo_only=true")

    if data.get("dry_run") is not True:
        errors.append("dry_run must be true")
    for field in [
        "mutation_performed",
        "runtime_action_performed",
        "github_issue_mutated",
        "branch_created",
        "pr_created",
        "merged",
    ]:
        require_false(data, field, errors)
    if data.get("pr_url") is not None:
        errors.append("pr_url must be null for v1 runner result artifacts")
    if data.get("merge_commit") is not None:
        errors.append("merge_commit must be null for v1 runner result artifacts")

    for field in ["labels_seen", "blocked_terms_detected", "files_changed", "validations_run", "errors", "warnings"]:
        if not isinstance(data.get(field), list):
            errors.append(f"{field} must be a list")
    if not isinstance(data.get("required_labels_present"), bool):
        errors.append("required_labels_present must be boolean")
    if not data.get("sanitized_summary"):
        errors.append("sanitized_summary must be present")
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
        "issue_number": data.get("issue_number"),
        "decision": decision or None,
        "eligible": eligible,
        "task_class": task_class or None,
        "errors": errors,
        "warnings": warnings,
        "values_included_or_printed": bool(value_hit_patterns),
        "value_hit_patterns": value_hit_patterns,
        "side_effects": {
            "runtime_action_performed": False,
            "github_issue_mutated": False,
            "github_api_mutation_called": False,
            "issue_comment_created": False,
            "issue_labels_modified": False,
            "notification_sent": False,
            "production_db_modified": False,
            "trading_or_order_execution": False,
            "daemon_or_background_service_created": False,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a GitHub Issue auto-runner result JSON file.")
    parser.add_argument("--input", default="templates/github_issue_auto_runner_result.example.json")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    data, load_errors = load_json(Path(args.input))
    if data is None:
        result = {
            "ok": False,
            "issue_number": None,
            "decision": None,
            "eligible": None,
            "task_class": None,
            "errors": load_errors,
            "warnings": [],
            "values_included_or_printed": False,
        }
    else:
        result = validate_result(data)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
