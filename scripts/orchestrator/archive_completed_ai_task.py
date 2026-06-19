#!/usr/bin/env python3
"""Archive a completed AI task from runtime pending queue to completed queue."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_RUNTIME_DIR = "~/.local/state/stock-ai-orchestrator"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def run_git(args: list[str], repo_root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(repo_root),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def find_task(tasks: list[Any], task_id: str, branch_name: str | None) -> tuple[int | None, dict[str, Any] | None]:
    for index, item in enumerate(tasks):
        if not isinstance(item, dict):
            continue
        if item.get("task_id") == task_id:
            return index, item
    if branch_name:
        for index, item in enumerate(tasks):
            if isinstance(item, dict) and item.get("branch_name") == branch_name:
                return index, item
    return None, None


def load_validation_summary(runtime_dir: Path) -> dict[str, Any]:
    validation_path = runtime_dir / "ai_dev_validation_bundle.json"
    if not validation_path.exists():
        return {"available": False, "path": str(validation_path)}
    try:
        data = load_json(validation_path)
    except Exception as exc:
        return {"available": False, "path": str(validation_path), "error": str(exc)}
    return {
        "available": True,
        "path": str(validation_path),
        "passed": data.get("passed"),
        "checked_at": data.get("checked_at"),
        "blocked_reasons": data.get("blocked_reasons", []),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Archive completed runtime AI task.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--runtime-dir", default=DEFAULT_RUNTIME_DIR)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--pr-number", type=int, required=True)
    parser.add_argument("--pr-url", required=True)
    parser.add_argument("--branch-name", required=True)
    parser.add_argument("--base-branch", required=True)
    parser.add_argument("--merged-at", default=None)
    parser.add_argument("--merge-commit-sha", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    runtime_dir = Path(args.runtime_dir).expanduser().resolve()
    pending_path = runtime_dir / "pending_tasks.json"
    completed_path = runtime_dir / "completed_tasks.json"
    reasons: list[str] = []

    if not pending_path.exists():
        reasons.append(f"missing runtime pending queue: {pending_path}")
    if not completed_path.exists():
        reasons.append(f"missing runtime completed queue: {completed_path}")

    pending_queue: dict[str, Any] = {}
    completed_queue: dict[str, Any] = {}
    selected_index: int | None = None
    selected_task: dict[str, Any] | None = None
    duplicate_reasons: list[str] = []
    completed_tasks: list[Any] = []
    pending_tasks: list[Any] = []

    if not reasons:
        pending_queue = load_json(pending_path)
        completed_queue = load_json(completed_path)
        pending_tasks = pending_queue.get("tasks", [])
        completed_tasks = completed_queue.get("completed_tasks", [])
        if not isinstance(pending_tasks, list):
            reasons.append("pending queue tasks must be a list")
            pending_tasks = []
        if not isinstance(completed_tasks, list):
            reasons.append("completed queue completed_tasks must be a list")
            completed_tasks = []

    if not reasons:
        selected_index, selected_task = find_task(pending_tasks, args.task_id, args.branch_name)
        if selected_task is None:
            reasons.append(f"pending task not found: {args.task_id}")
        elif selected_task.get("status") not in {"promoted", "in_progress", "merged"}:
            reasons.append("pending task status must be promoted, in_progress, or merged")

        for item in completed_tasks:
            if not isinstance(item, dict):
                continue
            if item.get("task_id") == args.task_id:
                duplicate_reasons.append(f"completed queue already has task_id: {args.task_id}")
            if item.get("pr_number") == args.pr_number:
                duplicate_reasons.append(f"completed queue already has pr_number: {args.pr_number}")
        reasons.extend(duplicate_reasons)

    merge_commit_sha = args.merge_commit_sha
    if not merge_commit_sha:
        head_proc = run_git(["rev-parse", "HEAD"], repo_root)
        if head_proc.returncode == 0:
            merge_commit_sha = head_proc.stdout.strip()

    completed_at = now_iso()
    merged_at = args.merged_at or completed_at
    validation_summary = load_validation_summary(runtime_dir)
    safety_result = {
        "task_status_allowed": selected_task.get("status") if selected_task else None,
        "duplicate_reasons": duplicate_reasons,
        "archive_action": "removed_from_pending_queue",
    }

    completed_record: dict[str, Any] | None = None
    if selected_task is not None:
        completed_record = {
            "archive_action": "removed_from_pending_queue",
            "task_id": args.task_id,
            "status": "completed_by_pr",
            "risk_level": selected_task.get("risk_level"),
            "base_branch": args.base_branch,
            "branch_name": args.branch_name,
            "pr_number": args.pr_number,
            "pr_url": args.pr_url,
            "merged": True,
            "merged_at": merged_at,
            "completed_at": completed_at,
            "merge_commit_sha": merge_commit_sha,
            "validation_summary": validation_summary,
            "safety_result": safety_result,
            "task": selected_task,
        }

    side_effects = {
        "pending_queue_modified": False,
        "completed_queue_modified": False,
        "source_files_modified": False,
        "branch_created": False,
        "commit_created": False,
        "push_run": False,
        "pr_created": False,
        "merge_run": False,
        "production_command_run": False,
        "notification_sent": False,
        "trading_execution_run": False,
        "scheduler_modified": False,
    }

    archived = False
    if not reasons and not args.dry_run and selected_index is not None and completed_record is not None:
        completed_tasks.append(completed_record)
        del pending_tasks[selected_index]
        pending_queue["tasks"] = pending_tasks
        completed_queue["completed_tasks"] = completed_tasks
        atomic_write_json(completed_path, completed_queue)
        atomic_write_json(pending_path, pending_queue)
        side_effects["pending_queue_modified"] = True
        side_effects["completed_queue_modified"] = True
        archived = True

    output = {
        "ok": not reasons,
        "dry_run": args.dry_run,
        "archived": archived,
        "would_archive": not reasons if args.dry_run else False,
        "task_id": args.task_id,
        "pr_number": args.pr_number,
        "pr_url": args.pr_url,
        "branch_name": args.branch_name,
        "base_branch": args.base_branch,
        "pending_queue_path": str(pending_path),
        "completed_queue_path": str(completed_path),
        "completed_record": completed_record,
        "reasons": reasons,
        "side_effects": side_effects,
    }
    json.dump(output, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    return 0 if output["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
