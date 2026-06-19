#!/usr/bin/env python3
"""Prepare a branch plan and PR draft for a queued AI development task.

This script is intentionally conservative. It reads a queue file, selects one
pending task, validates its safety envelope, and writes review artifacts under
the runtime directory. It does not create branches, edit source files, commit,
push, merge, run production workflows, send notifications, or place orders.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_QUEUE_PATH = "orchestrator/queue/pending_tasks.example.json"
DEFAULT_RUNTIME_DIR = "~/.local/state/stock-ai-orchestrator"
ALLOWED_RISK_LEVELS = {"low"}
REQUIRED_BLOCKED_PATHS = {
    ".env",
    "data/stock_analysis.db",
    "data/backups/",
    "analysis/output/",
}
DEFAULT_ALLOWED_PREFIXES = {
    "docs/",
    "tests/",
    "scripts/orchestrator/",
    "orchestrator/queue/",
    "orchestrator/templates/",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_git(args: list[str], repo_root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(repo_root),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be object: {path}")
    return data


def safe_branch_value(value: Any) -> str:
    raw = str(value or "ai-task")
    cleaned = re.sub(r"[^A-Za-z0-9._/-]+", "-", raw).strip("-/.").lower()
    cleaned = cleaned.replace("..", ".")
    return cleaned or "ai-task"


def validate_task(task: dict[str, Any], queue_defaults: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if task.get("status") != "pending":
        reasons.append("task status must be pending")
    if task.get("risk_level") not in ALLOWED_RISK_LEVELS:
        reasons.append("task risk_level must be low")
    if queue_defaults.get("allow_direct_main_push") is not False:
        reasons.append("queue must disallow direct main push")
    if queue_defaults.get("allow_production_commands") is not False:
        reasons.append("queue must disallow production commands")
    if queue_defaults.get("allow_line_notifications") is not False:
        reasons.append("queue must disallow LINE notifications")
    if queue_defaults.get("allow_trading_execution") is not False:
        reasons.append("queue must disallow trading execution")

    allowed_paths = task.get("allowed_paths", [])
    if not isinstance(allowed_paths, list) or not allowed_paths:
        reasons.append("allowed_paths must be a non-empty list")
    else:
        for path in allowed_paths:
            if path not in DEFAULT_ALLOWED_PREFIXES:
                reasons.append(f"allowed path not approved for scaffold: {path}")

    blocked_paths = task.get("blocked_paths", [])
    if not isinstance(blocked_paths, list):
        reasons.append("blocked_paths must be a list")
    else:
        missing = sorted(REQUIRED_BLOCKED_PATHS.difference(set(blocked_paths)))
        if missing:
            reasons.append("blocked_paths missing: " + ", ".join(missing))

    validation_commands = task.get("validation_commands", [])
    if not isinstance(validation_commands, list) or not validation_commands:
        reasons.append("validation_commands must be a non-empty list")

    success_criteria = task.get("success_criteria", [])
    if not isinstance(success_criteria, list) or not success_criteria:
        reasons.append("success_criteria must be a non-empty list")

    return reasons


def build_pr_body(task: dict[str, Any], branch_name: str) -> str:
    validation_commands = task.get("validation_commands", [])
    success_criteria = task.get("success_criteria", [])
    allowed_paths = task.get("allowed_paths", [])
    blocked_paths = task.get("blocked_paths", [])
    lines = [
        f"# AI Development Task: {task.get('task_id')}",
        "",
        "## Objective",
        "",
        str(task.get("objective", "")),
        "",
        "## Branch",
        "",
        f"`{branch_name}`",
        "",
        "## Allowed paths",
        "",
    ]
    lines.extend(f"- `{path}`" for path in allowed_paths)
    lines.extend(["", "## Blocked paths", ""])
    lines.extend(f"- `{path}`" for path in blocked_paths)
    lines.extend(["", "## Validation commands", ""])
    lines.extend(f"- `{cmd}`" for cmd in validation_commands)
    lines.extend(["", "## Success criteria", ""])
    lines.extend(f"- {item}" for item in success_criteria)
    lines.extend([
        "",
        "## Safety notes",
        "",
        "This PR must not send LINE notifications, place orders, run production workflows, modify scheduler settings, read secrets, or modify production database files.",
    ])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare AI task branch and PR review artifacts.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--queue-path", default=DEFAULT_QUEUE_PATH)
    parser.add_argument("--runtime-dir", default=DEFAULT_RUNTIME_DIR)
    parser.add_argument("--task-id", default=None)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    queue_path = (repo_root / args.queue_path).resolve()
    runtime_dir = Path(args.runtime_dir).expanduser().resolve()
    runtime_dir.mkdir(parents=True, exist_ok=True)

    queue = load_json(queue_path)
    defaults = queue.get("defaults", {}) if isinstance(queue.get("defaults", {}), dict) else {}
    tasks = queue.get("tasks", [])
    if not isinstance(tasks, list):
        raise ValueError("queue tasks must be a list")

    selected = None
    for task in tasks:
        if not isinstance(task, dict):
            continue
        if args.task_id and task.get("task_id") != args.task_id:
            continue
        if task.get("status") == "pending":
            selected = task
            break

    if selected is None:
        result = {
            "ok": True,
            "prepared": False,
            "reason": "no matching pending task",
            "side_effects": {"branch_created": False, "commit_created": False, "push_run": False, "merge_run": False},
        }
        json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
        sys.stdout.write("\n")
        return 0

    reasons = validate_task(selected, defaults)
    branch_name = safe_branch_value(selected.get("branch_name") or ("ai-dev/" + str(selected.get("task_id", "task"))))
    base_branch = selected.get("target_base_branch") or defaults.get("target_base_branch") or "main"

    git_status = run_git(["status", "--short"], repo_root)
    git_clean = git_status.returncode == 0 and git_status.stdout.strip() == ""
    if not git_clean:
        reasons.append("git working tree is not clean")

    current_branch_proc = run_git(["rev-parse", "--abbrev-ref", "HEAD"], repo_root)
    current_branch = current_branch_proc.stdout.strip() if current_branch_proc.returncode == 0 else None
    if current_branch != base_branch:
        reasons.append(f"current branch must be {base_branch}, got {current_branch}")

    pr_body = build_pr_body(selected, branch_name)
    plan = {
        "schema_version": 1,
        "prepared_at": now_iso(),
        "prepared": not reasons,
        "task": selected,
        "base_branch": base_branch,
        "branch_name": branch_name,
        "current_branch": current_branch,
        "git_clean": git_clean,
        "validation_blocked_reasons": reasons,
        "recommended_commands": [
            f"git switch {base_branch}",
            f"git switch -c {branch_name}",
            "# apply AI-assisted changes within allowed paths only",
            f"python3 scripts/orchestrator/validate_ai_branch.py --base {base_branch} --head HEAD --pretty",
            f"python3 scripts/orchestrator/check_forbidden_changes.py --base {base_branch} --head HEAD --pretty",
            "git status",
            "# commit, push branch, and open PR only after validation passes",
        ],
        "pr_title": f"AI Dev: {selected.get('task_id')} - {selected.get('objective', '')[:60]}",
        "pr_body": pr_body,
        "side_effects": {
            "branch_created": False,
            "files_modified": False,
            "commit_created": False,
            "push_run": False,
            "merge_run": False,
            "production_command_run": False,
            "notification_sent": False,
            "trading_execution_run": False,
        },
    }

    plan_path = runtime_dir / "ai_task_branch_plan.json"
    pr_body_path = runtime_dir / "ai_task_pr_body.md"
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    pr_body_path.write_text(pr_body, encoding="utf-8")

    result = {
        "ok": True,
        "prepared": not reasons,
        "task_id": selected.get("task_id"),
        "base_branch": base_branch,
        "branch_name": branch_name,
        "plan_path": str(plan_path),
        "pr_body_path": str(pr_body_path),
        "blocked_reasons": reasons,
        "side_effects": plan["side_effects"],
    }
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    return 0 if not reasons else 2


if __name__ == "__main__":
    raise SystemExit(main())
