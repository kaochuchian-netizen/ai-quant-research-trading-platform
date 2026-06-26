#!/usr/bin/env python3
"""Validate the AI-DEV-037 n8n runtime dry-run operation runbook.

The validator is read-only. It checks repo-contained docs and templates without
calling n8n, Dify, GitHub, production systems, notification systems, or trading
services.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


REQUIRED_FILES = [
    "docs/n8n_dify_runtime_activation_e2e_dry_run.md",
    "templates/n8n_runtime_dry_run_operation_record.example.json",
    "templates/n8n_runtime_enable_disable_runbook_checklist.example.json",
    "scripts/orchestrator/validate_n8n_runtime_dry_run_runbook.py",
]

JSON_FILES = [
    "templates/n8n_runtime_dry_run_operation_record.example.json",
    "templates/n8n_runtime_enable_disable_runbook_checklist.example.json",
]

DOC_REQUIRED_PHRASES = [
    "saved but not published",
    "workflow not active",
    "Manual Trigger only",
    "no secrets in repo",
    "no production mutation",
    "no notification",
    "no auto-merge",
    "n8n container stopped",
    "SSH tunnel closed",
    "no Codex real execution task was sent",
    "AI-DEV-038",
]

REQUIRED_FIELDS = {
    "templates/n8n_runtime_dry_run_operation_record.example.json": [
        "schema_version",
        "artifact_type",
        "task_id",
        "source_task",
        "record_type",
        "observed_runtime_state",
        "side_effects",
        "required_phrases",
        "notes",
    ],
    "templates/n8n_runtime_enable_disable_runbook_checklist.example.json": [
        "schema_version",
        "artifact_type",
        "task_id",
        "activation_mode",
        "enable_preconditions",
        "enable_steps",
        "disable_steps",
        "rollback_steps",
        "human_gates",
        "must_remain_false",
    ],
}

SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{20,}"),
    re.compile(r"AIza[0-9A-Za-z_-]{20,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]{20,}", re.IGNORECASE),
]

PLACEHOLDER_WORDS = ("EXAMPLE", "example", "placeholder", "sandbox")


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
        for item in value.values():
            result.extend(iter_strings(item))
        return result
    return []


def missing_fields(data: Any, fields: list[str]) -> list[str]:
    if not isinstance(data, dict):
        return fields
    return [field for field in fields if field not in data]


def all_bool_values_false(value: Any) -> bool:
    return isinstance(value, dict) and all(item is False for item in value.values())


def detect_secret_like_values(json_objects: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    for rel_path, data in json_objects.items():
        for text in iter_strings(data):
            if any(word in text for word in PLACEHOLDER_WORDS):
                continue
            for pattern in SECRET_PATTERNS:
                if pattern.search(text):
                    reasons.append(f"secret-like value found in {rel_path}")
                    break
    return reasons


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate AI-DEV-037 runtime dry-run runbook.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    reasons: list[str] = []
    json_results: dict[str, Any] = {}

    missing_files = [rel_path for rel_path in REQUIRED_FILES if not (repo_root / rel_path).is_file()]
    for rel_path in missing_files:
        reasons.append(f"required file missing: {rel_path}")

    for rel_path in JSON_FILES:
        path = repo_root / rel_path
        if not path.is_file():
            continue
        data, error = load_json(path)
        json_results[rel_path] = data
        if error:
            reasons.append(f"invalid JSON in {rel_path}: {error}")

    doc_path = repo_root / "docs/n8n_dify_runtime_activation_e2e_dry_run.md"
    doc_text = doc_path.read_text(encoding="utf-8") if doc_path.is_file() else ""
    missing_doc_phrases = [phrase for phrase in DOC_REQUIRED_PHRASES if phrase not in doc_text]
    for phrase in missing_doc_phrases:
        reasons.append(f"required doc phrase missing: {phrase}")

    missing_required_fields: dict[str, list[str]] = {}
    for rel_path, fields in REQUIRED_FIELDS.items():
        missing = missing_fields(json_results.get(rel_path), fields)
        if missing:
            missing_required_fields[rel_path] = missing
            for field in missing:
                reasons.append(f"required field missing in {rel_path}: {field}")

    operation = json_results.get("templates/n8n_runtime_dry_run_operation_record.example.json")
    operation_side_effects_false = (
        isinstance(operation, dict) and all_bool_values_false(operation.get("side_effects"))
    )
    if not operation_side_effects_false:
        reasons.append("operation record side_effects must all be false")

    observed = operation.get("observed_runtime_state") if isinstance(operation, dict) else {}
    required_true_observed = [
        "dify_workflow_api_dry_run_completed",
        "n8n_manual_workflow_saved",
        "saved_but_not_published",
        "workflow_not_active",
        "manual_trigger_only",
        "n8n_container_stopped",
        "ssh_tunnel_closed",
    ]
    missing_true_observed = [
        key for key in required_true_observed if not isinstance(observed, dict) or observed.get(key) is not True
    ]
    for key in missing_true_observed:
        reasons.append(f"observed runtime state must be true: {key}")
    if isinstance(observed, dict) and observed.get("n8n_manual_workflow_published") is not False:
        reasons.append("n8n_manual_workflow_published must be false")

    checklist = json_results.get("templates/n8n_runtime_enable_disable_runbook_checklist.example.json")
    checklist_false = isinstance(checklist, dict) and all_bool_values_false(checklist.get("must_remain_false"))
    if not checklist_false:
        reasons.append("runbook checklist must_remain_false values must all be false")

    secret_like_values = detect_secret_like_values(json_results)
    reasons.extend(secret_like_values)

    result = {
        "ok": True,
        "passed": not reasons,
        "repo_root": str(repo_root),
        "required_files": REQUIRED_FILES,
        "missing_files": missing_files,
        "json_files": JSON_FILES,
        "json_valid": not any(reason.startswith("invalid JSON") for reason in reasons),
        "missing_doc_phrases": missing_doc_phrases,
        "missing_required_fields": missing_required_fields,
        "operation_side_effects_false": operation_side_effects_false,
        "missing_true_observed": missing_true_observed,
        "checklist_must_remain_false": checklist_false,
        "secret_like_values_found": secret_like_values,
        "reasons": reasons,
        "side_effects": {
            "files_modified": False,
            "external_api_called": False,
            "dify_called": False,
            "n8n_called": False,
            "credential_read_or_modified": False,
            "production_pipeline_run": False,
            "notification_sent": False,
            "trading_execution_run": False,
            "codex_real_execution_task_sent": False,
            "auto_merge_executed": False,
            "ai_dev_038_run": False,
        },
    }
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    return 0 if result["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
