#!/usr/bin/env python3
"""Run VM-side stage validation for the AI DevOps Orchestrator.

This runner is intentionally conservative:
- It validates branch and clean working tree state.
- It executes only allowlisted validation command types from task state.
- The initial skeleton supports only py_compile.
- It does not run git pull, main.py, backtests, migrations, DB writes, LINE,
  cron edits, approval endpoints, or production pipelines.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ALLOWED_COMMAND_TYPES = {"py_compile"}
DEFAULT_TMP_PREFIX = "stock_ai_orchestrator_vm_validation_"
FORBIDDEN_PATH_MARKERS = (
    ".env",
    "data/stock_analysis.db",
    "data/backups/",
    "analysis/output/",
    "crontab",
    "credentials",
    "production credentials",
)
FORBIDDEN_COMMAND_TARGETS = (
    "main.py",
    "migration",
    "migrations",
    "backtest",
    "line",
    "cron",
    "stock_analysis.db",
)


def run_command(args: list[str], repo_root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=str(repo_root),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def git_output(repo_root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return run_command(["git", *args], repo_root)


def command_summary(
    completed: subprocess.CompletedProcess[str],
    include_output: bool = True,
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "returncode": completed.returncode,
    }

    if include_output:
        summary["stdout"] = completed.stdout.strip()
        summary["stderr"] = completed.stderr.strip()

    return summary


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError("task state must be a JSON object")

    return data


def make_default_output_path() -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path(tempfile.gettempdir()) / f"{DEFAULT_TMP_PREFIX}{timestamp}.json"


def normalize_repo_path(path_value: str) -> str:
    return path_value.replace("\\", "/")


def path_is_forbidden(path_value: str, forbidden_files: list[str]) -> bool:
    normalized = normalize_repo_path(path_value)

    for forbidden in [*FORBIDDEN_PATH_MARKERS, *forbidden_files]:
        forbidden_normalized = normalize_repo_path(str(forbidden))
        if not forbidden_normalized:
            continue
        if normalized == forbidden_normalized:
            return True
        if forbidden_normalized.endswith("/") and normalized.startswith(forbidden_normalized):
            return True
        if forbidden_normalized in normalized:
            return True

    return False


def command_has_forbidden_target(command: dict[str, Any], forbidden_files: list[str]) -> str | None:
    command_type = str(command.get("type") or "")
    args = command.get("args") or []

    if command_type not in ALLOWED_COMMAND_TYPES:
        return f"command type not allowlisted: {command_type}"

    if not isinstance(args, list):
        return "command args must be a list"

    for arg in args:
        arg_value = str(arg)
        normalized = normalize_repo_path(arg_value)

        for marker in FORBIDDEN_COMMAND_TARGETS:
            if marker in normalized:
                return f"forbidden command target: {arg_value}"

        if path_is_forbidden(arg_value, forbidden_files):
            return f"forbidden path target: {arg_value}"

    return None


def validate_task_state(task_state: dict[str, Any]) -> tuple[bool, list[str]]:
    errors: list[str] = []

    scope = task_state.get("scope") or {}
    vm_validation = task_state.get("vm_validation") or {}
    sync = vm_validation.get("sync") or {}
    commands = vm_validation.get("commands") or []

    if not vm_validation.get("enabled", False):
        errors.append("vm_validation.enabled must be true")

    if scope.get("production_side_effect_allowed") is not False:
        errors.append("production_side_effect_allowed must be false")

    if sync.get("git_pull_allowed") is True:
        errors.append("git_pull_allowed must remain false in Phase C-6-1 skeleton")

    if not isinstance(commands, list) or not commands:
        errors.append("vm_validation.commands must be a non-empty list")

    forbidden_files = scope.get("forbidden_files") or []
    if not isinstance(forbidden_files, list):
        errors.append("scope.forbidden_files must be a list")
        forbidden_files = []

    for idx, command in enumerate(commands):
        if not isinstance(command, dict):
            errors.append(f"command #{idx + 1} must be an object")
            continue

        command_id = command.get("id") or f"command_{idx + 1}"
        reason = command_has_forbidden_target(command, forbidden_files)
        if reason:
            errors.append(f"{command_id}: {reason}")

    return len(errors) == 0, errors


def check_git_state(repo_root: Path, expected_branch: str) -> dict[str, Any]:
    branch_result = git_output(repo_root, ["rev-parse", "--abbrev-ref", "HEAD"])
    status_result = git_output(repo_root, ["status", "--short"])
    head_result = git_output(repo_root, ["rev-parse", "HEAD"])

    current_branch = branch_result.stdout.strip() if branch_result.returncode == 0 else None
    status_short = status_result.stdout.strip()
    untracked_files = [
        line[3:]
        for line in status_short.splitlines()
        if line.startswith("?? ")
    ]

    ok = (
        branch_result.returncode == 0
        and status_result.returncode == 0
        and current_branch == expected_branch
        and status_short == ""
    )

    blocked_reasons: list[str] = []
    if branch_result.returncode != 0:
        blocked_reasons.append("failed to read current branch")
    elif current_branch != expected_branch:
        blocked_reasons.append(f"branch mismatch: {current_branch} != {expected_branch}")

    if status_result.returncode != 0:
        blocked_reasons.append("failed to read git status")
    elif status_short:
        blocked_reasons.append("working tree is not clean")

    return {
        "ok": ok,
        "expected_branch": expected_branch,
        "current_branch": current_branch,
        "head": head_result.stdout.strip() if head_result.returncode == 0 else None,
        "status_short": status_short,
        "untracked_files": untracked_files,
        "blocked_reasons": blocked_reasons,
    }


def run_py_compile(repo_root: Path, command: dict[str, Any]) -> dict[str, Any]:
    command_id = str(command.get("id") or "py_compile")
    args = command.get("args") or []

    if len(args) != 1:
        return {
            "id": command_id,
            "type": "py_compile",
            "ok": False,
            "returncode": 2,
            "error": "py_compile command requires exactly one file argument",
        }

    target = str(args[0])
    completed = run_command(
        [sys.executable, "-m", "py_compile", target],
        repo_root,
    )

    return {
        "id": command_id,
        "type": "py_compile",
        "target": target,
        "required": bool(command.get("required", True)),
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def run_validation_commands(repo_root: Path, commands: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []

    for command in commands:
        command_type = command.get("type")
        if command_type == "py_compile":
            results.append(run_py_compile(repo_root, command))
        else:
            results.append({
                "id": command.get("id"),
                "type": command_type,
                "ok": False,
                "returncode": 2,
                "error": f"unsupported command type: {command_type}",
            })

    return results


def all_required_checks_passed(results: list[dict[str, Any]]) -> bool:
    for result in results:
        if result.get("required", True) and not result.get("ok", False):
            return False
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run VM-side allowlisted validation commands from task state.",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root. Defaults to current directory.",
    )
    parser.add_argument(
        "--task-state",
        required=True,
        help="Task state JSON path.",
    )
    parser.add_argument(
        "--output",
        help="Validation result JSON output path. Defaults to a /tmp file.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    task_state_path = Path(args.task_state).expanduser()
    output_path = Path(args.output).expanduser() if args.output else make_default_output_path()

    if not task_state_path.is_absolute():
        task_state_path = repo_root / task_state_path

    if not output_path.is_absolute():
        output_path = repo_root / output_path

    try:
        task_state = load_json(task_state_path)
    except Exception as exc:
        result = {
            "ok": False,
            "stage": "load_task_state",
            "task_state": str(task_state_path),
            "error": str(exc),
        }
        json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
        sys.stdout.write("\n")
        return 2

    state_ok, state_errors = validate_task_state(task_state)
    vm_validation = task_state.get("vm_validation") or {}
    sync = vm_validation.get("sync") or {}
    expected_branch = str(sync.get("expected_branch") or task_state.get("git", {}).get("base_branch") or "main")
    git_state = check_git_state(repo_root, expected_branch)

    result: dict[str, Any] = {
        "ok": False,
        "mode": "validation_only",
        "task_id": task_state.get("task_id"),
        "task_name": task_state.get("task_name"),
        "task_state": str(task_state_path),
        "output_path": str(output_path),
        "task_state_valid": state_ok,
        "task_state_errors": state_errors,
        "git_state": git_state,
        "validation_results": [],
        "all_required_checks_passed": False,
        "production_side_effect": "not_allowed",
        "git_pull_executed": False,
        "email_sent": False,
    }

    if not state_ok:
        result["blocked_reason"] = "task state validation failed"
    elif not git_state["ok"]:
        result["blocked_reason"] = "git safety check failed"
    else:
        commands = vm_validation.get("commands") or []
        validation_results = run_validation_commands(repo_root, commands)
        result["validation_results"] = validation_results
        result["all_required_checks_passed"] = all_required_checks_passed(validation_results)
        result["ok"] = result["all_required_checks_passed"]
        if not result["ok"]:
            result["blocked_reason"] = "required validation command failed"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_text = json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None)
    output_path.write_text(output_text + "\n", encoding="utf-8")

    json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
    sys.stdout.write("\n")

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
