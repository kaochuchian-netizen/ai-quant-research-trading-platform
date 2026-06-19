#!/usr/bin/env python3
"""Prepare a PR command summary for an AI development branch.

This helper reads runtime branch-plan artifacts and current Git state, then writes
review files with suggested commands. It does not create PRs, commit, push,
merge, send notifications, run production workflows, or modify source files.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


DEFAULT_RUNTIME_DIR = "~/.local/state/stock-ai-orchestrator"


def run_git(args: list[str], repo_root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(repo_root),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be object: {path}")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare AI PR command summary.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--runtime-dir", default=DEFAULT_RUNTIME_DIR)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    runtime_dir = Path(args.runtime_dir).expanduser().resolve()
    plan_path = runtime_dir / "ai_task_branch_plan.json"
    pr_body_path = runtime_dir / "ai_task_pr_body.md"
    summary_path = runtime_dir / "ai_task_pr_summary.md"
    command_path = runtime_dir / "ai_task_pr_commands.sh"

    reasons: list[str] = []
    if not plan_path.exists():
        reasons.append(f"missing branch plan: {plan_path}")
    if not pr_body_path.exists():
        reasons.append(f"missing PR body: {pr_body_path}")

    plan: dict[str, Any] = {}
    if not reasons:
        plan = load_json(plan_path)
        if not plan.get("prepared"):
            reasons.append("branch plan is not prepared")

    branch_proc = run_git(["rev-parse", "--abbrev-ref", "HEAD"], repo_root)
    current_branch = branch_proc.stdout.strip() if branch_proc.returncode == 0 else None
    status_proc = run_git(["status", "--short"], repo_root)
    git_status_short = status_proc.stdout.strip().splitlines() if status_proc.returncode == 0 else []

    base_branch = plan.get("base_branch", "main")
    branch_name = plan.get("branch_name")
    task = plan.get("task", {}) if isinstance(plan.get("task", {}), dict) else {}
    task_id = task.get("task_id", "unknown")
    pr_title = plan.get("pr_title") or f"AI Dev: {task_id}"

    if branch_name and current_branch != branch_name:
        reasons.append(f"current branch must be {branch_name}, got {current_branch}")

    changed_proc = run_git(["diff", "--name-only", f"{base_branch}...HEAD"], repo_root)
    changed_files = [line.strip() for line in changed_proc.stdout.splitlines() if line.strip()] if changed_proc.returncode == 0 else []
    if not changed_files:
        reasons.append("no changed files found for PR")

    validation_commands = [
        f"python3 scripts/orchestrator/validate_ai_branch.py --base {base_branch} --head HEAD --pretty",
        f"python3 scripts/orchestrator/check_forbidden_changes.py --base {base_branch} --head HEAD --pretty",
    ]

    push_command = f"git push -u origin {branch_name}" if branch_name else "git push -u origin <branch>"
    pr_command = (
        f"gh pr create --base {base_branch} --head {branch_name} "
        f"--title {json.dumps(pr_title, ensure_ascii=False)} "
        f"--body-file {pr_body_path}"
        if branch_name
        else "gh pr create --base main --head <branch> --body-file <body-file>"
    )

    command_text = "\n".join([
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        "",
        "git status",
        "git diff --stat",
        *validation_commands,
        push_command,
        pr_command,
        "",
    ])

    summary_lines = [
        f"# AI PR Summary: {task_id}",
        "",
        f"Base branch: `{base_branch}`",
        f"Working branch: `{branch_name}`",
        f"Current branch: `{current_branch}`",
        "",
        "## Changed files",
        "",
    ]
    summary_lines.extend(f"- `{path}`" for path in changed_files)
    summary_lines.extend([
        "",
        "## Validation commands",
        "",
    ])
    summary_lines.extend(f"- `{cmd}`" for cmd in validation_commands)
    summary_lines.extend([
        "",
        "## Suggested PR commands",
        "",
        "```bash",
        push_command,
        pr_command,
        "```",
        "",
        "## Blocked reasons",
        "",
    ])
    summary_lines.extend(f"- {reason}" for reason in reasons) if reasons else summary_lines.append("- None")
    summary_text = "\n".join(summary_lines) + "\n"

    runtime_dir.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(summary_text, encoding="utf-8")
    command_path.write_text(command_text, encoding="utf-8")

    result = {
        "ok": True,
        "ready_for_pr": not reasons,
        "task_id": task_id,
        "base_branch": base_branch,
        "branch_name": branch_name,
        "current_branch": current_branch,
        "changed_files": changed_files,
        "git_status_short": git_status_short,
        "summary_path": str(summary_path),
        "command_path": str(command_path),
        "push_command": push_command,
        "pr_command": pr_command,
        "blocked_reasons": reasons,
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
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    return 0 if result["ready_for_pr"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
