#!/usr/bin/env python3
"""Materialize the next safe Codex handoff into runtime files.

This script reads a Codex handoff queue and writes current_codex_handoff.json/md only
when the next pending item passes structural safety checks.

It does not start Codex, run Git, send notifications, or run production workflows.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


DEFAULT_QUEUE_PATH = "orchestrator/templates/codex_handoff_queue.example.json"
DEFAULT_RUNTIME_DIR = "~/.local/state/stock-ai-orchestrator"
DEFAULT_TIMEZONE = "Asia/Taipei"
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


def now_iso(timezone_name: str) -> str:
    return datetime.now(ZoneInfo(timezone_name)).replace(microsecond=0).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"ok": False, "error": "queue file missing", "path": str(path)}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"ok": False, "error": "queue root is not an object", "path": str(path)}
        return {"ok": True, "data": data, "path": str(path)}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "path": str(path)}


def select_next_pending_item(items: list[Any]) -> dict[str, Any] | None:
    pending = [item for item in items if isinstance(item, dict) and item.get("status") == "pending"]
    if not pending:
        return None
    return sorted(pending, key=lambda item: int(item.get("priority", 999999)))[0]


def evaluate_gate(item: dict[str, Any] | None) -> dict[str, Any]:
    if item is None:
        return {"gate_passed": False, "blocked_reasons": ["no pending queue item"]}

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
        missing = sorted(REQUIRED_BLOCKED_PATHS.difference(set(blocked_paths)))
        if missing:
            blocked.append("missing required blocked paths: " + ", ".join(missing))

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

    return {"gate_passed": not blocked, "blocked_reasons": blocked}


def build_handoff_json(item: dict[str, Any], queue_path: Path, created_at: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "handoff_id": item.get("handoff_id"),
        "task_id": item.get("task_id"),
        "task_name": item.get("task_name"),
        "status": "materialized",
        "created_at": created_at,
        "source_queue_path": str(queue_path),
        "allowed_task_type": item.get("allowed_task_type"),
        "priority": item.get("priority"),
        "manual_start_required": item.get("manual_start_required"),
        "agent_started": False,
        "agent_finished": False,
        "allowed_paths": item.get("allowed_paths", []),
        "blocked_paths": item.get("blocked_paths", []),
        "objective": item.get("objective"),
        "validation_commands": item.get("validation_commands", []),
        "safety_boundaries": item.get("safety_boundaries", []),
        "execution": {
            "codex_start_allowed": False,
            "codex_started": False,
            "notes": "Materialized handoff only. Codex is not started by this script.",
        },
    }


def build_handoff_markdown(handoff: dict[str, Any]) -> str:
    validation = "\n".join(f"- `{cmd}`" for cmd in handoff.get("validation_commands", [])) or "- None"
    allowed = "\n".join(f"- `{path}`" for path in handoff.get("allowed_paths", [])) or "- None"
    blocked = "\n".join(f"- `{path}`" for path in handoff.get("blocked_paths", [])) or "- None"
    boundaries = "\n".join(f"- {line}" for line in handoff.get("safety_boundaries", [])) or "- None"
    return f"""# Codex Handoff

## Task

- Handoff ID: `{handoff.get('handoff_id')}`
- Task ID: `{handoff.get('task_id')}`
- Task name: {handoff.get('task_name')}
- Status: `{handoff.get('status')}`
- Created at: `{handoff.get('created_at')}`
- Manual start required: `{handoff.get('manual_start_required')}`
- Codex start allowed: `False`

## Objective

{handoff.get('objective')}

## Allowed paths

{allowed}

## Blocked paths

{blocked}

## Validation commands

{validation}

## Safety boundaries

{boundaries}

## Execution note

This file is a materialized handoff only. It does not start Codex.
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Materialize safe Codex handoff runtime files.")
    parser.add_argument("--queue-path", default=DEFAULT_QUEUE_PATH)
    parser.add_argument("--runtime-dir", default=DEFAULT_RUNTIME_DIR)
    parser.add_argument("--timezone", default=DEFAULT_TIMEZONE)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    queue_path = Path(args.queue_path)
    runtime_dir = Path(args.runtime_dir).expanduser().resolve()
    loaded = load_json(queue_path)

    result: dict[str, Any] = {
        "ok": False,
        "dry_run": bool(args.dry_run),
        "queue_path": str(queue_path),
        "runtime_dir": str(runtime_dir),
        "json_path": str(runtime_dir / "current_codex_handoff.json"),
        "markdown_path": str(runtime_dir / "current_codex_handoff.md"),
        "codex_started": False,
        "side_effects": {
            "runtime_files_written": False,
            "queue_modified": False,
            "codex_started": False,
            "git_command_run": False,
            "notification_sent": False,
            "production_command_run": False,
        },
    }

    if not loaded.get("ok"):
        result["error"] = loaded.get("error")
        json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
        sys.stdout.write("\n")
        return 1

    queue = loaded["data"]
    items = queue.get("items", [])
    if not isinstance(items, list):
        result["error"] = "queue items is not a list"
        json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
        sys.stdout.write("\n")
        return 1

    item = select_next_pending_item(items)
    gate = evaluate_gate(item)
    result["gate"] = gate
    if item is None or not gate.get("gate_passed"):
        result["error"] = "no materializable handoff"
        json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
        sys.stdout.write("\n")
        return 1

    created_at = now_iso(args.timezone)
    handoff = build_handoff_json(item, queue_path, created_at)
    result["ok"] = True
    result["handoff_id"] = handoff.get("handoff_id")
    result["task_id"] = handoff.get("task_id")
    result["codex_start_allowed"] = False

    if not args.dry_run:
        runtime_dir.mkdir(parents=True, exist_ok=True)
        (runtime_dir / "current_codex_handoff.json").write_text(
            json.dumps(handoff, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (runtime_dir / "current_codex_handoff.md").write_text(
            build_handoff_markdown(handoff),
            encoding="utf-8",
        )
        result["side_effects"]["runtime_files_written"] = True

    json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
