#!/usr/bin/env python3
"""Validate the scheduled LINE runner entrypoint without running it.

This checker is intentionally read-only. It inspects source files and the cron
shell script, but it does not execute pipelines, send notifications, read
secrets, modify schedulers, or write production data.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


EXPECTED_SHELL_COMMAND = (
    "/home/kaochuchian/stock-ai/venv/bin/python "
    "scripts/run_pipeline.py pre_open --production-approved"
)
MAIN_PY_GUARD = (
    "main.py only allows --dry-run execution. "
    "Use scripts/run_pipeline.py for formal runs."
)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate scheduled runner wiring.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    shell_path = repo_root / "run_stock_analysis.sh"
    cli_path = repo_root / "scripts" / "run_pipeline.py"
    runner_path = repo_root / "app" / "pipelines" / "runner.py"
    main_path = repo_root / "main.py"

    reasons: list[str] = []
    files = {
        "run_stock_analysis.sh": shell_path,
        "scripts/run_pipeline.py": cli_path,
        "app/pipelines/runner.py": runner_path,
        "main.py": main_path,
    }

    missing_files = [name for name, path in files.items() if not path.exists()]
    for name in missing_files:
        reasons.append(f"required file missing: {name}")

    shell_text = read_text(shell_path) if shell_path.exists() else ""
    cli_text = read_text(cli_path) if cli_path.exists() else ""
    runner_text = read_text(runner_path) if runner_path.exists() else ""
    main_text = read_text(main_path) if main_path.exists() else ""

    shell_command_lines = [
        line.strip()
        for line in shell_text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]

    shell_invocation = next(
        (line for line in shell_command_lines if "venv/bin/python" in line),
        "",
    )
    shell_command = shell_invocation.split(">>", 1)[0].strip()

    if shell_command != EXPECTED_SHELL_COMMAND:
        reasons.append("run_stock_analysis.sh does not call the expected scheduled runner command")
    if " main.py" in shell_command or shell_command.endswith("main.py"):
        reasons.append("run_stock_analysis.sh still calls main.py")
    if "scripts/run_pipeline.py" not in shell_command:
        reasons.append("run_stock_analysis.sh does not call scripts/run_pipeline.py")
    if "--production-approved" not in shell_command:
        reasons.append("scheduled runner command does not require --production-approved")
    if "--dry-run" in shell_command:
        reasons.append("scheduled runner command should not include --dry-run")
    if "--production-approved" not in cli_text:
        reasons.append("scripts/run_pipeline.py does not expose --production-approved")
    if "production_approved" not in runner_text:
        reasons.append("app/pipelines/runner.py does not enforce production approval")
    if MAIN_PY_GUARD not in main_text:
        reasons.append("main.py dry-run safety guard is missing or changed")

    result = {
        "ok": True,
        "passed": not reasons,
        "checked_files": sorted(files),
        "scheduled_command": shell_command,
        "expected_command": EXPECTED_SHELL_COMMAND,
        "main_py_guard_present": MAIN_PY_GUARD in main_text,
        "reasons": reasons,
        "side_effects": {
            "files_modified": False,
            "pipeline_executed": False,
            "production_command_run": False,
            "notification_sent": False,
            "secrets_read": False,
            "scheduler_modified": False,
            "database_modified": False,
            "trading_execution_run": False,
        },
    }
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    return 0 if result["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
