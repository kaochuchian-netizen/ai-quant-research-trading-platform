#!/usr/bin/env python3
"""Validate the AI-DEV-052 Dify review workflow mapping setup package."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs/dify_review_workflow_mapping_setup.md"
MAPPING = ROOT / "templates/dify_review_workflow_mapping.example.json"
RESULT = ROOT / "templates/ai_dev_052_dify_review_mapping_setup_result.example.json"
RELATED = [
    ROOT / "docs/ai_dev_one_shot_multi_agent_automation.md",
    ROOT / "docs/ai_task_queue_runbook.md",
    ROOT / "docs/ai_dev_051_dify_review_package_runtime_result.md",
]

ALLOWED_MAPPING_KEYS = {
    "workflow_name",
    "workflow_id",
    "node_display_name",
    "contract_version",
    "task_id",
    "template_file",
    "sanitized_placeholder",
}

REQUIRED_MAPPING_KEYS = [
    "contract_version",
    "task_id",
    "template_file",
    "sanitized_placeholder",
    "workflow_name",
    "workflow_id",
    "node_display_name",
    "runtime_safe_lookup_rule",
    "runtime_verification",
    "ai_dev_053_readiness_checklist",
]

REQUIRED_RESULT_KEYS = [
    "task_id",
    "contract_version",
    "setup_result",
    "safe_dify_review_mapping_found",
    "readiness_gap",
    "mapping_contract",
    "runtime_lookup",
    "sanitized_summary",
    "secret_scan_summary",
    "ai_dev_053_readiness_checklist",
    "safety_flags",
]

REQUIRED_DOC_PHRASES = [
    "Credential-Safe Mapping Contract",
    "Runtime-Safe Lookup Rule",
    "Sanitized Summary Template",
    "AI-DEV-053 Readiness Checklist",
    "readiness gap",
    "workflow_name",
    "workflow_id",
    "node_display_name",
    "contract_version",
    "task_id",
    "template_file",
    "sanitized_placeholder",
    "AI-DEV-053 was not executed",
]

SECRET_VALUE_PATTERNS = {
    "github_pat": re.compile(r"github_pat_[A-Za-z0-9_]+"),
    "ghp": re.compile(r"ghp_[A-Za-z0-9_]+"),
    "sk": re.compile(r"sk-[A-Za-z0-9_-]{12,}"),
    "bearer_value": re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE),
    "authorization_assignment": re.compile(
        r"Authorization\s*[:=]\s*(?!placeholder|redacted|none|null)[A-Za-z0-9._~+/=-]{8,}",
        re.IGNORECASE,
    ),
    "api_key_assignment": re.compile(
        r"api[-_]?key\s*[:=]\s*(?!placeholder|redacted|false|true|null)[A-Za-z0-9._~+/=-]{8,}",
        re.IGNORECASE,
    ),
    "token_assignment": re.compile(
        r"token\s*[:=]\s*(?!placeholder|redacted|false|true|null)[A-Za-z0-9._~+/=-]{8,}",
        re.IGNORECASE,
    ),
    "password_assignment": re.compile(
        r"password\s*[:=]\s*(?!placeholder|redacted|false|true|null)[A-Za-z0-9._~+/=-]{8,}",
        re.IGNORECASE,
    ),
    "private_key": re.compile(r"BEGIN (RSA |OPENSSH |EC |DSA )?PRIVATE KEY"),
    "env_assignment": re.compile(r"^[A-Z0-9_]{4,}=.+$", re.MULTILINE),
}

POLICY_TERM_PATTERNS = {
    "authorization": re.compile(r"authorization", re.IGNORECASE),
    "bearer": re.compile(r"bearer", re.IGNORECASE),
    "api_key": re.compile(r"api[_ -]?key", re.IGNORECASE),
    "token": re.compile(r"token", re.IGNORECASE),
    "password": re.compile(r"password", re.IGNORECASE),
    "credential": re.compile(r"credential", re.IGNORECASE),
    ".env": re.compile(r"\.env", re.IGNORECASE),
}


def load_json(path: Path) -> tuple[Any | None, str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except Exception as exc:
        return None, str(exc)


def missing_keys(data: Any, keys: list[str]) -> list[str]:
    if not isinstance(data, dict):
        return keys
    return [key for key in keys if key not in data]


def collect_text(paths: list[Path]) -> str:
    chunks: list[str] = []
    for path in paths:
        if path.exists():
            chunks.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(chunks)


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


def secret_value_hits(text: str) -> dict[str, int]:
    return {name: len(pattern.findall(text)) for name, pattern in SECRET_VALUE_PATTERNS.items()}


def policy_term_counts(text: str) -> dict[str, int]:
    return {name: len(pattern.findall(text)) for name, pattern in POLICY_TERM_PATTERNS.items()}


def validate_mapping(mapping: Any) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    if not isinstance(mapping, dict):
        return {"loaded": False}, ["mapping template root must be object"]

    for key in missing_keys(mapping, REQUIRED_MAPPING_KEYS):
        errors.append(f"mapping template missing key: {key}")

    if mapping.get("task_id") != "AI-DEV-052":
        errors.append("mapping task_id must be AI-DEV-052")
    if mapping.get("sanitized_placeholder") is not True:
        errors.append("mapping sanitized_placeholder must be true")

    allowed = mapping.get("allowed_metadata_fields")
    if not isinstance(allowed, list):
        errors.append("allowed_metadata_fields must be a list")
        allowed_set: set[str] = set()
    else:
        allowed_set = {str(item) for item in allowed}
    missing_allowed = ALLOWED_MAPPING_KEYS - allowed_set
    extra_allowed = allowed_set - ALLOWED_MAPPING_KEYS
    for key in sorted(missing_allowed):
        errors.append(f"allowed metadata field missing: {key}")
    for key in sorted(extra_allowed):
        errors.append(f"unexpected allowed metadata field: {key}")

    lookup_rule = mapping.get("runtime_safe_lookup_rule")
    if not isinstance(lookup_rule, dict):
        errors.append("runtime_safe_lookup_rule must be object")
    else:
        stop_if_requires = lookup_rule.get("stop_if_requires")
        if not isinstance(stop_if_requires, list) or not stop_if_requires:
            errors.append("runtime_safe_lookup_rule.stop_if_requires must be non-empty list")
        for required_stop in [
            "authorization_header_value",
            "bearer_value",
            "api_key_value",
            "token_value",
            "password_value",
            "credential_secret",
            ".env_content",
            "raw_node_credential_payload",
            "raw_node_parameter_payload",
        ]:
            if required_stop not in (stop_if_requires or []):
                errors.append(f"runtime_safe_lookup_rule.stop_if_requires missing {required_stop}")
        if lookup_rule.get("fallback_output") != "readiness_gap_or_blocked_report":
            errors.append("runtime_safe_lookup_rule.fallback_output must be readiness_gap_or_blocked_report")

    runtime = mapping.get("runtime_verification")
    if not isinstance(runtime, dict):
        errors.append("runtime_verification must be object")
    else:
        for key in ["attempted", "n8n_started", "dify_runtime_called", "safe_mapping_found"]:
            if runtime.get(key) is not False:
                errors.append(f"runtime_verification.{key} must be false for AI-DEV-052 setup")

    checklist = mapping.get("ai_dev_053_readiness_checklist")
    if not isinstance(checklist, dict):
        errors.append("ai_dev_053_readiness_checklist must be object")
    else:
        for key in [
            "repo_mapping_contract_validates",
            "safe_metadata_only",
            "sanitized_placeholder",
            "secret_values_absent",
            "raw_node_credential_payload_absent",
            "raw_node_parameter_payload_absent",
            "n8n_shutdown_required_if_started",
            "dify_call_requires_safe_mapping",
            "notifications_blocked",
            "production_mutation_blocked",
            "trading_and_orders_blocked",
            "ai_dev_053_not_executed",
        ]:
            if checklist.get(key) is not True:
                errors.append(f"ai_dev_053_readiness_checklist.{key} must be true")

    return {
        "loaded": True,
        "task_id": mapping.get("task_id"),
        "contract_version": mapping.get("contract_version"),
        "sanitized_placeholder": mapping.get("sanitized_placeholder"),
        "safe_mapping_found": runtime.get("safe_mapping_found") if isinstance(runtime, dict) else None,
    }, errors


def validate_result(result_data: Any) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    if not isinstance(result_data, dict):
        return {"loaded": False}, ["result template root must be object"]

    for key in missing_keys(result_data, REQUIRED_RESULT_KEYS):
        errors.append(f"result template missing key: {key}")
    if result_data.get("task_id") != "AI-DEV-052":
        errors.append("result task_id must be AI-DEV-052")
    if result_data.get("safe_dify_review_mapping_found") is not False:
        errors.append("AI-DEV-052 result must keep safe_dify_review_mapping_found false until runtime verification")

    runtime_lookup = result_data.get("runtime_lookup")
    if not isinstance(runtime_lookup, dict):
        errors.append("runtime_lookup must be object")
    else:
        for key in ["attempted", "n8n_started", "dify_runtime_called", "dify_runtime_call_allowed"]:
            if runtime_lookup.get(key) is not False:
                errors.append(f"runtime_lookup.{key} must be false")

    secret_scan = result_data.get("secret_scan_summary")
    if not isinstance(secret_scan, dict):
        errors.append("secret_scan_summary must be object")
    else:
        if secret_scan.get("secret_values_printed") is not False:
            errors.append("secret_scan_summary.secret_values_printed must be false")
        if secret_scan.get("values_included") is not False:
            errors.append("secret_scan_summary.values_included must be false")
        if secret_scan.get("placeholder_or_policy_context_only") is not True:
            errors.append("secret_scan_summary.placeholder_or_policy_context_only must be true")

    safety_flags = result_data.get("safety_flags")
    if not isinstance(safety_flags, dict):
        errors.append("safety_flags must be object")
    else:
        for key in [
            "no_secret_values",
            "no_raw_node_payloads",
            "no_n8n_start",
            "no_dify_runtime_call",
            "no_notification",
            "no_production_db_write",
            "no_cron_or_timer_change",
            "no_trading",
            "no_order_execution",
            "no_ai_dev_053",
        ]:
            if safety_flags.get(key) is not True:
                errors.append(f"safety_flags.{key} must be true")

    checklist = result_data.get("ai_dev_053_readiness_checklist")
    if not isinstance(checklist, dict):
        errors.append("result ai_dev_053_readiness_checklist must be object")
    else:
        if checklist.get("ai_dev_053_not_executed") is not True:
            errors.append("ai_dev_053_readiness_checklist.ai_dev_053_not_executed must be true")

    return {
        "loaded": True,
        "task_id": result_data.get("task_id"),
        "setup_result": result_data.get("setup_result"),
        "safe_mapping_found": result_data.get("safe_dify_review_mapping_found"),
        "readiness_gap": result_data.get("readiness_gap"),
    }, errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate AI-DEV-052 Dify review mapping setup package.")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    errors: list[str] = []
    warnings: list[str] = []
    required_files = [DOC, MAPPING, RESULT, *RELATED]
    file_checks = {str(path.relative_to(ROOT)): path.exists() for path in required_files}
    for rel_path, exists in file_checks.items():
        if not exists:
            errors.append(f"missing required file: {rel_path}")

    mapping_data: Any = {}
    if MAPPING.exists():
        mapping_data, err = load_json(MAPPING)
        if err:
            errors.append(f"mapping JSON parse failed: {err}")
    result_data: Any = {}
    if RESULT.exists():
        result_data, err = load_json(RESULT)
        if err:
            errors.append(f"result JSON parse failed: {err}")

    mapping_summary, mapping_errors = validate_mapping(mapping_data)
    result_summary, result_errors = validate_result(result_data)
    errors.extend(mapping_errors)
    errors.extend(result_errors)

    doc_text = DOC.read_text(encoding="utf-8", errors="replace") if DOC.exists() else ""
    for phrase in REQUIRED_DOC_PHRASES:
        if phrase not in doc_text:
            errors.append(f"mapping setup doc missing phrase: {phrase}")

    combined_text = collect_text([DOC, MAPPING, RESULT, *RELATED])
    value_hits = secret_value_hits(combined_text)
    for name, count in value_hits.items():
        if count:
            errors.append(f"forbidden secret-like value pattern found: {name} ({count})")
    term_counts = policy_term_counts(combined_text)

    mapping_strings = "\n".join(iter_strings(mapping_data))
    if "raw_node_credential_payload" not in mapping_strings:
        errors.append("mapping policy must explicitly stop on raw_node_credential_payload")
    if "raw_node_parameter_payload" not in mapping_strings:
        errors.append("mapping policy must explicitly stop on raw_node_parameter_payload")

    result = {
        "ok": not errors,
        "passed": not errors,
        "task_id": "AI-DEV-052",
        "file_checks": file_checks,
        "mapping": mapping_summary,
        "setup_result": result_summary,
        "secret_scan_summary": {
            "secret_value_pattern_hits": value_hits,
            "policy_term_counts": term_counts,
            "secret_values_printed": False,
            "placeholder_or_policy_context_only": True,
            "values_included": False,
        },
        "runtime_summary": {
            "n8n_started": False,
            "n8n_stopped": False,
            "dify_runtime_called": False,
            "safe_dify_review_mapping_found": False,
            "ai_dev_053_executed": False,
        },
        "errors": errors,
        "warnings": warnings,
        "side_effects": {
            "files_modified": False,
            "n8n_started": False,
            "dify_called": False,
            "notification_sent": False,
            "runtime_queue_modified": False,
            "production_db_modified": False,
            "trading_execution_run": False,
            "ai_dev_053_run": False,
        },
    }
    json.dump(result, sys.stdout, indent=2 if args.pretty else None, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
