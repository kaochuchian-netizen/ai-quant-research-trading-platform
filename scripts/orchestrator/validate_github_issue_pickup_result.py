#!/usr/bin/env python3
"""Validate a sanitized GitHub Issue pickup dry-run result."""

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
    "eligible",
    "decision",
    "reasons",
    "labels_seen",
    "required_labels_present",
    "missing_required_labels",
    "blocked_terms_detected",
    "task_class",
    "dry_run",
    "runtime_action_performed",
    "mutation_performed",
    "github_issue_mutation_performed",
    "sanitized_summary",
    "next_step_recommendation",
    "idempotency",
    "safety",
    "errors",
    "warnings",
]

DECISIONS = {"accepted", "rejected", "needs_manual_review"}
TASK_CLASSES = {
    "repo_side_contract",
    "documentation",
    "dry_run_orchestration",
    "needs_manual_review",
    "blocked_runtime_action",
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


def as_object(data: dict[str, Any], field: str, errors: list[str]) -> dict[str, Any]:
    value = data.get(field)
    if not isinstance(value, dict):
        errors.append(f"{field} must be an object")
        return {}
    return value


def require_false(obj: dict[str, Any], field: str, label: str, errors: list[str]) -> None:
    if obj.get(field) is not False:
        errors.append(f"{label}.{field} must be false")


def flatten_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def validate_result(data: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    for field in REQUIRED_FIELDS:
        if field not in data:
            errors.append(f"missing required field: {field}")

    decision = str(data.get("decision", ""))
    task_class = str(data.get("task_class", ""))
    eligible = data.get("eligible")

    if not isinstance(data.get("issue_number"), int):
        errors.append("issue_number must be an integer")
    if not str(data.get("issue_url", "")).startswith("https://github.com/"):
        errors.append("issue_url must be a GitHub URL")
    if decision not in DECISIONS:
        errors.append("decision must be accepted, rejected, or needs_manual_review")
    if task_class not in TASK_CLASSES:
        errors.append("task_class is not recognized")
    if not isinstance(eligible, bool):
        errors.append("eligible must be boolean")
    if decision == "accepted" and eligible is not True:
        errors.append("accepted results must have eligible=true")
    if decision in {"rejected", "needs_manual_review"} and eligible is not False:
        errors.append("rejected or manual review results must have eligible=false")

    for field in [
        "reasons",
        "labels_seen",
        "missing_required_labels",
        "blocked_terms_detected",
        "errors",
        "warnings",
    ]:
        if not isinstance(data.get(field), list):
            errors.append(f"{field} must be a list")

    if data.get("dry_run") is not True:
        errors.append("dry_run must be true")
    for field in ["runtime_action_performed", "mutation_performed", "github_issue_mutation_performed"]:
        if data.get(field) is not False:
            errors.append(f"{field} must be false")
    if not data.get("sanitized_summary"):
        errors.append("sanitized_summary must be present")
    if not data.get("next_step_recommendation"):
        errors.append("next_step_recommendation must be present")

    idempotency = as_object(data, "idempotency", errors)
    if decision != "rejected" and not idempotency.get("key"):
        errors.append("idempotency.key must be present for non-rejected results")
    if idempotency.get("duplicate_terminal_result_found") is not False:
        errors.append("idempotency.duplicate_terminal_result_found must be false")
    if idempotency.get("on_duplicate_terminal_result") != "skip_without_github_or_runtime_mutation":
        errors.append("idempotency.on_duplicate_terminal_result must be skip_without_github_or_runtime_mutation")

    safety = as_object(data, "safety", errors)
    for field in [
        "external_delivery_performed",
        "production_db_modified",
        "runtime_or_background_worker_started",
        "github_api_called",
        "issue_comment_created",
        "issue_labels_modified",
    ]:
        require_false(safety, field, "safety", errors)
    if safety.get("secret_values_included") is not False:
        errors.append("safety.secret_values_included must be false for repo artifacts")

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
            "github_api_called": False,
            "issue_comment_created": False,
            "issue_labels_modified": False,
            "notification_sent": False,
            "production_db_modified": False,
            "trading_or_order_execution": False,
            "background_worker_started": False,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a GitHub Issue pickup dry-run result JSON file.")
    parser.add_argument("--input", default="templates/github_issue_pickup_result.example.json")
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
