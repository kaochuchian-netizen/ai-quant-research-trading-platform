#!/usr/bin/env python3
"""Validate a sanitized GCP runtime relay result.

This validator is read-only and verifies that a result artifact is safe to
review in git. It never executes runtime work or contacts external services.
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
    "relay_result_id",
    "ai_dev_id",
    "created_at",
    "status",
    "status_reason",
    "execution",
    "validation",
    "action_outcome",
    "artifacts",
    "retry",
    "idempotency",
    "safety",
    "audit",
    "closeout",
    "errors",
]

TERMINAL_STATUSES = {"succeeded", "blocked", "skipped", "failed"}
REQUEST_ID_RE = re.compile(r"^gcp-runtime-relay-[a-z0-9-]+$")
RESULT_ID_RE = re.compile(r"^gcp-runtime-relay-result-[a-z0-9-]+$")
AI_DEV_RE = re.compile(r"^AI-DEV-\d{3}$")

SECRET_VALUE_PATTERNS = [
    re.compile(r"ghp_[A-Za-z0-9_]+"),
    re.compile(r"github_pat_[A-Za-z0-9_]+"),
    re.compile(r"sk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]+"),
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?i)(api[_-]?key|access[_-]?token|password)\s*[:=]\s*[^\s,}\"']+"),
]


def load_json(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, [f"failed to parse JSON result: {exc}"]
    if not isinstance(data, dict):
        return None, ["result root must be a JSON object"]
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


def require_false(obj: dict[str, Any], field: str, label: str, errors: list[str]) -> None:
    if obj.get(field) is not False:
        errors.append(f"{label}.{field} must be false")


def require_true(obj: dict[str, Any], field: str, label: str, errors: list[str]) -> None:
    if obj.get(field) is not True:
        errors.append(f"{label}.{field} must be true")


def validate_result(data: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    for field in REQUIRED_FIELDS:
        if field not in data:
            errors.append(f"missing required field: {field}")

    relay_request_id = str(data.get("relay_request_id", ""))
    relay_result_id = str(data.get("relay_result_id", ""))
    ai_dev_id = str(data.get("ai_dev_id", ""))
    status = str(data.get("status", ""))

    if not REQUEST_ID_RE.match(relay_request_id):
        errors.append("relay_request_id must match gcp-runtime-relay-<lowercase-token>")
    if not RESULT_ID_RE.match(relay_result_id):
        errors.append("relay_result_id must match gcp-runtime-relay-result-<lowercase-token>")
    if not AI_DEV_RE.match(ai_dev_id):
        errors.append("ai_dev_id must match AI-DEV-###")
    if status not in TERMINAL_STATUSES:
        errors.append("status must be one of succeeded, blocked, skipped, failed")

    execution = require_object(data, "execution", errors)
    if execution.get("mode") != "dry_run":
        errors.append("execution.mode must be dry_run for AI-DEV-054 repo-side result")
    for field in [
        "runtime_execution_attempted",
        "n8n_called",
        "dify_called",
        "openai_chatgpt_api_called",
        "notification_sent",
        "order_or_trade_executed",
        "production_db_modified",
        "production_infra_modified",
    ]:
        require_false(execution, field, "execution", errors)

    validation = require_object(data, "validation", errors)
    require_true(validation, "request_validation_passed", "validation", errors)
    if not isinstance(validation.get("errors"), list):
        errors.append("validation.errors must be a list")
    if not isinstance(validation.get("warnings"), list):
        errors.append("validation.warnings must be a list")

    action_outcome = require_object(data, "action_outcome", errors)
    require_true(action_outcome, "allowed_action", "action_outcome", errors)
    require_false(action_outcome, "runtime_boundary_crossed", "action_outcome", errors)

    artifacts = require_object(data, "artifacts", errors)
    require_false(artifacts, "raw_runtime_output_repo_committed", "artifacts", errors)
    if not as_list(artifacts.get("local_only_artifact_refs")):
        errors.append("artifacts.local_only_artifact_refs must contain at least one local-only reference")

    retry = require_object(data, "retry", errors)
    attempts = retry.get("attempts")
    max_attempts = retry.get("max_attempts")
    if not isinstance(attempts, int) or attempts < 0:
        errors.append("retry.attempts must be a non-negative integer")
    if not isinstance(max_attempts, int) or max_attempts < 1:
        errors.append("retry.max_attempts must be a positive integer")
    if isinstance(attempts, int) and isinstance(max_attempts, int) and attempts > max_attempts:
        errors.append("retry.attempts must not exceed retry.max_attempts")

    idempotency = require_object(data, "idempotency", errors)
    if not idempotency.get("key"):
        errors.append("idempotency.key must be present")
    if idempotency.get("duplicate_terminal_result_found") is True and idempotency.get("execution_skipped_for_duplicate") is not True:
        errors.append("idempotency.execution_skipped_for_duplicate must be true for duplicate terminal results")

    safety = require_object(data, "safety", errors)
    for field in [
        "secret_values_included",
        "raw_runtime_output_included",
        "external_delivery_performed",
        "forbidden_action_performed",
    ]:
        require_false(safety, field, "safety", errors)
    require_true(safety, "safety_gates_passed", "safety", errors)

    audit = require_object(data, "audit", errors)
    if not as_list(audit.get("events")):
        errors.append("audit.events must contain at least one event")
    require_false(audit, "raw_runtime_output_in_audit", "audit", errors)

    closeout = require_object(data, "closeout", errors)
    for field in [
        "request_validation_recorded",
        "result_validation_required",
        "sanitized_artifact_ready_for_repo_pr",
    ]:
        require_true(closeout, field, "closeout", errors)
    require_false(closeout, "runtime_action_performed", "closeout", errors)

    if not isinstance(data.get("errors"), list):
        errors.append("errors must be a list")

    text = flatten_text(data)
    value_hit_patterns = [pattern.pattern for pattern in SECRET_VALUE_PATTERNS if pattern.search(text)]
    if value_hit_patterns:
        errors.append("result appears to include sensitive values")

    return {
        "ok": not errors,
        "relay_request_id": relay_request_id or None,
        "relay_result_id": relay_result_id or None,
        "ai_dev_id": ai_dev_id or None,
        "status": status or None,
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
    parser = argparse.ArgumentParser(description="Validate a sanitized GCP runtime relay result JSON file.")
    parser.add_argument("--input", default="templates/gcp_runtime_relay_result.example.json")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    data, load_errors = load_json(Path(args.input))
    if data is None:
        result = {
            "ok": False,
            "relay_request_id": None,
            "relay_result_id": None,
            "ai_dev_id": None,
            "status": None,
            "errors": load_errors,
            "warnings": [],
            "values_included_or_printed": False,
        }
    else:
        result = validate_result(data)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
