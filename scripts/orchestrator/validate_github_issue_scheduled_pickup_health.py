#!/usr/bin/env python3
"""Validate a scheduled GitHub Issue pickup health report."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REQUIRED_FIELDS = [
    "schema_version",
    "generated_at",
    "state_dir",
    "timer_name",
    "service_name",
    "timer_present",
    "timer_enabled",
    "timer_active",
    "next_trigger_summary",
    "service_present",
    "last_service_status_summary",
    "latest_artifact_path",
    "latest_artifact_present",
    "latest_artifact_valid",
    "latest_artifact_summary",
    "lock_file_path",
    "lock_file_present",
    "idempotency_file_path",
    "idempotency_file_present",
    "log_file_path",
    "log_file_present",
    "side_effect_flags_ok",
    "github_issue_mutated",
    "runtime_action_performed",
    "daemon_or_background_service_created",
    "recommended_operator_action",
    "rollback_disable_commands",
    "safety_confirmation",
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


def load_json(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, [f"failed to parse JSON health report: {exc}"]
    if not isinstance(data, dict):
        return None, ["health report root must be a JSON object"]
    return data, []


def flatten_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def validate_report(data: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    for field in REQUIRED_FIELDS:
        if field not in data:
            errors.append(f"missing required field: {field}")

    for field in [
        "timer_present",
        "timer_enabled",
        "timer_active",
        "service_present",
        "latest_artifact_present",
        "latest_artifact_valid",
        "lock_file_present",
        "idempotency_file_present",
        "log_file_present",
        "side_effect_flags_ok",
        "github_issue_mutated",
        "runtime_action_performed",
        "daemon_or_background_service_created",
    ]:
        if not isinstance(data.get(field), bool):
            errors.append(f"{field} must be boolean")

    for field in ["state_dir", "timer_name", "service_name", "latest_artifact_path", "lock_file_path", "idempotency_file_path", "log_file_path"]:
        if not isinstance(data.get(field), str) or not data.get(field):
            errors.append(f"{field} must be a non-empty string")

    if not isinstance(data.get("last_service_status_summary"), dict):
        errors.append("last_service_status_summary must be an object")
    if not isinstance(data.get("latest_artifact_summary"), dict):
        errors.append("latest_artifact_summary must be an object")
    if not isinstance(data.get("rollback_disable_commands"), list) or not data.get("rollback_disable_commands"):
        errors.append("rollback_disable_commands must be a non-empty list")
    if data.get("github_issue_mutated") is not False:
        errors.append("github_issue_mutated must be false")
    if data.get("runtime_action_performed") is not False:
        errors.append("runtime_action_performed must be false")
    if data.get("daemon_or_background_service_created") is not False:
        errors.append("daemon_or_background_service_created must be false")
    if data.get("side_effect_flags_ok") is not True:
        warnings.append("side_effect_flags_ok is not true")
    if not data.get("safety_confirmation"):
        errors.append("safety_confirmation must be present")

    text = flatten_text(data)
    value_hit_patterns = [pattern.pattern for pattern in SECRET_VALUE_PATTERNS if pattern.search(text)]
    if value_hit_patterns:
        errors.append("health report appears to include sensitive values")

    return {
        "ok": not errors,
        "timer_present": data.get("timer_present"),
        "timer_enabled": data.get("timer_enabled"),
        "timer_active": data.get("timer_active"),
        "service_present": data.get("service_present"),
        "latest_artifact_present": data.get("latest_artifact_present"),
        "latest_artifact_valid": data.get("latest_artifact_valid"),
        "side_effect_flags_ok": data.get("side_effect_flags_ok"),
        "recommended_operator_action": data.get("recommended_operator_action"),
        "errors": errors,
        "warnings": warnings,
        "values_included_or_printed": bool(value_hit_patterns),
        "value_hit_patterns": value_hit_patterns,
        "side_effects": {
            "runtime_action_performed": False,
            "github_issue_mutated": False,
            "schedule_modified": False,
            "notification_sent": False,
            "production_db_modified": False,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a scheduled pickup health report.")
    parser.add_argument("--input", default="templates/github_issue_scheduled_pickup_health.example.json")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    data, load_errors = load_json(Path(args.input))
    if data is None:
        result = {
            "ok": False,
            "timer_present": None,
            "timer_enabled": None,
            "timer_active": None,
            "service_present": None,
            "latest_artifact_present": None,
            "latest_artifact_valid": None,
            "side_effect_flags_ok": None,
            "recommended_operator_action": None,
            "errors": load_errors,
            "warnings": [],
            "values_included_or_printed": False,
            "value_hit_patterns": [],
        }
    else:
        result = validate_report(data)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
