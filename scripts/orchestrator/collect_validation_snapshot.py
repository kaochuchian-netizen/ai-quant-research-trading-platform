#!/usr/bin/env python3
"""Collect a read-only validation snapshot for AI DevOps Orchestrator review.

This tool is intentionally conservative:
- It does not modify repository files.
- It does not run main.py.
- It does not run backtests.
- It does not run migrations.
- It does not send LINE messages.
- It does not commit, push, reset, checkout, or delete files.

It collects Git status / diff metadata and can perform a py_compile-like
syntax validation by compiling source text in memory without writing .pyc files.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

FORBIDDEN_PATH_KEYWORDS = (
    ".env",
    "credentials",
    "token",
    "secret",
    "data/stock_analysis.db",
    "data/backups/",
    "crontab",
)

FORBIDDEN_COMMAND_KEYWORDS = (
    "main.py",
    "run_pipeline.py pre_open",
    "migration",
    "LINE",
    "cron",
    "git commit",
    "git push",
    "git reset",
    "git checkout",
    "rm ",
)


def run_read_only_command(args: list[str], cwd: Path) -> dict[str, Any]:
    completed = subprocess.run(
        args,
        cwd=str(cwd),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    return {
        "command": args,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def collect_git_snapshot(repo_root: Path) -> dict[str, Any]:
    return {
        "status_short": run_read_only_command(["git", "status", "--short"], repo_root),
        "diff_stat": run_read_only_command(["git", "diff", "--stat"], repo_root),
        "diff_name_only": run_read_only_command(["git", "diff", "--name-only"], repo_root),
        "head": run_read_only_command(["git", "rev-parse", "HEAD"], repo_root),
        "branch": run_read_only_command(["git", "branch", "--show-current"], repo_root),
    }


def syntax_check_python_file(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "path": str(path),
        "exists": path.exists(),
        "ok": False,
        "error": None,
    }

    if not path.exists():
        result["error"] = "file does not exist"
        return result

    try:
        source = path.read_text(encoding="utf-8")
        compile(source, str(path), "exec")
    except Exception as exc:  # noqa: BLE001 - report validation errors verbatim
        result["error"] = f"{type(exc).__name__}: {exc}"
        return result

    result["ok"] = True
    return result


def detect_forbidden_path_changes(diff_name_only: str) -> list[str]:
    changed_paths = [line.strip() for line in diff_name_only.splitlines() if line.strip()]
    flagged: list[str] = []

    for path in changed_paths:
        normalized = path.replace("\\", "/")
        if any(keyword in normalized for keyword in FORBIDDEN_PATH_KEYWORDS):
            flagged.append(path)

    return flagged


def build_snapshot(repo_root: Path, python_files: list[str]) -> dict[str, Any]:
    git_snapshot = collect_git_snapshot(repo_root)
    diff_name_only = git_snapshot["diff_name_only"].get("stdout", "")

    syntax_results = [
        syntax_check_python_file(repo_root / python_file)
        for python_file in python_files
    ]

    return {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "repo_root": str(repo_root),
        "tool_mode": "read_only_validation_snapshot",
        "safety_rules": {
            "does_not_run_main_py": True,
            "does_not_run_backtest": True,
            "does_not_run_migration": True,
            "does_not_send_line": True,
            "does_not_commit_or_push": True,
            "does_not_modify_db": True,
            "forbidden_command_keywords": list(FORBIDDEN_COMMAND_KEYWORDS),
        },
        "git": git_snapshot,
        "python_syntax_validation": syntax_results,
        "forbidden_path_changes": detect_forbidden_path_changes(diff_name_only),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Collect a read-only Orchestrator validation snapshot.",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root. Defaults to current directory.",
    )
    parser.add_argument(
        "--python-file",
        action="append",
        default=[],
        help="Python file to syntax-check in memory. Can be repeated.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output.",
    )

    args = parser.parse_args()
    repo_root = Path(args.repo_root).resolve()

    snapshot = build_snapshot(repo_root, args.python_file)
    json.dump(
        snapshot,
        sys.stdout,
        ensure_ascii=False,
        indent=2 if args.pretty else None,
    )
    sys.stdout.write("\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
