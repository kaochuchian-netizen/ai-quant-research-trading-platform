#!/usr/bin/env python3
"""Validate Dashboard Delivery Gate V1 fixture results."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "dashboard_delivery_gate_v1"
SUMMARY_SCHEMA_VERSION = "dashboard_delivery_gate_summary_v1"
CONTRACT_NAME = "dashboard_delivery_gate"
CONTRACT_VERSION = "v1"
DECISIONS = {
    "dashboard_delivery_gate_contract_completed",
    "dashboard_delivery_gate_contract_completed_with_warnings",
    "dashboard_delivery_blocked_pending_approval",
    "validation_failed",
    "blocked",
}
TOP_LEVEL = [
    "schema_version",
    "task_id",
    "run_id",
    "generated_at",
    "mode",
    "dashboard_delivery_gate",
    "dashboard_delivery_summary",
    "validation_summary",
    "side_effects",
    "safety",
    "ok",
    "decision",
    "next_recommendation",
]
DASHBOARD_DELIVERY_GATE_FIELDS = [
    "dashboard_delivery_id",
    "payload_id",
    "preview_id",
    "report_date",
    "review_id",
    "review_status",
    "approval_gate",
    "delivery_allowed",
    "dashboard_channel_enabled",
    "preview_only",
    "dashboard_page_ref",
    "static_page_summary",
    "publish_target_policy",
    "publish_preview",
    "delivery_blockers",
    "warning_badges",
    "human_review_required",
    "advisory_disclaimer",
    "publish_intent",
    "publish_status",
]
SIDE_EFFECTS_FALSE = [
    "read_secrets",
    "called_external_model_runtime",
    "called_market_data_runtime",
    "sent_notification",
    "sent_email",
    "sent_line_push",
    "called_smtp",
    "called_gmail_api",
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
    "no_dashboard_deploy",
    "no_api_server_created",
    "no_email_send",
    "no_line_push",
    "no_smtp_call",
    "no_gmail_api_call",
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
    re.compile(r"\.env", re.IGNORECASE),
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


def validate_dashboard_delivery_gate(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    gate = payload.get("dashboard_delivery_gate")
    if not isinstance(gate, dict):
        return ["dashboard_delivery_gate must be an object"]
    for key in missing(gate, DASHBOARD_DELIVERY_GATE_FIELDS):
        errors.append(f"dashboard_delivery_gate missing {key}")
    if not re.fullmatch(r"20\d{2}-\d{2}-\d{2}", str(gate.get("report_date", ""))):
        errors.append("dashboard_delivery_gate.report_date must be YYYY-MM-DD")
    for key in [
        "dashboard_delivery_id",
        "payload_id",
        "preview_id",
        "review_id",
        "review_status",
        "dashboard_page_ref",
        "advisory_disclaimer",
        "publish_intent",
        "publish_status",
    ]:
        if not isinstance(gate.get(key), str) or not gate.get(key):
            errors.append(f"dashboard_delivery_gate.{key} must be a non-empty string")
    if gate.get("preview_only") is not True:
        errors.append("dashboard_delivery_gate.preview_only must be true")
    if gate.get("publish_status") != "not_published":
        errors.append("dashboard_delivery_gate.publish_status must remain not_published in fixture mode")
    delivery_allowed = gate.get("delivery_allowed")
    review_status = gate.get("review_status")
    if delivery_allowed is not (review_status == "approved"):
        errors.append("dashboard_delivery_gate.delivery_allowed must be true only when review_status is approved")
    if gate.get("dashboard_channel_enabled") is True and not (delivery_allowed is True and review_status == "approved"):
        errors.append("dashboard_channel_enabled cannot be true unless delivery_allowed is true and review_status is approved")
    if gate.get("dashboard_channel_enabled") is not False:
        errors.append("dashboard_channel_enabled must be false in fixture mode")
    approval = as_dict(gate.get("approval_gate"))
    if approval.get("required_review_status") != "approved":
        errors.append("dashboard_delivery_gate.approval_gate.required_review_status must be approved")
    if approval.get("current_review_status") != review_status:
        errors.append("dashboard_delivery_gate.approval_gate.current_review_status must match review_status")
    if approval.get("delivery_allowed") != delivery_allowed or approval.get("gate_open") != delivery_allowed:
        errors.append("dashboard_delivery_gate.approval_gate must match delivery_allowed")
    policy = as_dict(gate.get("publish_target_policy"))
    if policy.get("requires_approval_gate") is not True or policy.get("requires_delivery_allowed") is not True:
        errors.append("dashboard_delivery_gate.publish_target_policy must require approval gate and delivery_allowed")
    if policy.get("deployment_permitted") is not False:
        errors.append("dashboard_delivery_gate.publish_target_policy.deployment_permitted must be false")
    if policy.get("fixture_mode_publish_status") != "not_published":
        errors.append("dashboard_delivery_gate.publish_target_policy.fixture_mode_publish_status must be not_published")
    publish_preview = as_dict(gate.get("publish_preview"))
    if publish_preview.get("preview_only") is not True:
        errors.append("dashboard_delivery_gate.publish_preview.preview_only must be true")
    if publish_preview.get("publish_action_performed") is not False:
        errors.append("dashboard_delivery_gate.publish_preview.publish_action_performed must be false")
    if publish_preview.get("publish_status") != "not_published":
        errors.append("dashboard_delivery_gate.publish_preview.publish_status must be not_published")
    if publish_preview.get("delivery_allowed") != delivery_allowed:
        errors.append("dashboard_delivery_gate.publish_preview.delivery_allowed must match delivery_allowed")
    if not isinstance(gate.get("static_page_summary"), dict):
        errors.append("dashboard_delivery_gate.static_page_summary must be an object")
    if not isinstance(gate.get("delivery_blockers"), list):
        errors.append("dashboard_delivery_gate.delivery_blockers must be a list")
    if delivery_allowed is False and "dashboard_delivery_gate_closed" not in as_list(gate.get("delivery_blockers")):
        errors.append("dashboard_delivery_gate.delivery_blockers must include dashboard_delivery_gate_closed when blocked")
    if not isinstance(gate.get("warning_badges"), list):
        errors.append("dashboard_delivery_gate.warning_badges must be a list")
    if not isinstance(gate.get("human_review_required"), bool):
        errors.append("dashboard_delivery_gate.human_review_required must be boolean")
    return errors


def validate_summary(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    summary = payload.get("dashboard_delivery_summary")
    gate = as_dict(payload.get("dashboard_delivery_gate"))
    if not isinstance(summary, dict):
        return ["dashboard_delivery_summary must be an object"]
    if summary.get("schema_version") != SUMMARY_SCHEMA_VERSION:
        errors.append("dashboard_delivery_summary.schema_version is invalid")
    for key in [
        "dashboard_delivery_id",
        "payload_id",
        "preview_id",
        "report_date",
        "review_id",
        "review_status",
        "delivery_allowed",
        "dashboard_channel_enabled",
        "publish_status",
        "publish_intent",
        "human_review_required",
    ]:
        if summary.get(key) != gate.get(key):
            errors.append(f"dashboard_delivery_summary.{key} must match dashboard_delivery_gate")
    if summary.get("warning_badge_count") != len(as_list(gate.get("warning_badges"))):
        errors.append("dashboard_delivery_summary.warning_badge_count must match warning_badges")
    if summary.get("delivery_blocker_count") != len(as_list(gate.get("delivery_blockers"))):
        errors.append("dashboard_delivery_summary.delivery_blocker_count must match delivery_blockers")
    return errors


def validate_validation_summary(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    summary = payload.get("validation_summary")
    gate = as_dict(payload.get("dashboard_delivery_gate"))
    if not isinstance(summary, dict):
        return ["validation_summary must be an object"]
    expected = {
        "contract_name": CONTRACT_NAME,
        "contract_version": CONTRACT_VERSION,
        "deterministic_output": True,
        "fixture_only": True,
        "preview_only": True,
        "advisory_only": True,
        "approval_gate_required": True,
        "delivery_allowed_policy_enforced": True,
        "dashboard_channel_policy_enforced": True,
        "publish_status_not_published": True,
        "no_publish_action_performed": True,
        "warning_count": len(as_list(gate.get("warning_badges"))),
        "delivery_blocker_count": len(as_list(gate.get("delivery_blockers"))),
    }
    for key, value in expected.items():
        if summary.get(key) != value:
            errors.append(f"validation_summary.{key} is invalid")
    for key in ["delivery_payload_source", "dashboard_static_page_source"]:
        source = as_dict(summary.get(key))
        if source.get("source_schema_matched") is not True:
            errors.append(f"validation_summary.{key}.source_schema_matched must be true")
        if source.get("source_ok") is not True:
            errors.append(f"validation_summary.{key}.source_ok must be true")
        if source.get("source_mode") != "fixture_dry_run":
            errors.append(f"validation_summary.{key}.source_mode must be fixture_dry_run")
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
    if payload.get("task_id") != "AI-DEV-096":
        errors.append("task_id must be AI-DEV-096")
    if payload.get("mode") != "fixture_dry_run":
        errors.append("mode must be fixture_dry_run")
    if payload.get("decision") not in DECISIONS:
        errors.append("decision is invalid")
    if payload.get("ok") is not True and payload.get("decision") not in {"validation_failed", "blocked"}:
        errors.append("ok must be true for completed decisions")
    errors.extend(validate_dashboard_delivery_gate(payload))
    errors.extend(validate_summary(payload))
    errors.extend(validate_validation_summary(payload))
    errors.extend(validate_side_effects(payload))
    errors.extend(validate_safety(payload))
    rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    for pattern in SECRET_PATTERNS:
        if pattern.search(rendered):
            errors.append(f"secret-like or private config text detected: {pattern.pattern}")
            break
    for text in iter_strings(payload):
        lowered = text.lower()
        for term in FORBIDDEN_RUNTIME_TERMS:
            if term in lowered:
                errors.append(f"forbidden live runtime source detected: {term}")
        for pattern in FORBIDDEN_TRADING_TEXT:
            if pattern.search(text):
                errors.append(f"possible trading/order instruction detected: {text}")
    gate = as_dict(payload.get("dashboard_delivery_gate"))
    validation = as_dict(payload.get("validation_summary"))
    return {
        "ok": not errors,
        "run_id": payload.get("run_id"),
        "decision": payload.get("decision"),
        "delivery_allowed": gate.get("delivery_allowed"),
        "dashboard_channel_enabled": gate.get("dashboard_channel_enabled"),
        "publish_status": gate.get("publish_status"),
        "deterministic_output": validation.get("deterministic_output"),
        "errors": errors,
        "side_effects": {key: False for key in SIDE_EFFECTS_FALSE},
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Dashboard Delivery Gate V1 result JSON.")
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
