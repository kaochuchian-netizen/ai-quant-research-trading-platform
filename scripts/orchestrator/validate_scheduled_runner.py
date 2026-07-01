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
EXPECTED_WINDOWS = [
    "pre_open_0700",
    "intraday_1305",
    "pre_close_1335",
    "post_close_1500",
]
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
    approved_delivery_path = repo_root / "scripts" / "orchestrator" / "approved_pre_open_delivery.py"
    runner_path = repo_root / "app" / "pipelines" / "runner.py"
    main_path = repo_root / "main.py"

    reasons: list[str] = []
    files = {
        "run_stock_analysis.sh": shell_path,
        "scripts/run_pipeline.py": cli_path,
        "scripts/orchestrator/approved_pre_open_delivery.py": approved_delivery_path,
        "app/pipelines/runner.py": runner_path,
        "main.py": main_path,
    }

    missing_files = [name for name, path in files.items() if not path.exists()]
    for name in missing_files:
        reasons.append(f"required file missing: {name}")

    shell_text = read_text(shell_path) if shell_path.exists() else ""
    cli_text = read_text(cli_path) if cli_path.exists() else ""
    approved_delivery_text = read_text(approved_delivery_path) if approved_delivery_path.exists() else ""
    runner_text = read_text(runner_path) if runner_path.exists() else ""
    main_text = read_text(main_path) if main_path.exists() else ""

    shell_command_lines = [
        line.strip()
        for line in shell_text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]

    shell_invocation = next(
        (line for line in shell_command_lines if "scripts/orchestrator/approved_pre_open_delivery.py" in line),
        "",
    ) or next(
        (line for line in shell_command_lines if "scripts/run_pipeline.py" in line),
        "",
    )
    shell_command = shell_invocation.split(">>", 1)[0].strip()

    supported_windows_present = all(window in shell_text and window in approved_delivery_text for window in EXPECTED_WINDOWS)
    afternoon_pipelines_present = all(
        text in approved_delivery_text
        for text in [
            '"pipeline_type": "pre_open"',
            '"pipeline_type": "intraday"',
            '"pipeline_type": "pre_close"',
            '"pipeline_type": "post_close"',
            "concise_reminder",
            "prediction review pending / insufficient data",
        ]
    )
    approved_runner_command_present = (
        '"scripts/run_pipeline.py", cfg["pipeline_type"], "--production-approved"' in approved_delivery_text
    )
    approved_wrapper_enabled = (
        "STOCK_AI_APPROVED_DELIVERY" in shell_text
        and "scripts/orchestrator/approved_pre_open_delivery.py" in shell_text
        and supported_windows_present
        and afternoon_pipelines_present
        and approved_runner_command_present
    )
    legacy_escape_hatch_present = EXPECTED_SHELL_COMMAND in shell_text
    production_runner_present = EXPECTED_SHELL_COMMAND in shell_text or approved_wrapper_enabled

    if not production_runner_present:
        reasons.append("run_stock_analysis.sh does not call the expected scheduled runner command")
    if " main.py" in shell_text or shell_text.strip().endswith("main.py"):
        reasons.append("run_stock_analysis.sh still calls main.py")
    if not production_runner_present:
        reasons.append("run_stock_analysis.sh does not call scripts/run_pipeline.py")
    if not production_runner_present:
        reasons.append("scheduled runner command does not require --production-approved")
    if not supported_windows_present:
        reasons.append("approved delivery wrapper does not support all required scheduler windows")
    if not afternoon_pipelines_present:
        reasons.append("approved delivery wrapper does not define afternoon concise delivery policy")
    if not approved_runner_command_present:
        reasons.append("approved delivery wrapper does not call scripts/run_pipeline.py with --production-approved")
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
        "approved_wrapper_enabled": approved_wrapper_enabled,
        "supported_windows": EXPECTED_WINDOWS,
        "supported_windows_present": supported_windows_present,
        "afternoon_concise_policy_present": afternoon_pipelines_present,
        "legacy_escape_hatch_present": legacy_escape_hatch_present,
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
