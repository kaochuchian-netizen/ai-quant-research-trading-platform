#!/usr/bin/env python3
"""Inspect runtime AI development queue state without side effects."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


DEFAULT_RUNTIME_DIR = "~/.local/state/stock-ai-orchestrator"


def load_json_if_exists(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.exists():
        return None, "missing"
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        return None, str(exc)
    if not isinstance(data, dict):
        return None, "JSON root must be object"
    return data, None


def run_git(args: list[str], repo_root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(repo_root),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def summarize_tasks(tasks: Any) -> list[dict[str, Any]]:
    if not isinstance(tasks, list):
        return []
    summary: list[dict[str, Any]] = []
    for item in tasks:
        if not isinstance(item, dict):
            continue
        summary.append(
            {
                "task_id": item.get("task_id"),
                "title": item.get("title"),
                "status": item.get("status"),
                "priority": item.get("priority"),
                "risk_level": item.get("risk_level"),
                "branch_name": item.get("branch_name"),
                "target_base_branch": item.get("target_base_branch"),
                "allow_auto_merge": item.get("allow_auto_merge"),
                "allowed_paths": item.get("allowed_paths", []),
            }
        )
    return summary


def summarize_completed(tasks: Any) -> list[dict[str, Any]]:
    if not isinstance(tasks, list):
        return []
    summary: list[dict[str, Any]] = []
    for item in tasks:
        if not isinstance(item, dict):
            continue
        summary.append(
            {
                "task_id": item.get("task_id"),
                "status": item.get("status"),
                "branch_name": item.get("branch_name"),
                "pr_number": item.get("pr_number"),
                "pr_url": item.get("pr_url"),
                "merged": item.get("merged"),
                "completed_at": item.get("completed_at"),
            }
        )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect AI runtime queue state.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--runtime-dir", default=DEFAULT_RUNTIME_DIR)
    parser.add_argument("--task-id", default=None)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    runtime_dir = Path(args.runtime_dir).expanduser().resolve()
    pending_path = runtime_dir / "pending_tasks.json"
    completed_path = runtime_dir / "completed_tasks.json"
    plan_path = runtime_dir / "ai_task_branch_plan.json"
    validation_path = runtime_dir / "ai_dev_validation_bundle.json"

    pending_queue, pending_error = load_json_if_exists(pending_path)
    completed_queue, completed_error = load_json_if_exists(completed_path)
    plan, plan_error = load_json_if_exists(plan_path)
    validation, validation_error = load_json_if_exists(validation_path)

    branch_proc = run_git(["rev-parse", "--abbrev-ref", "HEAD"], repo_root)
    status_proc = run_git(["status", "--short"], repo_root)
    current_branch = branch_proc.stdout.strip() if branch_proc.returncode == 0 else None
    git_status_short = status_proc.stdout.strip().splitlines() if status_proc.returncode == 0 else []

    pending_tasks = summarize_tasks(pending_queue.get("tasks", []) if pending_queue else [])
    completed_tasks = summarize_completed(completed_queue.get("completed_tasks", []) if completed_queue else [])

    matching_pending = [task for task in pending_tasks if task.get("task_id") == args.task_id] if args.task_id else []
    matching_completed = [
        task for task in completed_tasks if task.get("task_id") == args.task_id
    ] if args.task_id else []

    active_plan_task = None
    if isinstance(plan, dict):
        task = plan.get("task")
        if isinstance(task, dict):
            active_plan_task = {
                "task_id": task.get("task_id"),
                "status": task.get("status"),
                "branch_name": plan.get("branch_name") or task.get("branch_name"),
                "base_branch": plan.get("base_branch") or task.get("target_base_branch"),
                "prepared": plan.get("prepared"),
            }

    output = {
        "ok": pending_error is None and completed_error is None,
        "runtime_dir": str(runtime_dir),
        "files": {
            "pending_queue": {"path": str(pending_path), "exists": pending_path.exists(), "error": pending_error},
            "completed_queue": {"path": str(completed_path), "exists": completed_path.exists(), "error": completed_error},
            "branch_plan": {"path": str(plan_path), "exists": plan_path.exists(), "error": plan_error},
            "validation_bundle": {
                "path": str(validation_path),
                "exists": validation_path.exists(),
                "error": validation_error,
            },
        },
        "git": {
            "current_branch": current_branch,
            "status_short": git_status_short,
            "clean": not git_status_short,
        },
        "pending": {
            "queue_name": pending_queue.get("queue_name") if pending_queue else None,
            "count": len(pending_tasks),
            "tasks": pending_tasks,
        },
        "completed": {
            "queue_name": completed_queue.get("queue_name") if completed_queue else None,
            "count": len(completed_tasks),
            "tasks": completed_tasks,
        },
        "active_plan": active_plan_task,
        "validation": {
            "available": validation is not None,
            "passed": validation.get("passed") if isinstance(validation, dict) else None,
            "checked_at": validation.get("checked_at") if isinstance(validation, dict) else None,
            "blocked_reasons": validation.get("blocked_reasons", []) if isinstance(validation, dict) else [],
        },
        "task_lookup": {
            "task_id": args.task_id,
            "pending": matching_pending,
            "completed": matching_completed,
        },
        "side_effects": {
            "runtime_queue_modified": False,
            "runtime_plan_written": False,
            "source_files_modified": False,
            "branch_created": False,
            "commit_created": False,
            "push_run": False,
            "pr_created": False,
            "merge_run": False,
            "archive_run": False,
            "production_command_run": False,
            "notification_sent": False,
            "trading_execution_run": False,
            "scheduler_modified": False,
        },
    }
    json.dump(output, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    return 0 if output["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
