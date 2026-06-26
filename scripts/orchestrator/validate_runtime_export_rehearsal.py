#!/usr/bin/env python3
"""Validate the AI-DEV-041 runtime export dry-run rehearsal package.

The validator uses only the repo synthetic fixture and temporary sanitizer
output. It does not start n8n, call Dify, read runtime exports, read secrets,
modify runtime queues, send notifications, trade, merge, or run production
entrypoints.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


REQUIRED_FILES = [
    "docs/n8n_dify_runtime_export_dry_run_rehearsal.md",
    "templates/n8n_runtime_export_rehearsal_request.example.json",
    "templates/n8n_runtime_export_rehearsal_result.example.json",
    "templates/n8n_runtime_export_synthetic_raw_workflow.fixture.json",
    "scripts/orchestrator/validate_runtime_export_rehearsal.py",
]

JSON_FILES = [
    "templates/n8n_runtime_export_rehearsal_request.example.json",
    "templates/n8n_runtime_export_rehearsal_result.example.json",
    "templates/n8n_runtime_export_synthetic_raw_workflow.fixture.json",
]

REQUIRED_GATES = [
    "dry_run",
    "raw_export_is_synthetic",
    "no_runtime_access",
    "no_secrets",
    "no_publish",
    "no_active_workflow",
    "no_notification",
    "no_auto_merge",
    "no_trading",
]

DOC_KEYWORDS = [
    "approval request",
    "synthetic raw export placeholder",
    "sanitize",
    "validator",
    "supervised result",
    "cleanup checklist",
    "closeout report",
    "synthetic fixture only",
    "AI-DEV-042",
]

REAL_SECRET_PATTERNS = [
    re.compile(r"Bearer\s+(?!FAKE_DO_NOT_USE)[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE),
    re.compile(r"sk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{16,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{16,}"),
    re.compile(r"AIza[0-9A-Za-z_-]{16,}"),
]

SANITIZED_BEARER_PATTERN = re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate AI-DEV-041 rehearsal package.")
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
        return REQUIRED_GATES
    gates = data.get("gates")
    if not isinstance(gates, dict):
        gates = data.get("meta")
    if not isinstance(gates, dict):
        return REQUIRED_GATES
    return [gate for gate in REQUIRED_GATES if gate not in gates]


def gates_true(data: Any) -> bool:
    if not isinstance(data, dict):
        return False
    gates = data.get("gates")
    if not isinstance(gates, dict):
        gates = data.get("meta")
    if not isinstance(gates, dict):
        return False
    return all(gates.get(gate) is True for gate in REQUIRED_GATES)


def detect_real_secret_patterns(data: Any) -> list[str]:
    reasons: list[str] = []
    for text in iter_strings(data):
        for pattern in REAL_SECRET_PATTERNS:
            if pattern.search(text):
                reasons.append("real secret-like pattern found")
                break
    return reasons


def run_sanitizer_on_fixture(repo_root: Path, fixture_path: Path) -> dict[str, Any]:
    sanitizer = repo_root / "scripts/orchestrator/sanitize_n8n_workflow_export.py"
    with tempfile.TemporaryDirectory(prefix="stock-ai-runtime-export-rehearsal-") as temp_dir:
        output_path = Path(temp_dir) / "sanitized_fixture.json"
        completed = subprocess.run(
            [
                sys.executable,
                str(sanitizer),
                "--input",
                str(fixture_path),
                "--output",
                str(output_path),
            ],
            cwd=repo_root,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        summary = json.loads(completed.stdout) if completed.stdout.strip() else {}
        sanitized_text = output_path.read_text(encoding="utf-8") if output_path.exists() else ""
        return {
            "ok": (
                completed.returncode == 0
                and summary.get("ok") is True
                and int(summary.get("redaction_count") or 0) > 0
                and SANITIZED_BEARER_PATTERN.search(sanitized_text) is None
            ),
            "returncode": completed.returncode,
            "redaction_count": summary.get("redaction_count"),
            "output_written": output_path.exists(),
            "sanitized_output_contains_bearer": SANITIZED_BEARER_PATTERN.search(sanitized_text) is not None,
            "temp_output_only": True,
            "errors": summary.get("errors", []),
            "stderr_present": bool(completed.stderr.strip()),
        }


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

    doc_path = repo_root / "docs/n8n_dify_runtime_export_dry_run_rehearsal.md"
    doc_text = doc_path.read_text(encoding="utf-8") if doc_path.is_file() else ""
    for keyword in DOC_KEYWORDS:
        if keyword not in doc_text:
            reasons.append(f"required doc keyword missing: {keyword}")

    gate_results: dict[str, Any] = {}
    for rel_path, data in json_results.items():
        missing = missing_gates(data)
        gate_results[rel_path] = {
            "missing": missing,
            "all_required_true": gates_true(data),
        }
        if missing:
            for gate in missing:
                reasons.append(f"required gate missing in {rel_path}: {gate}")
        if not gates_true(data):
            reasons.append(f"required gates must be true in {rel_path}")

    fixture_rel = "templates/n8n_runtime_export_synthetic_raw_workflow.fixture.json"
    fixture = json_results.get(fixture_rel)
    fixture_only_fake_secret = (
        isinstance(fixture, dict)
        and fixture.get("synthetic_fixture") is True
        and fixture.get("contains_real_secret") is False
    )
    if not fixture_only_fake_secret:
        reasons.append("fixture must be marked synthetic and contain no real secret")

    fixture_secret_findings = detect_real_secret_patterns(fixture)
    if fixture_secret_findings:
        reasons.extend(f"fixture check failed: {finding}" for finding in fixture_secret_findings)

    sanitizer_test = run_sanitizer_on_fixture(repo_root, repo_root / fixture_rel)
    if not sanitizer_test["ok"]:
        reasons.append("sanitizer fixture test failed")

    result = {
        "ok": not reasons,
        "checked_files": REQUIRED_FILES,
        "json_files_valid": sorted(json_results),
        "required_gates": REQUIRED_GATES,
        "gate_results": gate_results,
        "fixture_only_fake_secret": fixture_only_fake_secret,
        "fixture_secret_findings": fixture_secret_findings,
        "sanitizer_fixture_test": sanitizer_test,
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
            "ai_dev_042_run": False,
        },
        "errors": reasons,
    }
    print(json.dumps(result, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
