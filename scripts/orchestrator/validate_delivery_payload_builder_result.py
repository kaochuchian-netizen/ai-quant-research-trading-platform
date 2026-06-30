#!/usr/bin/env python3
"""Validate Delivery Payload Builder V1 fixture results."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "delivery_payload_builder_v1"
SUMMARY_SCHEMA_VERSION = "delivery_payload_summary_v1"
CONTRACT_NAME = "delivery_payload_builder"
CONTRACT_VERSION = "v1"
DECISIONS = {
    "delivery_payload_builder_completed",
    "delivery_payload_builder_completed_with_warnings",
    "delivery_blocked_pending_approval",
    "validation_failed",
    "blocked",
}
TOP_LEVEL = [
    "schema_version",
    "task_id",
    "run_id",
    "generated_at",
    "mode",
    "delivery_payload",
    "delivery_summary",
    "validation_summary",
    "side_effects",
    "safety",
    "ok",
    "decision",
    "next_recommendation",
]
DELIVERY_PAYLOAD_FIELDS = [
    "payload_id",
    "report_date",
    "preview_id",
    "review_id",
    "review_status",
    "approval_gate",
    "delivery_allowed",
    "channels",
    "email_payload",
    "line_payload",
    "dashboard_payload",
    "explainability_refs",
    "warning_badges",
    "human_review_required",
    "delivery_blockers",
    "advisory_disclaimer",
]
SIDE_EFFECTS_FALSE = [
    "read_secrets",
    "called_external_model_runtime",
    "called_market_data_runtime",
    "sent_notification",
    "sent_email",
    "sent_line_push",
    "deployed_dashboard",
    "created_api_server",
    "placed_trade_order",
    "modified_portfolio",
    "wrote_persistent_store",
    "modified_schedule_or_service",
    "modified_github_remote",
]
SAFETY_TRUE = [
    "repo_only",
    "fixture_only",
    "advisory_only",
    "preview_only",
    "no_external_model_calls",
    "no_market_data_calls",
    "no_delivery_actions",
    "no_email_send",
    "no_line_push",
    "no_dashboard_deploy",
    "no_persistent_store_writes",
    "no_portfolio_actions",
    "no_schedule_service_changes",
]
SAFETY_FALSE = ["dashboard_deploy", "api_server_created", "trading_instruction"]
SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{20,}"),
    re.compile(r"AIza[0-9A-Za-z_-]{20,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{20,}", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
]
FORBIDDEN_RUNTIME_TERMS = ["shioaji", "production_db", "webhook", "broker"]
FORBIDDEN_TRADING_TEXT = [
    re.compile(r"\b(buy|sell|short|long)\s+(now|today|at market|at open|at close)\b", re.IGNORECASE),
    re.compile(r"\b(place|submit|route|execute)\s+(an?\s+)?order\b", re.IGNORECASE),
    re.compile(r"\border\s+(now|immediately|ticket|instruction)\b", re.IGNORECASE),
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


def missing(data: Any, keys: list[str]) -> list[str]:
    if not isinstance(data, dict):
        return keys
    return [key for key in keys if key not in data]


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


def validate_channel_payload(payload: dict[str, Any], key: str) -> list[str]:
    errors: list[str] = []
    channel_payload = payload.get(key)
    if not isinstance(channel_payload, dict):
        return [f"delivery_payload.{key} must be an object"]
    if channel_payload.get("enabled") is not False:
        errors.append(f"delivery_payload.{key}.enabled must be false")
    if channel_payload.get("preview_only") is not True:
        errors.append(f"delivery_payload.{key}.preview_only must be true")
    if channel_payload.get("delivery_action_performed") is not False:
        errors.append(f"delivery_payload.{key}.delivery_action_performed must be false")
    if channel_payload.get("delivery_allowed") != payload.get("delivery_allowed"):
        errors.append(f"delivery_payload.{key}.delivery_allowed must match delivery_payload.delivery_allowed")
    if not str(channel_payload.get("advisory_disclaimer", "")).strip():
        errors.append(f"delivery_payload.{key}.advisory_disclaimer is required")
    return errors


def validate_delivery_payload(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    delivery = payload.get("delivery_payload")
    if not isinstance(delivery, dict):
        return ["delivery_payload must be an object"]
    for key in missing(delivery, DELIVERY_PAYLOAD_FIELDS):
        errors.append(f"delivery_payload missing {key}")
    if not re.fullmatch(r"20\d{2}-\d{2}-\d{2}", str(delivery.get("report_date", ""))):
        errors.append("delivery_payload.report_date must be YYYY-MM-DD")
    for key in ["payload_id", "preview_id", "review_id", "review_status", "advisory_disclaimer"]:
        if not str(delivery.get(key, "")).strip():
            errors.append(f"delivery_payload.{key} is required")
    delivery_allowed = delivery.get("delivery_allowed")
    review_status = delivery.get("review_status")
    if delivery_allowed is not (review_status == "approved"):
        errors.append("delivery_payload.delivery_allowed must be true only when review_status is approved")
    gate = as_dict(delivery.get("approval_gate"))
    if gate.get("required_review_status") != "approved":
        errors.append("delivery_payload.approval_gate.required_review_status must be approved")
    if gate.get("current_review_status") != review_status:
        errors.append("delivery_payload.approval_gate.current_review_status must match review_status")
    if gate.get("delivery_allowed") != delivery_allowed or gate.get("gate_open") != delivery_allowed:
        errors.append("delivery_payload.approval_gate must match delivery_allowed")
    channels = as_list(delivery.get("channels"))
    if [as_dict(item).get("channel") for item in channels] != ["email", "line", "dashboard"]:
        errors.append("delivery_payload.channels must contain email, line, dashboard in order")
    for index, item in enumerate(channels):
        channel = as_dict(item)
        if channel.get("enabled") is not False:
            errors.append(f"delivery_payload.channels[{index}].enabled must be false")
        if channel.get("preview_only") is not True:
            errors.append(f"delivery_payload.channels[{index}].preview_only must be true")
        if channel.get("delivery_action_performed") is not False:
            errors.append(f"delivery_payload.channels[{index}].delivery_action_performed must be false")
        if channel.get("delivery_allowed") != delivery_allowed:
            errors.append(f"delivery_payload.channels[{index}].delivery_allowed must match delivery_allowed")
    for key in ["email_payload", "line_payload", "dashboard_payload"]:
        errors.extend(validate_channel_payload(delivery, key))
    if delivery_allowed is False:
        disabled = all(as_dict(item).get("enabled") is False and as_dict(item).get("preview_only") is True for item in channels)
        disabled = disabled and all(
            as_dict(delivery.get(key)).get("enabled") is False and as_dict(delivery.get(key)).get("preview_only") is True
            for key in ["email_payload", "line_payload", "dashboard_payload"]
        )
        if not disabled:
            errors.append("all channels and channel payloads must remain disabled and preview_only when delivery_allowed is false")
    if not isinstance(delivery.get("explainability_refs"), list):
        errors.append("delivery_payload.explainability_refs must be a list")
    if not isinstance(delivery.get("warning_badges"), list):
        errors.append("delivery_payload.warning_badges must be a list")
    if not isinstance(delivery.get("human_review_required"), bool):
        errors.append("delivery_payload.human_review_required must be boolean")
    if not isinstance(delivery.get("delivery_blockers"), list):
        errors.append("delivery_payload.delivery_blockers must be a list")
    if delivery_allowed is False and "approval_gate_closed" not in as_list(delivery.get("delivery_blockers")):
        errors.append("delivery_payload.delivery_blockers must include approval_gate_closed when blocked")
    return errors


def validate_summary(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    summary = payload.get("delivery_summary")
    delivery = as_dict(payload.get("delivery_payload"))
    if not isinstance(summary, dict):
        return ["delivery_summary must be an object"]
    if summary.get("schema_version") != SUMMARY_SCHEMA_VERSION:
        errors.append("delivery_summary.schema_version is invalid")
    for key in ["payload_id", "report_date", "preview_id", "review_id", "review_status", "delivery_allowed"]:
        if summary.get(key) != delivery.get(key):
            errors.append(f"delivery_summary.{key} must match delivery_payload")
    if summary.get("channel_count") != len(as_list(delivery.get("channels"))):
        errors.append("delivery_summary.channel_count must match delivery_payload.channels")
    if summary.get("enabled_channel_count") != 0:
        errors.append("delivery_summary.enabled_channel_count must be 0")
    if summary.get("warning_badge_count") != len(as_list(delivery.get("warning_badges"))):
        errors.append("delivery_summary.warning_badge_count must match delivery_payload.warning_badges")
    if summary.get("explainability_ref_count") != len(as_list(delivery.get("explainability_refs"))):
        errors.append("delivery_summary.explainability_ref_count must match delivery_payload.explainability_refs")
    return errors


def validate_validation_summary(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    summary = payload.get("validation_summary")
    if not isinstance(summary, dict):
        return ["validation_summary must be an object"]
    expected = {
        "contract_name": CONTRACT_NAME,
        "contract_version": CONTRACT_VERSION,
        "deterministic_output": True,
        "fixture_only": True,
        "preview_only": True,
        "review_source_schema_matched": True,
        "explainability_source_schema_matched": True,
        "review_source_ok": True,
        "explainability_source_ok": True,
        "delivery_allowed_policy_enforced": True,
        "channels_disabled": True,
        "channels_preview_only": True,
        "channel_payloads_disabled": True,
    }
    for key, value in expected.items():
        if summary.get(key) != value:
            errors.append(f"validation_summary.{key} is invalid")
    for key in ["warning_count", "delivery_blocker_count"]:
        if not isinstance(summary.get(key), int) or summary.get(key, -1) < 0:
            errors.append(f"validation_summary.{key} must be a non-negative integer")
    if not isinstance(summary.get("warnings"), list):
        errors.append("validation_summary.warnings must be a list")
    return errors


def validate_side_effects(payload: dict[str, Any]) -> list[str]:
    side_effects = payload.get("side_effects")
    if not isinstance(side_effects, dict):
        return ["side_effects must be an object"]
    return [f"side_effects.{key} must be false" for key in SIDE_EFFECTS_FALSE if side_effects.get(key) is not False]


def validate_safety(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    safety = payload.get("safety")
    if not isinstance(safety, dict):
        return ["safety must be an object"]
    for key in SAFETY_TRUE:
        if safety.get(key) is not True:
            errors.append(f"safety.{key} must be true")
    for key in SAFETY_FALSE:
        if safety.get(key) is not False:
            errors.append(f"safety.{key} must be false")
    return errors


def validate_payload(payload: Any) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return {"ok": False, "errors": ["result root must be an object"]}
    for key in missing(payload, TOP_LEVEL):
        errors.append(f"missing top-level field: {key}")
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    if payload.get("task_id") != "AI-DEV-093":
        errors.append("task_id must be AI-DEV-093")
    if payload.get("mode") != "fixture_dry_run":
        errors.append("mode must be fixture_dry_run")
    if payload.get("decision") not in DECISIONS:
        errors.append("decision is invalid")
    if payload.get("ok") is not True and payload.get("decision") not in {"validation_failed", "blocked"}:
        errors.append("ok must be true for completed decisions")
    errors.extend(validate_delivery_payload(payload))
    errors.extend(validate_summary(payload))
    errors.extend(validate_validation_summary(payload))
    errors.extend(validate_side_effects(payload))
    errors.extend(validate_safety(payload))
    rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    for pattern in SECRET_PATTERNS:
        if pattern.search(rendered):
            errors.append(f"secret-like text detected: {pattern.pattern}")
            break
    for text in iter_strings(payload):
        lowered = text.lower()
        for term in FORBIDDEN_RUNTIME_TERMS:
            if term in lowered:
                errors.append(f"forbidden live runtime source detected: {term}")
        for pattern in FORBIDDEN_TRADING_TEXT:
            if pattern.search(text):
                errors.append(f"possible trading/order instruction detected: {text}")
    delivery = as_dict(payload.get("delivery_payload"))
    validation = as_dict(payload.get("validation_summary"))
    return {
        "ok": not errors,
        "run_id": payload.get("run_id"),
        "decision": payload.get("decision"),
        "delivery_allowed": delivery.get("delivery_allowed"),
        "review_status": delivery.get("review_status"),
        "deterministic_output": validation.get("deterministic_output"),
        "errors": errors,
        "side_effects": {key: False for key in SIDE_EFFECTS_FALSE},
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Delivery Payload Builder V1 result JSON.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload, load_errors = load_json(Path(args.input))
    result = {"ok": False, "errors": load_errors, "decision": "validation_failed"} if load_errors else validate_payload(payload)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
