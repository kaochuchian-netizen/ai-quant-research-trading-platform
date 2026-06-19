#!/usr/bin/env python3
"""Summarize whether the Orchestrator may proceed to the next task.

This script is read-only except for writing a decision summary JSON:
- It reads a VM validation result JSON.
- It optionally reads a task state JSON for next-task metadata.
- It outputs continue / pause / blocked.
- It does not start tasks, run Git, send mail, or execute production commands.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


DEFAULT_TIMEZONE = "Asia/Taipei"
DEFAULT_TMP_PREFIX = "stock_ai_orchestrator_next_task_decision_"


def now_iso(timezone_name: str) -> str:
    return datetime.now(ZoneInfo(timezone_name)).replace(microsecond=0).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("JSON file must contain an object")
    return data


def nested_get(data: dict[str, Any], *keys: str) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def default_output_path(task_id: str | None) -> Path:
    safe_task_id = task_id or "unknown_task"
    safe_task_id = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in safe_task_id)
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    return Path(tempfile.gettempdir()) / f"{DEFAULT_TMP_PREFIX}{safe_task_id}_{timestamp}.json"


def build_decision_summary(
    validation_result: dict[str, Any],
    task_state: dict[str, Any],
    timezone_name: str,
) -> dict[str, Any]:
    task_id = validation_result.get("task_id") or task_state.get("task_id")
    task_name = validation_result.get("task_name") or task_state.get("task_name")
    next_task = task_state.get("next_task") if isinstance(task_state.get("next_task"), dict) else {}
    approval_gate = validation_result.get("approval_gate") if isinstance(validation_result.get("approval_gate"), dict) else {}

    validation_ok = bool(validation_result.get("ok"))
    next_task_allowed = bool(validation_result.get("next_task_allowed"))
    pause_requested = bool(validation_result.get("pause_requested"))
    blocked_reason = validation_result.get("blocked_reason") or approval_gate.get("blocked_reason")

    decision = "blocked"
    should_start_next_task = False
    if validation_ok and next_task_allowed:
        decision = "continue"
        should_start_next_task = True
    elif validation_ok and pause_requested:
        decision = "pause"
        should_start_next_task = False
    elif validation_ok and not approval_gate:
        decision = "no_approval_gate"
        blocked_reason = blocked_reason or "approval gate result is missing"
    else:
        blocked_reason = blocked_reason or "validation result is not ok"

    return {
        "ok": decision in {"continue", "pause"},
        "decision": decision,
        "task_id": task_id,
        "task_name": task_name,
        "created_at": now_iso(timezone_name),
        "next_task": {
            "suggested_task_id": next_task.get("suggested_task_id"),
            "suggested_task_name": next_task.get("suggested_task_name"),
            "requires_user_approval": next_task.get("requires_user_approval"),
            "should_start_next_task": should_start_next_task,
        },
        "approval_gate": {
            "state": approval_gate.get("approval_state"),
            "selected_action": approval_gate.get("selected_action"),
            "next_task_allowed": next_task_allowed,
            "pause_requested": pause_requested,
        },
        "blocked_reason": blocked_reason,
        "side_effects": {
            "email_sent": False,
            "git_command_run": False,
            "task_started": False,
            "production_command_run": False,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize Orchestrator next-task decision from validation output.")
    parser.add_argument("--validation-result", required=True, help="VM validation result JSON path.")
    parser.add_argument("--task-state", help="Optional task state JSON path for next-task metadata.")
    parser.add_argument("--output", help="Output JSON path. Defaults to a /tmp file.")
    parser.add_argument("--timezone", default=DEFAULT_TIMEZONE)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        validation_result = load_json(Path(args.validation_result).expanduser())
        task_state = load_json(Path(args.task_state).expanduser()) if args.task_state else {}
        decision_summary = build_decision_summary(validation_result, task_state, args.timezone)
    except Exception as exc:
        decision_summary = {
            "ok": False,
            "decision": "error",
            "blocked_reason": str(exc),
            "side_effects": {
                "email_sent": False,
                "git_command_run": False,
                "task_started": False,
                "production_command_run": False,
            },
        }

    output_path = Path(args.output).expanduser() if args.output else default_output_path(decision_summary.get("task_id"))
    if not output_path.is_absolute():
        output_path = Path.cwd() / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)

    decision_summary["output_path"] = str(output_path)
    output_text = json.dumps(decision_summary, ensure_ascii=False, indent=2 if args.pretty else None)
    output_path.write_text(output_text + "\n", encoding="utf-8")
    sys.stdout.write(output_text + "\n")

    return 0 if decision_summary.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
