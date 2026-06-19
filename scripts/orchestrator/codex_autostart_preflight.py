#!/usr/bin/env python3
"""Preflight checks for controlled Codex autostart.

This script checks whether the local VM is allowed to open an interactive Codex
session in tmux. It is intentionally conservative and does not start Codex, run
production commands, send notifications, commit, push, or merge.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


DEFAULT_REPO_DIR = "~/stock-ai"
DEFAULT_RUNTIME_DIR = "~/.local/state/stock-ai-orchestrator"
ENABLE_FLAG = "enable_codex_autostart"
SESSION_NAME = "stock-ai-codex"
ALLOWED_TASK_TYPE = "orchestrator_low_risk"
REQUIRED_BLOCKED_PATHS = {
    ".env",
    "data/stock_analysis.db",
    "data/backups/",
    "analysis/output/",
}


def run_command(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"ok": False, "error": "missing", "path": str(path)}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"ok": False, "error": "not an object", "path": str(path)}
        return {"ok": True, "data": data, "path": str(path)}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "path": str(path)}


def safe_branch_value(value: Any) -> str:
    raw = str(value or "manual-task")
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", raw).strip("-.").lower()
    return cleaned or "manual-task"


def main() -> int:
    parser = argparse.ArgumentParser(description="Check controlled Codex autostart preflight.")
    parser.add_argument("--repo-dir", default=DEFAULT_REPO_DIR)
    parser.add_argument("--runtime-dir", default=DEFAULT_RUNTIME_DIR)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    repo_dir = Path(args.repo_dir).expanduser().resolve()
    runtime_dir = Path(args.runtime_dir).expanduser().resolve()
    enable_flag_path = runtime_dir / ENABLE_FLAG
    handoff_json_path = runtime_dir / "current_codex_handoff.json"
    handoff_md_path = runtime_dir / "current_codex_handoff.md"

    blocked: list[str] = []

    if not enable_flag_path.exists():
        blocked.append("enable flag missing")
    if not repo_dir.exists():
        blocked.append("repo dir missing")

    branch_name = None
    git_clean = False
    current_branch = None
    tmux_session_exists = False

    git_root = run_command(["git", "rev-parse", "--show-toplevel"], repo_dir) if repo_dir.exists() else None
    if git_root is None or git_root.returncode != 0:
        blocked.append("repo dir is not a git repository")
    else:
        branch = run_command(["git", "rev-parse", "--abbrev-ref", "HEAD"], repo_dir)
        status = run_command(["git", "status", "--short"], repo_dir)
        current_branch = branch.stdout.strip() if branch.returncode == 0 else None
        git_clean = status.returncode == 0 and status.stdout.strip() == ""
        if current_branch != "main":
            blocked.append(f"expected branch main, got {current_branch}")
        if not git_clean:
            blocked.append("git working tree is not clean")

    if run_command(["command", "-v", "codex"]).returncode != 0:
        blocked.append("codex command not found")
    if run_command(["command", "-v", "tmux"]).returncode != 0:
        blocked.append("tmux command not found")

    tmux_check = run_command(["tmux", "has-session", "-t", SESSION_NAME])
    tmux_session_exists = tmux_check.returncode == 0
    if tmux_session_exists:
        blocked.append("codex tmux session already exists")

    handoff_loaded = load_json(handoff_json_path)
    handoff = handoff_loaded.get("data") if handoff_loaded.get("ok") else None
    if not handoff_loaded.get("ok"):
        blocked.append("handoff json missing or invalid")
    if not handoff_md_path.exists() or handoff_md_path.stat().st_size == 0:
        blocked.append("handoff markdown missing or empty")

    if isinstance(handoff, dict):
        if handoff.get("allowed_task_type") != ALLOWED_TASK_TYPE:
            blocked.append("handoff task type is not allowed")
        if handoff.get("manual_start_required") is not True:
            blocked.append("handoff manual_start_required must be true")
        if handoff.get("agent_started") is not False:
            blocked.append("handoff agent_started must be false")
        if handoff.get("agent_finished") is not False:
            blocked.append("handoff agent_finished must be false")
        allowed_paths = handoff.get("allowed_paths", [])
        if not isinstance(allowed_paths, list) or not allowed_paths:
            blocked.append("handoff allowed_paths must be non-empty")
        blocked_paths = handoff.get("blocked_paths", [])
        if not isinstance(blocked_paths, list):
            blocked.append("handoff blocked_paths must be a list")
        else:
            missing = sorted(REQUIRED_BLOCKED_PATHS.difference(set(blocked_paths)))
            if missing:
                blocked.append("handoff blocked_paths missing: " + ", ".join(missing))
        task_key = handoff.get("task_id") or handoff.get("handoff_id")
        branch_name = "codex/" + safe_branch_value(task_key)

    result = {
        "ok": True,
        "autostart_allowed": not blocked,
        "codex_started": False,
        "repo_dir": str(repo_dir),
        "runtime_dir": str(runtime_dir),
        "enable_flag_path": str(enable_flag_path),
        "current_branch": current_branch,
        "git_clean": git_clean,
        "tmux_session_name": SESSION_NAME,
        "tmux_session_exists": tmux_session_exists,
        "handoff_json_path": str(handoff_json_path),
        "handoff_md_path": str(handoff_md_path),
        "branch_name": branch_name,
        "blocked_reasons": blocked,
        "side_effects": {
            "codex_started": False,
            "branch_created": False,
            "commit_created": False,
            "push_run": False,
            "merge_run": False,
            "production_command_run": False,
            "notification_sent": False,
        },
    }
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
