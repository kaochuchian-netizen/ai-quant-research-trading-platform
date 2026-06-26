#!/usr/bin/env python3
"""Backfill a completed AI task record when primary archive closeout cannot run.

This recovery tool appends a completed record to completed_tasks.json without
modifying pending_tasks.json. It is dry-run by default and writes only when
--apply is supplied.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
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


def task_in_pending(pending_queue: dict[str, Any], task_id: str) -> bool:
    tasks = pending_queue.get("tasks", [])
    if not isinstance(tasks, list):
        return False
    return any(isinstance(item, dict) and item.get("task_id") == task_id for item in tasks)


def completed_duplicate_reasons(completed_tasks: list[Any], task_id: str, pr_number: int) -> list[str]:
    reasons: list[str] = []
    for item in completed_tasks:
        if not isinstance(item, dict):
            continue
        if item.get("task_id") == task_id:
            reasons.append(f"completed record already exists for task_id: {task_id}")
        if item.get("pr_number") == pr_number:
            reasons.append(f"completed record already exists for pr_number: {pr_number}")
    return reasons


def build_completed_record(args: argparse.Namespace) -> dict[str, Any]:
    completed_at = args.completed_at or now_iso()
    return {
        "archive_action": "backfilled_completed_record",
        "backfill_reason": args.reason,
        "task_id": args.task_id,
        "status": "completed_by_pr",
        "base_branch": args.base_branch,
        "branch_name": args.branch_name,
        "pr_number": args.pr_number,
        "pr_url": args.pr_url,
        "merged": True,
        "merged_at": args.merged_at or completed_at,
        "completed_at": completed_at,
        "merge_commit_sha": args.merge_commit,
        "recovery_path": {
            "tool": "scripts/orchestrator/backfill_completed_ai_task_record.py",
            "primary_archive_available": False,
            "pending_queue_modified": False,
            "completed_queue_modified": True,
            "operator_note": "Recovery fallback only; primary closeout remains archive_completed_ai_task.py.",
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill completed AI task record without touching pending queue.")
    parser.add_argument("--runtime-dir", default=DEFAULT_RUNTIME_DIR)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--pr-number", type=int, required=True)
    parser.add_argument("--pr-url", required=True)
    parser.add_argument("--branch-name", required=True)
    parser.add_argument("--base-branch", required=True)
    parser.add_argument("--merge-commit", required=True)
    parser.add_argument("--merged-at", default=None)
    parser.add_argument("--completed-at", default=None)
    parser.add_argument(
        "--reason",
        default="primary archive closeout could not find pending task after PR merge",
    )
    parser.add_argument("--apply", action="store_true", help="Write completed_tasks.json after making a backup.")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    runtime_dir = Path(args.runtime_dir).expanduser().resolve()
    pending_path = runtime_dir / "pending_tasks.json"
    completed_path = runtime_dir / "completed_tasks.json"
    dry_run = not args.apply
    errors: list[str] = []
    warnings: list[str] = []
    modified_files: list[str] = []
    backup_path: str | None = None
    pending_contains_task = False
    completed_contains_task_before = False
    completed_contains_task_after = False

    pending_queue: dict[str, Any] = {}
    completed_queue: dict[str, Any] = {}
    completed_tasks: list[Any] = []

    try:
        if pending_path.exists():
            pending_queue = load_json(pending_path)
            pending_contains_task = task_in_pending(pending_queue, args.task_id)
        else:
            warnings.append(f"pending queue missing; recovery path will not create it: {pending_path}")

        if not completed_path.exists():
            errors.append(f"missing completed queue: {completed_path}")
        else:
            completed_queue = load_json(completed_path)
            completed_tasks = completed_queue.get("completed_tasks", [])
            if not isinstance(completed_tasks, list):
                errors.append("completed queue completed_tasks must be a list")
                completed_tasks = []

        duplicate_reasons = completed_duplicate_reasons(completed_tasks, args.task_id, args.pr_number)
        if duplicate_reasons:
            errors.extend(duplicate_reasons)
            completed_contains_task_before = any(
                isinstance(item, dict) and item.get("task_id") == args.task_id for item in completed_tasks
            )
        else:
            completed_contains_task_before = False

        completed_record = build_completed_record(args)
        if not errors and args.apply:
            backup = completed_path.with_name(completed_path.name + f".bak.{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}")
            shutil.copy2(completed_path, backup)
            backup_path = str(backup)
            completed_tasks.append(completed_record)
            completed_queue["completed_tasks"] = completed_tasks
            atomic_write_json(completed_path, completed_queue)
            modified_files.append(str(completed_path))

        completed_contains_task_after = (
            any(isinstance(item, dict) and item.get("task_id") == args.task_id for item in completed_tasks)
            if args.apply and not errors
            else completed_contains_task_before
        )
    except Exception as exc:
        errors.append(str(exc))
        completed_record = None

    output = {
        "ok": not errors,
        "dry_run": dry_run,
        "applied": bool(args.apply and not errors),
        "task_id": args.task_id,
        "pr_number": args.pr_number,
        "merge_commit": args.merge_commit,
        "pending_contains_task": pending_contains_task,
        "completed_contains_task_before": completed_contains_task_before,
        "completed_contains_task_after": completed_contains_task_after,
        "backup_path": backup_path,
        "modified_files": modified_files,
        "warnings": warnings,
        "errors": errors,
        "completed_record": completed_record,
        "side_effects": {
            "pending_tasks_modified": False,
            "completed_tasks_modified": bool(modified_files),
            "next_task_created": False,
            "production_pipeline_run": False,
            "notification_sent": False,
            "trading_execution_run": False,
            "ai_dev_039_run": False,
        },
    }
    json.dump(output, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    return 0 if output["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
