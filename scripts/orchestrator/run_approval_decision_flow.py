#!/usr/bin/env python3
"""Run the local approval-to-decision notification flow.

This runner chains existing local tools:
- parse_approval_reply.py
- run_vm_stage_validation.py
- summarize_next_task_decision.py
- run_stage_notification.py

Default mode previews notification output only. Mail delivery requires --send.
This runner does not start the next task, run Codex, or execute production commands.
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


DEFAULT_TMP_PREFIX = "stock_ai_orchestrator_approval_flow_"


def repo_script(repo_root: Path, name: str) -> Path:
    return repo_root / "scripts" / "orchestrator" / name


def run_command(args: list[str], repo_root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=str(repo_root),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def command_summary(
    name: str,
    completed: subprocess.CompletedProcess[str],
    include_stdout: bool = False,
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "name": name,
        "returncode": completed.returncode,
    }
    if include_stdout:
        summary["stdout"] = completed.stdout.strip()
    if completed.stderr:
        summary["stderr"] = completed.stderr.strip()
    return summary


def make_default_outputs(task_id: str) -> dict[str, Path]:
    safe_task_id = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in task_id)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    tmp_dir = Path(tempfile.gettempdir())
    prefix = f"{DEFAULT_TMP_PREFIX}{safe_task_id}_{timestamp}"
    return {
        "approval_state": tmp_dir / f"{prefix}_approval_state.json",
        "validation_result": tmp_dir / f"{prefix}_validation_result.json",
        "decision_summary": tmp_dir / f"{prefix}_decision_summary.json",
    }


def read_task_id(task_state_path: Path) -> str:
    try:
        with task_state_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        task_id = data.get("task_id") if isinstance(data, dict) else None
        return str(task_id or "unknown_task")
    except Exception:
        return "unknown_task"


def parse_reply(
    repo_root: Path,
    reply_file: str | None,
    task_state: Path,
    approval_state_output: Path,
    sender: str | None,
    allowed_sender: str | None,
    pretty: bool,
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(repo_script(repo_root, "parse_approval_reply.py")),
        "--task-state",
        str(task_state),
        "--output",
        str(approval_state_output),
    ]
    if reply_file:
        command.extend(["--reply-file", reply_file])
    if sender:
        command.extend(["--sender", sender])
    if allowed_sender:
        command.extend(["--allowed-sender", allowed_sender])
    if pretty:
        command.append("--pretty")
    return run_command(command, repo_root)


def run_validation_gate(
    repo_root: Path,
    validation_task_state: Path,
    approval_state_output: Path,
    validation_result_output: Path,
    expected_task_id: str,
    require_continue: bool,
    pretty: bool,
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(repo_script(repo_root, "run_vm_stage_validation.py")),
        "--task-state",
        str(validation_task_state),
        "--approval-state",
        str(approval_state_output),
        "--expected-approval-task-id",
        expected_task_id,
        "--output",
        str(validation_result_output),
    ]
    if require_continue:
        command.append("--require-approval-continue")
    if pretty:
        command.append("--pretty")
    return run_command(command, repo_root)


def summarize_decision(
    repo_root: Path,
    validation_result_output: Path,
    task_state: Path,
    decision_summary_output: Path,
    pretty: bool,
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(repo_script(repo_root, "summarize_next_task_decision.py")),
        "--validation-result",
        str(validation_result_output),
        "--task-state",
        str(task_state),
        "--output",
        str(decision_summary_output),
    ]
    if pretty:
        command.append("--pretty")
    return run_command(command, repo_root)


def run_notification(
    repo_root: Path,
    task_state: Path,
    decision_summary_output: Path,
    env_file: str | None,
    subject: str | None,
    send: bool,
    pretty: bool,
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(repo_script(repo_root, "run_stage_notification.py")),
        "--task-state",
        str(task_state),
        "--decision-summary",
        str(decision_summary_output),
        "--python-file",
        "scripts/orchestrator/run_approval_decision_flow.py",
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run local approval-to-decision notification flow.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--reply-file", help="Reply text file. Omit to read stdin in parse_approval_reply.py.")
    parser.add_argument("--task-state", required=True, help="Concrete stage task state JSON path.")
    parser.add_argument("--validation-task-state", required=True, help="VM validation task state JSON path.")
    parser.add_argument("--approval-state-output", help="Approval state output path. Defaults to /tmp.")
    parser.add_argument("--validation-result-output", help="VM validation result output path. Defaults to /tmp.")
    parser.add_argument("--decision-summary-output", help="Decision summary output path. Defaults to /tmp.")
    parser.add_argument("--sender", help="Optional reply sender identifier.")
    parser.add_argument("--allowed-sender", help="Optional exact sender allowlist check.")
    parser.add_argument("--expected-task-id", help="Expected approval task ID. Defaults to task_state task_id.")
    parser.add_argument("--require-continue", action="store_true", help="Block unless decision is continue.")
    parser.add_argument("--notify", action="store_true", help="Run stage notification after decision summary. Preview by default.")
    parser.add_argument("--env-file", help="Mail environment file path passed through to stage notification.")
    parser.add_argument("--subject", help="Optional subject override for stage notification.")
    parser.add_argument("--send", action="store_true", help="Actually send notification. Requires --notify.")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    task_state = Path(args.task_state).expanduser()
    validation_task_state = Path(args.validation_task_state).expanduser()

    if not task_state.is_absolute():
        task_state = repo_root / task_state
    if not validation_task_state.is_absolute():
        validation_task_state = repo_root / validation_task_state

    task_id = args.expected_task_id or read_task_id(task_state)
    defaults = make_default_outputs(task_id)
    approval_state_output = Path(args.approval_state_output).expanduser() if args.approval_state_output else defaults["approval_state"]
    validation_result_output = Path(args.validation_result_output).expanduser() if args.validation_result_output else defaults["validation_result"]
    decision_summary_output = Path(args.decision_summary_output).expanduser() if args.decision_summary_output else defaults["decision_summary"]

    if not approval_state_output.is_absolute():
        approval_state_output = repo_root / approval_state_output
    if not validation_result_output.is_absolute():
        validation_result_output = repo_root / validation_result_output
    if not decision_summary_output.is_absolute():
        decision_summary_output = repo_root / decision_summary_output

    result: dict[str, Any] = {
        "ok": False,
        "task_id": task_id,
        "task_state": str(task_state),
        "validation_task_state": str(validation_task_state),
        "approval_state_output": str(approval_state_output),
        "validation_result_output": str(validation_result_output),
        "decision_summary_output": str(decision_summary_output),
        "notification_requested": bool(args.notify),
        "send_requested": bool(args.send),
        "email_sent": False,
        "next_task_started": False,
    }

    if args.send and not args.notify:
        result["blocked_reason"] = "--send requires --notify"
        json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
        sys.stdout.write("\n")
        return 1

    parse_result = parse_reply(
        repo_root=repo_root,
        reply_file=args.reply_file,
        task_state=task_state,
        approval_state_output=approval_state_output,
        sender=args.sender,
        allowed_sender=args.allowed_sender,
        pretty=args.pretty,
    )
    result["parse_approval_reply"] = command_summary("parse_approval_reply", parse_result, include_stdout=True)
    if parse_result.returncode != 0:
        result["blocked_reason"] = "approval reply parse failed"
        json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
        sys.stdout.write("\n")
        return parse_result.returncode

    validation_result = run_validation_gate(
        repo_root=repo_root,
        validation_task_state=validation_task_state,
        approval_state_output=approval_state_output,
        validation_result_output=validation_result_output,
        expected_task_id=task_id,
        require_continue=args.require_continue,
        pretty=args.pretty,
    )
    result["run_vm_stage_validation"] = command_summary("run_vm_stage_validation", validation_result, include_stdout=True)
    if validation_result.returncode != 0:
        result["blocked_reason"] = "approval validation gate failed"
        json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
        sys.stdout.write("\n")
        return validation_result.returncode

    decision_result = summarize_decision(
        repo_root=repo_root,
        validation_result_output=validation_result_output,
        task_state=task_state,
        decision_summary_output=decision_summary_output,
        pretty=args.pretty,
    )
    result["summarize_next_task_decision"] = command_summary("summarize_next_task_decision", decision_result, include_stdout=True)
    if decision_result.returncode != 0:
        result["blocked_reason"] = "decision summary failed"
        json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
        sys.stdout.write("\n")
        return decision_result.returncode

    if args.notify:
        notify_result = run_notification(
            repo_root=repo_root,
            task_state=task_state,
            decision_summary_output=decision_summary_output,
            env_file=args.env_file,
            subject=args.subject,
            send=args.send,
            pretty=args.pretty,
        )
        result["run_stage_notification"] = command_summary("run_stage_notification", notify_result, include_stdout=not args.send)
        result["email_sent"] = bool(args.send and notify_result.returncode == 0)
        if notify_result.returncode != 0:
            result["blocked_reason"] = "stage notification failed"
            json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
            sys.stdout.write("\n")
            return notify_result.returncode

    try:
        with decision_summary_output.open("r", encoding="utf-8") as f:
            decision_summary = json.load(f)
        result["decision"] = decision_summary.get("decision")
        result["should_start_next_task"] = (decision_summary.get("next_task") or {}).get("should_start_next_task")
    except Exception:
        result["decision"] = None
        result["should_start_next_task"] = False

    result["ok"] = True
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
