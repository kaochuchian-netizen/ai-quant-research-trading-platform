#!/usr/bin/env python3
"""Inspect platform status without modifying repo, runtime, or production state."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_RUNTIME_DIR = "~/.local/state/stock-ai-orchestrator"

REQUIRED_RUNTIME_FILES = [
    "pending_tasks.json",
    "completed_tasks.json",
    "loop_status.json",
    "loop.log",
]

OPTIONAL_ACTIVE_RUNTIME_FILES = [
    "ai_task_branch_plan.json",
    "ai_task_pr_body.md",
    "current_codex_handoff.json",
    "current_codex_handoff.md",
    "ai_dev_validation_bundle.json",
]

ACTIVE_HANDOFF_RUNTIME_FILES = [
    "ai_task_branch_plan.json",
    "ai_task_pr_body.md",
    "current_codex_handoff.json",
    "current_codex_handoff.md",
]

STALE_HANDOFF_DIR_NAME = "stale_handoff"
RUNTIME_ARCHIVE_DIR_NAME = "archive"

KEY_ORCHESTRATOR_SCRIPTS = [
    "scripts/orchestrator/inspect_ai_runtime_queue.py",
    "scripts/orchestrator/promote_next_ai_task.py",
    "scripts/orchestrator/prepare_ai_task_branch.py",
    "scripts/orchestrator/validate_ai_branch.py",
    "scripts/orchestrator/check_forbidden_changes.py",
    "scripts/orchestrator/run_ai_dev_validation_bundle.py",
    "scripts/orchestrator/archive_completed_ai_task.py",
    "scripts/orchestrator/run_ai_task_queue_once.py",
    "scripts/orchestrator/run_loop_once.py",
]

PIPELINE_ENTRYPOINTS = [
    "main.py",
    "run_stock_analysis.sh",
]

SAFETY_BOUNDARY_REMINDERS = [
    "read_only_inspector_only",
    "does_not_run_python3_main_py",
    "does_not_run_production_pipeline",
    "does_not_send_line_email_or_external_notifications",
    "does_not_trade_or_place_orders",
    "does_not_modify_cron_systemd_or_timers",
    "does_not_read_or_modify_secrets_env_credentials_or_tokens",
    "does_not_modify_repo_runtime_queue_data_env_or_git_state",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def run_git(args: list[str], repo_root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(repo_root),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


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


def file_status(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "exists": path.exists(),
        "is_file": path.is_file() if path.exists() else False,
        "size_bytes": path.stat().st_size if path.exists() and path.is_file() else None,
    }


def merged_completed_task_ids(tasks: list[Any]) -> set[str]:
    task_ids: set[str] = set()
    for item in tasks:
        if not isinstance(item, dict):
            continue
        task_id = item.get("task_id")
        pull_request = item.get("pull_request")
        pull_request_merged = pull_request.get("merged") if isinstance(pull_request, dict) else None
        merged = item.get("merged")
        if task_id and (merged is True or pull_request_merged is True):
            task_ids.add(str(task_id))
    return task_ids


def extract_handoff_metadata(path: Path) -> tuple[dict[str, Any], str | None]:
    if path.suffix != ".json":
        return {}, None
    data, error = load_json_if_exists(path)
    if error:
        return {}, error
    if not isinstance(data, dict):
        return {}, "JSON root must be object"

    task = data.get("task")
    task_data = task if isinstance(task, dict) else {}
    target = data.get("target")
    target_data = target if isinstance(target, dict) else {}

    return {
        "schema_version": data.get("schema_version"),
        "task_id": data.get("task_id") or task_data.get("task_id"),
        "handoff_id": data.get("handoff_id"),
        "status": data.get("status") or task_data.get("status"),
        "prepared": data.get("prepared"),
        "branch_name": data.get("branch_name") or task_data.get("branch_name") or target_data.get("branch"),
        "base_branch": data.get("base_branch") or task_data.get("target_base_branch"),
    }, None


def looks_like_example(value: Any) -> bool:
    if value is None:
        return False
    return "EXAMPLE" in str(value).upper() or "example_only" == str(value)


def summarize_stale_handoff_dir(runtime_dir: Path) -> dict[str, Any]:
    path = runtime_dir / STALE_HANDOFF_DIR_NAME
    task_ids: list[str] = []
    file_count = 0
    if path.exists() and path.is_dir():
        for child in sorted(path.iterdir()):
            if child.is_dir():
                task_ids.append(child.name)
                file_count += sum(1 for item in child.iterdir() if item.is_file())
            elif child.is_file():
                file_count += 1
    return {
        "path": str(path),
        "exists": path.exists(),
        "task_ids": task_ids,
        "file_count": file_count,
    }


def summarize_archive_dir(runtime_dir: Path) -> dict[str, Any]:
    path = runtime_dir / RUNTIME_ARCHIVE_DIR_NAME
    file_count = 0
    if path.exists() and path.is_dir():
        file_count = sum(1 for item in path.iterdir() if item.is_file())
    return {
        "path": str(path),
        "exists": path.exists(),
        "file_count": file_count,
    }


def git_lines(args: list[str], repo_root: Path) -> tuple[list[str], str | None]:
    proc = run_git(args, repo_root)
    if proc.returncode != 0:
        return [], proc.stderr.strip() or proc.stdout.strip() or "git command failed"
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()], None


def collect_git_status(repo_root: Path) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []

    branch_proc = run_git(["rev-parse", "--abbrev-ref", "HEAD"], repo_root)
    current_branch = branch_proc.stdout.strip() if branch_proc.returncode == 0 else None
    if branch_proc.returncode != 0:
        warnings.append("unable to determine current git branch")

    status_lines, status_error = git_lines(["status", "--short"], repo_root)
    if status_error:
        warnings.append("unable to read git status: " + status_error)

    local_branches, local_error = git_lines(["branch", "--format=%(refname:short)"], repo_root)
    if local_error:
        warnings.append("unable to list local branches: " + local_error)

    remote_branches, remote_error = git_lines(["branch", "-r", "--format=%(refname:short)"], repo_root)
    if remote_error:
        warnings.append("unable to list remote branches: " + remote_error)

    main_sync = {
        "base": "main",
        "remote": "origin/main",
        "status": "unknown",
        "ahead": None,
        "behind": None,
        "notes": "Uses local refs only; this inspector does not fetch or pull.",
    }
    main_ref_proc = run_git(["rev-parse", "--verify", "main"], repo_root)
    origin_main_ref_proc = run_git(["rev-parse", "--verify", "origin/main"], repo_root)
    if main_ref_proc.returncode != 0 or origin_main_ref_proc.returncode != 0:
        main_sync["status"] = "missing_ref"
        warnings.append("unable to compare main and origin/main; one or both refs are missing")
    else:
        left_right_proc = run_git(["rev-list", "--left-right", "--count", "main...origin/main"], repo_root)
        if left_right_proc.returncode != 0:
            warnings.append("unable to compare main and origin/main")
        else:
            parts = left_right_proc.stdout.strip().split()
            if len(parts) == 2:
                ahead = int(parts[0])
                behind = int(parts[1])
                main_sync["ahead"] = ahead
                main_sync["behind"] = behind
                if ahead == 0 and behind == 0:
                    main_sync["status"] = "in_sync"
                elif ahead and behind:
                    main_sync["status"] = "diverged"
                    warnings.append("main and origin/main have diverged")
                elif ahead:
                    main_sync["status"] = "local_ahead"
                    warnings.append("main is ahead of origin/main")
                else:
                    main_sync["status"] = "local_behind"
                    warnings.append("main is behind origin/main")

    return {
        "current_branch": current_branch,
        "clean": not status_lines and status_error is None,
        "status_short": status_lines,
        "main_origin_main_sync": main_sync,
        "local_branches": local_branches,
        "remote_branches": remote_branches,
    }, warnings


def summarize_pending_queue(runtime_dir: Path) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    pending_path = runtime_dir / "pending_tasks.json"
    data, error = load_json_if_exists(pending_path)
    tasks = data.get("tasks", []) if data else []
    if error:
        warnings.append(f"pending queue unavailable: {error}")
    if not isinstance(tasks, list):
        warnings.append("pending queue tasks must be a list")
        tasks = []
    pending_tasks = [task for task in tasks if isinstance(task, dict) and task.get("status") == "pending"]
    promoted_tasks = [task for task in tasks if isinstance(task, dict) and task.get("status") == "promoted"]
    return {
        "path": str(pending_path),
        "exists": pending_path.exists(),
        "error": error,
        "count": len(tasks),
        "pending_count": len(pending_tasks),
        "promoted_count": len(promoted_tasks),
        "task_ids": [task.get("task_id") for task in tasks if isinstance(task, dict)],
    }, warnings


def summarize_completed_queue(runtime_dir: Path) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    completed_path = runtime_dir / "completed_tasks.json"
    data, error = load_json_if_exists(completed_path)
    tasks = data.get("completed_tasks", []) if data else []
    if error:
        warnings.append(f"completed queue unavailable: {error}")
    if not isinstance(tasks, list):
        warnings.append("completed queue completed_tasks must be a list")
        tasks = []
    return {
        "path": str(completed_path),
        "exists": completed_path.exists(),
        "error": error,
        "count": len(tasks),
        "task_ids": [task.get("task_id") for task in tasks if isinstance(task, dict)],
        "merged_task_ids": sorted(merged_completed_task_ids(tasks)),
    }, warnings


def collect_runtime_status(runtime_dir: Path) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    pending, pending_warnings = summarize_pending_queue(runtime_dir)
    completed, completed_warnings = summarize_completed_queue(runtime_dir)
    warnings.extend(pending_warnings)
    warnings.extend(completed_warnings)

    required_files = {name: file_status(runtime_dir / name) for name in REQUIRED_RUNTIME_FILES}
    for name, status in required_files.items():
        if not status["exists"]:
            warnings.append(f"required runtime file missing: {name}")

    active_files = {name: file_status(runtime_dir / name) for name in OPTIONAL_ACTIVE_RUNTIME_FILES}
    merged_task_ids = set(completed.get("merged_task_ids", []))
    handoff_files: dict[str, dict[str, Any]] = {}
    example_indicators: list[str] = []
    stale_indicators: list[str] = []
    active_task_ids: set[str] = set()

    for name in OPTIONAL_ACTIVE_RUNTIME_FILES:
        path = runtime_dir / name
        status = dict(active_files[name])
        metadata, metadata_error = extract_handoff_metadata(path) if path.exists() else ({}, None)
        task_id = metadata.get("task_id")
        handoff_id = metadata.get("handoff_id")
        status["metadata"] = metadata
        status["metadata_error"] = metadata_error
        handoff_files[name] = status

        if task_id:
            active_task_ids.add(str(task_id))
        if metadata_error:
            stale_indicators.append(f"{name} metadata unavailable: {metadata_error}")
        if any(looks_like_example(value) for value in (task_id, handoff_id, metadata.get("status"))):
            example_indicators.append(f"{name} contains example metadata")
        if task_id and str(task_id) in merged_task_ids:
            stale_indicators.append(f"{name} points at merged completed task: {task_id}")

    active_handoff_exists = any(active_files[name]["exists"] for name in ACTIVE_HANDOFF_RUNTIME_FILES)
    stale_handoff_dir = summarize_stale_handoff_dir(runtime_dir)
    archive_dir = summarize_archive_dir(runtime_dir)
    classification = "no_active_handoff"
    if active_handoff_exists and (example_indicators or stale_indicators):
        classification = "stale_or_example_suspected"
    elif active_handoff_exists:
        classification = "active_handoff_present"

    if example_indicators:
        warnings.append("active handoff appears to contain example metadata")
    if stale_indicators:
        warnings.append("active handoff may be stale")

    return {
        "runtime_dir": str(runtime_dir),
        "pending_queue": pending,
        "completed_queue": completed,
        "active_handoff_or_branch_plan": {
            "branch_plan_exists": active_files["ai_task_branch_plan.json"]["exists"],
            "pr_body_exists": active_files["ai_task_pr_body.md"]["exists"],
            "current_codex_handoff_json_exists": active_files["current_codex_handoff.json"]["exists"],
            "current_codex_handoff_md_exists": active_files["current_codex_handoff.md"]["exists"],
        },
        "handoff_diagnostics": {
            "classification": classification,
            "active_task_ids": sorted(active_task_ids),
            "example_indicators": example_indicators,
            "stale_indicators": stale_indicators,
            "completed_task_matches": sorted(active_task_ids.intersection(merged_task_ids)),
            "files": handoff_files,
            "stale_handoff_dir": stale_handoff_dir,
            "archive_dir": archive_dir,
            "read_only": True,
            "auto_repair_attempted": False,
            "recommended_operator_action": (
                "inspect active handoff files and move confirmed stale artifacts to stale_handoff/<task-id>/"
                if classification == "stale_or_example_suspected"
                else None
            ),
        },
        "required_runtime_files": required_files,
        "optional_active_runtime_files": active_files,
    }, warnings


def collect_repo_files(repo_root: Path) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    scripts = {path: file_status(repo_root / path) for path in KEY_ORCHESTRATOR_SCRIPTS}
    for path, status in scripts.items():
        if not status["exists"]:
            warnings.append(f"key orchestrator script missing: {path}")

    entrypoints = {path: file_status(repo_root / path) for path in PIPELINE_ENTRYPOINTS}
    if not entrypoints["main.py"]["exists"]:
        warnings.append("pipeline entrypoint missing: main.py")

    return {
        "key_orchestrator_scripts": scripts,
        "pipeline_entrypoints": entrypoints,
        "pipeline_entrypoint_check": {
            "main_py_exists": entrypoints["main.py"]["exists"],
            "main_py_executed": False,
            "production_pipeline_executed": False,
        },
    }, warnings


def build_report(repo_root: Path, runtime_dir: Path) -> dict[str, Any]:
    warnings: list[str] = []
    git_status, git_warnings = collect_git_status(repo_root)
    runtime_status, runtime_warnings = collect_runtime_status(runtime_dir)
    repo_files, repo_warnings = collect_repo_files(repo_root)
    warnings.extend(git_warnings)
    warnings.extend(runtime_warnings)
    warnings.extend(repo_warnings)

    if git_status.get("current_branch") != "main":
        warnings.append("current branch is not main")
    if not git_status.get("clean"):
        warnings.append("git working tree is not clean")

    return {
        "ok": True,
        "inspected_at": now_iso(),
        "repo_root": str(repo_root),
        "git": git_status,
        "runtime": runtime_status,
        "repo_files": repo_files,
        "warnings": warnings,
        "safety_boundary_reminder": SAFETY_BOUNDARY_REMINDERS,
        "side_effects": {
            "repo_modified": False,
            "runtime_queue_modified": False,
            "data_modified": False,
            "env_modified": False,
            "git_state_modified": False,
            "branch_created": False,
            "commit_created": False,
            "push_run": False,
            "pr_created": False,
            "merge_run": False,
            "python3_main_py_run": False,
            "production_pipeline_run": False,
            "line_or_email_notification_sent": False,
            "trading_or_order_run": False,
            "cron_systemd_timer_modified": False,
            "secrets_read_or_modified": False,
            "auto_repair_attempted": False,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect AI Quant platform status without side effects.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--runtime-dir", default=DEFAULT_RUNTIME_DIR)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    runtime_dir = Path(args.runtime_dir).expanduser().resolve()
    report = build_report(repo_root, runtime_dir)
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
