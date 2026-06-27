#!/usr/bin/env python3
"""Validate mobile GitHub Issue auto-pickup result artifacts."""

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
    "source",
    "dry_run",
    "scheduler_enabled",
    "total_issues_seen",
    "eligible_count",
    "rejected_count",
    "needs_manual_review_count",
    "candidate_issue_numbers",
    "selected_issue_number",
    "selected_issue_url",
    "task_class",
    "decision",
    "branch_created",
    "pr_created",
    "pr_url",
    "merged",
    "merge_commit",
    "files_changed",
    "validations_run",
    "github_actions_result",
    "issue_comment_created",
    "issue_labels_changed",
    "github_issue_mutated",
    "runtime_action_performed",
    "production_action_performed",
    "daemon_or_background_service_created",
    "candidates",
    "rejected",
    "idempotency_keys",
    "rollback_or_disable_commands",
    "next_step_recommendation",
    "safety_confirmation",
    "errors",
    "warnings",
]
DECISIONS = {"no_candidate", "accepted", "rejected", "needs_manual_review", "already_processed", "executed_repo_only"}
SOURCES = {"fixture", "live_read"}
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
        return None, [f"failed to parse JSON: {exc}"]
    if not isinstance(data, dict):
        return None, ["result root must be a JSON object"]
    return data, []


def flatten_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def validate_record(record: Any, bucket: str, errors: list[str]) -> None:
    if not isinstance(record, dict):
        errors.append(f"{bucket} entries must be objects")
        return
    for field in [
        "issue_number",
        "issue_url",
        "title",
        "labels_seen",
        "eligible",
        "decision",
        "task_class",
        "required_labels_present",
        "approval_label_present",
        "blocked_terms_detected",
        "idempotency_key",
        "sanitized_summary",
        "execute_repo_only_allowed",
    ]:
        if field not in record:
            errors.append(f"{bucket} entry missing required field: {field}")
    if record.get("issue_number") is not None and not isinstance(record.get("issue_number"), int):
        errors.append(f"{bucket}.issue_number must be integer or null")
    issue_url = str(record.get("issue_url", ""))
    if record.get("issue_number") is not None and not issue_url.startswith("https://github.com/"):
        errors.append(f"{bucket}.issue_url must be a GitHub URL")
    if not isinstance(record.get("labels_seen"), list):
        errors.append(f"{bucket}.labels_seen must be a list")
    if not str(record.get("idempotency_key", "")).startswith("mobile-auto-pickup-v1|"):
        errors.append(f"{bucket}.idempotency_key must start with mobile-auto-pickup-v1|")
    if bucket == "candidates" and record.get("eligible") is not True:
        errors.append("candidate entries must have eligible=true")
    if bucket == "rejected" and record.get("eligible") is not False:
        errors.append("rejected entries must have eligible=false")


def validate_result(data: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    for field in REQUIRED_FIELDS:
        if field not in data:
            errors.append(f"missing required field: {field}")

    if data.get("source") not in SOURCES:
        errors.append("source must be fixture or live_read")
    if data.get("decision") not in DECISIONS:
        errors.append("decision is not recognized")
    if data.get("dry_run") is not True:
        errors.append("dry_run must be true")
    if data.get("scheduler_enabled") is not False:
        errors.append("scheduler_enabled must be false")
    for field in [
        "github_issue_mutated",
        "runtime_action_performed",
        "production_action_performed",
        "daemon_or_background_service_created",
        "issue_comment_created",
        "issue_labels_changed",
    ]:
        if data.get(field) is not False:
            errors.append(f"{field} must be false")

    for field in ["total_issues_seen", "eligible_count", "rejected_count", "needs_manual_review_count"]:
        if not isinstance(data.get(field), int) or data.get(field) < 0:
            errors.append(f"{field} must be a non-negative integer")
    for field in ["candidate_issue_numbers", "files_changed", "validations_run", "candidates", "rejected", "idempotency_keys", "errors", "warnings"]:
        if not isinstance(data.get(field), list):
            errors.append(f"{field} must be a list")

    candidates = data.get("candidates", [])
    rejected = data.get("rejected", [])
    if isinstance(candidates, list):
        for record in candidates:
            validate_record(record, "candidates", errors)
    if isinstance(rejected, list):
        for record in rejected:
            validate_record(record, "rejected", errors)

    if isinstance(candidates, list) and data.get("eligible_count") != len(candidates):
        errors.append("eligible_count must equal candidates length")
    if isinstance(rejected, list):
        rejected_count = sum(1 for item in rejected if isinstance(item, dict) and item.get("decision") == "rejected")
        manual_count = sum(1 for item in rejected if isinstance(item, dict) and item.get("decision") == "needs_manual_review")
        if data.get("rejected_count") != rejected_count:
            errors.append("rejected_count must equal rejected entries")
        if data.get("needs_manual_review_count") != manual_count:
            errors.append("needs_manual_review_count must equal manual review entries")

    text = flatten_text(data)
    value_hit_patterns = [pattern.pattern for pattern in SECRET_VALUE_PATTERNS if pattern.search(text)]
    if value_hit_patterns:
        errors.append("result appears to include sensitive values")
    if data.get("issue_comment_created") or data.get("issue_labels_changed"):
        warnings.append("Issue mutation flags are enabled; v1 scheduled mode should keep them disabled")

    return {
        "ok": not errors,
        "run_id": data.get("run_id"),
        "source": data.get("source"),
        "decision": data.get("decision"),
        "selected_issue_number": data.get("selected_issue_number"),
        "eligible_count": data.get("eligible_count"),
        "rejected_count": data.get("rejected_count"),
        "needs_manual_review_count": data.get("needs_manual_review_count"),
        "errors": errors,
        "warnings": warnings,
        "values_included_or_printed": bool(value_hit_patterns),
        "value_hit_patterns": value_hit_patterns,
        "side_effects": {
            "runtime_action_performed": False,
            "production_action_performed": False,
            "github_issue_mutated": False,
            "issue_comment_created": False,
            "issue_labels_changed": False,
            "notification_sent": False,
            "production_db_modified": False,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate mobile GitHub Issue auto-pickup result.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    data, load_errors = load_json(Path(args.input))
    result = {"ok": False, "errors": load_errors} if data is None else validate_result(data)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
