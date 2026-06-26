#!/usr/bin/env python3
"""Validate the AI-DEV-040 runtime export approval procedure package.

The validator is read-only. It checks repo-contained docs and JSON templates
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
    "docs/n8n_dify_runtime_export_approval_procedure.md",
    "templates/n8n_runtime_export_approval_request.example.json",
    "templates/n8n_runtime_export_supervised_result.example.json",
    "scripts/orchestrator/validate_runtime_export_approval_procedure.py",
]

JSON_FILES = [
    "templates/n8n_runtime_export_approval_request.example.json",
    "templates/n8n_runtime_export_supervised_result.example.json",
]

REQUIRED_GATES = [
    "approved_by_human",
    "export_scope",
    "raw_export_local_only",
    "sanitize_required",
    "secrets_must_not_leave_runtime",
    "no_publish",
    "no_active_workflow",
    "no_notification",
    "no_auto_merge",
    "no_trading",
]

REQUIRED_DOC_KEYWORDS = [
    "Pre-Approval",
    "Runtime Access",
    "Raw Export Local-Only Handling",
    "Sanitize",
    "Validation",
    "Recovery Verification",
    "Cleanup",
    "Closeout",
    "AI-DEV-040 is not a runtime export",
    "real workflow export requires a separate human approval",
    "Raw export commit is forbidden",
]

SECRET_PATTERNS = [
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE),
    re.compile(r"sk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{16,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{16,}"),
    re.compile(r"AIza[0-9A-Za-z_-]{16,}"),
]

ALLOWED_PLACEHOLDERS = {
    "DIFY_API_KEY_STORED_IN_N8N_ONLY",
    "DO_NOT_COMMIT_REAL_SECRET",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate AI-DEV-040 runtime export approval procedure files."
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


def find_missing_gates(data: Any) -> list[str]:
    if not isinstance(data, dict):
        return REQUIRED_GATES
    gates = data.get("gates")
    if not isinstance(gates, dict):
        return REQUIRED_GATES
    return [gate for gate in REQUIRED_GATES if gate not in gates]


def detect_secret_like_patterns(json_results: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    for rel_path, data in json_results.items():
        for text in iter_strings(data):
            if text in ALLOWED_PLACEHOLDERS:
                continue
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

    doc_path = repo_root / "docs/n8n_dify_runtime_export_approval_procedure.md"
    doc_text = doc_path.read_text(encoding="utf-8") if doc_path.is_file() else ""
    for keyword in REQUIRED_DOC_KEYWORDS:
        if keyword not in doc_text:
            reasons.append(f"required doc keyword missing: {keyword}")

    raw_export_forbidden_phrases = [
        "Raw export commit is forbidden",
        "never be committed",
        "must stay outside the repository",
    ]
    raw_export_commit_forbidden = all(phrase in doc_text for phrase in raw_export_forbidden_phrases)
    if not raw_export_commit_forbidden:
        reasons.append("docs must explicitly forbid raw export commit")

    missing_gate_results: dict[str, list[str]] = {}
    for rel_path, data in json_results.items():
        missing = find_missing_gates(data)
        if missing:
            missing_gate_results[rel_path] = missing
            for gate in missing:
                reasons.append(f"required gate missing in {rel_path}: {gate}")

    secret_findings = detect_secret_like_patterns(json_results)
    reasons.extend(secret_findings)

    result = {
        "ok": not reasons,
        "checked_files": REQUIRED_FILES,
        "json_files_valid": sorted(json_results),
        "required_gates": REQUIRED_GATES,
        "missing_gates": missing_gate_results,
        "raw_export_commit_forbidden": raw_export_commit_forbidden,
        "secret_pattern_findings": secret_findings,
        "runtime_side_effects": {
            "n8n_started": False,
            "dify_logged_in_or_called": False,
            "raw_export_created_or_read": False,
            "secrets_read_printed_saved_or_committed": False,
            "runtime_queue_modified": False,
            "notification_sent": False,
            "codex_real_task_sent": False,
            "auto_merge_executed": False,
            "python3_main_py_run": False,
            "ai_dev_041_run": False,
        },
        "errors": reasons,
    }
    print(json.dumps(result, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
