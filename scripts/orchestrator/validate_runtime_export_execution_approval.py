#!/usr/bin/env python3
"""Validate the AI-DEV-042 runtime export execution approval package.

This validator is read-only. It checks repo-contained docs and JSON templates
without starting n8n, calling Dify, reading raw exports, reading secrets,
modifying runtime queues, sending notifications, trading, merging, or running
production entrypoints.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


REQUIRED_FILES = [
    "docs/n8n_runtime_export_execution_approval.md",
    "templates/n8n_runtime_export_execution_approval_request.example.json",
    "templates/n8n_runtime_export_preflight_checklist.example.json",
    "templates/n8n_runtime_export_execution_closeout.example.json",
    "scripts/orchestrator/validate_runtime_export_execution_approval.py",
]

JSON_FILES = [
    "templates/n8n_runtime_export_execution_approval_request.example.json",
    "templates/n8n_runtime_export_preflight_checklist.example.json",
    "templates/n8n_runtime_export_execution_closeout.example.json",
]

REQUIRED_APPROVAL_GATES = [
    "task_id",
    "approval_scope",
    "approved_by_human",
    "approved_runtime_access",
    "approved_n8n_start",
    "approved_raw_export_local_only",
    "approved_sanitize_after_export",
    "approved_no_publish",
    "approved_no_active_workflow",
    "approved_no_notification",
    "approved_no_auto_merge",
    "approved_no_trading",
    "approved_no_secret_disclosure",
    "approval_expiry",
]

RUNTIME_APPROVAL_GATES = [
    "approved_by_human",
    "approved_runtime_access",
    "approved_n8n_start",
    "approved_raw_export_local_only",
    "approved_sanitize_after_export",
    "approved_no_publish",
    "approved_no_active_workflow",
    "approved_no_notification",
    "approved_no_auto_merge",
    "approved_no_trading",
    "approved_no_secret_disclosure",
]

REQUIRED_DOC_KEYWORDS = [
    "planning approval",
    "preflight approval",
    "runtime execution approval",
    "post-export sanitize approval",
    "cleanup and closeout",
    "A real export needs separate AI-DEV-043 or later human-approved task",
    "Raw export commit is forbidden",
    "Raw export must remain local-only",
    "Sanitize before repo inclusion is mandatory",
    "Human approval before runtime access is mandatory",
]

SECRET_PATTERNS = [
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE),
    re.compile(r"sk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{16,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{16,}"),
    re.compile(r"AIza[0-9A-Za-z_-]{16,}"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate AI-DEV-042 runtime export execution approval files."
    )
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def load_json(path: Path) -> tuple[Any | None, str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except Exception as exc:
        return None, str(exc)


def iter_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            result.extend(iter_strings(item))
        return result
    if isinstance(value, dict):
        result = []
        for key, item in value.items():
            result.append(str(key))
            result.extend(iter_strings(item))
        return result
    return []


def missing_gates(data: Any) -> list[str]:
    if not isinstance(data, dict):
        return REQUIRED_APPROVAL_GATES
    return [gate for gate in REQUIRED_APPROVAL_GATES if gate not in data]


def runtime_gates_default_false(data: Any) -> list[str]:
    if not isinstance(data, dict):
        return RUNTIME_APPROVAL_GATES
    return [gate for gate in RUNTIME_APPROVAL_GATES if data.get(gate) is not False]


def detect_secret_like_values(json_results: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    for rel_path, data in json_results.items():
        for text in iter_strings(data):
            for pattern in SECRET_PATTERNS:
                if pattern.search(text):
                    reasons.append(f"secret-like pattern found in {rel_path}")
                    break
    return reasons


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    reasons: list[str] = []
    json_results: dict[str, Any] = {}

    for rel_path in REQUIRED_FILES:
        if not (repo_root / rel_path).is_file():
            reasons.append(f"required file missing: {rel_path}")

    for rel_path in JSON_FILES:
        path = repo_root / rel_path
        if not path.is_file():
            continue
        data, error = load_json(path)
        json_results[rel_path] = data
        if error:
            reasons.append(f"invalid JSON in {rel_path}: {error}")

    doc_path = repo_root / "docs/n8n_runtime_export_execution_approval.md"
    doc_text = doc_path.read_text(encoding="utf-8") if doc_path.is_file() else ""
    for keyword in REQUIRED_DOC_KEYWORDS:
        if keyword not in doc_text:
            reasons.append(f"required doc keyword missing: {keyword}")

    doc_requirements = {
        "raw_export_commit_forbidden": "Raw export commit is forbidden" in doc_text,
        "raw_export_local_only": "Raw export must remain local-only" in doc_text,
        "sanitize_before_repo_inclusion": "Sanitize before repo inclusion is mandatory" in doc_text,
        "human_approval_before_runtime_access": "Human approval before runtime access is mandatory" in doc_text,
    }
    for name, ok in doc_requirements.items():
        if not ok:
            reasons.append(f"doc requirement missing: {name}")

    missing_gate_results: dict[str, list[str]] = {}
    non_false_gate_results: dict[str, list[str]] = {}
    for rel_path, data in json_results.items():
        missing = missing_gates(data)
        if missing:
            missing_gate_results[rel_path] = missing
            for gate in missing:
                reasons.append(f"required approval gate missing in {rel_path}: {gate}")
        non_false = runtime_gates_default_false(data)
        if non_false:
            non_false_gate_results[rel_path] = non_false
            for gate in non_false:
                reasons.append(f"runtime approval gate must default false in {rel_path}: {gate}")

    secret_findings = detect_secret_like_values(json_results)
    reasons.extend(secret_findings)

    result = {
        "ok": not reasons,
        "checked_files": REQUIRED_FILES,
        "json_files_valid": sorted(json_results),
        "required_approval_gates": REQUIRED_APPROVAL_GATES,
        "missing_gates": missing_gate_results,
        "runtime_gates_not_default_false": non_false_gate_results,
        "doc_requirements": doc_requirements,
        "secret_pattern_findings": secret_findings,
        "runtime_side_effects": {
            "n8n_started": False,
            "dify_logged_in_or_called": False,
            "real_raw_export_created_or_read": False,
            "secrets_read_printed_saved_or_committed": False,
            "runtime_queue_modified": False,
            "notification_sent": False,
            "codex_real_task_sent": False,
            "auto_merge_executed": False,
            "python3_main_py_run": False,
            "ai_dev_043_run": False,
        },
        "errors": reasons,
    }
    print(json.dumps(result, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
