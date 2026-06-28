#!/usr/bin/env python3
"""Validate Codex handoff auto executor result artifacts."""

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
    "headless_supported",
    "supported_command",
    "manual_one_shot_viable",
    "schedule_ready",
    "tmux_paste_required",
    "decision",
    "safe_to_schedule",
    "safe_to_execute",
    "blocked_reasons",
    "validation_errors",
    "feasibility",
    "execution_plan",
    "side_effects",
    "next_recommendation",
]

DECISIONS = {
    "plan_created",
    "headless_supported_manual_only",
    "headless_unsupported",
    "blocked",
    "invalid_handoff_path",
    "validation_failed",
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
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
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
    if data.get("task_id") != "AI-DEV-067":
        errors.append("task_id must be AI-DEV-067")
    if data.get("mode") not in {"dry_run", "plan_only"}:
        errors.append("mode must be dry_run or plan_only")
    if data.get("safe_to_schedule") is not False:
        errors.append("safe_to_schedule must be false")
    if data.get("schedule_ready") is not False:
        errors.append("schedule_ready must be false")
    if data.get("safe_to_execute") is not False:
        errors.append("safe_to_execute must be false in V1 result artifacts")
    if decision == "headless_unsupported" and data.get("safe_to_execute") is not False:
        errors.append("headless_unsupported requires safe_to_execute=false")
    blocked_reasons = data.get("blocked_reasons")
    if not isinstance(blocked_reasons, list):
        errors.append("blocked_reasons must be a list")
    elif decision == "blocked" and not blocked_reasons:
        errors.append("blocked decision requires blocked_reasons")
    if not isinstance(data.get("validation_errors"), list):
        errors.append("validation_errors must be a list")

    side_effects = data.get("side_effects")
    if not isinstance(side_effects, dict):
        errors.append("side_effects must be an object")
    else:
        for field in SIDE_EFFECT_FIELDS:
            if side_effects.get(field) is not False:
                errors.append(f"side_effects.{field} must be false")

    feasibility = data.get("feasibility")
    if not isinstance(feasibility, dict):
        errors.append("feasibility must be an object")
    else:
        for field in [
            "which_codex",
            "codex_version",
            "codex_help_available",
            "codex_exec_help_available",
            "codex_run_help_available",
            "sanitized_help_notes",
        ]:
            if field not in feasibility:
                errors.append(f"feasibility missing {field}")
        if not isinstance(feasibility.get("sanitized_help_notes"), list):
            errors.append("feasibility.sanitized_help_notes must be a list")

    execution_plan = data.get("execution_plan")
    if not isinstance(execution_plan, dict):
        errors.append("execution_plan must be an object")
    else:
        if execution_plan.get("default_calls_codex") is not False:
            errors.append("execution_plan.default_calls_codex must be false")
        if execution_plan.get("execute_shell_from_handoff") is not False:
            errors.append("execution_plan.execute_shell_from_handoff must be false")

    rendered = json.dumps(data, ensure_ascii=False, sort_keys=True)
    hit_patterns = [pattern.pattern for pattern in SECRET_PATTERNS if pattern.search(rendered)]
    if hit_patterns:
        errors.append("result appears to contain secret, token, credential, or .env-like material")

    return {
        "ok": not errors,
        "task_id": data.get("task_id"),
        "decision": decision,
        "headless_supported": data.get("headless_supported"),
        "manual_one_shot_viable": data.get("manual_one_shot_viable"),
        "schedule_ready": data.get("schedule_ready"),
        "safe_to_schedule": data.get("safe_to_schedule"),
        "safe_to_execute": data.get("safe_to_execute"),
        "errors": errors,
        "side_effects": {field: False for field in SIDE_EFFECT_FIELDS},
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a Codex handoff auto executor result JSON.")
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
