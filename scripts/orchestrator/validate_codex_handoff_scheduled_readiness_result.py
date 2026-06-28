#!/usr/bin/env python3
"""Validate Codex handoff scheduled readiness result artifacts."""

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
    "handoff_path",
    "handoff_exists",
    "handoff_under_allowed_dir",
    "handoff_sanitized",
    "headless_supported",
    "manual_one_shot_viable",
    "schedule_ready",
    "single_active_lock_required",
    "single_active_lock_present",
    "idempotency_required",
    "idempotency_key",
    "already_processed",
    "max_handoffs_per_run",
    "selected_handoff_count",
    "safe_to_call_executor",
    "safe_to_schedule",
    "decision",
    "blocked_reasons",
    "side_effects",
    "next_recommendation",
]

DECISIONS = {
    "readiness_pass_manual_only",
    "readiness_blocked",
    "invalid_handoff_path",
    "handoff_missing",
    "already_processed",
    "lock_missing",
    "idempotency_missing",
    "unsafe_handoff",
    "activation_proposal_created",
    "validation_failed",
}

SIDE_EFFECT_FIELDS = [
    "called_codex_runtime",
    "called_external_ai_runtime",
    "sent_notification",
    "modified_production_db",
    "modified_cron_systemd_timer",
    "mutated_github_issue",
    "modified_n8n",
    "placed_trade_order",
    "executed_shell_from_handoff",
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
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return None, [f"failed to parse JSON result: {exc}"]
    if not isinstance(data, dict):
        return None, ["result root must be a JSON object"]
    return data, []


def validate_result(data: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    for field in REQUIRED_FIELDS:
        if field not in data:
            errors.append(f"missing required field: {field}")

    decision = data.get("decision")
    if decision not in DECISIONS:
        errors.append(f"decision must be one of: {', '.join(sorted(DECISIONS))}")
    if data.get("task_id") != "AI-DEV-068":
        errors.append("task_id must be AI-DEV-068")
    if data.get("mode") != "dry_run":
        errors.append("mode must be dry_run")
    if data.get("safe_to_schedule") is not False:
        errors.append("safe_to_schedule must be false")
    if data.get("schedule_ready") is not False:
        errors.append("schedule_ready must be false")
    if data.get("max_handoffs_per_run") != 1:
        errors.append("max_handoffs_per_run must be 1")

    selected_count = data.get("selected_handoff_count")
    if not isinstance(selected_count, int):
        errors.append("selected_handoff_count must be an integer")
    elif selected_count > 1:
        errors.append("selected_handoff_count must not exceed 1")

    blocked_reasons = data.get("blocked_reasons")
    if not isinstance(blocked_reasons, list):
        errors.append("blocked_reasons must be a list")
    elif decision in {"readiness_blocked", "unsafe_handoff"} and not blocked_reasons:
        errors.append("readiness_blocked or unsafe_handoff requires blocked_reasons")

    side_effects = data.get("side_effects")
    if not isinstance(side_effects, dict):
        errors.append("side_effects must be an object")
    else:
        for field in SIDE_EFFECT_FIELDS:
            if side_effects.get(field) is not False:
                errors.append(f"side_effects.{field} must be false")

    if data.get("safe_to_call_executor") is True:
        required_true_fields = [
            "handoff_exists",
            "handoff_under_allowed_dir",
            "handoff_sanitized",
            "headless_supported",
            "manual_one_shot_viable",
            "single_active_lock_required",
            "idempotency_required",
        ]
        for field in required_true_fields:
            if data.get(field) is not True:
                errors.append(f"safe_to_call_executor=true requires {field}=true")
        if data.get("already_processed") is not False:
            errors.append("safe_to_call_executor=true requires already_processed=false")
        if not isinstance(data.get("idempotency_key"), str) or not data.get("idempotency_key"):
            errors.append("safe_to_call_executor=true requires a non-empty idempotency_key")

    rendered = json.dumps(data, ensure_ascii=False, sort_keys=True)
    if any(pattern.search(rendered) for pattern in SECRET_PATTERNS):
        errors.append("result appears to contain secret-like values")

    return {
        "ok": not errors,
        "task_id": data.get("task_id"),
        "decision": decision,
        "headless_supported": data.get("headless_supported"),
        "manual_one_shot_viable": data.get("manual_one_shot_viable"),
        "schedule_ready": data.get("schedule_ready"),
        "safe_to_call_executor": data.get("safe_to_call_executor"),
        "safe_to_schedule": data.get("safe_to_schedule"),
        "max_handoffs_per_run": data.get("max_handoffs_per_run"),
        "selected_handoff_count": data.get("selected_handoff_count"),
        "idempotency_key": data.get("idempotency_key"),
        "errors": errors,
        "side_effects": {field: False for field in SIDE_EFFECT_FIELDS},
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a Codex handoff scheduled readiness result JSON.")
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
