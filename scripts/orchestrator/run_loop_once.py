#!/usr/bin/env python3
"""Run one safe Orchestrator loop iteration.

This script checks local runtime state and repository state, then writes loop_status.json.
It does not pull, start Codex, send notifications, or run production workflows.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


DEFAULT_RUNTIME_DIR = "~/.local/state/stock-ai-orchestrator"
DEFAULT_TIMEZONE = "Asia/Taipei"


def now_iso(timezone_name: str) -> str:
    return datetime.now(ZoneInfo(timezone_name)).replace(microsecond=0).isoformat()


def run_command(args: list[str], repo_root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=str(repo_root),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def load_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"ok": False, "state": "missing", "path": str(path)}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
        return {"ok": False, "state": "invalid", "reason": "not an object", "path": str(path)}
    except Exception as exc:
        return {"ok": False, "state": "invalid", "reason": str(exc), "path": str(path)}


def read_text_status(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False, "path": str(path)}
    try:
        text = path.read_text(encoding="utf-8")
        return {
            "exists": True,
            "path": str(path),
            "bytes": len(text.encode("utf-8")),
            "has_content": bool(text.strip()),
        }
    except Exception as exc:
        return {"exists": True, "path": str(path), "error": str(exc)}


def check_git_state(repo_root: Path, expected_branch: str) -> dict[str, Any]:
    branch = run_command(["git", "rev-parse", "--abbrev-ref", "HEAD"], repo_root)
    status = run_command(["git", "status", "--short"], repo_root)
    head = run_command(["git", "rev-parse", "HEAD"], repo_root)

    current_branch = branch.stdout.strip() if branch.returncode == 0 else None
    status_short = status.stdout.strip() if status.returncode == 0 else ""
    ok = branch.returncode == 0 and status.returncode == 0 and current_branch == expected_branch and status_short == ""

    reasons: list[str] = []
    if branch.returncode != 0:
        reasons.append("branch check failed")
    elif current_branch != expected_branch:
        reasons.append(f"branch mismatch: {current_branch} != {expected_branch}")
    if status.returncode != 0:
        reasons.append("git status failed")
    elif status_short:
        reasons.append("working tree is not clean")

    return {
        "ok": ok,
        "expected_branch": expected_branch,
        "current_branch": current_branch,
        "head": head.stdout.strip() if head.returncode == 0 else None,
        "status_short": status_short,
        "blocked_reasons": reasons,
    }


def write_json(path: Path, data: dict[str, Any], pretty: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2 if pretty else None) + "\n", encoding="utf-8")


def append_log(path: Path, message: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(message + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one safe Orchestrator loop iteration.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--runtime-dir", default=DEFAULT_RUNTIME_DIR)
    parser.add_argument("--expected-branch", default="main")
    parser.add_argument("--timezone", default=DEFAULT_TIMEZONE)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    runtime_dir = Path(args.runtime_dir).expanduser().resolve()
    runtime_dir.mkdir(parents=True, exist_ok=True)

    paths = {
        "current_task_state": runtime_dir / "current_task_state.json",
        "current_codex_handoff": runtime_dir / "current_codex_handoff.md",
        "latest_approval_state": runtime_dir / "latest_approval_state.json",
        "latest_validation_result": runtime_dir / "latest_validation_result.json",
        "latest_decision_summary": runtime_dir / "latest_decision_summary.json",
        "latest_notice": runtime_dir / "latest_notice.md",
        "loop_status": runtime_dir / "loop_status.json",
        "loop_log": runtime_dir / "loop.log",
    }

    git_state = check_git_state(repo_root, args.expected_branch)
    task_state = load_json_if_exists(paths["current_task_state"])
    approval_state = load_json_if_exists(paths["latest_approval_state"])
    validation_result = load_json_if_exists(paths["latest_validation_result"])
    decision_summary = load_json_if_exists(paths["latest_decision_summary"])
    handoff_status = read_text_status(paths["current_codex_handoff"])
    notice_status = read_text_status(paths["latest_notice"])

    status = {
        "ok": bool(git_state.get("ok")),
        "checked_at": now_iso(args.timezone),
        "mode": "single_iteration",
        "runtime_dir": str(runtime_dir),
        "repo_root": str(repo_root),
        "loop_running": False,
        "codex_running": False,
        "git_state": git_state,
        "runtime_state": {
            "current_task_state": task_state,
            "latest_approval_state": approval_state,
            "latest_validation_result": validation_result,
            "latest_decision_summary": decision_summary,
            "current_codex_handoff": handoff_status,
            "latest_notice": notice_status,
        },
        "actions": {
            "git_pull_run": False,
            "codex_started": False,
            "notification_sent": False,
            "production_command_run": False,
        },
        "next_action": "ready_for_dry_run_loop_command",
    }

    write_json(paths["loop_status"], status, args.pretty)
    append_log(paths["loop_log"], f"{status['checked_at']} single_iteration ok={status['ok']}")

    json.dump(status, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    return 0 if status["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
