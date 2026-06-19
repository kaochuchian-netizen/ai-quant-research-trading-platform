#!/usr/bin/env python3
"""Initialize the local Orchestrator runtime state directory.

This script only creates local state files for the VM-side Orchestrator loop.
It does not start a loop, run Codex, run Git, send email, or touch production data.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


DEFAULT_RUNTIME_DIR = "~/.local/state/stock-ai-orchestrator"
DEFAULT_TIMEZONE = "Asia/Taipei"
RUNTIME_FILES = {
    "current_task_state": "current_task_state.json",
    "current_codex_handoff": "current_codex_handoff.md",
    "latest_approval_state": "latest_approval_state.json",
    "latest_validation_result": "latest_validation_result.json",
    "latest_decision_summary": "latest_decision_summary.json",
    "latest_notice": "latest_notice.md",
    "loop_status": "loop_status.json",
    "loop_log": "loop.log",
}


def now_iso(timezone_name: str) -> str:
    return datetime.now(ZoneInfo(timezone_name)).replace(microsecond=0).isoformat()


def write_json(path: Path, data: dict[str, Any], pretty: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2 if pretty else None) + "\n",
        encoding="utf-8",
    )


def ensure_text_file(path: Path, content: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(content, encoding="utf-8")


def build_initial_status(runtime_dir: Path, timezone_name: str) -> dict[str, Any]:
    files = {name: str(runtime_dir / filename) for name, filename in RUNTIME_FILES.items()}
    return {
        "ok": True,
        "initialized_at": now_iso(timezone_name),
        "runtime_dir": str(runtime_dir),
        "mode": "initialized",
        "loop_running": False,
        "codex_running": False,
        "next_action": "ready_for_single_iteration_runner",
        "files": files,
        "side_effects": {
            "loop_started": False,
            "codex_started": False,
            "git_command_run": False,
            "email_sent": False,
            "production_command_run": False,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Initialize VM-local Orchestrator runtime state.")
    parser.add_argument("--runtime-dir", default=DEFAULT_RUNTIME_DIR)
    parser.add_argument("--timezone", default=DEFAULT_TIMEZONE)
    parser.add_argument("--force", action="store_true", help="Overwrite loop_status.json if it already exists.")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    runtime_dir = Path(args.runtime_dir).expanduser().resolve()
    runtime_dir.mkdir(parents=True, exist_ok=True)

    paths = {name: runtime_dir / filename for name, filename in RUNTIME_FILES.items()}

    ensure_text_file(paths["current_codex_handoff"], "# Current Codex handoff\n\nNo handoff has been generated yet.\n")
    ensure_text_file(paths["latest_notice"])
    ensure_text_file(paths["loop_log"])

    for key in [
        "current_task_state",
        "latest_approval_state",
        "latest_validation_result",
        "latest_decision_summary",
    ]:
        if not paths[key].exists():
            write_json(paths[key], {"ok": False, "state": "not_available"}, args.pretty)

    status = build_initial_status(runtime_dir, args.timezone)
    if args.force or not paths["loop_status"].exists():
        write_json(paths["loop_status"], status, args.pretty)
    else:
        status["loop_status_preserved"] = True

    json.dump(status, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
