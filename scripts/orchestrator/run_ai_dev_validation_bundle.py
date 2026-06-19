#!/usr/bin/env python3
"""Run the AI development validation bundle for the current branch.

This script orchestrates existing read-only validators and writes a combined
runtime report. It does not modify source files, commit, push, merge, create PRs,
send notifications, run production workflows, or place orders.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_RUNTIME_DIR = "~/.local/state/stock-ai-orchestrator"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_command(args: list[str], repo_root: Path) -> dict[str, Any]:
    proc = subprocess.run(
        args,
        cwd=str(repo_root),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    parsed = None
    if proc.stdout.strip().startswith("{"):
        try:
            parsed = json.loads(proc.stdout)
        except Exception:
            parsed = None
    return {
        "command": args,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "json": parsed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run AI development validation bundle.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--runtime-dir", default=DEFAULT_RUNTIME_DIR)
    parser.add_argument("--base", default="main")
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    runtime_dir = Path(args.runtime_dir).expanduser().resolve()
    runtime_dir.mkdir(parents=True, exist_ok=True)

    commands = [
        [sys.executable, "scripts/orchestrator/check_forbidden_changes.py", "--base", args.base, "--head", args.head, "--pretty"],
        [sys.executable, "scripts/orchestrator/validate_ai_branch.py", "--base", args.base, "--head", args.head, "--pretty"],
        [sys.executable, "scripts/orchestrator/prepare_ai_pr_summary.py", "--runtime-dir", str(runtime_dir), "--pretty"],
    ]

    results = [run_command(command, repo_root) for command in commands]
    passed = all(result["returncode"] == 0 for result in results)
    blocked_reasons: list[str] = []
    for result in results:
        data = result.get("json")
        if isinstance(data, dict):
            for key in ("reasons", "blocked_reasons"):
                values = data.get(key, [])
                if isinstance(values, list):
                    blocked_reasons.extend(str(item) for item in values)
        elif result["returncode"] != 0:
            blocked_reasons.append("command failed: " + " ".join(result["command"]))

    report = {
        "schema_version": 1,
        "checked_at": now_iso(),
        "ok": True,
        "passed": passed,
        "base": args.base,
        "head": args.head,
        "runtime_dir": str(runtime_dir),
        "results": results,
        "blocked_reasons": blocked_reasons,
        "side_effects": {
            "source_files_modified": False,
            "commit_created": False,
            "push_run": False,
            "pr_created": False,
            "merge_run": False,
            "production_command_run": False,
            "notification_sent": False,
            "trading_execution_run": False,
        },
    }

    report_path = runtime_dir / "ai_dev_validation_bundle.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    summary_path = runtime_dir / "ai_dev_validation_bundle.md"
    lines = [
        "# AI Development Validation Bundle",
        "",
        f"Checked at: `{report['checked_at']}`",
        f"Base: `{args.base}`",
        f"Head: `{args.head}`",
        f"Passed: `{passed}`",
        "",
        "## Commands",
        "",
    ]
    for result in results:
        lines.append("- `" + " ".join(result["command"]) + f"` → `{result['returncode']}`")
    lines.extend(["", "## Blocked reasons", ""])
    if blocked_reasons:
        lines.extend(f"- {reason}" for reason in blocked_reasons)
    else:
        lines.append("- None")
    lines.append("")
    summary_path.write_text("\n".join(lines), encoding="utf-8")

    output = {
        "ok": True,
        "passed": passed,
        "report_path": str(report_path),
        "summary_path": str(summary_path),
        "blocked_reasons": blocked_reasons,
        "side_effects": report["side_effects"],
    }
    json.dump(output, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
