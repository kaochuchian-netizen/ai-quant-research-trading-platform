#!/usr/bin/env python3
"""Run the Phase C stage notification pipeline.

This runner only orchestrates existing safety-scoped scripts:
- collect_validation_snapshot.py
- render_notice_from_template.py
- notify_stage_report.py

Default mode is preview only. Mail delivery is only enabled when --send is
explicitly provided.
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


DEFAULT_TEMPLATE = "orchestrator/templates/email_summary_template.md"
DEFAULT_TMP_PREFIX = "stock_ai_orchestrator_stage_"


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
        summary["stdout"] = completed.stdout
    if completed.stderr:
        summary["stderr"] = completed.stderr
    return summary


def make_default_outputs() -> tuple[Path, Path]:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    tmp_dir = Path(tempfile.gettempdir())
    return (
        tmp_dir / f"{DEFAULT_TMP_PREFIX}{timestamp}_validation_snapshot.json",
        tmp_dir / f"{DEFAULT_TMP_PREFIX}{timestamp}_notice.md",
    )


def collect_snapshot(
    repo_root: Path,
    snapshot_output: Path,
    python_files: list[str],
    pretty: bool,
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(repo_script(repo_root, "collect_validation_snapshot.py")),
        "--repo-root",
        str(repo_root),
    ]
    for python_file in python_files:
        command.extend(["--python-file", python_file])
    if pretty:
        command.append("--pretty")

    completed = run_command(command, repo_root)
    if completed.returncode == 0:
        snapshot_output.parent.mkdir(parents=True, exist_ok=True)
        snapshot_output.write_text(completed.stdout, encoding="utf-8")
    return completed


def render_notice(
    repo_root: Path,
    template: Path,
    task_state: Path,
    snapshot_output: Path,
    notice_output: Path,
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(repo_script(repo_root, "render_notice_from_template.py")),
        "--template",
        str(template),
        "--task-state",
        str(task_state),
        "--validation-snapshot",
        str(snapshot_output),
        "--output",
        str(notice_output),
    ]
    return run_command(command, repo_root)


def notify_stage(
    repo_root: Path,
    notice_output: Path,
    env_file: str | None,
    subject: str | None,
    send: bool,
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(repo_script(repo_root, "notify_stage_report.py")),
        "--notice",
        str(notice_output),
    ]
    if subject:
        command.extend(["--subject", subject])
    if env_file:
        command.extend(["--env-file", env_file])
    if send:
        command.append("--send")

    return run_command(command, repo_root)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the Orchestrator stage notification pipeline.",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root. Defaults to current directory.",
    )
    parser.add_argument(
        "--template",
        default=DEFAULT_TEMPLATE,
        help=f"Notice template path. Defaults to {DEFAULT_TEMPLATE}.",
    )
    parser.add_argument(
        "--task-state",
        required=True,
        help="Task state JSON path.",
    )
    parser.add_argument(
        "--snapshot-output",
        help="Validation snapshot output path. Defaults to a /tmp file.",
    )
    parser.add_argument(
        "--notice-output",
        help="Rendered notice output path. Defaults to a /tmp file.",
    )
    parser.add_argument(
        "--python-file",
        action="append",
        default=[],
        help="Python file to syntax-check in the validation snapshot. Can be repeated.",
    )
    parser.add_argument(
        "--env-file",
        help="Mail environment file path passed through to notify_stage_report.py.",
    )
    parser.add_argument(
        "--subject",
        help="Optional subject override passed through to notify_stage_report.py.",
    )
    parser.add_argument(
        "--send",
        action="store_true",
        help="Actually deliver the notice. Preview mode is the default.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON outputs where supported.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    default_snapshot, default_notice = make_default_outputs()
    snapshot_output = Path(args.snapshot_output).expanduser() if args.snapshot_output else default_snapshot
    notice_output = Path(args.notice_output).expanduser() if args.notice_output else default_notice
    template = Path(args.template).expanduser()
    task_state = Path(args.task_state).expanduser()

    if not template.is_absolute():
        template = repo_root / template
    if not task_state.is_absolute():
        task_state = repo_root / task_state
    if not snapshot_output.is_absolute():
        snapshot_output = repo_root / snapshot_output
    if not notice_output.is_absolute():
        notice_output = repo_root / notice_output

    collect_result = collect_snapshot(
        repo_root=repo_root,
        snapshot_output=snapshot_output,
        python_files=args.python_file,
        pretty=args.pretty,
    )
    if collect_result.returncode != 0:
        json.dump(
            {
                "ok": False,
                "failed_stage": "collect_validation_snapshot",
                "send_requested": bool(args.send),
                "snapshot_output": str(snapshot_output),
                "notice_output": str(notice_output),
                "collect_validation_snapshot": command_summary("collect_validation_snapshot", collect_result),
            },
            sys.stdout,
            ensure_ascii=False,
            indent=2,
        )
        sys.stdout.write("\n")
        return collect_result.returncode

    render_result = render_notice(
        repo_root=repo_root,
        template=template,
        task_state=task_state,
        snapshot_output=snapshot_output,
        notice_output=notice_output,
    )
    if render_result.returncode != 0:
        json.dump(
            {
                "ok": False,
                "failed_stage": "render_notice_from_template",
                "send_requested": bool(args.send),
                "snapshot_output": str(snapshot_output),
                "notice_output": str(notice_output),
                "collect_validation_snapshot": command_summary("collect_validation_snapshot", collect_result),
                "render_notice_from_template": command_summary("render_notice_from_template", render_result),
            },
            sys.stdout,
            ensure_ascii=False,
            indent=2,
        )
        sys.stdout.write("\n")
        return render_result.returncode

    notify_result = notify_stage(
        repo_root=repo_root,
        notice_output=notice_output,
        env_file=args.env_file,
        subject=args.subject,
        send=args.send,
    )

    output = {
        "ok": notify_result.returncode == 0,
        "mode": "send" if args.send else "preview",
        "send_requested": bool(args.send),
        "snapshot_output": str(snapshot_output),
        "notice_output": str(notice_output),
        "collect_validation_snapshot": command_summary("collect_validation_snapshot", collect_result),
        "render_notice_from_template": command_summary("render_notice_from_template", render_result),
        "notify_stage_report": command_summary(
            "notify_stage_report",
            notify_result,
            include_stdout=not args.send,
        ),
    }
    json.dump(output, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return notify_result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
