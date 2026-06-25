#!/usr/bin/env python3
"""Validate the AI-DEV-035 n8n/Dify runtime activation dry-run pack.

This validator is read-only. It checks repo-contained docs and JSON examples
without calling n8n, Dify, GitHub, production systems, or external services.
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
    "templates/n8n_dify_runtime_activation_checklist.example.json",
    "templates/n8n_dify_e2e_dry_run_payload.example.json",
    "templates/n8n_dify_e2e_dry_run_result.example.json",
    "templates/n8n_codex_relay_dry_run_payload.example.json",
    "templates/n8n_merge_gate_dry_run_report.example.json",
    "templates/n8n_runtime_disable_rollback_checklist.example.json",
    "scripts/orchestrator/validate_n8n_dify_runtime_activation_pack.py",
]

JSON_FILES = [path for path in REQUIRED_FILES if path.endswith(".json")]

FORBIDDEN_ALTERNATIVE_FILES = [
    "docs/n8n_dify_runtime_activation_e2e_dry_run_pack.md",
    "templates/n8n_dify_runtime_activation_e2e_dry_run_plan.example.json",
    "templates/n8n_dify_runtime_activation_e2e_dry_run_input.example.json",
    "templates/n8n_dify_runtime_activation_e2e_dry_run_result.example.json",
    "scripts/orchestrator/validate_n8n_dify_runtime_activation_e2e_dry_run.py",
]

DOC_REQUIRED_KEYWORDS = [
    "Purpose",
    "Scope",
    "Non-Goals",
    "Runtime Activation Model",
    "Required Operator Preconditions",
    "Dry-Run Procedure",
    "Dry-Run Success Criteria",
    "Rollback and Disable Procedure",
    "Safety Boundaries",
    "Human-Gated Actions",
    "Acceptance Criteria",
    "Follow-Up Tasks",
    "trading / order execution",
    "secrets / `.env` / credentials",
    "production DB writes",
    "production-approved runner",
    "formal LINE / Email / notification sending",
    "cron / systemd / timer modification",
    "Dify / n8n credential setup",
    "paid data source integration",
    "public dashboard publishing",
    "trading / order logic",
    "real auto-merge execution",
]

REQUIRED_FIELDS = {
    "templates/n8n_dify_runtime_activation_checklist.example.json": [
        "schema_version",
        "artifact_type",
        "checklist_version",
        "task_id",
        "environment",
        "required_credentials",
        "workflow_nodes",
        "dry_run_steps",
        "rollback_steps",
        "human_gates",
        "prohibited_actions",
    ],
    "templates/n8n_dify_e2e_dry_run_payload.example.json": [
        "schema_version",
        "artifact_type",
        "task_id",
        "source",
        "mode",
        "requested_actions",
        "safety_constraints",
        "expected_outputs",
    ],
    "templates/n8n_dify_e2e_dry_run_result.example.json": [
        "schema_version",
        "artifact_type",
        "task_id",
        "ok",
        "dry_run",
        "dify_request_built",
        "dify_response_received",
        "chatgpt_ready_summary_built",
        "codex_relay_payload_built",
        "merge_gate_report_built",
        "external_side_effects",
        "blocked_actions",
        "operator_next_steps",
    ],
    "templates/n8n_codex_relay_dry_run_payload.example.json": [
        "schema_version",
        "artifact_type",
        "task_id",
        "dry_run",
        "target",
        "task_package_preview",
        "no_execution_guarantee",
        "prohibited_runtime_actions",
    ],
    "templates/n8n_merge_gate_dry_run_report.example.json": [
        "schema_version",
        "artifact_type",
        "task_id",
        "dry_run",
        "pr_number",
        "pr_state",
        "draft",
        "mergeable",
        "head_sha",
        "ci_status",
        "changed_files_summary",
        "prohibited_scope_touched",
        "chatgpt_decision_required",
        "would_merge",
        "actual_merge_executed",
        "blocked_reasons",
    ],
    "templates/n8n_runtime_disable_rollback_checklist.example.json": [
        "schema_version",
        "artifact_type",
        "task_id",
        "disable_workflow_steps",
        "revoke_or_rotate_credentials_steps",
        "remove_webhook_exposure_steps",
        "audit_logs_to_check",
        "restore_previous_state_steps",
        "escalation_conditions",
    ],
}

SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{20,}"),
    re.compile(r"AIza[0-9A-Za-z_-]{20,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]{20,}", re.IGNORECASE),
]

PLACEHOLDER_WORDS = ("PLACEHOLDER", "EXAMPLE", "example", "sandbox_placeholder")


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


def external_side_effects_are_false(data: Any) -> bool:
    if not isinstance(data, dict):
        return False
    side_effects = data.get("external_side_effects")
    if not isinstance(side_effects, dict):
        return False
    return all(value is False for value in side_effects.values())


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate AI-DEV-035 dry-run pack files.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    reasons: list[str] = []
    json_results: dict[str, Any] = {}

    missing_required_files = [
        rel_path for rel_path in REQUIRED_FILES if not (repo_root / rel_path).is_file()
    ]
    for rel_path in missing_required_files:
        reasons.append(f"required file missing: {rel_path}")

    forbidden_existing_files = [
        rel_path for rel_path in FORBIDDEN_ALTERNATIVE_FILES if (repo_root / rel_path).exists()
    ]
    for rel_path in forbidden_existing_files:
        reasons.append(f"forbidden alternative file exists: {rel_path}")

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
    missing_doc_keywords = [keyword for keyword in DOC_REQUIRED_KEYWORDS if keyword not in doc_text]
    for keyword in missing_doc_keywords:
        reasons.append(f"required doc keyword missing: {keyword}")

    missing_required_fields: dict[str, list[str]] = {}
    for rel_path, fields in REQUIRED_FIELDS.items():
        missing = missing_fields(json_results.get(rel_path), fields)
        if missing:
            missing_required_fields[rel_path] = missing
            for field in missing:
                reasons.append(f"required payload field missing in {rel_path}: {field}")

    secret_like_values = detect_secret_like_values(json_results)
    reasons.extend(secret_like_values)

    payload = json_results.get("templates/n8n_dify_e2e_dry_run_payload.example.json")
    payload_mode_dry_run = isinstance(payload, dict) and payload.get("mode") == "dry_run"
    if not payload_mode_dry_run:
        reasons.append("dry-run payload mode must be dry_run")

    result_payload = json_results.get("templates/n8n_dify_e2e_dry_run_result.example.json")
    result_dry_run_true = isinstance(result_payload, dict) and result_payload.get("dry_run") is True
    if not result_dry_run_true:
        reasons.append("dry-run result must include dry_run true")
    result_side_effects_false = external_side_effects_are_false(result_payload)
    if not result_side_effects_false:
        reasons.append("dry-run result external_side_effects must all be false")

    relay_payload = json_results.get("templates/n8n_codex_relay_dry_run_payload.example.json")
    relay_dry_run_true = isinstance(relay_payload, dict) and relay_payload.get("dry_run") is True
    if not relay_dry_run_true:
        reasons.append("Codex relay dry-run payload must include dry_run true")

    merge_report = json_results.get("templates/n8n_merge_gate_dry_run_report.example.json")
    merge_report_dry_run_true = isinstance(merge_report, dict) and merge_report.get("dry_run") is True
    actual_merge_executed_false = (
        isinstance(merge_report, dict) and merge_report.get("actual_merge_executed") is False
    )
    would_merge_false = isinstance(merge_report, dict) and merge_report.get("would_merge") is False
    auto_merge_blocked = merge_report_dry_run_true and actual_merge_executed_false and would_merge_false
    if not merge_report_dry_run_true:
        reasons.append("merge gate dry-run report must include dry_run true")
    if not actual_merge_executed_false:
        reasons.append("merge gate dry-run report must include actual_merge_executed false")
    if not would_merge_false:
        reasons.append("merge gate dry-run report must include would_merge false")

    result = {
        "ok": True,
        "passed": not reasons,
        "repo_root": str(repo_root),
        "required_files": REQUIRED_FILES,
        "missing_required_files": missing_required_files,
        "forbidden_alternative_files": FORBIDDEN_ALTERNATIVE_FILES,
        "forbidden_existing_files": forbidden_existing_files,
        "json_files": JSON_FILES,
        "json_valid": not any(reason.startswith("invalid JSON") for reason in reasons),
        "missing_doc_keywords": missing_doc_keywords,
        "missing_required_fields": missing_required_fields,
        "secret_like_values_found": secret_like_values,
        "payload_mode_dry_run": payload_mode_dry_run,
        "dry_run_result_dry_run_true": result_dry_run_true,
        "dry_run_result_external_side_effects_false": result_side_effects_false,
        "relay_payload_dry_run_true": relay_dry_run_true,
        "merge_report_dry_run_true": merge_report_dry_run_true,
        "actual_merge_executed_false": actual_merge_executed_false,
        "would_merge_false": would_merge_false,
        "auto_merge_blocked": auto_merge_blocked,
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
            "real_auto_merge_executed": False,
            "ai_dev_036_run": False,
        },
    }
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    return 0 if result["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
