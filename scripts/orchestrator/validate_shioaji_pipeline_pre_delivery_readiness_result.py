#!/usr/bin/env python3
"""Validate Shioaji pipeline pre-delivery readiness repair V1 results."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "shioaji_pipeline_pre_delivery_readiness_repair_v1"
TASK_ID = "AI-DEV-105"
DECISIONS = {
    "shioaji_pipeline_pre_delivery_readiness_repair_completed",
    "shioaji_pipeline_pre_delivery_readiness_repair_completed_with_warnings",
    "pipeline_pre_delivery_still_blocked",
    "validation_failed",
    "blocked",
}
TOP_LEVEL = [
    "schema_version",
    "task_id",
    "run_id",
    "generated_at",
    "mode",
    "shioaji_readiness",
    "historical_data_readiness",
    "pipeline_pre_delivery_status",
    "fallback_policy",
    "warnings",
    "side_effects",
    "safety",
    "ok",
    "decision",
    "next_recommendation",
]
SAFETY_TRUE = [
    "repo_only",
    "no_send",
    "diagnostic_and_repair_only",
    "no_line_push",
    "no_line_api_call",
    "no_email_send",
    "no_smtp_call",
    "no_gmail_api_call",
    "no_dashboard_deploy",
    "no_api_server_created",
    "no_secret_read",
    "no_secret_mutation",
    "no_persistent_store_writes",
    "no_portfolio_actions",
    "no_cron_modification",
    "no_systemd_modification",
    "no_timer_modification",
    "no_service_modification",
    "no_schedule_service_changes",
]
SAFETY_FALSE = ["external_side_effects_allowed", "trading_instruction"]
SIDE_EFFECTS_FALSE = [
    "read_secrets",
    "mutated_secrets",
    "sent_line_push",
    "called_line_api",
    "sent_email",
    "called_smtp",
    "called_gmail_api",
    "deployed_dashboard",
    "created_api_server",
    "wrote_persistent_store",
    "placed_trade_order",
    "modified_portfolio",
    "modified_cron",
    "modified_systemd",
    "modified_timer",
    "modified_service",
    "modified_schedule_or_service",
    "called_market_data_runtime",
]
SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{20,}", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
]


def load_json(path: Path) -> tuple[Any | None, list[str]]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), []
    except Exception as exc:
        return None, [f"failed to read JSON: {exc}"]


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def missing(payload: dict[str, Any], keys: list[str]) -> list[str]:
    return [key for key in keys if key not in payload]


def iter_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            result.extend(iter_strings(item))
        return result
    if isinstance(value, dict):
        result: list[str] = []
        for item in value.values():
            result.extend(iter_strings(item))
        return result
    return []


def validate_payload(payload: Any) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return {"ok": False, "errors": ["result root must be an object"]}

    for key in missing(payload, TOP_LEVEL):
        errors.append(f"missing top-level field: {key}")
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    if payload.get("task_id") != TASK_ID:
        errors.append(f"task_id must be {TASK_ID}")
    if payload.get("decision") not in DECISIONS:
        errors.append("decision is invalid")
    if not isinstance(payload.get("ok"), bool):
        errors.append("ok must be boolean")
    if not str(payload.get("run_id", "")).strip():
        errors.append("run_id is required")
    if not str(payload.get("generated_at", "")).strip():
        errors.append("generated_at is required")

    shioaji = as_dict(payload.get("shioaji_readiness"))
    historical = as_dict(payload.get("historical_data_readiness"))
    pre_delivery = as_dict(payload.get("pipeline_pre_delivery_status"))
    fallback = as_dict(payload.get("fallback_policy"))
    warnings = as_list(payload.get("warnings"))

    if shioaji.get("market_data_runtime_called") is not False:
        errors.append("shioaji_readiness.market_data_runtime_called must be false")
    if shioaji.get("login_required_for_report_path") is not False:
        errors.append("shioaji_readiness.login_required_for_report_path must be false")
    if historical.get("kbars_window_bounded") is not True:
        errors.append("historical_data_readiness.kbars_window_bounded must be true")
    if historical.get("bounded_kbars_window_days") != 30:
        errors.append("historical_data_readiness.bounded_kbars_window_days must be 30")
    if historical.get("fallback_to_existing_csv") is not True:
        errors.append("historical_data_readiness.fallback_to_existing_csv must be true")
    if historical.get("persistent_store_writes") is not False:
        errors.append("historical_data_readiness.persistent_store_writes must be false")
    if pre_delivery.get("schema_version") != "pipeline_pre_delivery_status_v1":
        errors.append("pipeline_pre_delivery_status.schema_version is invalid")
    if pre_delivery.get("crash_pipeline_on_shioaji_failure") is not False:
        errors.append("pipeline_pre_delivery_status.crash_pipeline_on_shioaji_failure must be false")
    if pre_delivery.get("delivery_stage_reachable") != pre_delivery.get("report_ready_available"):
        errors.append("pipeline_pre_delivery_status delivery fields must match")
    if fallback.get("enabled") is not True or fallback.get("source") != "existing_historical_csv":
        errors.append("fallback_policy must enable existing_historical_csv")
    if fallback.get("do_not_suppress_warnings") is not True:
        errors.append("fallback_policy.do_not_suppress_warnings must be true")
    if not isinstance(warnings, list):
        errors.append("warnings must be a list")

    side_effects = as_dict(payload.get("side_effects"))
    for key in SIDE_EFFECTS_FALSE:
        if side_effects.get(key) is not False:
            errors.append(f"side_effects.{key} must be false")
    safety = as_dict(payload.get("safety"))
    for key in SAFETY_TRUE:
        if safety.get(key) is not True:
            errors.append(f"safety.{key} must be true")
    for key in SAFETY_FALSE:
        if safety.get(key) is not False:
            errors.append(f"safety.{key} must be false")

    all_text = "\n".join(iter_strings(payload))
    for pattern in SECRET_PATTERNS:
        if pattern.search(all_text):
            errors.append("payload appears to contain a secret-like value")
            break

    expected_decision = (
        "pipeline_pre_delivery_still_blocked"
        if pre_delivery.get("delivery_stage_reachable") is not True
        else "shioaji_pipeline_pre_delivery_readiness_repair_completed_with_warnings"
        if warnings
        else "shioaji_pipeline_pre_delivery_readiness_repair_completed"
    )
    if payload.get("decision") != expected_decision:
        errors.append(f"decision must be {expected_decision}")
    if payload.get("ok") is not (expected_decision != "pipeline_pre_delivery_still_blocked"):
        errors.append("ok does not match expected decision")

    return {"ok": not errors, "errors": errors}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Shioaji pre-delivery readiness repair result.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload, errors = load_json(Path(args.input))
    result = {"ok": False, "errors": errors} if errors else validate_payload(payload)
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
