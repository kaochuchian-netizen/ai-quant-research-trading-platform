#!/usr/bin/env python3
"""Validate the AI-DEV-034 n8n/Dify manual trigger workflow pack.

The validator is read-only. It checks repo-contained docs and JSON examples
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
    "docs/n8n_dify_manual_trigger_workflow_pack.md",
    "templates/n8n_dify_manual_trigger_workflow.example.json",
    "templates/n8n_chatgpt_approved_payload.example.json",
    "templates/n8n_dify_manual_trigger_request.example.json",
    "templates/n8n_dify_manual_trigger_response.example.json",
    "templates/n8n_chatgpt_ready_task_draft_summary.example.json",
    "scripts/orchestrator/validate_n8n_dify_workflow_pack.py",
]

JSON_FILES = [path for path in REQUIRED_FILES if path.endswith(".json")]

DOC_REQUIRED_KEYWORDS = [
    "Purpose",
    "Scope",
    "Non-Goals",
    "Workflow Overview",
    "n8n Manual Trigger Design",
    "ChatGPT-Approved Payload Input",
    "n8n to Dify Request Mapping",
    "Dify Response Mapping",
    "ChatGPT-Ready Summary Output",
    "Credential Requirements",
    "Runtime Activation Runbook",
    "Dry-Run Procedure",
    "Rollback / Disable Procedure",
    "Safety Boundaries",
    "Human-Gated Actions",
    "Acceptance Criteria",
    "Follow-Up Tasks for AI-DEV-035",
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
    "templates/n8n_chatgpt_approved_payload.example.json": [
        "schema_version",
        "artifact_type",
        "task_id",
        "approved_by",
        "approval_status",
        "requested_flow",
        "repository",
        "branch",
        "base_branch",
        "scope",
        "files_in_scope",
        "validation_commands",
        "safety_boundary",
        "human_gates",
    ],
    "templates/n8n_dify_manual_trigger_request.example.json": [
        "schema_version",
        "artifact_type",
        "request_id",
        "source_system",
        "target_system",
        "task_id",
        "workflow",
        "inputs",
        "response_mode",
        "user",
    ],
    "templates/n8n_dify_manual_trigger_response.example.json": [
        "schema_version",
        "artifact_type",
        "request_id",
        "task_id",
        "source_system",
        "target_system",
        "status",
        "outputs",
        "metadata",
    ],
    "templates/n8n_chatgpt_ready_task_draft_summary.example.json": [
        "schema_version",
        "artifact_type",
        "summary_id",
        "task_id",
        "generated_by",
        "source_response",
        "draft_status",
        "draft_type",
        "draft_markdown",
        "missing_inputs",
        "safety_flags",
        "recommended_chatgpt_action",
        "blockers",
    ],
}

SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{20,}"),
    re.compile(r"AIza[0-9A-Za-z_-]{20,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]{20,}", re.IGNORECASE),
]

PLACEHOLDER_WORDS = ("PLACEHOLDER", "EXAMPLE", "example", "Placeholder")


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


def credential_references_are_placeholders(workflow: Any) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if not isinstance(workflow, dict):
        return False, ["workflow example is not an object"]

    for node in workflow.get("nodes", []):
        if not isinstance(node, dict):
            continue
        credentials = node.get("credentials")
        if credentials is None:
            continue
        if not isinstance(credentials, dict):
            reasons.append(f"node {node.get('name')} credentials must be an object")
            continue
        for credential_type, credential_ref in credentials.items():
            if not isinstance(credential_ref, dict):
                reasons.append(f"credential {credential_type} must use placeholder object reference")
                continue
            combined = " ".join(str(value) for value in credential_ref.values())
            if not any(word in combined for word in PLACEHOLDER_WORDS):
                reasons.append(f"credential {credential_type} does not look like a placeholder")
    return not reasons, reasons


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


def has_fields(data: Any, fields: list[str]) -> list[str]:
    if not isinstance(data, dict):
        return fields
    return [field for field in fields if field not in data]


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate AI-DEV-034 workflow pack files.")
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

    doc_path = repo_root / "docs/n8n_dify_manual_trigger_workflow_pack.md"
    doc_text = doc_path.read_text(encoding="utf-8") if doc_path.is_file() else ""
    missing_keywords = [keyword for keyword in DOC_REQUIRED_KEYWORDS if keyword not in doc_text]
    for keyword in missing_keywords:
        reasons.append(f"required doc keyword missing: {keyword}")

    workflow_rel = "templates/n8n_dify_manual_trigger_workflow.example.json"
    workflow = json_results.get(workflow_rel)
    manual_trigger_present = contains_manual_trigger(workflow)
    if not manual_trigger_present:
        reasons.append("workflow example must include manual trigger concept")

    placeholder_credentials_ok, credential_reasons = credential_references_are_placeholders(workflow)
    reasons.extend(credential_reasons)

    secret_reasons = detect_secret_like_values(json_results)
    reasons.extend(secret_reasons)

    missing_required_fields: dict[str, list[str]] = {}
    for rel_path, fields in REQUIRED_FIELDS.items():
        missing = has_fields(json_results.get(rel_path), fields)
        if missing:
            missing_required_fields[rel_path] = missing
            for field in missing:
                reasons.append(f"required payload field missing in {rel_path}: {field}")

    result = {
        "ok": True,
        "passed": not reasons,
        "repo_root": str(repo_root),
        "required_files": REQUIRED_FILES,
        "missing_files": missing_files,
        "json_files": JSON_FILES,
        "json_valid": not any(
            reason.startswith("invalid JSON") for reason in reasons
        ),
        "workflow_manual_trigger_present": manual_trigger_present,
        "workflow_placeholder_credentials_ok": placeholder_credentials_ok,
        "missing_doc_keywords": missing_keywords,
        "missing_required_fields": missing_required_fields,
        "secret_like_values_found": secret_reasons,
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
        },
    }
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    return 0 if result["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
