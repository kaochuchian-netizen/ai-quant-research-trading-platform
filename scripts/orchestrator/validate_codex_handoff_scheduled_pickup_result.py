#!/usr/bin/env python3
"""Validate scheduled pickup to Codex handoff executor result artifacts."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


REQUIRED_FIELDS = [
    "task_id",
    "ok",
    "mode",
    "decision",
    "pickup_artifact",
    "handoff_path",
    "readiness",
    "executor",
    "lock",
    "idempotency",
    "limits",
    "side_effects",
    "safe_to_continue",
    "next_recommendation",
]

DECISIONS = {
    "executed_codex_handoff",
    "dry_run_plan_created",
    "no_pending_handoff",
    "readiness_failed",
    "locked",
    "already_processed",
    "invalid_handoff_path",
    "unsafe_handoff",
    "codex_executor_failed",
    "validation_failed",
    "activation_completed",
}

SIDE_EFFECT_FIELDS = [
    "called_codex_runtime",
    "called_external_ai_runtime",
    "sent_notification",
    "modified_production_db",
    "modified_cron_systemd_timer",
    "mutated_github_issue",
]

SECRET_PATTERNS = [
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{20,}"),
    re.compile(r"AIza[0-9A-Za-z_-]{20,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{20,}", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"(?i)(api[_-]?key|access[_-]?token|password)\s*[:=]\s*[^\s,}\"']+"),
]


def load_json(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        data = json.loads(path.expanduser().read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return None, [f"failed to parse JSON result: {exc}"]
    if not isinstance(data, dict):
        return None, ["result root must be a JSON object"]
    return data, []


def require_object(data: dict[str, Any], field: str, errors: list[str]) -> dict[str, Any]:
    value = data.get(field)
    if not isinstance(value, dict):
        errors.append(f"{field} must be an object")
        return {}
    return value


def validate_result(data: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    for field in REQUIRED_FIELDS:
        if field not in data:
            errors.append(f"missing required field: {field}")

    if data.get("task_id") != "AI-DEV-069":
        errors.append("task_id must be AI-DEV-069")
    if data.get("mode") not in {"dry_run", "execute"}:
        errors.append("mode must be dry_run or execute")
    decision = data.get("decision")
    if decision not in DECISIONS:
        errors.append(f"decision must be one of: {', '.join(sorted(DECISIONS))}")

    readiness = require_object(data, "readiness", errors)
    executor = require_object(data, "executor", errors)
    lock = require_object(data, "lock", errors)
    idempotency = require_object(data, "idempotency", errors)
    limits = require_object(data, "limits", errors)
    side_effects = require_object(data, "side_effects", errors)

    if limits.get("max_handoffs_per_run") != 1:
        errors.append("limits.max_handoffs_per_run must be 1")
    selected_count = limits.get("selected_handoff_count")
    if not isinstance(selected_count, int):
        errors.append("limits.selected_handoff_count must be an integer")
    elif selected_count > 1:
        errors.append("limits.selected_handoff_count must not exceed 1")
    if lock.get("required") is not True:
        errors.append("lock.required must be true")
    if idempotency.get("required") is not True:
        errors.append("idempotency.required must be true")

    for field in SIDE_EFFECT_FIELDS:
        if field == "modified_cron_systemd_timer" and decision == "activation_completed":
            if not isinstance(side_effects.get(field), bool):
                errors.append("side_effects.modified_cron_systemd_timer must be boolean")
            continue
        if side_effects.get(field) is not False:
            errors.append(f"side_effects.{field} must be false")
    for field in ["sent_notification", "modified_production_db", "mutated_github_issue"]:
        if side_effects.get(field) is True:
            errors.append(f"side_effects.{field}=true is never allowed")

    if decision == "executed_codex_handoff":
        if data.get("mode") != "execute":
            errors.append("executed_codex_handoff requires mode=execute")
        if readiness.get("safe_to_call_executor") is not True:
            errors.append("executed_codex_handoff requires readiness.safe_to_call_executor=true")
        if lock.get("acquired") is not True:
            errors.append("executed_codex_handoff requires lock.acquired=true")
        if idempotency.get("already_processed") is not False:
            errors.append("executed_codex_handoff requires idempotency.already_processed=false")
        if executor.get("called") is not True:
            errors.append("executed_codex_handoff requires executor.called=true")
    if decision == "already_processed":
        if executor.get("called") is not False:
            errors.append("already_processed requires executor.called=false")
        if idempotency.get("already_processed") is not True:
            errors.append("already_processed requires idempotency.already_processed=true")
    if decision == "locked" and executor.get("called") is not False:
        errors.append("locked requires executor.called=false")
    if decision in {"readiness_failed", "unsafe_handoff", "codex_executor_failed", "validation_failed"}:
        reasons = data.get("blocked_reasons", [])
        if not isinstance(reasons, list) or not reasons:
            errors.append(f"{decision} requires blocked_reasons")

    rendered = json.dumps(data, ensure_ascii=False, sort_keys=True)
    if any(pattern.search(rendered) for pattern in SECRET_PATTERNS):
        errors.append("result appears to contain secret-like values")

    return {
        "ok": not errors,
        "task_id": data.get("task_id"),
        "mode": data.get("mode"),
        "decision": decision,
        "readiness_safe_to_call_executor": readiness.get("safe_to_call_executor"),
        "executor_called": executor.get("called"),
        "max_handoffs_per_run": limits.get("max_handoffs_per_run"),
        "selected_handoff_count": limits.get("selected_handoff_count"),
        "idempotency_key": idempotency.get("key"),
        "already_processed": idempotency.get("already_processed"),
        "marked_processed": idempotency.get("marked_processed"),
        "errors": errors,
        "side_effects": {field: False for field in SIDE_EFFECT_FIELDS},
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate scheduled Codex handoff pickup result JSON.")
    parser.add_argument("input", nargs="?", default=None)
    parser.add_argument("--input", dest="input_option", default=None)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = args.input_option or args.input
    if not input_path:
        result = {"ok": False, "errors": ["input path is required"]}
    else:
        data, load_errors = load_json(Path(input_path))
        result = {"ok": False, "errors": load_errors} if data is None else validate_result(data)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
