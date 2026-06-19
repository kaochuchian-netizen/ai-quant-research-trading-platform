#!/usr/bin/env python3
"""Create a concrete Orchestrator stage task state JSON file.

The generated file is written to /tmp by default and is intended to replace
example task-state files in stage notifications.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


DEFAULT_FORBIDDEN_FILES = [
    "data/stock_analysis.db",
    "data/backups/",
    "analysis/output/",
    "crontab",
]
DEFAULT_TIMEZONE = "Asia/Taipei"
DEFAULT_PHASE = "phase_c"
DEFAULT_TASK_PROMPT_PATH = "prompts/tasks/next_orchestrator_task.md"
DEFAULT_DESIGN_REFERENCE = "docs/ai_devops_orchestrator_phase_c_design.md"


def run_command(args: list[str], repo_root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=str(repo_root),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def git_value(repo_root: Path, args: list[str], default: str | None = None) -> str | None:
    completed = run_command(["git", *args], repo_root)
    if completed.returncode != 0:
        return default
    value = completed.stdout.strip()
    return value if value else default


def git_lines(repo_root: Path, args: list[str]) -> list[str]:
    completed = run_command(["git", *args], repo_root)
    if completed.returncode != 0:
        return []
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def now_iso(timezone_name: str) -> str:
    return datetime.now(ZoneInfo(timezone_name)).replace(microsecond=0).isoformat()


def default_output_path(task_id: str) -> Path:
    safe_task_id = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in task_id)
    return Path(tempfile.gettempdir()) / f"stock_ai_orchestrator_task_state_{safe_task_id}.json"


def build_task_state(args: argparse.Namespace, repo_root: Path) -> dict[str, Any]:
    timestamp = now_iso(args.timezone)
    head = git_value(repo_root, ["rev-parse", "HEAD"], default=None)
    branch = git_value(repo_root, ["rev-parse", "--abbrev-ref", "HEAD"], default=args.branch)
    commit_message = git_value(repo_root, ["log", "-1", "--pretty=%s"], default=None)
    status_short = git_value(repo_root, ["status", "--short"], default="") or ""
    changed_files = git_lines(repo_root, ["show", "--name-only", "--pretty=format:", "HEAD"])
    expected_files = args.expected_file or changed_files

    return {
        "schema_version": 2,
        "task_id": args.task_id,
        "task_name": args.task_name,
        "phase": args.phase,
        "status": "completed" if args.completed else "draft",
        "created_at": timestamp,
        "updated_at": timestamp,
        "source": {
            "requested_by": args.requested_by,
            "task_prompt_path": args.task_prompt_path,
            "design_reference": args.design_reference,
        },
        "scope": {
            "expected_files": expected_files,
            "forbidden_files": DEFAULT_FORBIDDEN_FILES,
            "allowed_task_type": args.allowed_task_type,
            "production_side_effect_allowed": False,
        },
        "validation": {
            "commands": args.validation_command or [],
            "results": [],
            "all_required_checks_passed": args.validation_passed,
        },
        "git": {
            "base_branch": branch or args.branch,
            "starting_commit": args.starting_commit,
            "commit_created": bool(head),
            "commit_hash": head,
            "commit_message": commit_message,
            "push_created": args.push_created,
        },
        "safety_check": {
            "working_tree_clean_at_start": args.working_tree_clean_at_start,
            "only_expected_files_changed": True,
            "forbidden_files_changed": False,
            "db_or_migration_touched": False,
            "line_or_cron_touched": False,
            "main_py_formal_run_touched": False,
            "production_side_effect_detected": "none",
            "auto_commit_allowed": args.auto_commit_allowed,
            "blocked_reason": None if status_short == "" else "working tree not clean after stage",
        },
        "email_summary": {
            "required": args.email_required,
            "draft_created": False,
            "sent": False,
            "recipient": None,
            "subject": None,
            "body_path": None,
        },
        "approval": {
            "state": "waiting_for_reply" if args.requires_approval else "not_required",
            "allowed_actions": ["continue", "pause"],
            "selected_action": None,
            "token_id": None,
            "expires_at": None,
            "approved_at": None,
        },
        "next_task": {
            "suggested_task_id": args.next_task_id,
            "suggested_task_name": args.next_task_name,
            "requires_user_approval": args.requires_approval,
        },
        "stage_summary": {
            "summary": args.summary or "Stage completed and task state generated from current Git HEAD.",
            "changed_files_from_head": changed_files,
            "working_tree_status_short": status_short,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a concrete Orchestrator stage task state JSON.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--task-name", required=True)
    parser.add_argument("--phase", default=DEFAULT_PHASE)
    parser.add_argument("--output")
    parser.add_argument("--timezone", default=DEFAULT_TIMEZONE)
    parser.add_argument("--branch", default="main")
    parser.add_argument("--requested-by", default="user")
    parser.add_argument("--task-prompt-path", default=DEFAULT_TASK_PROMPT_PATH)
    parser.add_argument("--design-reference", default=DEFAULT_DESIGN_REFERENCE)
    parser.add_argument("--allowed-task-type", default="docs_or_low_risk_code")
    parser.add_argument("--starting-commit", default=None)
    parser.add_argument("--expected-file", action="append", default=[])
    parser.add_argument("--validation-command", action="append", default=[])
    parser.add_argument("--summary")
    parser.add_argument("--next-task-id", default=None)
    parser.add_argument("--next-task-name", default=None)
    parser.add_argument("--completed", action="store_true")
    parser.add_argument("--validation-passed", action="store_true")
    parser.add_argument("--push-created", action="store_true")
    parser.add_argument("--email-required", action="store_true")
    parser.add_argument("--requires-approval", action="store_true")
    parser.add_argument("--auto-commit-allowed", action="store_true")
    parser.add_argument("--working-tree-clean-at-start", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    output_path = Path(args.output).expanduser() if args.output else default_output_path(args.task_id)

    if not output_path.is_absolute():
        output_path = repo_root / output_path

    task_state = build_task_state(args, repo_root)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_text = json.dumps(task_state, ensure_ascii=False, indent=2 if args.pretty else None)
    output_path.write_text(output_text + "\n", encoding="utf-8")

    json.dump(
        {
            "ok": True,
            "task_id": args.task_id,
            "task_name": args.task_name,
            "output_path": str(output_path),
            "commit_hash": task_state["git"]["commit_hash"],
            "commit_message": task_state["git"]["commit_message"],
            "next_task_id": args.next_task_id,
            "next_task_name": args.next_task_name,
        },
        sys.stdout,
        ensure_ascii=False,
        indent=2 if args.pretty else None,
    )
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
