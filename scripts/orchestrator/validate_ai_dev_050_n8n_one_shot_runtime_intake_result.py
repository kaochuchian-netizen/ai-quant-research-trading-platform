#!/usr/bin/env python3
"""Validate AI-DEV-050 n8n one-shot runtime intake result package."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

DOC_PATH = Path("docs/ai_dev_050_n8n_one_shot_runtime_intake_result.md")
TEMPLATE_PATH = Path("templates/ai_dev_050_n8n_one_shot_runtime_intake_result.example.json")
RELATED_DOCS = [
    Path("docs/n8n_one_shot_runtime_intake_dry_run.md"),
    Path("docs/ai_dev_one_shot_multi_agent_automation.md"),
    Path("docs/ai_task_queue_runbook.md"),
]
REQUIRED_KEYS = [
    "task_id",
    "dry_run",
    "runtime_dry_run",
    "n8n_started",
    "n8n_stopped",
    "workflow_found_or_created",
    "workflow_state",
    "runtime_dry_run_executed",
    "dify_runtime_called",
    "chatgpt_openai_api_called",
    "notification_sent",
    "production_db_modified",
    "cron_or_timer_modified",
    "main_py_executed",
    "trading_executed",
    "no_secret_values",
    "local_only_outputs",
    "secret_scan_summary",
    "safety_flags",
]
EXPECTED_VALUES = {
    "n8n_started": True,
    "n8n_stopped": True,
    "runtime_dry_run": True,
    "runtime_dry_run_executed": True,
    "dify_runtime_called": False,
    "chatgpt_openai_api_called": False,
    "notification_sent": False,
    "production_db_modified": False,
    "cron_or_timer_modified": False,
    "main_py_executed": False,
    "trading_executed": False,
    "no_secret_values": True,
}
REQUIRED_SAFETY_TRUE = [
    "workflow_inactive",
    "dry_run_only",
    "no_notification",
    "no_production_write",
    "no_real_credentials",
    "no_dify_runtime_call",
    "no_chatgpt_openai_api_call",
    "ai_dev_051_not_executed",
]
SECRET_PATTERNS = [
    re.compile(r"Bearer\s+[A-Za-z0-9._~+\/-]{12,}", re.IGNORECASE),
    re.compile(r"Authorization\s*[:=]\s*(?!0\b|false\b|placeholder|\[REDACTED\])[A-Za-z0-9._~+\/-]{8,}", re.IGNORECASE),
    re.compile(r"api[_-]?key\s*[:=]\s*(?!0\b|false\b|placeholder|redacted)[A-Za-z0-9._~+\/-]{8,}", re.IGNORECASE),
    re.compile(r"token\s*[:=]\s*(?!0\b|false\b|placeholder|redacted)[A-Za-z0-9._~+\/-]{8,}", re.IGNORECASE),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
]


def load_json(path: Path) -> tuple[Any | None, str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except Exception as exc:
        return None, str(exc)


def has_secret_value(text: str) -> bool:
    return any(pattern.search(text) for pattern in SECRET_PATTERNS)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate AI-DEV-050 runtime result package.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    repo_root = Path(args.repo_root).resolve()
    errors: list[str] = []
    warnings: list[str] = []
    required_files = [DOC_PATH, TEMPLATE_PATH, *RELATED_DOCS]
    file_checks = {str(path): (repo_root / path).is_file() for path in required_files}
    for path, exists in file_checks.items():
        if not exists:
            errors.append(f"required file missing: {path}")

    data: dict[str, Any] = {}
    if file_checks.get(str(TEMPLATE_PATH)):
        loaded, err = load_json(repo_root / TEMPLATE_PATH)
        if err:
            errors.append(f"JSON parse failed for {TEMPLATE_PATH}: {err}")
        elif not isinstance(loaded, dict):
            errors.append("result template root must be object")
        else:
            data = loaded
            if has_secret_value(json.dumps(data, ensure_ascii=False, sort_keys=True)):
                errors.append("secret-like value found in result template")

    for key in REQUIRED_KEYS:
        if key not in data:
            errors.append(f"result template missing key: {key}")
    for key, expected in EXPECTED_VALUES.items():
        if data.get(key) is not expected:
            errors.append(f"{key} must be {expected}")

    local_outputs = data.get("local_only_outputs", {})
    if not isinstance(local_outputs, dict) or not local_outputs:
        errors.append("local_only_outputs must be present")
    else:
        for key in ["input_payload", "runtime_result", "chatgpt_report", "runtime_summary"]:
            if key not in local_outputs:
                errors.append(f"local_only_outputs missing {key}")
        for value in local_outputs.values():
            if isinstance(value, str) and value.startswith(str(repo_root)):
                errors.append("local-only runtime artifact path must not point inside repo")

    scan = data.get("secret_scan_summary", {})
    if not isinstance(scan, dict):
        errors.append("secret_scan_summary must be object")
    else:
        if scan.get("secret_values_printed") is not False:
            errors.append("secret values must not be printed")
        if scan.get("values_included") is not False:
            errors.append("secret scan summary must not include values")
        if not isinstance(scan.get("pattern_hit_counts"), dict):
            errors.append("secret scan pattern counts missing")

    workflow = data.get("workflow_state", {})
    for key, expected in {
        "workflow_found_or_created": True,
        "workflow_active": False,
        "workflow_dry_run_only": True,
        "no_notification_nodes": True,
        "no_production_write_nodes": True,
        "no_real_credentials": True,
        "no_dify_node": True,
        "no_chatgpt_openai_node": True,
    }.items():
        if workflow.get(key) is not expected:
            errors.append(f"workflow_state.{key} must be {expected}")

    flags = data.get("safety_flags", {})
    for flag in REQUIRED_SAFETY_TRUE:
        if not isinstance(flags, dict) or flags.get(flag) is not True:
            errors.append(f"safety_flags.{flag} must be true")

    for rel_path in [DOC_PATH, *RELATED_DOCS]:
        path = repo_root / rel_path
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        if has_secret_value(text):
            errors.append(f"secret-like value found in {rel_path}")
    doc_text = (repo_root / DOC_PATH).read_text(encoding="utf-8") if (repo_root / DOC_PATH).is_file() else ""
    for phrase in ["n8n started", "n8n stopped", "AI-DEV-051 was not executed", "no Dify runtime call", "no ChatGPT/OpenAI API call"]:
        if phrase not in doc_text:
            errors.append(f"result doc missing phrase: {phrase}")

    output = {
        "ok": not errors,
        "passed": not errors,
        "file_checks": file_checks,
        "task_id": data.get("task_id"),
        "runtime_state": {key: data.get(key) for key in EXPECTED_VALUES},
        "secret_scan_summary": data.get("secret_scan_summary"),
        "errors": errors,
        "warnings": warnings,
        "side_effects": {
            "files_modified": False,
            "n8n_started": False,
            "dify_called": False,
            "chatgpt_openai_api_called": False,
            "notification_sent": False,
            "runtime_queue_modified": False,
            "production_db_modified": False,
            "trading_execution_run": False,
        },
    }
    json.dump(output, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    return 0 if output["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
