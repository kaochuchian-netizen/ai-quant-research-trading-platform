#!/usr/bin/env python3
"""Validate completed-record backfill behavior using a temp runtime fixture."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


TASK_ID = "AI-DEV-037"
PR_NUMBER = "36"
PR_URL = "https://github.com/example-org/example-repo/pull/36"
BRANCH_NAME = "ai-dev/037-n8n-runtime-dry-run-runbook"
BASE_BRANCH = "main"
MERGE_COMMIT = "b05c0e2f6e67c88c08cef441532409f6550687b4"


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_tool(repo_root: Path, runtime_dir: Path, *, apply: bool) -> subprocess.CompletedProcess[str]:
    args = [
        sys.executable,
        "scripts/orchestrator/backfill_completed_ai_task_record.py",
        "--runtime-dir",
        str(runtime_dir),
        "--task-id",
        TASK_ID,
        "--pr-number",
        PR_NUMBER,
        "--pr-url",
        PR_URL,
        "--branch-name",
        BRANCH_NAME,
        "--base-branch",
        BASE_BRANCH,
        "--merge-commit",
        MERGE_COMMIT,
        "--pretty",
    ]
    if apply:
        args.append("--apply")
    return subprocess.run(args, cwd=str(repo_root), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


def parse_json_output(proc: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    try:
        data = json.loads(proc.stdout)
        return data if isinstance(data, dict) else {"ok": False, "error": "JSON root is not object"}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "stdout": proc.stdout, "stderr": proc.stderr}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate completed record backfill in temp runtime dir.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    reasons: list[str] = []

    with tempfile.TemporaryDirectory(prefix="stock-ai-backfill-runtime-") as temp_dir:
        runtime_dir = Path(temp_dir)
        pending_path = runtime_dir / "pending_tasks.json"
        completed_path = runtime_dir / "completed_tasks.json"
        pending_seed = {
            "schema_version": 1,
            "queue_name": "ai-development-pending-tasks",
            "status": "active",
            "tasks": [],
        }
        completed_seed = {
            "schema_version": 1,
            "queue_name": "ai-development-completed-tasks",
            "status": "active",
            "completed_tasks": [],
        }
        write_json(pending_path, pending_seed)
        write_json(completed_path, completed_seed)
        pending_before = pending_path.read_text(encoding="utf-8")

        dry_proc = run_tool(repo_root, runtime_dir, apply=False)
        dry_result = parse_json_output(dry_proc)
        if dry_proc.returncode != 0 or not dry_result.get("ok"):
            reasons.append("dry-run backfill failed")
        if dry_result.get("dry_run") is not True or dry_result.get("applied") is not False:
            reasons.append("dry-run result must be dry_run true and applied false")
        if dry_result.get("modified_files") != []:
            reasons.append("dry-run must not modify files")

        apply_proc = run_tool(repo_root, runtime_dir, apply=True)
        apply_result = parse_json_output(apply_proc)
        if apply_proc.returncode != 0 or not apply_result.get("ok"):
            reasons.append("apply backfill failed in temp runtime dir")
        if apply_result.get("dry_run") is not False or apply_result.get("applied") is not True:
            reasons.append("apply result must be dry_run false and applied true")
        if not apply_result.get("backup_path"):
            reasons.append("apply result must include backup_path")
        if apply_result.get("pending_contains_task") is not False:
            reasons.append("pending_contains_task should be false for recovery fixture")
        if apply_result.get("completed_contains_task_after") is not True:
            reasons.append("completed_contains_task_after should be true after apply")
        if pending_path.read_text(encoding="utf-8") != pending_before:
            reasons.append("pending_tasks.json was modified during recovery apply")

        completed_after = json.loads(completed_path.read_text(encoding="utf-8"))
        completed_records = completed_after.get("completed_tasks", [])
        if len(completed_records) != 1:
            reasons.append("completed_tasks.json should contain exactly one backfilled record")
        if not apply_result.get("modified_files") == [str(completed_path)]:
            reasons.append("apply modified_files should contain only temp completed_tasks.json")

        duplicate_proc = run_tool(repo_root, runtime_dir, apply=True)
        duplicate_result = parse_json_output(duplicate_proc)
        if duplicate_proc.returncode == 0 or duplicate_result.get("ok"):
            reasons.append("duplicate apply should fail")
        completed_after_duplicate = json.loads(completed_path.read_text(encoding="utf-8"))
        if len(completed_after_duplicate.get("completed_tasks", [])) != 1:
            reasons.append("duplicate apply should not append another record")

        output = {
            "ok": not reasons,
            "passed": not reasons,
            "runtime_dir": str(runtime_dir),
            "dry_run_result": dry_result,
            "apply_result": apply_result,
            "duplicate_result": duplicate_result,
            "pending_unchanged_after_apply": pending_path.read_text(encoding="utf-8") == pending_before,
            "completed_record_count": len(completed_after_duplicate.get("completed_tasks", [])),
            "reasons": reasons,
            "side_effects": {
                "real_runtime_queue_modified": False,
                "temp_runtime_dir_used": True,
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
