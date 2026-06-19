#!/usr/bin/env python3
"""Run VM-side stage validation for the AI DevOps Orchestrator.

This runner is intentionally conservative:
- It validates branch and clean working tree state.
- It executes only allowlisted validation command types from task state.
- It supports controlled git pull only when --pull is provided and task state allows it.
- It supports stage notification only when --notify is provided.
- It supports a read-only approval gate from a local approval-state JSON file.
- It does not run main.py, backtests, migrations, DB writes, LINE, cron edits,
  approval endpoints, production pipelines, or trading actions.
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
APPROVED_CONTINUE = "approved_continue"
APPROVED_PAUSE = "approved_pause"
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


def repo_script(repo_root: Path, name: str) -> Path:
    return repo_root / "scripts" / "orchestrator" / name


def git_output(repo_root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return run_command(["git", *args], repo_root)


def command_summary(
    completed: subprocess.CompletedProcess[str],
    include_output: bool = True,
) -> dict[str, Any]:
    summary: dict[str, Any] = {"returncode": completed.returncode}

    if include_output:
        summary["stdout"] = completed.stdout.strip()
        summary["stderr"] = completed.stderr.strip()

    return summary


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError("JSON file must contain an object")

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

    if sync.get("git_pull_allowed") not in (True, False, None):
        errors.append("git_pull_allowed must be true, false, or omitted")

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


def run_git_pull(repo_root: Path) -> subprocess.CompletedProcess[str]:
    return git_output(repo_root, ["pull", "--ff-only"])


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
    completed = run_command([sys.executable, "-m", "py_compile", target], repo_root)

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


def run_stage_notification(
    repo_root: Path,
    task_state_path: Path,
    env_file: str | None,
    subject: str | None,
    send: bool,
    pretty: bool,
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(repo_script(repo_root, "run_stage_notification.py")),
        "--repo-root",
        str(repo_root),
        "--task-state",
        str(task_state_path),
        "--python-file",
        "scripts/orchestrator/run_vm_stage_validation.py",
    ]

    if env_file:
        command.extend(["--env-file", env_file])
    if subject:
        command.extend(["--subject", subject])
    if send:
        command.append("--send")
    if pretty:
        command.append("--pretty")

    return run_command(command, repo_root)


def nested_get(data: dict[str, Any], *keys: str) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def evaluate_approval_gate(
    approval_state: dict[str, Any],
    expected_task_id: str | None,
    require_continue: bool,
) -> dict[str, Any]:
    task_id = approval_state.get("task_id")
    task_name = approval_state.get("task_name")
    state = nested_get(approval_state, "approval", "state")
    selected_action = nested_get(approval_state, "approval", "selected_action")

    task_id_matches = True
    if expected_task_id:
        task_id_matches = task_id == expected_task_id

    decision = "blocked"
    next_task_allowed = False
    pause_requested = False
    blocked_reason = None

    if not task_id_matches:
        blocked_reason = f"task_id mismatch: {task_id} != {expected_task_id}"
    elif state == APPROVED_CONTINUE and selected_action == "continue":
        decision = "continue"
        next_task_allowed = True
    elif state == APPROVED_PAUSE and selected_action == "pause":
        decision = "pause"
        pause_requested = True
    else:
        blocked_reason = f"unsupported approval state: {state}"

    if require_continue and not next_task_allowed:
        blocked_reason = blocked_reason or "continue approval required"

    return {
        "ok": blocked_reason is None,
        "task_id": task_id,
        "task_name": task_name,
        "expected_task_id": expected_task_id,
        "task_id_matches": task_id_matches,
        "approval_state": state,
        "selected_action": selected_action,
        "decision": decision,
        "next_task_allowed": next_task_allowed,
        "pause_requested": pause_requested,
        "blocked_reason": blocked_reason,
        "side_effects": {
            "email_sent": False,
            "git_command_run": False,
            "task_started": False,
            "production_command_run": False,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run VM-side allowlisted validation commands from task state.")
    parser.add_argument("--repo-root", default=".", help="Repository root. Defaults to current directory.")
    parser.add_argument("--task-state", required=True, help="Task state JSON path.")
    parser.add_argument("--output", help="Validation result JSON output path. Defaults to a /tmp file.")
    parser.add_argument("--pull", action="store_true", help="Run git pull --ff-only only when task state allows it.")
    parser.add_argument("--notify", action="store_true", help="Run stage notification after successful validation. Preview mode by default.")
    parser.add_argument("--env-file", help="Mail environment file path passed through to stage notification.")
    parser.add_argument("--subject", help="Optional subject override passed through to stage notification.")
    parser.add_argument("--send", action="store_true", help="Actually send the stage notification. Requires --notify.")
    parser.add_argument("--approval-state", help="Optional local approval-state JSON path to evaluate after validation.")
    parser.add_argument("--expected-approval-task-id", help="Require approval-state task_id to match this value. Defaults to task_state task_id.")
    parser.add_argument("--require-approval-continue", action="store_true", help="Block unless approval-state decision is continue.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    task_state_path = Path(args.task_state).expanduser()
    output_path = Path(args.output).expanduser() if args.output else make_default_output_path()
    approval_state_path = Path(args.approval_state).expanduser() if args.approval_state else None

    if not task_state_path.is_absolute():
        task_state_path = repo_root / task_state_path
    if not output_path.is_absolute():
        output_path = repo_root / output_path
    if approval_state_path and not approval_state_path.is_absolute():
        approval_state_path = repo_root / approval_state_path

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
    expected_approval_task_id = args.expected_approval_task_id or str(task_state.get("task_id") or "")
    git_state_before = check_git_state(repo_root, expected_branch)
    git_state_after_pull: dict[str, Any] | None = None

    result: dict[str, Any] = {
        "ok": False,
        "mode": "validation_only",
        "task_id": task_state.get("task_id"),
        "task_name": task_state.get("task_name"),
        "task_state": str(task_state_path),
        "output_path": str(output_path),
        "task_state_valid": state_ok,
        "task_state_errors": state_errors,
        "git_state_before": git_state_before,
        "git_state_after_pull": None,
        "validation_results": [],
        "all_required_checks_passed": False,
        "production_side_effect": "not_allowed",
        "git_pull_requested": bool(args.pull),
        "git_pull_executed": False,
        "notification_requested": bool(args.notify),
        "notification_result": None,
        "email_send_requested": bool(args.send),
        "email_sent": False,
        "approval_state_requested": bool(approval_state_path),
        "approval_gate": None,
        "next_task_allowed": False,
        "pause_requested": False,
    }

    blocked_reason: str | None = None

    if args.send and not args.notify:
        blocked_reason = "--send requires --notify"
    elif not state_ok:
        blocked_reason = "task state validation failed"
    elif not git_state_before["ok"]:
        blocked_reason = "git safety check failed before validation"

    if blocked_reason is None and args.pull:
        if sync.get("git_pull_allowed") is not True:
            blocked_reason = "git pull requested but task state does not allow it"
        else:
            pull_completed = run_git_pull(repo_root)
            result["git_pull_result"] = command_summary(pull_completed)
            result["git_pull_executed"] = True

            if pull_completed.returncode != 0:
                blocked_reason = "git pull failed"
            else:
                git_state_after_pull = check_git_state(repo_root, expected_branch)
                result["git_state_after_pull"] = git_state_after_pull
                if not git_state_after_pull["ok"]:
                    blocked_reason = "git safety check failed after git pull"

    if blocked_reason is None:
        commands = vm_validation.get("commands") or []
        validation_results = run_validation_commands(repo_root, commands)
        validation_ok = all_required_checks_passed(validation_results)
        result["validation_results"] = validation_results
        result["all_required_checks_passed"] = validation_ok

        if not validation_ok:
            blocked_reason = "required validation command failed"
        elif args.notify:
            notify_completed = run_stage_notification(
                repo_root=repo_root,
                task_state_path=task_state_path,
                env_file=args.env_file,
                subject=args.subject,
                send=args.send,
                pretty=args.pretty,
            )
            result["notification_result"] = command_summary(notify_completed, include_output=not args.send)
            result["email_sent"] = bool(args.send and notify_completed.returncode == 0)
            if notify_completed.returncode != 0:
                blocked_reason = "stage notification failed"

    if blocked_reason is None and approval_state_path:
        try:
            approval_state = load_json(approval_state_path)
            approval_gate = evaluate_approval_gate(
                approval_state=approval_state,
                expected_task_id=expected_approval_task_id,
                require_continue=args.require_approval_continue,
            )
            result["approval_gate"] = approval_gate
            result["next_task_allowed"] = bool(approval_gate.get("next_task_allowed"))
            result["pause_requested"] = bool(approval_gate.get("pause_requested"))
            if not approval_gate.get("ok"):
                blocked_reason = str(approval_gate.get("blocked_reason") or "approval gate failed")
        except Exception as exc:
            blocked_reason = f"approval gate error: {exc}"

    if blocked_reason is not None:
        result["blocked_reason"] = blocked_reason
        result["ok"] = False
    else:
        result["ok"] = True

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_text = json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None)
    output_path.write_text(output_text + "\n", encoding="utf-8")

    json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
    sys.stdout.write("\n")

    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
