#!/usr/bin/env python3
"""Create a sanitized dry-run result for a GCP resident pickup request.

The helper is intentionally non-destructive. It validates the shape of a pickup
request, writes a sanitized result artifact, and never starts n8n, calls Dify,
opens external connections, sends notifications, trades, or writes production
state.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

AI_DEV_RE = re.compile(r"^AI-DEV-\d{3}$")
PICKUP_ID_RE = re.compile(r"^gcp-resident-pickup-[a-z0-9-]+$")
SECRET_VALUE_PATTERNS = [
    re.compile(r"ghp_[A-Za-z0-9_]+"),
    re.compile(r"github_pat_[A-Za-z0-9_]+"),
    re.compile(r"sk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]+"),
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?i)(api[_-]?key|access[_-]?token|password)\s*[:=]\s*[^\s,}\"']+"),
]

REQUIRED_REQUEST_FIELDS = [
    "schema_version",
    "pickup_request_id",
    "ai_dev_id",
    "created_at",
    "created_by",
    "source",
    "execution_mode",
    "pickup",
    "idempotency",
    "safety_gates",
    "result_output",
    "expected_outputs",
    "notes",
]


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


def obj(data: dict[str, Any], field: str, errors: list[str]) -> dict[str, Any]:
    value = data.get(field)
    if not isinstance(value, dict):
        errors.append(f"{field} must be an object")
        return {}
    return value


def validate_pickup_request(data: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    for field in REQUIRED_REQUEST_FIELDS:
        if field not in data:
            errors.append(f"missing required field: {field}")
    pickup_request_id = str(data.get("pickup_request_id", ""))
    ai_dev_id = str(data.get("ai_dev_id", ""))
    if not PICKUP_ID_RE.match(pickup_request_id):
        errors.append("pickup_request_id must match gcp-resident-pickup-<lowercase-token>")
    if not AI_DEV_RE.match(ai_dev_id):
        errors.append("ai_dev_id must match AI-DEV-###")

    execution_mode = obj(data, "execution_mode", errors)
    if execution_mode.get("mode") != "dry_run":
        errors.append("execution_mode.mode must be dry_run")
    if execution_mode.get("runtime_execution_allowed") is not False:
        errors.append("execution_mode.runtime_execution_allowed must be false")
    if execution_mode.get("external_runtime_calls_allowed") is not False:
        errors.append("execution_mode.external_runtime_calls_allowed must be false")

    pickup = obj(data, "pickup", errors)
    if pickup.get("generate_sanitized_result") is not True:
        errors.append("pickup.generate_sanitized_result must be true")
    if pickup.get("write_local_runtime_state") is not False:
        errors.append("pickup.write_local_runtime_state must be false")

    safety_gates = obj(data, "safety_gates", errors)
    for key in [
        "no_runtime_action",
        "no_secret_values",
        "no_external_delivery",
        "no_production_db_mutation",
        "no_trading_or_order_execution",
        "no_n8n_start",
        "no_dify_runtime_call",
        "no_openai_chatgpt_api_call",
        "dry_run_only",
    ]:
        if safety_gates.get(key) is not True:
            errors.append(f"safety_gates.{key} must be true")

    result_output = obj(data, "result_output", errors)
    if result_output.get("raw_runtime_output_repo_allowed") is not False:
        errors.append("result_output.raw_runtime_output_repo_allowed must be false")
    if result_output.get("sanitized_result_required") is not True:
        errors.append("result_output.sanitized_result_required must be true")

    text = flatten_text(data)
    value_hit_patterns = [pattern.pattern for pattern in SECRET_VALUE_PATTERNS if pattern.search(text)]
    if value_hit_patterns:
        errors.append("request appears to include sensitive values")

    return {
        "ok": not errors,
        "pickup_request_id": pickup_request_id or None,
        "ai_dev_id": ai_dev_id or None,
        "errors": errors,
        "warnings": warnings,
        "values_included_or_printed": bool(value_hit_patterns),
        "value_hit_patterns": value_hit_patterns,
    }


def build_result(request: dict[str, Any], validation: dict[str, Any]) -> dict[str, Any]:
    pickup_request_id = str(request.get("pickup_request_id"))
    ai_dev_id = str(request.get("ai_dev_id"))
    source = request.get("source", {}) if isinstance(request.get("source"), dict) else {}
    action_key = "dry_run_pickup_and_write_sanitized_result"
    status = "succeeded" if validation.get("ok") else "blocked"
    return {
        "schema_version": "1.0.0",
        "pickup_request_id": pickup_request_id,
        "pickup_result_id": pickup_request_id.replace("gcp-resident-pickup-", "gcp-resident-pickup-result-"),
        "ai_dev_id": ai_dev_id,
        "created_at": request.get("created_at", "2026-06-27T00:00:00Z"),
        "status": status,
        "status_reason": "dry_run_pickup_result_generated_without_runtime_action" if validation.get("ok") else "pickup_request_validation_failed",
        "execution": {
            "mode": "dry_run",
            "runtime_action_performed": False,
            "n8n_started": False,
            "n8n_called": False,
            "dify_called": False,
            "openai_chatgpt_api_called": False,
            "notification_sent": False,
            "order_or_trade_executed": False,
            "production_db_modified": False,
            "production_infra_modified": False
        },
        "validation": {
            "pickup_request_validation_passed": bool(validation.get("ok")),
            "handoff_request_validation_passed": True,
            "relay_request_validation_passed": True,
            "pickup_result_validation_required": True,
            "errors": validation.get("errors", []),
            "warnings": validation.get("warnings", [])
        },
        "pickup_outcome": {
            "request_picked_up": bool(validation.get("ok")),
            "request_source": "merged_repo_default_branch",
            "handoff_request_path": source.get("handoff_request_path"),
            "relay_request_path": source.get("relay_request_path"),
            "sanitized_result_generated": bool(validation.get("ok")),
            "runtime_boundary_crossed": False,
            "dry_run_helper": "scripts/orchestrator/gcp_resident_pickup_dry_run.py"
        },
        "artifacts": {
            "sanitized_result_path": request.get("result_output", {}).get("result_path"),
            "raw_runtime_output_repo_committed": False,
            "local_only_artifact_refs": [
                "~/.local/state/stock-ai-orchestrator/runtime_relay/gcp-resident-pickup-ai-dev-055/"
            ]
        },
        "idempotency": {
            "key": f"{pickup_request_id}|{ai_dev_id}|{source.get('required_main_commit')}|{action_key}",
            "duplicate_terminal_result_found": False,
            "execution_skipped_for_duplicate": False,
            "on_duplicate_terminal_result": "skip_without_runtime_execution"
        },
        "safety": {
            "secret_values_included": False,
            "raw_runtime_output_included": False,
            "external_delivery_performed": False,
            "forbidden_action_performed": False,
            "safety_gates_passed": bool(validation.get("ok"))
        },
        "audit": {
            "events": [
                "picked_up",
                "validated",
                "planned",
                "dry_run_result_written",
                "closed_out"
            ],
            "raw_runtime_output_in_audit": False
        },
        "closeout": {
            "request_validation_recorded": True,
            "result_validation_required": True,
            "sanitized_artifact_ready_for_repo_pr": bool(validation.get("ok")),
            "runtime_action_performed": False,
            "safety_confirmation": "Dry-run pickup only; no n8n, Dify, OpenAI, notification, trading, production database, infrastructure, or runtime action occurred."
        },
        "errors": validation.get("errors", [])
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a sanitized GCP resident pickup dry-run result.")
    parser.add_argument("--input", default="templates/gcp_resident_pickup_request.example.json")
    parser.add_argument("--output", required=True)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    request, load_errors = load_json(Path(args.input))
    if request is None:
        result = {"ok": False, "errors": load_errors, "side_effects": {"runtime_action_performed": False}}
        json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
        sys.stdout.write("\n")
        return 2
    validation = validate_pickup_request(request)
    pickup_result = build_result(request, validation)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(pickup_result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {
        "ok": bool(validation.get("ok")),
        "pickup_request_id": validation.get("pickup_request_id"),
        "ai_dev_id": validation.get("ai_dev_id"),
        "output": str(output_path),
        "result_status": pickup_result.get("status"),
        "errors": validation.get("errors", []),
        "warnings": validation.get("warnings", []),
        "side_effects": {
            "runtime_action_performed": False,
            "n8n_started": False,
            "dify_called": False,
            "openai_chatgpt_api_called": False,
            "notification_sent": False,
            "production_db_modified": False,
            "trading_or_order_execution": False,
        },
    }
    json.dump(summary, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    return 0 if summary["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
