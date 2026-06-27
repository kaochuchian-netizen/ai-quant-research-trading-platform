#!/usr/bin/env python3
"""Dry-run GitHub Issue auto-runner for safe repo-only tasks.

The runner is manually invoked with --once. It never runs as a daemon, never
executes shell commands from Issue text, and never mutates real GitHub Issues.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

REQUIRED_LABELS = ["ai-dev", "gcp-pickup", "auto-run", "repo-only"]
RECOMMENDED_LABELS = ["dry-run"]
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


def load_json(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, [f"failed to parse JSON issue fixture: {exc}"]
    if not isinstance(data, dict):
        return None, ["issue fixture root must be a JSON object"]
    return data, []


def run_gh_issue_view(issue_number: str, repo: str | None) -> tuple[dict[str, Any] | None, list[str]]:
    args = [
        "gh",
        "issue",
        "view",
        issue_number,
        "--json",
        "number,url,state,title,body,labels,author,createdAt,updatedAt",
    ]
    if repo:
        args.extend(["--repo", repo])
    proc = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if proc.returncode != 0:
        return None, [proc.stderr.strip() or proc.stdout.strip() or "gh issue view failed"]
    try:
        raw = json.loads(proc.stdout)
    except Exception as exc:
        return None, [f"failed to parse gh issue JSON: {exc}"]
    if not isinstance(raw, dict):
        return None, ["gh issue JSON root must be an object"]
    return {
        "schema_version": "1.0.0",
        "issue_number": raw.get("number"),
        "issue_url": raw.get("url"),
        "state": str(raw.get("state", "")).lower(),
        "title": raw.get("title"),
        "body": raw.get("body"),
        "labels": raw.get("labels", []),
        "author": raw.get("author", {}),
        "created_at": raw.get("createdAt"),
        "updated_at": raw.get("updatedAt"),
    }, []


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


def classify_allowed_task(labels: list[str], title: str, body: str, blocked_classes: list[str]) -> str:
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


def validation_items(
    issue_loaded: bool,
    required_labels_present: bool,
    blocked_terms_absent: bool,
    task_class_allowlisted: bool,
    secrets_absent: bool,
) -> list[dict[str, Any]]:
    return [
        {"name": "issue_fixture_loaded", "passed": issue_loaded},
        {"name": "required_labels_present", "passed": required_labels_present},
        {"name": "blocked_terms_absent", "passed": blocked_terms_absent},
        {"name": "task_class_allowlisted", "passed": task_class_allowlisted},
        {"name": "sensitive_value_patterns_absent", "passed": secrets_absent},
    ]


def build_result(issue: dict[str, Any], execute_repo_only: bool) -> dict[str, Any]:
    issue_number = issue.get("issue_number", issue.get("number"))
    issue_url = str(issue.get("issue_url", issue.get("html_url", "")))
    title = str(issue.get("title", ""))
    body = str(issue.get("body", ""))
    state = str(issue.get("state", "")).lower()
    labels_seen = extract_labels(issue)
    missing_labels = [label for label in REQUIRED_LABELS if label not in labels_seen]
    required_labels_present = not missing_labels
    blocked_classes = find_blocked_classes(title, body)
    secret_hits = find_secret_patterns(issue)
    task_class = classify_allowed_task(labels_seen, title, body, blocked_classes)
    task_class_allowlisted = task_class in ALLOWED_TASK_CLASSES
    blocked_terms_absent = not blocked_classes
    secrets_absent = not secret_hits
    issue_open = state == "open"

    eligible = issue_open and required_labels_present and blocked_terms_absent and secrets_absent and task_class_allowlisted
    if eligible and execute_repo_only:
        decision = "executed_repo_only"
    elif eligible:
        decision = "accepted"
    elif blocked_classes or secret_hits:
        decision = "rejected"
    else:
        decision = "needs_manual_review"

    warnings: list[str] = []
    if "dry-run" not in labels_seen:
        warnings.append("dry-run label is strongly recommended for v1 auto-runner requests")
    if task_class == "needs_manual_review":
        warnings.append("task class could not be confidently classified")

    files_changed = ["sanitized auto-runner result artifact"] if decision == "executed_repo_only" else []
    summary_action = "executed a constrained repo-only plan artifact" if decision == "executed_repo_only" else "produced a dry-run execution plan"
    if decision == "rejected":
        sanitized_summary = "Rejected GitHub Issue auto-run request because safety or eligibility gates failed."
    elif decision == "needs_manual_review":
        sanitized_summary = "GitHub Issue auto-run request needs manual review before repo-side execution."
    else:
        sanitized_summary = f"Accepted repo-only GitHub Issue auto-run request for {task_class} work and {summary_action}."

    next_step = {
        "accepted": "Review the sanitized plan before enabling deterministic repo edits or scheduled pickup in a later task.",
        "executed_repo_only": "Use this result as proof of the v1 controlled repo-only path; future tasks may add allowlisted deterministic repo edits.",
        "rejected": "Create a new repo-only auto-run Issue without runtime, notification, production, secret, trading, n8n, Dify, OpenAI, cron, systemd, or daemon instructions.",
        "needs_manual_review": "Human review should clarify labels, task class, and safety boundaries before future pickup.",
    }[decision]

    return {
        "schema_version": "1.0.0",
        "issue_number": issue_number,
        "issue_url": issue_url,
        "title": title,
        "labels_seen": labels_seen,
        "eligible": eligible,
        "decision": decision,
        "task_class": task_class,
        "required_labels_present": required_labels_present,
        "missing_required_labels": missing_labels,
        "blocked_terms_detected": blocked_classes + (["secret_handling"] if secret_hits else []),
        "dry_run": True,
        "execute_repo_only": bool(execute_repo_only),
        "mutation_performed": False,
        "runtime_action_performed": False,
        "github_issue_mutated": False,
        "branch_created": False,
        "pr_created": False,
        "pr_url": None,
        "merged": False,
        "merge_commit": None,
        "files_changed": files_changed,
        "validations_run": validation_items(True, required_labels_present, blocked_terms_absent, task_class_allowlisted, secrets_absent),
        "sanitized_summary": sanitized_summary,
        "next_step_recommendation": next_step,
        "safety_confirmation": (
            "No runtime action, GitHub Issue mutation, daemon, scheduler, notification, Dify, OpenAI, "
            "n8n, trading, production pipeline, or production database action was performed."
        ),
        "errors": [],
        "warnings": warnings,
    }


def invalid_result(errors: list[str], execute_repo_only: bool) -> dict[str, Any]:
    return {
        "schema_version": "1.0.0",
        "issue_number": None,
        "issue_url": None,
        "title": None,
        "labels_seen": [],
        "eligible": False,
        "decision": "rejected",
        "task_class": "invalid_fixture",
        "required_labels_present": False,
        "missing_required_labels": REQUIRED_LABELS,
        "blocked_terms_detected": [],
        "dry_run": True,
        "execute_repo_only": bool(execute_repo_only),
        "mutation_performed": False,
        "runtime_action_performed": False,
        "github_issue_mutated": False,
        "branch_created": False,
        "pr_created": False,
        "pr_url": None,
        "merged": False,
        "merge_commit": None,
        "files_changed": [],
        "validations_run": validation_items(False, False, True, False, True),
        "sanitized_summary": "Rejected invalid GitHub Issue auto-runner input.",
        "next_step_recommendation": "Fix the fixture or read-only issue lookup and rerun with --once.",
        "safety_confirmation": (
            "No runtime action, GitHub Issue mutation, daemon, scheduler, notification, Dify, OpenAI, "
            "n8n, trading, production pipeline, or production database action was performed."
        ),
        "errors": errors,
        "warnings": [],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manual --once GitHub Issue auto-runner v1 for repo-only tasks.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", help="Sanitized issue fixture JSON.")
    source.add_argument("--issue", help="Read issue metadata with gh issue view without mutation.")
    parser.add_argument("--repo", default=None, help="Repository for --issue, for example OWNER/REPO.")
    parser.add_argument("--output", required=True)
    parser.add_argument("--once", action="store_true", help="Required guard; this runner never polls.")
    parser.add_argument("--execute-repo-only", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.once:
        result = invalid_result(["--once is required; daemon or polling mode is not implemented"], args.execute_repo_only)
    elif args.issue:
        issue, load_errors = run_gh_issue_view(str(args.issue), args.repo)
        result = invalid_result(load_errors, args.execute_repo_only) if issue is None else build_result(issue, args.execute_repo_only)
    else:
        issue, load_errors = load_json(Path(str(args.input)))
        result = invalid_result(load_errors, args.execute_repo_only) if issue is None else build_result(issue, args.execute_repo_only)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {
        "ok": result.get("decision") in {"accepted", "rejected", "needs_manual_review", "executed_repo_only"},
        "output": str(output_path),
        "issue_number": result.get("issue_number"),
        "eligible": result.get("eligible"),
        "decision": result.get("decision"),
        "task_class": result.get("task_class"),
        "execute_repo_only": result.get("execute_repo_only"),
        "blocked_terms_detected": result.get("blocked_terms_detected", []),
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
    json.dump(summary, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    return 0 if summary["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
