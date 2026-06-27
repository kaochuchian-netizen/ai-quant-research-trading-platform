#!/usr/bin/env python3
"""Validate a GCP runtime relay request.

This validator is read-only. It never contacts GCP, n8n, Dify, OpenAI, LINE, or
other external services and never performs runtime actions.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REQUIRED_FIELDS = [
    "schema_version",
    "relay_request_id",
    "ai_dev_id",
    "created_at",
    "created_by",
    "source",
    "trigger",
    "validation",
    "execution_mode",
    "action",
    "allowed_actions",
    "forbidden_actions",
    "payload_schema",
    "result_output",
    "retry_policy",
    "idempotency",
    "redaction_policy",
    "audit",
    "closeout",
    "safety_gates",
]

REQUIRED_FORBIDDEN_ACTIONS = {
    "order_execution",
    "trade_execution",
    "line_email_delivery",
    "external_notification_delivery",
    "production_db_mutation",
    "scheduler_or_infra_mutation",
    "production_n8n_mutation",
    "dify_runtime_call",
    "openai_chatgpt_api_call",
    "credential_disclosure",
    "direct_codex_app_connection",
    "raw_runtime_output_commit",
}

DRY_RUN_ALLOWED_ACTIONS = {
    "validate_relay_request",
    "prepare_runtime_plan",
    "write_sanitized_result",
}

REQUIRED_IDEMPOTENCY_FIELDS = [
    "relay_request_id",
    "ai_dev_id",
    "source.merge_commit",
    "action.name",
]

SECRET_VALUE_PATTERNS = [
    re.compile(r"ghp_[A-Za-z0-9_]+"),
    re.compile(r"github_pat_[A-Za-z0-9_]+"),
    re.compile(r"sk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]+"),
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?i)(api[_-]?key|access[_-]?token|password)\s*[:=]\s*[^\s,}\"']+"),
]

REQUEST_ID_RE = re.compile(r"^gcp-runtime-relay-[a-z0-9-]+$")
AI_DEV_RE = re.compile(r"^AI-DEV-\d{3}$")
COMMIT_RE = re.compile(r"^[a-f0-9]{40}$")


def load_json(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, [f"failed to parse JSON request: {exc}"]
    if not isinstance(data, dict):
        return None, ["request root must be a JSON object"]
    return data, []


def flatten_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def require_object(data: dict[str, Any], field: str, errors: list[str]) -> dict[str, Any]:
    value = data.get(field)
    if not isinstance(value, dict):
        errors.append(f"{field} must be an object")
        return {}
    return value


def validate_request(data: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    for field in REQUIRED_FIELDS:
        if field not in data:
            errors.append(f"missing required field: {field}")

    relay_request_id = str(data.get("relay_request_id", ""))
    ai_dev_id = str(data.get("ai_dev_id", ""))
    if not REQUEST_ID_RE.match(relay_request_id):
        errors.append("relay_request_id must match gcp-runtime-relay-<lowercase-token>")
    if not AI_DEV_RE.match(ai_dev_id):
        errors.append("ai_dev_id must match AI-DEV-###")

    source = require_object(data, "source", errors)
    merge_commit = str(source.get("merge_commit", ""))
    if merge_commit and not COMMIT_RE.match(merge_commit):
        errors.append("source.merge_commit must be a 40-character lowercase git SHA")
    if source.get("pickup_location") != "merged_repo_default_branch":
        errors.append("source.pickup_location must be merged_repo_default_branch")

    trigger = require_object(data, "trigger", errors)
    if trigger.get("source") != "gcp_resident_pickup_loop":
        errors.append("trigger.source must be gcp_resident_pickup_loop")
    if trigger.get("external_trigger_allowed") is not False:
        errors.append("trigger.external_trigger_allowed must be false")
    if trigger.get("requires_merged_request") is not True:
        errors.append("trigger.requires_merged_request must be true")

    validation = require_object(data, "validation", errors)
    if validation.get("must_pass_before_runtime_boundary") is not True:
        errors.append("validation.must_pass_before_runtime_boundary must be true")
    if validation.get("fail_closed_on_error") is not True:
        errors.append("validation.fail_closed_on_error must be true")
    if validation.get("n8n_is_first_validation_point") is not False:
        errors.append("validation.n8n_is_first_validation_point must be false")

    execution_mode = require_object(data, "execution_mode", errors)
    if execution_mode.get("mode") != "dry_run":
        errors.append("execution_mode.mode must be dry_run for repo-side relay contract")
    if execution_mode.get("runtime_execution_allowed") is not False:
        errors.append("execution_mode.runtime_execution_allowed must be false")
    if execution_mode.get("separate_runtime_approval_required") is not True:
        errors.append("execution_mode.separate_runtime_approval_required must be true")

    action = require_object(data, "action", errors)
    action_name = str(action.get("name", ""))
    allowed_actions = [str(item) for item in as_list(data.get("allowed_actions"))]
    if action_name not in allowed_actions:
        errors.append("action.name must be present in allowed_actions")
    disallowed_dry_run_actions = sorted(set(allowed_actions) - DRY_RUN_ALLOWED_ACTIONS)
    for item in disallowed_dry_run_actions:
        errors.append(f"allowed action is not approved for dry-run relay contract: {item}")

    forbidden_actions = {str(item) for item in as_list(data.get("forbidden_actions"))}
    for action_id in sorted(REQUIRED_FORBIDDEN_ACTIONS - forbidden_actions):
        errors.append(f"missing required forbidden action: {action_id}")

    payload_schema = require_object(data, "payload_schema", errors)
    if payload_schema.get("sensitive_values_allowed") is not False:
        errors.append("payload_schema.sensitive_values_allowed must be false")
    if payload_schema.get("raw_runtime_outputs_allowed") is not False:
        errors.append("payload_schema.raw_runtime_outputs_allowed must be false")

    result_output = require_object(data, "result_output", errors)
    if result_output.get("sanitized_result_required") is not True:
        errors.append("result_output.sanitized_result_required must be true")
    if result_output.get("raw_output_repo_allowed") is not False:
        errors.append("result_output.raw_output_repo_allowed must be false")
    if result_output.get("blocked_result_allowed") is not True:
        errors.append("result_output.blocked_result_allowed must be true")

    retry_policy = require_object(data, "retry_policy", errors)
    max_attempts = retry_policy.get("max_attempts")
    if not isinstance(max_attempts, int) or not 1 <= max_attempts <= 5:
        errors.append("retry_policy.max_attempts must be an integer between 1 and 5")
    do_not_retry_on = {str(item) for item in as_list(retry_policy.get("do_not_retry_on"))}
    for item in ["validation_error", "safety_gate_hit", "forbidden_action", "duplicate_terminal_result"]:
        if item not in do_not_retry_on:
            errors.append(f"retry_policy.do_not_retry_on must include {item}")

    idempotency = require_object(data, "idempotency", errors)
    if idempotency.get("required") is not True:
        errors.append("idempotency.required must be true")
    key_fields = [str(item) for item in as_list(idempotency.get("key_fields"))]
    if key_fields != REQUIRED_IDEMPOTENCY_FIELDS:
        errors.append("idempotency.key_fields must match the required relay idempotency key order")
    if idempotency.get("on_duplicate_terminal_result") != "skip_without_runtime_execution":
        errors.append("idempotency.on_duplicate_terminal_result must be skip_without_runtime_execution")

    redaction_policy = require_object(data, "redaction_policy", errors)
    if redaction_policy.get("sensitive_values_allowed") is not False:
        errors.append("redaction_policy.sensitive_values_allowed must be false")
    if redaction_policy.get("store_raw_headers_or_credentials") is not False:
        errors.append("redaction_policy.store_raw_headers_or_credentials must be false")

    audit = require_object(data, "audit", errors)
    if audit.get("required") is not True:
        errors.append("audit.required must be true")
    if audit.get("raw_runtime_output_in_audit_allowed") is not False:
        errors.append("audit.raw_runtime_output_in_audit_allowed must be false")

    closeout = require_object(data, "closeout", errors)
    for key in ["result_validation_required", "safety_confirmation_required", "repo_pr_for_sanitized_result_required"]:
        if closeout.get(key) is not True:
            errors.append(f"closeout.{key} must be true")

    safety_gates = require_object(data, "safety_gates", errors)
    for key in [
        "no_order_execution",
        "no_secret_values",
        "no_external_delivery",
        "no_production_db_mutation",
        "no_infra_mutation",
        "no_dify_runtime_call",
        "no_openai_chatgpt_api_call",
        "no_codex_app_direct_connection",
        "dry_run_default",
    ]:
        if safety_gates.get(key) is not True:
            errors.append(f"safety_gates.{key} must be true")

    text = flatten_text(data)
    value_hit_patterns = [pattern.pattern for pattern in SECRET_VALUE_PATTERNS if pattern.search(text)]
    if value_hit_patterns:
        errors.append("request appears to include sensitive values")

    return {
        "ok": not errors,
        "relay_request_id": relay_request_id or None,
        "ai_dev_id": ai_dev_id or None,
        "errors": errors,
        "warnings": warnings,
        "values_included_or_printed": bool(value_hit_patterns),
        "value_hit_patterns": value_hit_patterns,
        "side_effects": {
            "runtime_action_performed": False,
            "n8n_called": False,
            "dify_called": False,
            "openai_chatgpt_api_called": False,
            "notification_sent": False,
            "production_db_modified": False,
            "trading_or_order_execution": False,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a GCP runtime relay request JSON file.")
    parser.add_argument("--input", default="templates/gcp_runtime_relay_request.example.json")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    data, load_errors = load_json(Path(args.input))
    if data is None:
        result = {
            "ok": False,
            "relay_request_id": None,
            "ai_dev_id": None,
            "errors": load_errors,
            "warnings": [],
            "values_included_or_printed": False,
        }
    else:
        result = validate_request(data)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
