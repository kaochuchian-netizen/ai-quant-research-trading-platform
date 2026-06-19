#!/usr/bin/env python3
"""Promote the next queued AI development task into runtime review artifacts.

This script creates a branch plan and PR body from the formal queue. It does not
create branches, edit implementation files, commit, push, open PRs, merge, run
production workflows, send notifications, or place orders.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_PENDING_QUEUE_PATH = "orchestrator/queue/pending_tasks.json"
DEFAULT_COMPLETED_QUEUE_PATH = "orchestrator/queue/completed_tasks.json"
DEFAULT_RUNTIME_DIR = "~/.local/state/stock-ai-orchestrator"

REQUIRED_SCHEMA_VERSION = 1
REQUIRED_ROOT_STATUS = "active"
ALLOWED_RISK_LEVELS = {"low"}
REQUIRED_BASE_BRANCH = "main"
REQUIRED_BRANCH_PREFIX = "ai-dev/"
SAFE_BRANCH_RE = re.compile(r"^[A-Za-z0-9._/-]+$")

REQUIRED_BLOCKED_PATHS = {
    ".env",
    "data/stock_analysis.db",
    "data/backups/",
    "analysis/output/",
}
ALLOWED_PATHS = {
    "docs/",
    "tests/",
    "scripts/orchestrator/",
    "orchestrator/queue/",
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


def atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    tmp_path = path.with_name(path.name + ".tmp")
    tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp_path, path)


def atomic_write_text(path: Path, text: str) -> None:
    tmp_path = path.with_name(path.name + ".tmp")
    tmp_path.write_text(text, encoding="utf-8")
    os.replace(tmp_path, path)


def queue_root_reasons(queue: dict[str, Any], label: str) -> list[str]:
    reasons: list[str] = []
    if queue.get("schema_version") != REQUIRED_SCHEMA_VERSION:
        reasons.append(f"{label} schema_version must be {REQUIRED_SCHEMA_VERSION}")
    if queue.get("status") != REQUIRED_ROOT_STATUS:
        reasons.append(f"{label} status must be {REQUIRED_ROOT_STATUS}")
    return reasons


def effective_value(task: dict[str, Any], defaults: dict[str, Any], key: str, fallback: Any = None) -> Any:
    if key in task:
        return task[key]
    if key in defaults:
        return defaults[key]
    return fallback


def path_set(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {str(item) for item in value}


def validate_allowed_paths(value: Any) -> list[str]:
    reasons: list[str] = []
    if not isinstance(value, list) or not value:
        return ["task allowed_paths must be a non-empty list"]
    for path in value:
        if str(path) not in ALLOWED_PATHS:
            reasons.append(f"allowed path is not permitted: {path}")
    return reasons


def validate_task(task: dict[str, Any], defaults: dict[str, Any]) -> list[str]:
    reasons: list[str] = []

    if task.get("status") != "pending":
        reasons.append("task status must be pending")
    if task.get("risk_level") not in ALLOWED_RISK_LEVELS:
        reasons.append("task risk_level must be low")

    target_base_branch = effective_value(task, defaults, "target_base_branch", REQUIRED_BASE_BRANCH)
    if target_base_branch != REQUIRED_BASE_BRANCH:
        reasons.append("target_base_branch must be main")

    branch_name = str(task.get("branch_name") or "")
    if branch_name == REQUIRED_BASE_BRANCH:
        reasons.append("branch_name must not be main")
    if not branch_name.startswith(REQUIRED_BRANCH_PREFIX):
        reasons.append("branch_name must start with ai-dev/")
    if not SAFE_BRANCH_RE.fullmatch(branch_name):
        reasons.append("branch_name contains unsafe characters")

    required_flags = {
        "requires_pull_request": True,
        "allow_direct_main_push": False,
        "allow_production_commands": False,
        "allow_line_notifications": False,
        "allow_trading_execution": False,
    }
    for key, expected in required_flags.items():
        if effective_value(task, defaults, key) is not expected:
            reasons.append(f"{key} must be {str(expected).lower()}")

    queue_blocked_paths = path_set(defaults.get("blocked_paths", []))
    task_blocked_paths = path_set(task.get("blocked_paths", []))
    blocked_paths = queue_blocked_paths.union(task_blocked_paths)
    missing_blocked = sorted(REQUIRED_BLOCKED_PATHS.difference(blocked_paths))
    if missing_blocked:
        reasons.append("blocked_paths missing: " + ", ".join(missing_blocked))

    reasons.extend(validate_allowed_paths(task.get("allowed_paths")))

    validation_commands = task.get("validation_commands", [])
    if not isinstance(validation_commands, list) or not validation_commands:
        reasons.append("validation_commands must be a non-empty list")

    success_criteria = task.get("success_criteria", [])
    if not isinstance(success_criteria, list) or not success_criteria:
        reasons.append("success_criteria must be a non-empty list")

    return reasons


def select_task(tasks: list[Any], task_id: str | None) -> tuple[int | None, dict[str, Any] | None]:
    candidates: list[tuple[int, int, dict[str, Any]]] = []
    for index, item in enumerate(tasks):
        if not isinstance(item, dict):
            continue
        if item.get("status") != "pending":
            continue
        if task_id and item.get("task_id") != task_id:
            continue
        priority = item.get("priority", 0)
        try:
            priority_value = int(priority)
        except Exception:
            priority_value = 0
        candidates.append((-priority_value, index, item))

    if not candidates:
        return None, None
    _, selected_index, selected = sorted(candidates, key=lambda item: (item[0], item[1]))[0]
    return selected_index, selected


def build_pr_body(task: dict[str, Any], base_branch: str, branch_name: str) -> str:
    lines = [
        f"# AI Development Task: {task.get('task_id')}",
        "",
        "## Objective",
        "",
        str(task.get("objective", "")),
        "",
        "## Branch",
        "",
        f"Base: `{base_branch}`",
        f"Head: `{branch_name}`",
        "",
        "## Allowed paths",
        "",
    ]
    lines.extend(f"- `{path}`" for path in task.get("allowed_paths", []))
    lines.extend(["", "## Blocked paths", ""])
    lines.extend(f"- `{path}`" for path in task.get("blocked_paths", []))
    lines.extend(["", "## Validation commands", ""])
    lines.extend(f"- `{cmd}`" for cmd in task.get("validation_commands", []))
    lines.extend(["", "## Success criteria", ""])
    lines.extend(f"- {item}" for item in task.get("success_criteria", []))
    lines.extend([
        "",
        "## Safety notes",
        "",
        "This PR must not send LINE notifications, place orders, run production workflows, modify scheduler settings, read secrets, or modify production database files.",
    ])
    return "\n".join(lines) + "\n"


def read_existing_plan_task_id(plan_path: Path) -> str | None:
    if not plan_path.exists():
        return None
    data = load_json(plan_path)
    task = data.get("task", {})
    if isinstance(task, dict):
        task_id = task.get("task_id")
        return str(task_id) if task_id else None
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Promote next AI task from queue into runtime artifacts.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--pending-queue-path", default=DEFAULT_PENDING_QUEUE_PATH)
    parser.add_argument("--completed-queue-path", default=DEFAULT_COMPLETED_QUEUE_PATH)
    parser.add_argument("--runtime-dir", default=DEFAULT_RUNTIME_DIR)
    parser.add_argument("--task-id", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    pending_path = (repo_root / args.pending_queue_path).resolve()
    completed_path = (repo_root / args.completed_queue_path).resolve()
    runtime_dir = Path(args.runtime_dir).expanduser().resolve()
    plan_path = runtime_dir / "ai_task_branch_plan.json"
    pr_body_path = runtime_dir / "ai_task_pr_body.md"

    reasons: list[str] = []
    pending_queue = load_json(pending_path)
    completed_queue = load_json(completed_path)
    reasons.extend(queue_root_reasons(pending_queue, "pending queue"))
    reasons.extend(queue_root_reasons(completed_queue, "completed queue"))

    defaults = pending_queue.get("defaults", {})
    if not isinstance(defaults, dict):
        defaults = {}
        reasons.append("pending queue defaults must be an object")
    defaults = {**defaults, "blocked_paths": pending_queue.get("blocked_paths", [])}

    tasks = pending_queue.get("tasks", [])
    if not isinstance(tasks, list):
        tasks = []
        reasons.append("pending queue tasks must be a list")

    status_proc = run_git(["status", "--short"], repo_root)
    git_status_short = status_proc.stdout.strip().splitlines() if status_proc.returncode == 0 else []
    git_clean = status_proc.returncode == 0 and not git_status_short
    if not git_clean:
        reasons.append("git working tree must be clean")

    selected_index, selected_task = select_task(tasks, args.task_id)
    if selected_task is None:
        if args.task_id:
            reasons.append(f"no pending task found for task_id: {args.task_id}")
        else:
            reasons.append("no pending task found")

    task_reasons: list[str] = []
    existing_plan_task_id = None
    if selected_task is not None:
        task_reasons = validate_task(selected_task, defaults)
        reasons.extend(task_reasons)
        existing_plan_task_id = read_existing_plan_task_id(plan_path)
        selected_task_id = str(selected_task.get("task_id") or "")
        if existing_plan_task_id and existing_plan_task_id != selected_task_id and not args.force:
            reasons.append(
                "runtime plan already exists for different task_id: "
                f"{existing_plan_task_id}; use --force to overwrite"
            )

    prepared = selected_task is not None and not reasons
    base_branch = None
    branch_name = None
    pr_title = None
    pr_body = None
    if selected_task is not None:
        base_branch = str(effective_value(selected_task, defaults, "target_base_branch", REQUIRED_BASE_BRANCH))
        branch_name = str(selected_task.get("branch_name") or "")
        pr_title = f"AI Dev: {selected_task.get('task_id')} - {str(selected_task.get('objective', ''))[:60]}"
        pr_body = build_pr_body(selected_task, base_branch, branch_name)

    side_effects = {
        "pending_queue_modified": False,
        "runtime_plan_written": False,
        "runtime_pr_body_written": False,
        "branch_created": False,
        "source_files_modified": False,
        "commit_created": False,
        "push_run": False,
        "pr_created": False,
        "merge_run": False,
        "production_command_run": False,
        "notification_sent": False,
        "trading_execution_run": False,
        "scheduler_modified": False,
    }

    if prepared and not args.dry_run and selected_index is not None and selected_task is not None:
        runtime_dir.mkdir(parents=True, exist_ok=True)
        promoted_at = now_iso()
        plan = {
            "schema_version": 1,
            "prepared_at": promoted_at,
            "prepared": True,
            "task": selected_task,
            "base_branch": base_branch,
            "branch_name": branch_name,
            "validation_blocked_reasons": [],
            "recommended_commands": [
                f"git switch {base_branch}",
                f"git switch -c {branch_name}",
                "# apply AI-assisted changes within allowed paths only",
                f"python3 scripts/orchestrator/validate_ai_branch.py --base {base_branch} --head HEAD --pretty",
                f"python3 scripts/orchestrator/check_forbidden_changes.py --base {base_branch} --head HEAD --pretty",
                "git status",
                "# commit, push branch, and open PR only after validation passes",
            ],
            "pr_title": pr_title,
            "pr_body": pr_body,
            "side_effects": side_effects,
        }
        atomic_write_json(plan_path, plan)
        atomic_write_text(pr_body_path, pr_body or "")
        updated_task = dict(selected_task)
        updated_task["status"] = "promoted"
        updated_task["promoted_at"] = promoted_at
        updated_task["runtime_plan_path"] = str(plan_path)
        updated_task["runtime_pr_body_path"] = str(pr_body_path)
        tasks[selected_index] = updated_task
        pending_queue["tasks"] = tasks
        atomic_write_json(pending_path, pending_queue)
        side_effects["pending_queue_modified"] = True
        side_effects["runtime_plan_written"] = True
        side_effects["runtime_pr_body_written"] = True

    output = {
        "ok": True,
        "dry_run": args.dry_run,
        "promoted": prepared and not args.dry_run,
        "would_promote": prepared if args.dry_run else False,
        "task_id": selected_task.get("task_id") if selected_task else None,
        "priority": selected_task.get("priority") if selected_task else None,
        "base_branch": base_branch,
        "branch_name": branch_name,
        "pending_queue_path": str(pending_path),
        "completed_queue_path": str(completed_path),
        "runtime_plan_path": str(plan_path),
        "runtime_pr_body_path": str(pr_body_path),
        "existing_runtime_plan_task_id": existing_plan_task_id,
        "safety_check": {
            "passed": not reasons,
            "reasons": reasons,
            "task_reasons": task_reasons,
            "git_clean": git_clean,
            "git_status_short": git_status_short,
            "allowed_paths": sorted(ALLOWED_PATHS),
            "required_blocked_paths": sorted(REQUIRED_BLOCKED_PATHS),
        },
        "side_effects": side_effects,
    }
    json.dump(output, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    return 0 if not reasons else 2


if __name__ == "__main__":
    raise SystemExit(main())
