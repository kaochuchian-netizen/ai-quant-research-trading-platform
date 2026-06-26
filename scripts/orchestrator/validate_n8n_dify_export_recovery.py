#!/usr/bin/env python3
"""Validate the AI-DEV-039 n8n/Dify export recovery package.

This validator is read-only for repo files and tests the sanitizer only with
synthetic temp files. It never reads raw n8n exports, secrets, runtime queues,
n8n runtime, or Dify runtime.
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
    "docs/n8n_dify_dry_run_export_recovery.md",
    "templates/n8n_dify_manual_dry_run_workflow.sanitized.example.json",
    "templates/dify_ai_dev_task_draft_dry_run_reconstruction.example.json",
    "scripts/orchestrator/sanitize_n8n_workflow_export.py",
    "scripts/orchestrator/validate_n8n_dify_export_recovery.py",
]

JSON_FILES = [
    "templates/n8n_dify_manual_dry_run_workflow.sanitized.example.json",
    "templates/dify_ai_dev_task_draft_dry_run_reconstruction.example.json",
]

SAFETY_MARKERS = [
    "dry_run",
    "no_auto_merge",
    "no_notification",
    "no_trading",
    "no_secrets",
]

REQUIRED_DOC_KEYWORDS = [
    "Purpose",
    "Scope",
    "Non-Goals",
    "Recovery Model",
    "Sanitizer Behavior",
    "Validator Behavior",
    "Safety Boundaries",
    "Human-Gated Actions",
    "Acceptance Criteria",
    "DIFY_API_KEY_STORED_IN_N8N_ONLY",
    "DO_NOT_COMMIT_REAL_SECRET",
]

REQUIRED_FIELDS = {
    "templates/dify_ai_dev_task_draft_dry_run_reconstruction.example.json": [
        "schema_version",
        "artifact_type",
        "task_id",
        "source",
        "mode",
        "dify_runtime_called_by_this_repo_task",
        "raw_export_included",
        "placeholders",
        "draft_outputs",
        "safety_markers",
        "runtime_side_effects",
        "operator_notes",
        "blocked_actions",
    ],
}

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
    parser = argparse.ArgumentParser(description="Validate AI-DEV-039 export recovery files.")
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


def missing_fields(data: Any, fields: list[str]) -> list[str]:
    if not isinstance(data, dict):
        return fields
    return [field for field in fields if field not in data]


def contains_manual_trigger(workflow: Any) -> bool:
    if not isinstance(workflow, dict):
        return False
    nodes = workflow.get("nodes")
    if not isinstance(nodes, list):
        return False
    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_type = str(node.get("type", "")).lower()
        node_name = str(node.get("name", "")).lower()
        if "manualtrigger" in node_type or "manual trigger" in node_name:
            return True
    return False


def detect_secret_patterns(json_results: dict[str, Any]) -> list[str]:
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


def safety_markers_present(text: str, json_results: dict[str, Any]) -> dict[str, bool]:
    combined = text + "\n" + "\n".join(
        json.dumps(value, sort_keys=True) for value in json_results.values()
    )
    return {marker: marker in combined for marker in SAFETY_MARKERS}


def run_sanitizer_synthetic_test(repo_root: Path) -> dict[str, Any]:
    sanitizer = repo_root / "scripts/orchestrator/sanitize_n8n_workflow_export.py"
    with tempfile.TemporaryDirectory(prefix="stock-ai-n8n-sanitize-test-") as temp_dir:
        temp_path = Path(temp_dir)
        input_path = temp_path / "synthetic_raw_workflow.json"
        output_path = temp_path / "sanitized_workflow.json"
        synthetic = {
            "name": "Synthetic n8n Workflow",
            "nodes": [
                {
                    "name": "Manual Trigger",
                    "type": "n8n-nodes-base.manualTrigger",
                    "parameters": {},
                },
                {
                    "name": "HTTP Request",
                    "type": "n8n-nodes-base.httpRequest",
                    "parameters": {
                        "headers": {
                            "Authorization": "Bearer synthetic-secret-value-123456",
                            "api_key": "synthetic-api-key-123456",
                        },
                        "body": {
                            "token": "synthetic-token-123456",
                            "safe_mode": "dry_run",
                        },
                    },
                    "credentials": {
                        "httpHeaderAuth": {
                            "id": "synthetic-credential-id",
                            "name": "Synthetic Credential",
                        }
                    },
                },
            ],
        }
        input_path.write_text(json.dumps(synthetic), encoding="utf-8")
        command = [
            sys.executable,
            str(sanitizer),
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ]
        completed = subprocess.run(
            command,
            check=False,
            cwd=repo_root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        summary = json.loads(completed.stdout) if completed.stdout.strip() else {}
        sanitized_data = json.loads(output_path.read_text(encoding="utf-8")) if output_path.exists() else {}
        sanitized_text = json.dumps(sanitized_data, sort_keys=True)
        leaked = any(
            secret in completed.stdout or secret in completed.stderr or secret in sanitized_text
            for secret in [
                "synthetic-secret-value-123456",
                "synthetic-api-key-123456",
                "synthetic-token-123456",
                "synthetic-credential-id",
            ]
        )
        return {
            "ok": completed.returncode == 0 and summary.get("ok") is True and not leaked,
            "returncode": completed.returncode,
            "redaction_count": summary.get("redaction_count"),
            "output_written": output_path.exists(),
            "secret_values_leaked": leaked,
            "temp_file_only": True,
            "errors": summary.get("errors", []),
            "stderr_present": bool(completed.stderr.strip()),
        }


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    reasons: list[str] = []
    json_results: dict[str, Any] = {}

    missing_required_files = [
        rel_path for rel_path in REQUIRED_FILES if not (repo_root / rel_path).is_file()
    ]
    for rel_path in missing_required_files:
        reasons.append(f"required file missing: {rel_path}")

    for rel_path in JSON_FILES:
        path = repo_root / rel_path
        if not path.is_file():
            continue
        data, error = load_json(path)
        json_results[rel_path] = data
        if error:
            reasons.append(f"invalid JSON in {rel_path}: {error}")

    doc_path = repo_root / "docs/n8n_dify_dry_run_export_recovery.md"
    doc_text = doc_path.read_text(encoding="utf-8") if doc_path.is_file() else ""
    for keyword in REQUIRED_DOC_KEYWORDS:
        if keyword not in doc_text:
            reasons.append(f"required doc keyword missing: {keyword}")

    workflow = json_results.get("templates/n8n_dify_manual_dry_run_workflow.sanitized.example.json")
    if not contains_manual_trigger(workflow):
        reasons.append("sanitized workflow example must include Manual Trigger concept")

    for rel_path, fields in REQUIRED_FIELDS.items():
        missing = missing_fields(json_results.get(rel_path), fields)
        for field in missing:
            reasons.append(f"required payload field missing in {rel_path}: {field}")

    marker_results = safety_markers_present(doc_text, json_results)
    for marker, present in marker_results.items():
        if not present:
            reasons.append(f"required safety marker missing: {marker}")

    secret_pattern_reasons = detect_secret_patterns(json_results)
    reasons.extend(secret_pattern_reasons)

    sanitizer_test = run_sanitizer_synthetic_test(repo_root)
    if not sanitizer_test["ok"]:
        reasons.append("synthetic sanitizer test failed")

    result = {
        "ok": not reasons,
        "checked_files": REQUIRED_FILES,
        "json_files_valid": sorted(json_results),
        "safety_markers": marker_results,
        "secret_pattern_findings": secret_pattern_reasons,
        "sanitizer_synthetic_test": sanitizer_test,
        "runtime_side_effects": {
            "n8n_started": False,
            "dify_called_or_logged_in": False,
            "raw_export_read": False,
            "secrets_printed": False,
            "runtime_queue_modified": False,
            "notification_sent": False,
            "codex_real_task_sent": False,
            "auto_merge_executed": False,
            "ai_dev_040_run": False,
        },
        "errors": reasons,
    }
    print(json.dumps(result, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
