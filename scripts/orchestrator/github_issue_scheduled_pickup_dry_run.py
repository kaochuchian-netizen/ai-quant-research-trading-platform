#!/usr/bin/env python3
"""Dry-run scheduled GitHub Issue pickup candidate discovery.

This helper is fixture-only for AI-DEV-059. It never polls, never runs as a
daemon, never mutates GitHub Issues, and never performs runtime actions.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REQUIRED_LABELS = ["ai-dev", "gcp-pickup", "auto-run", "repo-only"]
RECOMMENDED_LABELS = ["dry-run"]
EXCLUDED_LABELS = {
    "manual-review",
    "blocked",
    "runtime",
    "production",
    "secret",
    "notification",
    "trading",
    "n8n",
    "dify",
}
ALLOWED_TASK_CLASSES = {
    "docs_only",
    "template_only",
    "validator_only",
    "repo_side_contract",
    "test_or_validation_helper",
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
BLOCKED_CLASS_PATTERNS = {
    "secret_handling": re.compile(r"(?i)\b(secret|token|credential|password|private key|\.env)\b"),
    "Dify_runtime_call": re.compile(r"(?i)\bdify\b.*\b(call|run|runtime|execute)\b|\b(call|run|execute)\b.*\bdify\b"),
    "OpenAI_API_call": re.compile(r"(?i)\b(openai|chatgpt)\b.*\b(api|call|run|execute)\b"),
    "notification_send": re.compile(r"(?i)\b(send|push|deliver)\b.*\b(line|email|notification|webhook|report)\b"),
    "trading_or_order": re.compile(r"(?i)\b(trade|trading|place order|order execution|buy order|sell order)\b"),
    "production_DB_mutation": re.compile(r"(?i)\b(production db|prod db|production database)\b.*\b(write|mutate|modify|update|delete)\b"),
    "n8n_control": re.compile(r"(?i)\b(start|stop|restart|modify|mutate)\b.*\b(n8n)\b|\bproduction n8n\b"),
    "production_pipeline": re.compile(r"(?i)\b(production pipeline|python3 main\.py|run_stock_analysis\.sh)\b"),
    "cron_systemd_timer_change": re.compile(r"(?i)\b(cron|systemd|timer|timers)\b.*\b(modify|update|start|stop|restart|enable|disable)\b"),
    "daemon_background_service": re.compile(r"(?i)\b(daemon|background service|polling worker|scheduler|scheduled polling)\b"),
    "runtime_action": re.compile(r"(?i)\b(runtime action|execute runtime|production runtime|real runtime)\b"),
}
PROPOSED_RUNNER_COMMAND = (
    "python3 scripts/orchestrator/github_issue_auto_runner.py "
    "--input <sanitized_issue_fixture> --output <sanitized_result_json> --pretty --once"
)
SAFETY_CONFIRMATION = (
    "Scheduler is disabled. No runtime action, GitHub Issue mutation, daemon, schedule, "
    "background service, branch, PR, merge, notification, Dify, OpenAI, n8n, trading, "
    "production pipeline, or production database action was performed."
)


def load_json(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, [f"failed to parse JSON scheduler fixture: {exc}"]
    if not isinstance(data, dict):
        return None, ["scheduler fixture root must be a JSON object"]
    return data, []


def normalize_label(label: Any) -> str:
    if isinstance(label, dict):
        value = label.get("name", "")
    else:
        value = label
    return str(value).strip().lower()


def extract_labels(issue: dict[str, Any]) -> list[str]:
    labels = issue.get("labels", [])
    if not isinstance(labels, list):
        return []
    normalized = [normalize_label(label) for label in labels]
    return [label for label in normalized if label]


def flatten_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def find_secret_patterns(issue: dict[str, Any]) -> list[str]:
    text = flatten_text(issue)
    return [pattern.pattern for pattern in SECRET_VALUE_PATTERNS if pattern.search(text)]


def find_blocked_classes(title: str, body: str) -> list[str]:
    text = f"{title}\n{body}"
    hits: list[str] = []
    for task_class, pattern in BLOCKED_CLASS_PATTERNS.items():
        if pattern.search(text):
            hits.append(task_class)
    return hits


def classify_task(labels: list[str], title: str, body: str, blocked_classes: list[str]) -> str:
    if blocked_classes:
        return blocked_classes[0]
    label_set = set(labels)
    text = f"{title}\n{body}".lower()
    if "validator" in label_set or "validator" in text:
        return "validator_only"
    if "template" in label_set or "template" in text:
        return "template_only"
    if "docs" in label_set or "documentation" in text or "runbook" in text:
        return "docs_only"
    if "test" in label_set or "validation helper" in text or "test helper" in text:
        return "test_or_validation_helper"
    if "contract" in label_set or "contract" in text:
        return "repo_side_contract"
    return "needs_manual_review"


def idempotency_key(issue_number: Any, issue_url: str, task_class: str, labels: list[str]) -> str:
    present_required_labels = ",".join(label for label in REQUIRED_LABELS if label in labels)
    return f"scheduled-pickup-v1|{issue_number}|{issue_url}|{task_class}|{present_required_labels}"


def issue_record(
    issue: dict[str, Any],
    existing_idempotency_keys: set[str],
) -> tuple[dict[str, Any], str]:
    issue_number = issue.get("issue_number", issue.get("number"))
    issue_url = str(issue.get("issue_url", issue.get("html_url", "")))
    title = str(issue.get("title", ""))
    body = str(issue.get("body", ""))
    state = str(issue.get("state", "")).lower()
    labels = extract_labels(issue)
    label_set = set(labels)
    missing_labels = [label for label in REQUIRED_LABELS if label not in label_set]
    required_labels_present = not missing_labels
    excluded_label_hits = [f"excluded_label:{label}" for label in sorted(label_set & EXCLUDED_LABELS)]
    blocked_classes = find_blocked_classes(title, body)
    secret_hits = find_secret_patterns(issue)
    task_class = classify_task(labels, title, body, blocked_classes)
    key = idempotency_key(issue_number, issue_url, task_class, labels)
    blocked_terms = excluded_label_hits + blocked_classes
    if secret_hits and "secret_handling" not in blocked_terms:
        blocked_terms.append("secret_handling")
    if state != "open":
        blocked_terms.append("issue_not_open")
    if key in existing_idempotency_keys:
        blocked_terms.append("duplicate_idempotency_key")

    allowlisted = task_class in ALLOWED_TASK_CLASSES
    eligible = (
        state == "open"
        and required_labels_present
        and not excluded_label_hits
        and not blocked_classes
        and not secret_hits
        and allowlisted
        and key not in existing_idempotency_keys
    )
    if eligible:
        decision = "accepted"
        bucket = "candidate"
        summary = f"Scheduled pickup candidate accepted for {task_class} repo-only work."
        proposed_command: str | None = PROPOSED_RUNNER_COMMAND
        manual_approval_required = True
    elif blocked_terms:
        decision = "rejected"
        bucket = "rejected"
        if "duplicate_idempotency_key" in blocked_terms:
            summary = "Scheduled pickup candidate rejected because the idempotency key already has a terminal result."
        elif "issue_not_open" in blocked_terms:
            summary = "Scheduled pickup candidate rejected because the Issue is not open."
        else:
            summary = "Scheduled pickup candidate rejected because blocked labels or task classes were detected."
        proposed_command = None
        manual_approval_required = True
    else:
        decision = "needs_manual_review"
        bucket = "manual_review"
        summary = "Scheduled pickup candidate needs manual review before any future repo-only execution."
        proposed_command = None
        manual_approval_required = True

    return {
        "issue_number": issue_number,
        "issue_url": issue_url,
        "title": title,
        "labels_seen": labels,
        "eligible": eligible,
        "decision": decision,
        "task_class": task_class,
        "required_labels_present": required_labels_present,
        "blocked_terms_detected": blocked_terms,
        "idempotency_key": key,
        "sanitized_summary": summary,
        "proposed_runner_command": proposed_command,
        "execute_repo_only_allowed": False,
        "manual_approval_required": manual_approval_required,
    }, bucket


def empty_result(run_id: str, source: str, errors: list[str] | None = None) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "dry_run": True,
        "scheduler_enabled": False,
        "runtime_action_performed": False,
        "github_issue_mutated": False,
        "daemon_or_background_service_created": False,
        "source": source,
        "total_issues_seen": 0,
        "eligible_count": 0,
        "rejected_count": 0,
        "needs_manual_review_count": 0,
        "candidate_issue_numbers": [],
        "candidates": [],
        "rejected": [],
        "idempotency_keys": [],
        "next_step_recommendation": "No eligible scheduled pickup candidates were found in the fixture.",
        "safety_confirmation": SAFETY_CONFIRMATION,
        "errors": errors or [],
        "warnings": [],
    }


def build_result(fixture: dict[str, Any]) -> dict[str, Any]:
    run_id = str(fixture.get("run_id") or f"scheduled-pickup-dry-run-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}")
    source = str(fixture.get("source") or "fixture")
    issues = fixture.get("issues", [])
    if not isinstance(issues, list):
        return empty_result(run_id, source, ["fixture.issues must be a list"])
    existing_keys_raw = fixture.get("existing_idempotency_keys", [])
    existing_keys = set(str(key) for key in existing_keys_raw if isinstance(key, str)) if isinstance(existing_keys_raw, list) else set()
    max_issues = fixture.get("max_issues_per_run", len(issues))
    if not isinstance(max_issues, int) or max_issues < 0:
        max_issues = len(issues)

    candidates: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    manual_review_count = 0
    evaluated_issues = issues[:max_issues]
    warnings: list[str] = []
    if len(issues) > max_issues:
        warnings.append(f"fixture contained {len(issues)} issues; evaluated max_issues_per_run={max_issues}")

    for raw_issue in evaluated_issues:
        if not isinstance(raw_issue, dict):
            record = {
                "issue_number": None,
                "issue_url": "",
                "title": "",
                "labels_seen": [],
                "eligible": False,
                "decision": "rejected",
                "task_class": "invalid_fixture",
                "required_labels_present": False,
                "blocked_terms_detected": ["invalid_issue_fixture"],
                "idempotency_key": "scheduled-pickup-v1|invalid|invalid|invalid_fixture|",
                "sanitized_summary": "Scheduled pickup candidate rejected because the Issue fixture is invalid.",
                "proposed_runner_command": None,
                "execute_repo_only_allowed": False,
                "manual_approval_required": True,
            }
            rejected.append(record)
            continue
        record, bucket = issue_record(raw_issue, existing_keys)
        if bucket == "candidate":
            candidates.append(record)
        else:
            rejected.append(record)
            if bucket == "manual_review":
                manual_review_count += 1

    accepted_keys = [candidate["idempotency_key"] for candidate in candidates]
    next_step = (
        "Review this sanitized report before AI-DEV-060 proposes real schedule activation."
        if candidates
        else "No eligible scheduled pickup candidates were found in the fixture."
    )
    return {
        "schema_version": "1.0.0",
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "dry_run": True,
        "scheduler_enabled": False,
        "runtime_action_performed": False,
        "github_issue_mutated": False,
        "daemon_or_background_service_created": False,
        "source": source,
        "total_issues_seen": len(evaluated_issues),
        "eligible_count": len(candidates),
        "rejected_count": len(rejected) - manual_review_count,
        "needs_manual_review_count": manual_review_count,
        "candidate_issue_numbers": [candidate["issue_number"] for candidate in candidates],
        "candidates": candidates,
        "rejected": rejected,
        "idempotency_keys": accepted_keys,
        "next_step_recommendation": next_step,
        "safety_confirmation": SAFETY_CONFIRMATION,
        "errors": [],
        "warnings": warnings,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fixture-only dry-run scheduled GitHub Issue pickup.")
    parser.add_argument("--input", required=True, help="Sanitized scheduler fixture JSON.")
    parser.add_argument("--output", required=True)
    parser.add_argument("--once", action="store_true", help="Required guard; this helper never polls.")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.once:
        result = empty_result(
            "scheduled-pickup-dry-run-invalid",
            "fixture",
            ["--once is required; daemon, schedule, and polling modes are not implemented"],
        )
    else:
        fixture, load_errors = load_json(Path(args.input))
        result = empty_result("scheduled-pickup-dry-run-invalid", "fixture", load_errors) if fixture is None else build_result(fixture)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {
        "ok": not result.get("errors"),
        "output": str(output_path),
        "run_id": result.get("run_id"),
        "source": result.get("source"),
        "total_issues_seen": result.get("total_issues_seen"),
        "eligible_count": result.get("eligible_count"),
        "rejected_count": result.get("rejected_count"),
        "needs_manual_review_count": result.get("needs_manual_review_count"),
        "candidate_issue_numbers": result.get("candidate_issue_numbers", []),
        "side_effects": {
            "runtime_action_performed": False,
            "github_issue_mutated": False,
            "daemon_or_background_service_created": False,
            "branch_created": False,
            "pr_created": False,
            "merge_performed": False,
        },
    }
    json.dump(summary, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    return 0 if summary["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
