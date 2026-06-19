#!/usr/bin/env python3
"""Run one supervised AI development loop without auto merge or archive."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


DEFAULT_RUNTIME_DIR = "~/.local/state/stock-ai-orchestrator"
REQUIRED_BASE_BRANCH = "main"
REQUIRED_BRANCH_PREFIX = "ai-dev/"


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


def run_git(args: list[str], repo_root: Path) -> dict[str, Any]:
    return run_command(["git", *args], repo_root)


def load_json_if_exists(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else None


def inspect_runtime(repo_root: Path, runtime_dir: Path, pretty: bool) -> dict[str, Any]:
    command = [
        sys.executable,
        "scripts/orchestrator/inspect_ai_runtime_queue.py",
        "--repo-root",
        str(repo_root),
        "--runtime-dir",
        str(runtime_dir),
    ]
    if pretty:
        command.append("--pretty")
    return run_command(command, repo_root)


def current_branch(repo_root: Path) -> str | None:
    result = run_git(["rev-parse", "--abbrev-ref", "HEAD"], repo_root)
    return result["stdout"].strip() if result["returncode"] == 0 else None


def git_status_short(repo_root: Path) -> list[str]:
    result = run_git(["status", "--short"], repo_root)
    if result["returncode"] != 0:
        return ["<git status failed>"]
    return result["stdout"].rstrip("\n").splitlines() if result["stdout"] else []


def status_paths(status_short: list[str]) -> list[str]:
    paths: list[str] = []
    for line in status_short:
        if not line:
            continue
        path = line[3:].strip() if len(line) > 3 else line.strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1].strip()
        if path:
            paths.append(path)
    return paths


def changed_files(repo_root: Path, base_branch: str) -> list[str]:
    result = run_git(["diff", "--name-only", f"{base_branch}...HEAD"], repo_root)
    if result["returncode"] != 0:
        return []
    return [line.strip() for line in result["stdout"].splitlines() if line.strip()]


def find_pr(repo_root: Path, branch_name: str) -> dict[str, Any] | None:
    if not branch_name.startswith(REQUIRED_BRANCH_PREFIX):
        return None
    result = run_command(
        [
            "gh",
            "pr",
            "view",
            branch_name,
            "--json",
            "number,url,state,mergeStateStatus,baseRefName,headRefName,statusCheckRollup",
        ],
        repo_root,
    )
    if result["returncode"] != 0 or not isinstance(result.get("json"), dict):
        return None
    return result["json"]


def status_rollup_summary(status_rollup: Any) -> list[dict[str, Any]]:
    if not isinstance(status_rollup, list):
        return []
    checks: list[dict[str, Any]] = []
    for item in status_rollup:
        if not isinstance(item, dict):
            continue
        checks.append(
            {
                "name": item.get("name") or item.get("context"),
                "status": item.get("status") or item.get("state"),
                "conclusion": item.get("conclusion"),
            }
        )
    return checks


def merge_eligibility(pr: dict[str, Any] | None, validation: dict[str, Any] | None, clean: bool) -> dict[str, Any]:
    reasons: list[str] = []
    if validation is None or validation.get("passed") is not True:
        reasons.append("local validation bundle must pass")
    if pr is None:
        reasons.append("PR must exist before merge eligibility can be evaluated")
    else:
        if pr.get("state") != "OPEN":
            reasons.append("PR state must be OPEN")
        if pr.get("mergeStateStatus") != "CLEAN":
            reasons.append("PR mergeStateStatus must be CLEAN")
        checks = status_rollup_summary(pr.get("statusCheckRollup"))
        if not any(check.get("name") == "validate-ai-branch" and check.get("conclusion") == "SUCCESS" for check in checks):
            reasons.append("required check validate-ai-branch must be SUCCESS")
    if not clean:
        reasons.append("working tree must be clean")
    return {"eligible": not reasons, "blocked_reasons": reasons}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one supervised AI development closed-loop step.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--runtime-dir", default=DEFAULT_RUNTIME_DIR)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--create-pr", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    runtime_dir = Path(args.runtime_dir).expanduser().resolve()
    plan_path = runtime_dir / "ai_task_branch_plan.json"
    validation_path = runtime_dir / "ai_dev_validation_bundle.json"
    plan = load_json_if_exists(plan_path)
    task = plan.get("task", {}) if isinstance(plan, dict) and isinstance(plan.get("task"), dict) else {}
    base_branch = str(plan.get("base_branch") if isinstance(plan, dict) else REQUIRED_BASE_BRANCH)
    branch_name = str(plan.get("branch_name") if isinstance(plan, dict) else task.get("branch_name", ""))
    branch = current_branch(repo_root)
    status_short = git_status_short(repo_root)
    clean = not status_short
    committed_changes = changed_files(repo_root, base_branch or REQUIRED_BASE_BRANCH)
    worktree_changes = status_paths(status_short)
    files_changed = sorted(set(committed_changes + worktree_changes))

    output: dict[str, Any] = {
        "ok": True,
        "state": "inspected",
        "dry_run": args.dry_run,
        "create_pr": args.create_pr,
        "auto_merge": False,
        "archive": False,
        "runtime_dir": str(runtime_dir),
        "task_id": task.get("task_id"),
        "base_branch": base_branch,
        "branch_name": branch_name,
        "current_branch": branch,
        "git_status_short": status_short,
        "changed_files": files_changed,
        "committed_changed_files": committed_changes,
        "worktree_changed_files": worktree_changes,
        "commands": [],
        "inspection": None,
        "validation": None,
        "pr": None,
        "merge_eligibility": None,
        "next_action": None,
        "reasons": [],
        "side_effects": {
            "runtime_queue_modified": False,
            "runtime_plan_written": False,
            "runtime_pr_body_written": False,
            "branch_created": False,
            "branch_switched": False,
            "source_files_modified": False,
            "commit_created": False,
            "push_run": False,
            "pr_created": False,
            "merge_run": False,
            "archive_run": False,
            "production_command_run": False,
            "notification_sent": False,
            "trading_execution_run": False,
            "scheduler_modified": False,
        },
    }

    inspection = inspect_runtime(repo_root, runtime_dir, args.pretty)
    output["commands"].append(inspection)
    output["inspection"] = inspection.get("json")

    if args.dry_run:
        output["state"] = "dry_run_preview"
        output["next_action"] = (
            "commit branch work before PR creation"
            if files_changed and not clean
            else "run without --dry-run to validate and optionally create PR"
        )
        output["preview"] = {
            "would_run_validation_bundle": bool(committed_changes and clean),
            "would_create_pr": bool(args.create_pr and files_changed and clean),
            "would_auto_merge": False,
            "would_archive": False,
            "would_run_production": False,
            "would_send_notifications": False,
            "would_trade": False,
            "would_modify_scheduler": False,
        }
        json.dump(output, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
        sys.stdout.write("\n")
        return 0

    if branch == REQUIRED_BASE_BRANCH:
        queue_result = run_command(
            [
                sys.executable,
                "scripts/orchestrator/run_ai_task_queue_once.py",
                "--repo-root",
                str(repo_root),
                "--runtime-dir",
                str(runtime_dir),
                "--pretty",
            ],
            repo_root,
        )
        output["commands"].append(queue_result)
        output["state"] = queue_result.get("json", {}).get("state", "queue_runner_finished") if isinstance(queue_result.get("json"), dict) else "queue_runner_finished"
        output["ok"] = queue_result["returncode"] == 0
        output["next_action"] = "implement task on the prepared ai-dev branch"
        json.dump(output, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
        sys.stdout.write("\n")
        return 0 if output["ok"] else 2

    if not branch or not branch.startswith(REQUIRED_BRANCH_PREFIX):
        output["ok"] = False
        output["state"] = "blocked_wrong_branch"
        output["reasons"].append("current branch must be main or ai-dev/*")
        output["next_action"] = "switch to the task branch or main"
        json.dump(output, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
        sys.stdout.write("\n")
        return 2

    if not files_changed:
        output["state"] = "handoff_ready"
        output["next_action"] = "implement task changes inside allowed paths"
        json.dump(output, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
        sys.stdout.write("\n")
        return 0

    if not clean:
        output["state"] = "branch_work_uncommitted"
        output["next_action"] = "commit branch work, then run validation and optionally create PR"
        json.dump(output, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
        sys.stdout.write("\n")
        return 0

    validation_result = run_command(
        [
            sys.executable,
            "scripts/orchestrator/run_ai_dev_validation_bundle.py",
            "--repo-root",
            str(repo_root),
            "--runtime-dir",
            str(runtime_dir),
            "--base",
            base_branch or REQUIRED_BASE_BRANCH,
            "--head",
            "HEAD",
            "--pretty",
        ],
        repo_root,
    )
    output["commands"].append(validation_result)
    validation_json = validation_result.get("json") if isinstance(validation_result.get("json"), dict) else None
    output["validation"] = validation_json
    if validation_result["returncode"] != 0 or not validation_json or validation_json.get("passed") is not True:
        output["ok"] = False
        output["state"] = "validation_failed"
        output["reasons"].extend(validation_json.get("blocked_reasons", []) if validation_json else [])
        output["next_action"] = "fix validation failures before PR creation"
        json.dump(output, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
        sys.stdout.write("\n")
        return 2

    validation_report = load_json_if_exists(validation_path)
    if git_status_short(repo_root):
        output["state"] = "validation_passed_dirty"
        output["next_action"] = "commit branch work, then rerun with --create-pr"
        output["merge_eligibility"] = merge_eligibility(None, validation_report, False)
        json.dump(output, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
        sys.stdout.write("\n")
        return 0

    pr: dict[str, Any] | None = find_pr(repo_root, branch_name)
    if args.create_pr and pr is None:
        pr_result = run_command(
            [
                sys.executable,
                "scripts/orchestrator/run_ai_task_queue_once.py",
                "--repo-root",
                str(repo_root),
                "--runtime-dir",
                str(runtime_dir),
                "--create-pr",
                "--pretty",
            ],
            repo_root,
        )
        output["commands"].append(pr_result)
        pr_json = pr_result.get("json") if isinstance(pr_result.get("json"), dict) else {}
        output["state"] = pr_json.get("state", "pr_runner_finished")
        output["ok"] = pr_result["returncode"] == 0
        output["pr"] = pr_json.get("pr")
        side_effects = pr_json.get("side_effects", {}) if isinstance(pr_json, dict) else {}
        output["side_effects"]["push_run"] = bool(side_effects.get("push_run"))
        output["side_effects"]["pr_created"] = bool(side_effects.get("pr_created"))
        output["merge_eligibility"] = merge_eligibility(output["pr"], validation_report, True)
        output["next_action"] = "wait for GitHub Actions and human review; do not merge or archive automatically"
        json.dump(output, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
        sys.stdout.write("\n")
        return 0 if output["ok"] else 2

    output["state"] = "validation_passed"
    output["pr"] = pr
    output["merge_eligibility"] = merge_eligibility(pr, validation_report, True)
    output["next_action"] = (
        "rerun with --create-pr to push and open PR"
        if pr is None
        else "wait for GitHub Actions and human review; merge/archive remain manual"
    )
    json.dump(output, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
