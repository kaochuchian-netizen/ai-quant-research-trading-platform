#!/usr/bin/env python3
"""Check an Orchestrator approval-state JSON file.

This gate is intentionally read-only:
- It reads one approval-state JSON file.
- It reports whether the decision is continue, pause, blocked, or error.
- It can require a matching task_id.
- It does not start tasks, run Git, send mail, or execute production commands.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


APPROVED_CONTINUE = "approved_continue"
APPROVED_PAUSE = "approved_pause"


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("approval state must be a JSON object")
    return data


def nested_get(data: dict[str, Any], *keys: str) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def evaluate_approval_state(
    approval_state: dict[str, Any],
    expected_task_id: str | None,
) -> dict[str, Any]:
    task_id = approval_state.get("task_id")
    task_name = approval_state.get("task_name")
    state = nested_get(approval_state, "approval", "state")
    selected_action = nested_get(approval_state, "approval", "selected_action")

    task_id_matches = True
    if expected_task_id:
        task_id_matches = task_id == expected_task_id

    decision = "blocked"
    next_task_allowed = False
    pause_requested = False
    blocked_reason = None

    if not task_id_matches:
        blocked_reason = f"task_id mismatch: {task_id} != {expected_task_id}"
    elif state == APPROVED_CONTINUE and selected_action == "continue":
        decision = "continue"
        next_task_allowed = True
    elif state == APPROVED_PAUSE and selected_action == "pause":
        decision = "pause"
        pause_requested = True
    else:
        blocked_reason = f"unsupported approval state: {state}"

    return {
        "ok": blocked_reason is None,
        "task_id": task_id,
        "task_name": task_name,
        "expected_task_id": expected_task_id,
        "task_id_matches": task_id_matches,
        "approval_state": state,
        "selected_action": selected_action,
        "decision": decision,
        "next_task_allowed": next_task_allowed,
        "pause_requested": pause_requested,
        "blocked_reason": blocked_reason,
        "side_effects": {
            "email_sent": False,
            "git_command_run": False,
            "task_started": False,
            "production_command_run": False,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check a local Orchestrator approval-state JSON file.")
    parser.add_argument("--approval-state", required=True, help="Approval-state JSON path.")
    parser.add_argument("--expected-task-id", help="Require approval state to match this task_id.")
    parser.add_argument(
        "--require-continue",
        action="store_true",
        help="Exit non-zero unless the decision is continue.",
    )
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        approval_state = load_json(Path(args.approval_state).expanduser())
        result = evaluate_approval_state(approval_state, args.expected_task_id)
    except Exception as exc:
        result = {
            "ok": False,
            "decision": "error",
            "next_task_allowed": False,
            "blocked_reason": str(exc),
        }

    if args.require_continue and not result.get("next_task_allowed"):
        result["ok"] = False
        if result.get("blocked_reason") is None:
            result["blocked_reason"] = "continue approval required"

    json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
    sys.stdout.write("\n")

    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
