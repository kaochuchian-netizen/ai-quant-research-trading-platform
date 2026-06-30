#!/usr/bin/env python3
"""Validate Production Scheduler Gate Runtime Smoke Test V1 fixtures."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "production_scheduler_gate_runtime_smoke_test_v1"
TASK_ID = "AI-DEV-102"
WINDOWS = ["pre_open_0700", "intraday_1305", "pre_close_1335"]
TOP_LEVEL = [
    "schema_version",
    "task_id",
    "run_id",
    "generated_at",
    "branch",
    "mode",
    "delivery_allowed",
    "run_stock_analysis_sh",
    "windows",
    "commands",
    "safety",
    "side_effects",
    "ok",
]
SAFETY_TRUE = [
    "no_email_send",
    "no_line_push",
    "no_dashboard_deploy",
    "no_persistent_store_writes",
    "no_production_db_writes",
    "no_schedule_service_changes",
    "no_cron_mutation",
    "no_systemd_mutation",
    "no_timer_mutation",
    "no_secret_mutation",
    "no_legacy_production_path",
]
SIDE_EFFECTS_FALSE = [
    "sent_email",
    "sent_line_push",
    "deployed_dashboard",
    "wrote_persistent_store",
    "wrote_production_db",
    "modified_schedule_or_service",
    "modified_cron",
    "modified_systemd",
    "modified_timer",
    "modified_secrets",
]
FORBIDDEN_TEXT = [
    re.compile(r"STOCK_AI_LEGACY_PRODUCTION_APPROVED=1"),
    re.compile(r"main\.py\s+--production-approved"),
    re.compile(r"run_pipeline\.py\s+pre_open\s+--production-approved"),
    re.compile(r"\bsystemctl\s+(enable|disable|start|stop|restart|daemon-reload)\b", re.I),
    re.compile(r"\bcrontab\s+-e\b", re.I),
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

    for key in TOP_LEVEL:
        if key not in payload:
            errors.append(f"missing top-level field: {key}")
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    if payload.get("task_id") != TASK_ID:
        errors.append(f"task_id must be {TASK_ID}")
    if payload.get("mode") != "dry_run_no_delivery":
        errors.append("mode must be dry_run_no_delivery")
    if payload.get("delivery_allowed") is not False:
        errors.append("delivery_allowed must be false")
    if payload.get("ok") is not True:
        errors.append("ok must be true")

    run_stock = as_dict(payload.get("run_stock_analysis_sh"))
    if run_stock.get("expected_runtime_path") != "scripts/orchestrator/production_scheduler_gate_runtime.py":
        errors.append("run_stock_analysis_sh.expected_runtime_path is invalid")
    for key in ["delivery_allowed", "legacy_production_approved"]:
        if run_stock.get(key) is not False:
            errors.append(f"run_stock_analysis_sh.{key} must be false")
    if run_stock.get("no_delivery_default") is not True:
        errors.append("run_stock_analysis_sh.no_delivery_default must be true")

    windows = as_list(payload.get("windows"))
    if [as_dict(item).get("window") for item in windows] != WINDOWS:
        errors.append("windows must cover pre_open_0700, intraday_1305, pre_close_1335 in order")
    for item in windows:
        window = as_dict(item)
        label = window.get("window")
        if window.get("delivery_allowed") is not False:
            errors.append(f"window {label} delivery_allowed must be false")
        for key in [
            "no_email_send",
            "no_line_push",
            "no_dashboard_deploy",
            "no_persistent_store_writes",
            "no_schedule_service_changes",
        ]:
            if window.get(key) is not True:
                errors.append(f"window {label} {key} must be true")

    commands = as_list(payload.get("commands"))
    if len(commands) < 5:
        errors.append("commands must include shell syntax, entrypoint, and three runtime smoke commands")
    rendered_commands = "\n".join(str(as_dict(item).get("command", "")) for item in commands)
    for required in [
        "bash -n run_stock_analysis.sh",
        "./run_stock_analysis.sh",
        "--window pre_open_0700",
        "--window intraday_1305",
        "--window pre_close_1335",
    ]:
        if required not in rendered_commands:
            errors.append(f"commands missing required command text: {required}")
    for item in commands:
        entry = as_dict(item)
        if entry.get("expected_exit_code") != 0:
            errors.append(f"command {entry.get('command')} expected_exit_code must be 0")

    safety = as_dict(payload.get("safety"))
    for key in SAFETY_TRUE:
        if safety.get(key) is not True:
            errors.append(f"safety.{key} must be true")
    side_effects = as_dict(payload.get("side_effects"))
    for key in SIDE_EFFECTS_FALSE:
        if side_effects.get(key) is not False:
            errors.append(f"side_effects.{key} must be false")

    for text in iter_strings(payload):
        for pattern in FORBIDDEN_TEXT:
            if pattern.search(text):
                errors.append(f"forbidden command text detected: {text}")
                break

    return {
        "ok": not errors,
        "schema_version": payload.get("schema_version"),
        "task_id": payload.get("task_id"),
        "run_id": payload.get("run_id"),
        "delivery_allowed": payload.get("delivery_allowed"),
        "windows": [as_dict(item).get("window") for item in windows],
        "errors": errors,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate Production Scheduler Gate Runtime Smoke Test V1 fixture.")
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
