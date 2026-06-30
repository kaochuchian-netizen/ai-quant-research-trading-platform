#!/usr/bin/env python3
"""Validate LINE Delivery Regression Diagnosis V1 result fixtures."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "line_delivery_regression_diagnosis_v1"
TASK_ID = "AI-DEV-104"
DECISIONS = {
    "line_delivery_regression_diagnosis_completed",
    "line_delivery_regression_diagnosis_completed_with_warnings",
    "line_delivery_regression_root_cause_uncertain",
    "validation_failed",
    "blocked",
}
TOP_LEVEL = [
    "schema_version",
    "task_id",
    "run_id",
    "generated_at",
    "mode",
    "user_report",
    "diagnostic_window",
    "scheduler_findings",
    "runner_findings",
    "pipeline_findings",
    "line_sender_findings",
    "log_findings",
    "git_timeline_findings",
    "likely_root_causes",
    "confidence",
    "recommended_next_actions",
    "side_effects",
    "safety",
    "ok",
    "decision",
    "next_recommendation",
]
SAFETY_TRUE = [
    "repo_only",
    "diagnostic_only",
    "read_only_runtime_inspection",
    "no_line_push",
    "no_line_api_call",
    "no_email_send",
    "no_dashboard_deploy",
    "no_smtp_call",
    "no_gmail_api_call",
    "no_secrets_read",
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
    "called_gmail_api",
    "called_line_api",
    "called_smtp",
    "deployed_dashboard",
    "external_side_effects_allowed",
    "modified_cron",
    "modified_persistent_store",
    "modified_service",
    "modified_systemd",
    "modified_timer",
    "read_secrets",
    "sent_email",
    "sent_line_push",
    "sent_notification",
    "triggered_production_delivery",
]
SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{20,}", re.IGNORECASE),
    re.compile(r"LINE_CHANNEL_ACCESS_TOKEN\s*[:=]\s*[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
]
FORBIDDEN_LIVE_COMMANDS = re.compile(
    r"\b("
    r"python3\s+main\.py\s+--production-approved|"
    r"scripts/run_pipeline\.py\s+pre_open\s+--production-approved|"
    r"STOCK_AI_LEGACY_PRODUCTION_APPROVED=1|"
    r"crontab\s+-e|"
    r"systemctl\s+(enable|disable|start|stop|restart|daemon-reload)"
    r")\b",
    re.IGNORECASE,
)


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


def validate_payload(payload: Any) -> dict[str, Any]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return {"ok": False, "errors": ["result root must be an object"], "decision": "validation_failed"}

    for key in missing(payload, TOP_LEVEL):
        errors.append(f"missing top-level field: {key}")
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    if payload.get("task_id") != TASK_ID:
        errors.append(f"task_id must be {TASK_ID}")
    if payload.get("decision") not in DECISIONS:
        errors.append("decision is invalid")
    if payload.get("ok") is not True and payload.get("decision") not in {"validation_failed", "blocked"}:
        errors.append("ok must be true unless decision is validation_failed or blocked")

    user_report = as_dict(payload.get("user_report"))
    if not user_report.get("reported_issue"):
        errors.append("user_report.reported_issue is required")
    diagnostic_window = as_dict(payload.get("diagnostic_window"))
    if diagnostic_window.get("start") != "2026-06-23T13:35:00+08:00":
        errors.append("diagnostic_window.start must match the reported regression boundary")

    scheduler = as_dict(payload.get("scheduler_findings"))
    cron_entries = as_list(scheduler.get("cron_entries_observed"))
    if len(cron_entries) < 3:
        errors.append("scheduler_findings.cron_entries_observed must include the three observed cron entries")
    if scheduler.get("likely_cron_not_firing") is not False:
        errors.append("scheduler_findings.likely_cron_not_firing must be false for the observed fixture")

    for list_key in [
        "runner_findings",
        "pipeline_findings",
        "line_sender_findings",
        "git_timeline_findings",
        "likely_root_causes",
        "recommended_next_actions",
    ]:
        if not as_list(payload.get(list_key)):
            errors.append(f"{list_key} must be a non-empty list")

    root_causes = as_list(payload.get("likely_root_causes"))
    if not any("Shioaji" in " ".join(iter_strings(item)) for item in root_causes):
        errors.append("likely_root_causes must include Shioaji evidence")
    if not any("delivery_allowed=false" in " ".join(iter_strings(item)) for item in root_causes):
        errors.append("likely_root_causes must include delivery_allowed=false gate evidence")

    confidence = as_dict(payload.get("confidence"))
    if confidence.get("level") not in {"low", "medium", "medium_high", "high"}:
        errors.append("confidence.level is invalid")
    score = confidence.get("score")
    if not isinstance(score, (int, float)) or not 0 <= score <= 1:
        errors.append("confidence.score must be between 0 and 1")

    safety = as_dict(payload.get("safety"))
    for key in SAFETY_TRUE:
        if safety.get(key) is not True:
            errors.append(f"safety.{key} must be true")
    for key in SAFETY_FALSE:
        if safety.get(key) is not False:
            errors.append(f"safety.{key} must be false")

    side_effects = as_dict(payload.get("side_effects"))
    for key in SIDE_EFFECTS_FALSE:
        if side_effects.get(key) is not False:
            errors.append(f"side_effects.{key} must be false")

    rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    for pattern in SECRET_PATTERNS:
        if pattern.search(rendered):
            errors.append(f"secret-like text detected: {pattern.pattern}")
            break
    for text in iter_strings(payload):
        if FORBIDDEN_LIVE_COMMANDS.search(text):
            errors.append(f"forbidden live command or approval flag detected: {text}")

    return {
        "ok": not errors,
        "run_id": payload.get("run_id"),
        "decision": payload.get("decision") if not errors else "validation_failed",
        "confidence": confidence,
        "likely_root_cause_count": len(root_causes),
        "cron_entry_count": len(cron_entries),
        "safety": {
            "repo_only": safety.get("repo_only"),
            "diagnostic_only": safety.get("diagnostic_only"),
            "no_line_push": safety.get("no_line_push"),
            "no_line_api_call": safety.get("no_line_api_call"),
            "no_secrets_read": safety.get("no_secrets_read"),
            "no_cron_modification": safety.get("no_cron_modification"),
            "external_side_effects_allowed": safety.get("external_side_effects_allowed"),
        },
        "errors": errors,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate LINE Delivery Regression Diagnosis V1 result JSON.")
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
