#!/usr/bin/env python3
"""Check whether a Codex handoff queue item passes safe gate rules.

This script is read-only. It does not start Codex, edit queue files, run Git, send
notifications, or run production workflows.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


DEFAULT_QUEUE_PATH = "orchestrator/templates/codex_handoff_queue.example.json"
ALLOWED_TASK_TYPES = {"orchestrator_low_risk"}
REQUIRED_BLOCKED_PATHS = {
    ".env",
    "data/stock_analysis.db",
    "data/backups/",
    "analysis/output/",
}
REQUIRED_BOUNDARY_PHRASES = [
    "Do not run production workflows.",
    "Do not read local secret files.",
    "Do not change scheduler settings.",
]


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"ok": False, "state": "missing", "path": str(path)}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return {"ok": True, "state": "loaded", "path": str(path), "data": data}
        return {"ok": False, "state": "invalid", "path": str(path), "error": "top-level JSON is not an object"}
    except Exception as exc:
        return {"ok": False, "state": "invalid", "path": str(path), "error": str(exc)}


def safe_item_summary(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "handoff_id": item.get("handoff_id"),
        "task_id": item.get("task_id"),
        "task_name": item.get("task_name"),
        "status": item.get("status"),
        "priority": item.get("priority"),
        "manual_start_required": item.get("manual_start_required"),
        "agent_started": item.get("agent_started"),
        "agent_finished": item.get("agent_finished"),
        "allowed_task_type": item.get("allowed_task_type"),
    }


def select_next_pending_item(items: list[Any]) -> dict[str, Any] | None:
    pending = [item for item in items if isinstance(item, dict) and item.get("status") == "pending"]
    if not pending:
        return None
    return sorted(pending, key=lambda item: int(item.get("priority", 999999)))[0]


def evaluate_gate(item: dict[str, Any] | None) -> dict[str, Any]:
    if item is None:
        return {
            "gate_passed": False,
            "codex_start_allowed": False,
            "blocked_reasons": ["no pending queue item"],
            "next_pending_item": None,
        }

    blocked: list[str] = []

    if item.get("allowed_task_type") not in ALLOWED_TASK_TYPES:
        blocked.append("allowed_task_type is not permitted")
    if item.get("manual_start_required") is not True:
        blocked.append("manual_start_required must be true")
    if item.get("agent_started") is not False:
        blocked.append("agent_started must be false")
    if item.get("agent_finished") is not False:
        blocked.append("agent_finished must be false")

    allowed_paths = item.get("allowed_paths", [])
    if not isinstance(allowed_paths, list) or not allowed_paths:
        blocked.append("allowed_paths must be a non-empty list")
    else:
        for path in allowed_paths:
            if not isinstance(path, str):
                blocked.append("allowed_paths contains non-string value")
                break
            if path.startswith("/") or ".." in path.split("/"):
                blocked.append("allowed_paths must be relative safe paths")
                break

    blocked_paths = item.get("blocked_paths", [])
    if not isinstance(blocked_paths, list):
        blocked.append("blocked_paths must be a list")
    else:
        missing_blocked = sorted(REQUIRED_BLOCKED_PATHS.difference(set(blocked_paths)))
        if missing_blocked:
            blocked.append("missing required blocked paths: " + ", ".join(missing_blocked))

    validation_commands = item.get("validation_commands", [])
    if not isinstance(validation_commands, list) or not validation_commands:
        blocked.append("validation_commands must be a non-empty list")

    safety_boundaries = item.get("safety_boundaries", [])
    if not isinstance(safety_boundaries, list):
        blocked.append("safety_boundaries must be a list")
    else:
        for phrase in REQUIRED_BOUNDARY_PHRASES:
            if phrase not in safety_boundaries:
                blocked.append("missing safety boundary: " + phrase)

    gate_passed = not blocked
    return {
        "gate_passed": gate_passed,
        "codex_start_allowed": False,
        "blocked_reasons": blocked,
        "next_pending_item": safe_item_summary(item),
        "notes": "Gate pass only means the item is structurally safe. This script never starts Codex.",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check Codex handoff queue gate rules.")
    parser.add_argument("--queue-path", default=DEFAULT_QUEUE_PATH)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    queue_path = Path(args.queue_path)
    loaded = load_json(queue_path)
    if not loaded.get("ok"):
        result = {
            "ok": False,
            "queue_path": str(queue_path),
            "queue_state": loaded.get("state"),
            "error": loaded.get("error"),
            "gate_passed": False,
            "codex_start_allowed": False,
            "side_effects": {
                "queue_modified": False,
                "codex_started": False,
                "git_command_run": False,
                "notification_sent": False,
                "production_command_run": False,
            },
        }
        json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
        sys.stdout.write("\n")
        return 1

    queue = loaded["data"]
    items = queue.get("items", [])
    if not isinstance(items, list):
        result = {
            "ok": False,
            "queue_path": str(queue_path),
            "queue_id": queue.get("queue_id"),
            "error": "items is not a list",
            "gate_passed": False,
            "codex_start_allowed": False,
        }
        json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
        sys.stdout.write("\n")
        return 1

    next_item = select_next_pending_item(items)
    gate = evaluate_gate(next_item)
    result = {
        "ok": True,
        "queue_path": str(queue_path),
        "queue_id": queue.get("queue_id"),
        "schema_version": queue.get("schema_version"),
        "item_count": len(items),
        "pending_count": len([item for item in items if isinstance(item, dict) and item.get("status") == "pending"]),
        **gate,
        "side_effects": {
            "queue_modified": False,
            "codex_started": False,
            "git_command_run": False,
            "notification_sent": False,
            "production_command_run": False,
        },
    }
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
