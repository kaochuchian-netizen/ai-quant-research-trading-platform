#!/usr/bin/env python3
"""Evaluate a GitHub Issue fixture for AI-DEV pickup eligibility.

This helper is dry-run only. It reads a sanitized fixture JSON file, writes a
sanitized pickup decision artifact, and never calls GitHub APIs, comments on
Issues, changes labels, starts workers, or performs runtime actions.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REQUIRED_LABELS = ["ai-dev", "gcp-pickup", "dry-run"]

SECRET_VALUE_PATTERNS = [
    re.compile(r"ghp_[A-Za-z0-9_]+"),
    re.compile(r"github_pat_[A-Za-z0-9_]+"),
    re.compile(r"sk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]+"),
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?i)(api[_-]?key|access[_-]?token|password)\s*[:=]\s*[^\s,}\"']+"),
]

BLOCKED_TERM_PATTERNS = {
    "secret material": re.compile(r"(?i)\b(secret|token|credential|password|private key|\.env)\b"),
    "dify runtime": re.compile(r"(?i)\bdify\b.*\b(call|run|runtime|execute)\b|\b(call|run|execute)\b.*\bdify\b"),
    "openai api": re.compile(r"(?i)\b(openai|chatgpt)\b.*\b(api|call|run|execute)\b"),
    "send notification": re.compile(r"(?i)\b(send|push|deliver)\b.*\b(line|email|notification|webhook)\b"),
    "trade or order": re.compile(r"(?i)\b(trade|trading|place order|order execution|buy order|sell order)\b"),
    "production db": re.compile(r"(?i)\b(production db|prod db|production database)\b.*\b(write|mutate|modify|update|delete)\b"),
    "production n8n": re.compile(r"(?i)\b(start|stop|restart|modify|mutate)\b.*\b(n8n)\b|\bproduction n8n\b"),
    "production pipeline": re.compile(r"(?i)\b(production pipeline|python3 main\.py|run_stock_analysis\.sh)\b"),
    "cron systemd timers": re.compile(r"(?i)\b(cron|systemd|timer|timers)\b.*\b(modify|update|start|stop|restart)\b"),
    "real github issue mutation": re.compile(r"(?i)\b(comment on|close issue|reopen issue|label issue|edit issue)\b"),
}


def load_json(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, [f"failed to parse JSON issue fixture: {exc}"]
    if not isinstance(data, dict):
        return None, ["issue fixture root must be a JSON object"]
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


def find_blocked_terms(title: str, body: str) -> list[str]:
    text = f"{title}\n{body}"
    hits: list[str] = []
    for label, pattern in BLOCKED_TERM_PATTERNS.items():
        if pattern.search(text):
            hits.append(label)
    return hits


def classify_task(labels: list[str], title: str, body: str, blocked_terms: list[str]) -> str:
    if blocked_terms:
        return "blocked_runtime_action"
    text = f"{title}\n{body}".lower()
    label_set = set(labels)
    if {"contract", "template", "validator"} & label_set:
        return "repo_side_contract"
    if "docs" in label_set or "documentation" in text or "runbook" in text:
        return "documentation"
    if "validator" in text or "template" in text or "contract" in text:
        return "repo_side_contract"
    if "dry-run" in label_set or "dry run" in text or "dry-run" in text:
        return "dry_run_orchestration"
    return "needs_manual_review"


def summarize(title: str, task_class: str, decision: str) -> str:
    if decision == "accepted":
        return f"Eligible dry-run GitHub Issue pickup request for {task_class.replace('_', ' ')} work."
    if decision == "rejected":
        return "Rejected dry-run GitHub Issue pickup request because safety or eligibility gates failed."
    return "Issue pickup request needs manual review before a future runner can create an AI-DEV plan."


def build_result(issue: dict[str, Any]) -> dict[str, Any]:
    issue_number = issue.get("issue_number", issue.get("number"))
    issue_url = str(issue.get("issue_url", issue.get("html_url", "")))
    title = str(issue.get("title", ""))
    body = str(issue.get("body", ""))
    state = str(issue.get("state", "")).lower()
    labels_seen = extract_labels(issue)
    missing_labels = [label for label in REQUIRED_LABELS if label not in labels_seen]
    required_labels_present = not missing_labels
    blocked_terms = find_blocked_terms(title, body)
    secret_hits = find_secret_patterns(issue)
    task_class = classify_task(labels_seen, title, body, blocked_terms)

    reasons: list[str] = []
    warnings: list[str] = []
    if state == "open":
        reasons.append("issue is open")
    else:
        reasons.append("issue is not open")
    if required_labels_present:
        reasons.append("required labels are present")
    else:
        reasons.append("missing required labels: " + ", ".join(missing_labels))
    if blocked_terms:
        reasons.append("blocked action terms detected")
    else:
        reasons.append("no blocked action terms detected")
    if secret_hits:
        reasons.append("sensitive value patterns detected")
    if task_class == "needs_manual_review":
        warnings.append("task class could not be confidently classified")

    eligible = state == "open" and required_labels_present and not blocked_terms and not secret_hits
    if eligible and task_class != "needs_manual_review":
        decision = "accepted"
    elif blocked_terms or secret_hits:
        decision = "rejected"
    else:
        decision = "needs_manual_review"
        eligible = False

    required_key_labels = ",".join(label for label in REQUIRED_LABELS if label in labels_seen)
    idempotency_key = f"{issue_number}|{issue_url}|{required_key_labels}|{task_class}"
    next_step = {
        "accepted": "Future GCP resident runner may convert this Issue into a reviewed AI-DEV branch plan without mutating the Issue in this dry run.",
        "rejected": "Create a new dry-run repo-side Issue without runtime, notification, production, secret, or trading instructions.",
        "needs_manual_review": "Human review should clarify task class, labels, and safety boundaries before future pickup.",
    }[decision]

    return {
        "schema_version": "1.0.0",
        "issue_number": issue_number,
        "issue_url": issue_url,
        "title": title,
        "eligible": eligible,
        "decision": decision,
        "reasons": reasons,
        "labels_seen": labels_seen,
        "required_labels_present": required_labels_present,
        "missing_required_labels": missing_labels,
        "blocked_terms_detected": blocked_terms,
        "task_class": task_class,
        "dry_run": True,
        "runtime_action_performed": False,
        "mutation_performed": False,
        "github_issue_mutation_performed": False,
        "sanitized_summary": summarize(title, task_class, decision),
        "next_step_recommendation": next_step,
        "idempotency": {
            "key": idempotency_key,
            "duplicate_terminal_result_found": False,
            "on_duplicate_terminal_result": "skip_without_github_or_runtime_mutation",
        },
        "safety": {
            "secret_values_included": bool(secret_hits),
            "external_delivery_performed": False,
            "production_db_modified": False,
            "runtime_or_background_worker_started": False,
            "github_api_called": False,
            "issue_comment_created": False,
            "issue_labels_modified": False,
        },
        "errors": [],
        "warnings": warnings,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Dry-run GitHub Issue pickup eligibility evaluation.")
    parser.add_argument("--input", default="templates/github_issue_pickup_request.example.json")
    parser.add_argument("--output", required=True)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    issue, load_errors = load_json(Path(args.input))
    if issue is None:
        result = {
            "schema_version": "1.0.0",
            "issue_number": None,
            "issue_url": None,
            "title": None,
            "eligible": False,
            "decision": "rejected",
            "reasons": load_errors,
            "labels_seen": [],
            "required_labels_present": False,
            "missing_required_labels": REQUIRED_LABELS,
            "blocked_terms_detected": [],
            "task_class": "invalid_fixture",
            "dry_run": True,
            "runtime_action_performed": False,
            "mutation_performed": False,
            "github_issue_mutation_performed": False,
            "sanitized_summary": "Rejected invalid GitHub Issue fixture.",
            "next_step_recommendation": "Fix the fixture JSON and rerun the dry-run helper.",
            "idempotency": {
                "key": None,
                "duplicate_terminal_result_found": False,
                "on_duplicate_terminal_result": "skip_without_github_or_runtime_mutation",
            },
            "safety": {
                "secret_values_included": False,
                "external_delivery_performed": False,
                "production_db_modified": False,
                "runtime_or_background_worker_started": False,
                "github_api_called": False,
                "issue_comment_created": False,
                "issue_labels_modified": False,
            },
            "errors": load_errors,
            "warnings": [],
        }
    else:
        result = build_result(issue)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {
        "ok": result.get("decision") in {"accepted", "needs_manual_review", "rejected"},
        "output": str(output_path),
        "issue_number": result.get("issue_number"),
        "eligible": result.get("eligible"),
        "decision": result.get("decision"),
        "task_class": result.get("task_class"),
        "blocked_terms_detected": result.get("blocked_terms_detected", []),
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
    json.dump(summary, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    return 0 if summary["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
