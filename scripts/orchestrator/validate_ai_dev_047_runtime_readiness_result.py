#!/usr/bin/env python3
"""Validate the AI-DEV-047 runtime readiness result package."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

DOC_PATH = Path("docs/ai_dev_047_runtime_readiness_result.md")
INTEGRATION_DOC_PATH = Path("docs/dify_n8n_daily_report_draft_dry_run_integration.md")
ROADMAP_PATH = Path("docs/daily_report_forecast_roadmap.md")
TEMPLATE_PATH = Path("templates/ai_dev_047_runtime_readiness_result.example.json")

REQUIRED_KEYS = [
    "task_id",
    "dry_run",
    "runtime_execution",
    "n8n_started",
    "n8n_stopped",
    "daily_report_workflow_found",
    "dify_runtime_called",
    "fallback_used",
    "fallback_reason",
    "local_only_artifacts",
    "secret_scan_summary",
    "readiness_gaps",
    "ai_dev_048_required_setup",
    "safety_flags",
]

REQUIRED_TRUE_FLAGS = [
    "dry_run",
    "no_notification",
    "no_production_db_write",
    "no_cron_or_timer_change",
    "no_trading",
    "no_main_py",
    "no_secret_values",
]

REQUIRED_GAPS = [
    "daily-report n8n workflow needs creation or safe import",
    "Dify daily-report app/input contract needs runtime mapping",
    "credential use requires explicit approval",
]

DOC_REQUIRED_PHRASES = [
    "n8n was started",
    "n8n was stopped",
    "Dify runtime was not called",
    "AI-DEV-048",
    "fallback/readiness mode",
    "no notification",
    "no production DB write",
    "no trading",
    "no `python3 main.py`",
]

SECRET_VALUE_PATTERNS = [
    re.compile(r"Bearer\s+[A-Za-z0-9._~+\/-]{12,}", re.IGNORECASE),
    re.compile(r"Authorization\s*[:=]\s*(?!0\b|\[REDACTED\]|placeholder)[A-Za-z0-9._~+\/-]{8,}", re.IGNORECASE),
    re.compile(r"api[_-]?key\s*[:=]\s*(?!0\b|placeholder|redacted)[A-Za-z0-9._~+\/-]{8,}", re.IGNORECASE),
    re.compile(r"token\s*[:=]\s*(?!0\b|placeholder|redacted)[A-Za-z0-9._~+\/-]{8,}", re.IGNORECASE),
    re.compile(r"password\s*[:=]\s*(?!0\b|placeholder|redacted)[A-Za-z0-9._~+\/-]{8,}", re.IGNORECASE),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{20,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
]

FORBIDDEN_PHRASES = [
    "LINE send node",
    "Email send node",
    "production write instruction",
    "order execution instruction",
]


def load_json(path: Path) -> tuple[Any | None, str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except Exception as exc:
        return None, str(exc)


def has_secret_value(text: str) -> bool:
    return any(pattern.search(text) for pattern in SECRET_VALUE_PATTERNS)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate AI-DEV-047 runtime readiness package.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    errors: list[str] = []
    warnings: list[str] = []

    required_files = [DOC_PATH, INTEGRATION_DOC_PATH, ROADMAP_PATH, TEMPLATE_PATH]
    file_checks = {str(path): (repo_root / path).is_file() for path in required_files}
    for path, exists in file_checks.items():
        if not exists:
            errors.append(f"required file missing: {path}")

    template: dict[str, Any] = {}
    if file_checks.get(str(TEMPLATE_PATH)):
        data, error = load_json(repo_root / TEMPLATE_PATH)
        if error:
            errors.append(f"JSON parse failed for {TEMPLATE_PATH}: {error}")
        elif not isinstance(data, dict):
            errors.append("readiness result template root must be an object")
        else:
            template = data
            serialized = json.dumps(data, ensure_ascii=False, sort_keys=True)
            if has_secret_value(serialized):
                errors.append("secret-like value found in readiness template")

    for key in REQUIRED_KEYS:
        if key not in template:
            errors.append(f"readiness template missing key: {key}")

    expected_values = {
        "n8n_started": True,
        "n8n_stopped": True,
        "daily_report_workflow_found": False,
        "dify_runtime_called": False,
        "fallback_used": True,
    }
    for key, expected in expected_values.items():
        if template.get(key) is not expected:
            errors.append(f"{key} must be {expected}")

    safety_flags = template.get("safety_flags", {})
    if not isinstance(safety_flags, dict):
        errors.append("safety_flags must be an object")
        safety_flags = {}
    for flag in REQUIRED_TRUE_FLAGS:
        if safety_flags.get(flag) is not True:
            errors.append(f"safety_flags.{flag} must be true")

    gaps = template.get("readiness_gaps", [])
    setup = template.get("ai_dev_048_required_setup", [])
    combined = "\n".join(str(item) for item in [*gaps, *setup])
    for phrase in REQUIRED_GAPS:
        if phrase not in combined:
            errors.append(f"missing AI-DEV-048 readiness gap: {phrase}")

    scan = template.get("secret_scan_summary", {})
    if isinstance(scan, dict):
        if scan.get("secret_values_printed") is not False:
            errors.append("secret_scan_summary.secret_values_printed must be false")
    else:
        errors.append("secret_scan_summary must be an object")

    for rel_path in [DOC_PATH, INTEGRATION_DOC_PATH, ROADMAP_PATH]:
        path = repo_root / rel_path
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        if has_secret_value(text):
            errors.append(f"secret-like value found in {rel_path}")
        if rel_path == DOC_PATH:
            for phrase in DOC_REQUIRED_PHRASES:
                if phrase not in text:
                    errors.append(f"readiness doc missing phrase: {phrase}")
        for phrase in FORBIDDEN_PHRASES:
            if phrase in text:
                errors.append(f"forbidden instruction phrase found in {rel_path}: {phrase}")

    result = {
        "ok": not errors,
        "passed": not errors,
        "doc_path": str(DOC_PATH),
        "template_path": str(TEMPLATE_PATH),
        "file_checks": file_checks,
        "expected_runtime_state": expected_values,
        "safety_flags_checked": REQUIRED_TRUE_FLAGS,
        "readiness_gap_checks": REQUIRED_GAPS,
        "errors": errors,
        "warnings": warnings,
        "side_effects": {
            "files_modified": False,
            "db_modified": False,
            "notification_sent": False,
            "runtime_queue_modified": False,
            "n8n_started": False,
            "dify_called": False,
            "trading_execution_run": False,
        },
    }
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
