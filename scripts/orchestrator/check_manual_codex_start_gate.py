#!/usr/bin/env python3
"""Check whether a materialized handoff is ready for a manual Codex start.

This script is read-only. It never starts Codex and never changes repository,
runtime, queue, scheduler, notification, or production state.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


DEFAULT_RUNTIME_DIR = "~/.local/state/stock-ai-orchestrator"
REQUIRED_HANDOFF_FIELDS = [
    "handoff_id",
    "task_id",
    "task_name",
    "status",
    "manual_start_required",
    "agent_started",
    "agent_finished",
    "allowed_paths",
    "blocked_paths",
    "objective",
    "validation_commands",
    "safety_boundaries",
]


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"ok": False, "error": "handoff json missing", "path": str(path)}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"ok": False, "error": "handoff json root is not an object", "path": str(path)}
        return {"ok": True, "data": data, "path": str(path)}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "path": str(path)}


def check_manual_start_gate(handoff: dict[str, Any], markdown_path: Path) -> dict[str, Any]:
    blocked: list[str] = []

    for field in REQUIRED_HANDOFF_FIELDS:
        if field not in handoff:
            blocked.append(f"missing required field: {field}")

    if handoff.get("status") != "materialized":
        blocked.append("handoff status must be materialized")
    if handoff.get("manual_start_required") is not True:
        blocked.append("manual_start_required must be true")
    if handoff.get("agent_started") is not False:
        blocked.append("agent_started must be false")
    if handoff.get("agent_finished") is not False:
        blocked.append("agent_finished must be false")
    if handoff.get("execution", {}).get("codex_start_allowed") is not False:
        blocked.append("execution.codex_start_allowed must remain false before manual approval")
    if handoff.get("execution", {}).get("codex_started") is not False:
        blocked.append("execution.codex_started must be false")

    if not isinstance(handoff.get("allowed_paths"), list) or not handoff.get("allowed_paths"):
        blocked.append("allowed_paths must be a non-empty list")
    if not isinstance(handoff.get("blocked_paths"), list) or not handoff.get("blocked_paths"):
        blocked.append("blocked_paths must be a non-empty list")
    if not isinstance(handoff.get("validation_commands"), list) or not handoff.get("validation_commands"):
        blocked.append("validation_commands must be a non-empty list")
    if not isinstance(handoff.get("safety_boundaries"), list) or not handoff.get("safety_boundaries"):
        blocked.append("safety_boundaries must be a non-empty list")
    if not markdown_path.exists():
        blocked.append("handoff markdown missing")

    return {
        "ok": True,
        "manual_start_ready": not blocked,
        "codex_start_allowed": False,
        "blocked_reasons": blocked,
        "handoff_id": handoff.get("handoff_id"),
        "task_id": handoff.get("task_id"),
        "task_name": handoff.get("task_name"),
        "notes": "manual_start_ready means a human can review the handoff. This script never starts Codex.",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check manual Codex start gate.")
    parser.add_argument("--runtime-dir", default=DEFAULT_RUNTIME_DIR)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    runtime_dir = Path(args.runtime_dir).expanduser().resolve()
    json_path = runtime_dir / "current_codex_handoff.json"
    markdown_path = runtime_dir / "current_codex_handoff.md"
    loaded = load_json(json_path)

    result: dict[str, Any] = {
        "ok": False,
        "runtime_dir": str(runtime_dir),
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "manual_start_ready": False,
        "codex_start_allowed": False,
        "side_effects": {
            "codex_started": False,
            "runtime_modified": False,
            "git_command_run": False,
            "notification_sent": False,
            "production_command_run": False,
        },
    }

    if not loaded.get("ok"):
        result["error"] = loaded.get("error")
        result["blocked_reasons"] = [loaded.get("error")]
        json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
        sys.stdout.write("\n")
        return 1

    gate = check_manual_start_gate(loaded["data"], markdown_path)
    result.update(gate)
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
