#!/usr/bin/env python3
"""Run one safe AI task queue iteration.

This is a one-shot runner, not a daemon. It does not call Codex or any AI tool
to modify files. It can prepare a task branch, run validation for completed
branch work, optionally create a PR, optionally merge only after strict gates,
and archive a merged task.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_RUNTIME_DIR = "~/.local/state/stock-ai-orchestrator"
REQUIRED_BASE_BRANCH = "main"
REQUIRED_BRANCH_PREFIX = "ai-dev/"
INIT_COMMAND = "python3 scripts/orchestrator/init_ai_runtime_queue.py --pretty"
SAFE_BRANCH_RE = re.compile(r"^[A-Za-z0-9._/-]+$")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_ai_dev_branch(value: str) -> bool:
    return value.startswith(REQUIRED_BRANCH_PREFIX) and bool(SAFE_BRANCH_RE.fullmatch(value))


def is_python_executable(value: str) -> bool:
    return Path(value).name.startswith("python")


def is_int_text(value: str) -> bool:
    try:
        int(value)
        return True
    except ValueError:
        return False


def has_only_allowed_options(args: list[str], options_with_values: set[str], bare_options: set[str]) -> bool:
    index = 0
    while index < len(args):
        option = args[index]
        if option in bare_options:
            index += 1
            continue
        if option in options_with_values and index + 1 < len(args):
            index += 2
            continue
        return False
    return True


def validate_allowed_command(args: list[str]) -> tuple[bool, str | None]:
    if not args:
        return False, "empty command"

    if args == ["git", "status", "--short"]:
        return True, None
    if len(args) == 4 and args[:3] == ["git", "diff", "--name-only"]:
        base_head = args[3]
        if base_head == "main...HEAD":
            return True, None
        return False, "git diff is limited to main...HEAD"
    if len(args) == 4 and args[:3] == ["git", "rev-list", "--count"]:
        if args[3] == "main..HEAD":
            return True, None
        return False, "git rev-list is limited to main..HEAD"
    if args == ["git", "rev-parse", "--abbrev-ref", "HEAD"]:
        return True, None
    if len(args) == 5 and args[:4] == ["git", "show-ref", "--verify", "--quiet"]:
        ref = args[4]
        if ref.startswith("refs/heads/") and is_ai_dev_branch(ref.removeprefix("refs/heads/")):
            return True, None
        return False, "git show-ref branch must be refs/heads/ai-dev/*"
    if len(args) == 3 and args[:2] == ["git", "switch"]:
        if args[2] == REQUIRED_BASE_BRANCH or is_ai_dev_branch(args[2]):
            return True, None
        return False, "git switch branch must be main or ai-dev/*"
    if len(args) == 4 and args[:3] == ["git", "switch", "-c"]:
        if is_ai_dev_branch(args[3]):
            return True, None
        return False, "git switch -c branch must be ai-dev/*"
    if len(args) == 5 and args[:4] == ["git", "push", "-u", "origin"]:
        if is_ai_dev_branch(args[4]):
            return True, None
        return False, "git push branch must be ai-dev/*"
    if args == ["git", "pull", "--ff-only"]:
        return True, None

    if len(args) == 6 and args[:3] == ["gh", "pr", "view"] and args[4] == "--json":
        if is_ai_dev_branch(args[3]) and args[5]:
            return True, None
        return False, "gh pr view branch must be ai-dev/*"
    if len(args) == 11 and args[:3] == ["gh", "pr", "create"]:
        expected_flags = ["--base", "--head", "--title", "--body-file"]
        if [args[3], args[5], args[7], args[9]] != expected_flags:
            return False, "gh pr create flags are not allowed"
        if args[4] == REQUIRED_BASE_BRANCH and is_ai_dev_branch(args[6]) and args[8] and args[10]:
            return True, None
        return False, "gh pr create is limited to base main and head ai-dev/*"
    if len(args) == 6 and args[:3] == ["gh", "pr", "merge"] and args[4:] == ["--merge", "--delete-branch"]:
        if is_int_text(args[3]):
            return True, None
        return False, "gh pr merge requires numeric PR number"

    if is_python_executable(args[0]) and len(args) >= 2:
        script = args[1]
        rest = args[2:]
        if script == "scripts/orchestrator/promote_next_ai_task.py":
            if has_only_allowed_options(
                rest,
                {"--repo-root", "--runtime-dir", "--task-id"},
                {"--pretty", "--dry-run"},
            ):
                return True, None
            return False, "promote_next_ai_task.py arguments are not allowed"
        if script == "scripts/orchestrator/run_ai_dev_validation_bundle.py":
            if has_only_allowed_options(rest, {"--base", "--head", "--runtime-dir"}, {"--pretty"}):
                if "--base" not in rest or "--head" not in rest:
                    return False, "validation requires --base and --head"
                if "--base" in rest and rest[rest.index("--base") + 1] != REQUIRED_BASE_BRANCH:
                    return False, "validation base must be main"
                if "--head" in rest and rest[rest.index("--head") + 1] != "HEAD":
                    return False, "validation head must be HEAD"
                return True, None
            return False, "run_ai_dev_validation_bundle.py arguments are not allowed"
        if script == "scripts/orchestrator/archive_completed_ai_task.py":
            if not has_only_allowed_options(
                rest,
                {
                    "--repo-root",
                    "--runtime-dir",
                    "--task-id",
                    "--pr-number",
                    "--pr-url",
                    "--branch-name",
                    "--base-branch",
                    "--merged-at",
                },
                {"--pretty"},
            ):
                return False, "archive_completed_ai_task.py arguments are not allowed"
            if "--base-branch" in rest and rest[rest.index("--base-branch") + 1] != REQUIRED_BASE_BRANCH:
                return False, "archive base branch must be main"
            if "--branch-name" in rest and not is_ai_dev_branch(rest[rest.index("--branch-name") + 1]):
                return False, "archive branch must be ai-dev/*"
            if "--pr-number" in rest and not is_int_text(rest[rest.index("--pr-number") + 1]):
                return False, "archive PR number must be numeric"
            return True, None

    return False, "command is not in allowlist"


def run_command(args: list[str], repo_root: Path) -> dict[str, Any]:
    allowed, reason = validate_allowed_command(args)
    if not allowed:
        return {
            "command": args,
            "returncode": 126,
            "stdout": "",
            "stderr": f"blocked by command allowlist: {reason}",
            "json": None,
        }
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


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be object: {path}")
    return data


def effective_value(task: dict[str, Any], defaults: dict[str, Any], key: str, fallback: Any = None) -> Any:
    if key in task:
        return task[key]
    if key in defaults:
        return defaults[key]
    return fallback


def is_allowed_path(path: str, allowed_paths: list[str]) -> bool:
    normalized = path.strip()
    for allowed in allowed_paths:
        allowed_text = str(allowed)
        if allowed_text.endswith("/"):
            if normalized.startswith(allowed_text):
                return True
        elif normalized == allowed_text:
            return True
    return False


def safety_reasons(task: dict[str, Any], defaults: dict[str, Any]) -> list[str]:
    checks = {
        "requires_pull_request": True,
        "allow_direct_main_push": False,
        "allow_production_commands": False,
        "allow_line_notifications": False,
        "allow_trading_execution": False,
    }
    reasons: list[str] = []
    if task.get("risk_level") != "low":
        reasons.append("task risk_level must be low")
    if effective_value(task, defaults, "target_base_branch", REQUIRED_BASE_BRANCH) != REQUIRED_BASE_BRANCH:
        reasons.append("task target_base_branch must be main")
    branch_name = str(task.get("branch_name") or "")
    if not branch_name.startswith(REQUIRED_BRANCH_PREFIX):
        reasons.append("task branch_name must start with ai-dev/")
    if branch_name == REQUIRED_BASE_BRANCH:
        reasons.append("task branch_name must not be main")
    for key, expected in checks.items():
        if effective_value(task, defaults, key) is not expected:
            reasons.append(f"task {key} must be {str(expected).lower()}")
    return reasons


def base_output(args: argparse.Namespace, runtime_dir: Path, state: str) -> dict[str, Any]:
    return {
        "ok": False,
        "state": state,
        "dry_run": args.dry_run,
        "create_pr": args.create_pr,
        "auto_merge": args.auto_merge,
        "runtime_dir": str(runtime_dir),
        "runtime_plan_path": str(runtime_dir / "ai_task_branch_plan.json"),
        "runtime_pr_body_path": str(runtime_dir / "ai_task_pr_body.md"),
        "reasons": [],
        "commands": [],
        "validation": None,
        "pr": None,
        "archive": None,
        "handoff": None,
        "preview": None,
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
            "production_command_run": False,
            "notification_sent": False,
            "trading_execution_run": False,
            "scheduler_modified": False,
        },
    }


def emit(output: dict[str, Any], pretty: bool, returncode: int) -> int:
    json.dump(output, sys.stdout, ensure_ascii=False, indent=2 if pretty else None)
    sys.stdout.write("\n")
    return returncode


def git_status_short(repo_root: Path) -> list[str]:
    status = run_git(["status", "--short"], repo_root)
    return status["stdout"].strip().splitlines() if status["returncode"] == 0 else ["<git status failed>"]


def changed_files(repo_root: Path, base_branch: str, head: str = "HEAD") -> list[str]:
    proc = run_git(["diff", "--name-only", f"{base_branch}...{head}"], repo_root)
    if proc["returncode"] != 0:
        return []
    return [line.strip() for line in proc["stdout"].splitlines() if line.strip()]


def has_branch_work(repo_root: Path, base_branch: str) -> bool:
    if changed_files(repo_root, base_branch):
        return True
    ahead = run_git(["rev-list", "--count", f"{base_branch}..HEAD"], repo_root)
    if ahead["returncode"] != 0:
        return False
    try:
        return int(ahead["stdout"].strip() or "0") > 0
    except ValueError:
        return False


def load_plan(runtime_dir: Path) -> dict[str, Any] | None:
    plan_path = runtime_dir / "ai_task_branch_plan.json"
    if not plan_path.exists():
        return None
    return load_json(plan_path)


def run_validation(repo_root: Path, runtime_dir: Path, base_branch: str) -> dict[str, Any]:
    return run_command(
        [
            sys.executable,
            "scripts/orchestrator/run_ai_dev_validation_bundle.py",
            "--base",
            base_branch,
            "--head",
            "HEAD",
            "--runtime-dir",
            str(runtime_dir),
            "--pretty",
        ],
        repo_root,
    )


def create_pr(repo_root: Path, branch_name: str, base_branch: str, pr_title: str, pr_body_path: Path) -> dict[str, Any]:
    push_result = run_git(["push", "-u", "origin", branch_name], repo_root)
    if push_result["returncode"] != 0:
        return {"push": push_result, "created": False}
    pr_result = run_command(
        [
            "gh",
            "pr",
            "create",
            "--base",
            base_branch,
            "--head",
            branch_name,
            "--title",
            pr_title,
            "--body-file",
            str(pr_body_path),
        ],
        repo_root,
    )
    return {"push": push_result, "create": pr_result, "created": pr_result["returncode"] == 0}


def find_pr(repo_root: Path, branch_name: str) -> dict[str, Any] | None:
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


def check_success(status_rollup: Any, check_name: str) -> bool:
    if not isinstance(status_rollup, list):
        return False
    for item in status_rollup:
        if not isinstance(item, dict):
            continue
        name = item.get("name") or item.get("context") or ""
        conclusion = item.get("conclusion") or item.get("state") or item.get("status")
        if name == check_name and conclusion == "SUCCESS":
            return True
    return False


def auto_merge_gate(
    task: dict[str, Any],
    defaults: dict[str, Any],
    validation_json: dict[str, Any] | None,
    pr: dict[str, Any] | None,
    repo_root: Path,
    base_branch: str,
    branch_name: str,
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if task.get("allow_auto_merge") is not True:
        reasons.append("task allow_auto_merge must be true")
    reasons.extend(safety_reasons(task, defaults))
    if not validation_json or validation_json.get("passed") is not True:
        reasons.append("local validation bundle must pass")
    if validation_json:
        results = validation_json.get("results", [])
        if isinstance(results, list):
            by_script = {" ".join(item.get("command", [])): item for item in results if isinstance(item, dict)}
            if not any("validate_ai_branch.py" in key and value.get("returncode") == 0 for key, value in by_script.items()):
                reasons.append("validate_ai_branch must pass")
            if not any("check_forbidden_changes.py" in key and value.get("returncode") == 0 for key, value in by_script.items()):
                reasons.append("check_forbidden_changes must pass")
    allowed_paths = task.get("allowed_paths", [])
    if not isinstance(allowed_paths, list) or not allowed_paths:
        reasons.append("task allowed_paths must be non-empty")
        allowed_paths = []
    for path in changed_files(repo_root, base_branch):
        if not is_allowed_path(path, allowed_paths):
            reasons.append(f"changed file outside task allowed_paths: {path}")
    if pr is None:
        reasons.append("PR must exist")
    else:
        if pr.get("state") != "OPEN":
            reasons.append("PR state must be OPEN")
        if pr.get("mergeStateStatus") != "CLEAN":
            reasons.append("PR mergeStateStatus must be CLEAN")
        if pr.get("baseRefName") != base_branch:
            reasons.append("PR base branch must be main")
        if pr.get("headRefName") != branch_name:
            reasons.append("PR head branch must match task branch")
        if not check_success(pr.get("statusCheckRollup"), "validate-ai-branch"):
            reasons.append("required check validate-ai-branch must be SUCCESS")
    if git_status_short(repo_root):
        reasons.append("working tree must be clean")
    return not reasons, reasons


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one AI task queue iteration.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--runtime-dir", default=DEFAULT_RUNTIME_DIR)
    parser.add_argument("--task-id", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--create-pr", action="store_true")
    parser.add_argument("--auto-merge", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    runtime_dir = Path(args.runtime_dir).expanduser().resolve()
    pending_path = runtime_dir / "pending_tasks.json"
    completed_path = runtime_dir / "completed_tasks.json"
    output = base_output(args, runtime_dir, "blocked_preflight")

    if not pending_path.exists() or not completed_path.exists():
        output["reasons"].append(f"runtime queue missing; initialize with: {INIT_COMMAND}")
        return emit(output, args.pretty, 2)

    current_branch_proc = run_git(["rev-parse", "--abbrev-ref", "HEAD"], repo_root)
    current_branch = current_branch_proc["stdout"].strip() if current_branch_proc["returncode"] == 0 else ""
    status_short = git_status_short(repo_root)
    output["current_branch"] = current_branch
    output["git_status_short"] = status_short

    plan = load_plan(runtime_dir)
    if current_branch == REQUIRED_BASE_BRANCH:
        if status_short:
            output["reasons"].append("working tree must be clean before starting a new promotion")
            return emit(output, args.pretty, 2)
        promote_command = [
            sys.executable,
            "scripts/orchestrator/promote_next_ai_task.py",
            "--repo-root",
            str(repo_root),
            "--runtime-dir",
            str(runtime_dir),
            "--pretty",
        ]
        if args.task_id:
            promote_command.extend(["--task-id", args.task_id])
        if args.dry_run:
            promote_command.append("--dry-run")
        promote_result = run_command(promote_command, repo_root)
        output["commands"].append(promote_result)
        promote_json = promote_result.get("json") if isinstance(promote_result.get("json"), dict) else {}
        if promote_result["returncode"] != 0:
            output["reasons"].extend(promote_json.get("safety_check", {}).get("reasons", []) if promote_json else [])
            return emit(output, args.pretty, 2)
        if args.dry_run:
            output["state"] = "handoff_ready_preview"
            output["ok"] = True
            output["task_id"] = promote_json.get("task_id")
            output["base_branch"] = promote_json.get("base_branch")
            output["branch_name"] = promote_json.get("branch_name")
            output["preview"] = {
                "would_promote": bool(promote_json.get("would_promote")),
                "would_prepare_branch": True,
                "would_branch_name": promote_json.get("branch_name"),
                "would_base_branch": promote_json.get("base_branch"),
                "would_stop_before_side_effects": True,
            }
            return emit(output, args.pretty, 0)
        output["state"] = "promoted"
        output["ok"] = True
        output["side_effects"]["runtime_queue_modified"] = True
        output["side_effects"]["runtime_plan_written"] = True
        output["side_effects"]["runtime_pr_body_written"] = True
        plan = load_plan(runtime_dir)
    elif not current_branch.startswith(REQUIRED_BRANCH_PREFIX):
        output["reasons"].append("runner must start on main or resume on ai-dev/* branch")
        return emit(output, args.pretty, 2)

    if not isinstance(plan, dict) or not plan.get("prepared"):
        output["reasons"].append("missing prepared runtime plan")
        return emit(output, args.pretty, 2)

    task = plan.get("task", {}) if isinstance(plan.get("task"), dict) else {}
    defaults = {}
    pending_queue = load_json(pending_path)
    if isinstance(pending_queue.get("defaults"), dict):
        defaults = pending_queue["defaults"]
    base_branch = str(plan.get("base_branch") or effective_value(task, defaults, "target_base_branch", REQUIRED_BASE_BRANCH))
    branch_name = str(plan.get("branch_name") or task.get("branch_name") or "")
    output["task_id"] = task.get("task_id")
    output["base_branch"] = base_branch
    output["branch_name"] = branch_name

    safe_reasons = safety_reasons(task, defaults)
    if safe_reasons:
        output["reasons"].extend(safe_reasons)
        return emit(output, args.pretty, 2)

    if current_branch == REQUIRED_BASE_BRANCH:
        if args.dry_run:
            output["state"] = "branch_ready"
            output["ok"] = True
            return emit(output, args.pretty, 0)
        show_ref = run_git(["show-ref", "--verify", "--quiet", f"refs/heads/{branch_name}"], repo_root)
        if show_ref["returncode"] == 0:
            switch_result = run_git(["switch", branch_name], repo_root)
            output["commands"].append(switch_result)
            output["side_effects"]["branch_switched"] = switch_result["returncode"] == 0
        else:
            create_result = run_git(["switch", "-c", branch_name], repo_root)
            output["commands"].append(create_result)
            output["side_effects"]["branch_created"] = create_result["returncode"] == 0
        if output["commands"][-1]["returncode"] != 0:
            output["reasons"].append("failed to prepare task branch")
            return emit(output, args.pretty, 2)
        current_branch = branch_name

    output["state"] = "branch_ready"
    output["ok"] = True
    if not has_branch_work(repo_root, base_branch):
        output["state"] = "handoff_ready"
        output["handoff"] = {
            "runtime_plan_path": str(runtime_dir / "ai_task_branch_plan.json"),
            "runtime_pr_body_path": str(runtime_dir / "ai_task_pr_body.md"),
            "current_branch": current_branch,
            "recommended_next_commands": [
                "bash scripts/orchestrator/start_codex_manual.sh",
                "python3 scripts/orchestrator/run_ai_dev_validation_bundle.py --base main --head HEAD --pretty",
                "git status --short",
                "git diff --stat",
            ],
        }
        return emit(output, args.pretty, 0)

    validation_result = run_validation(repo_root, runtime_dir, base_branch)
    output["commands"].append(validation_result)
    validation_json = validation_result.get("json") if isinstance(validation_result.get("json"), dict) else None
    output["validation"] = validation_json
    if validation_result["returncode"] != 0 or not validation_json or validation_json.get("passed") is not True:
        output["state"] = "validation_failed"
        output["ok"] = False
        return emit(output, args.pretty, 2)

    output["state"] = "validation_passed"
    output["ok"] = True
    if git_status_short(repo_root):
        output["state"] = "pr_ready_blocked_dirty"
        output["reasons"].append("working tree must be clean before PR creation")
        return emit(output, args.pretty, 2)

    pr: dict[str, Any] | None = find_pr(repo_root, branch_name)
    if args.create_pr and pr is None:
        if args.dry_run:
            output["state"] = "validation_passed"
            output["reasons"].append("dry-run: PR creation skipped")
            return emit(output, args.pretty, 0)
        pr_result = create_pr(
            repo_root,
            branch_name,
            base_branch,
            str(plan.get("pr_title") or f"AI Dev: {task.get('task_id')}"),
            runtime_dir / "ai_task_pr_body.md",
        )
        output["commands"].append(pr_result.get("push"))
        if pr_result.get("create"):
            output["commands"].append(pr_result.get("create"))
        if not pr_result.get("created"):
            output["reasons"].append("failed to push branch or create PR")
            return emit(output, args.pretty, 2)
        output["side_effects"]["push_run"] = True
        output["side_effects"]["pr_created"] = True
        output["state"] = "pr_created"
        pr = find_pr(repo_root, branch_name)
    elif not args.create_pr and pr is None:
        output["state"] = "validation_passed"
        output["reasons"].append("PR creation skipped because --create-pr was not provided")
        return emit(output, args.pretty, 0)

    output["pr"] = pr
    if not args.auto_merge:
        output["state"] = "auto_merge_skipped"
        return emit(output, args.pretty, 0)

    gate_passed, gate_reasons = auto_merge_gate(task, defaults, validation_json, pr, repo_root, base_branch, branch_name)
    if not gate_passed:
        output["state"] = "auto_merge_blocked"
        output["reasons"].extend(gate_reasons)
        return emit(output, args.pretty, 2)

    if args.dry_run:
        output["state"] = "auto_merge_blocked"
        output["reasons"].append("dry-run: merge skipped")
        return emit(output, args.pretty, 0)

    merge_result = run_command(["gh", "pr", "merge", str(pr["number"]), "--merge", "--delete-branch"], repo_root)
    output["commands"].append(merge_result)
    if merge_result["returncode"] != 0:
        output["state"] = "auto_merge_blocked"
        output["reasons"].append("gh merge command failed")
        return emit(output, args.pretty, 2)
    output["side_effects"]["merge_run"] = True
    output["state"] = "auto_merged"

    switch_main = run_git(["switch", REQUIRED_BASE_BRANCH], repo_root)
    pull_main = run_git(["pull", "--ff-only"], repo_root) if switch_main["returncode"] == 0 else {
        "command": ["git", "pull", "--ff-only"],
        "returncode": 1,
        "stdout": "",
        "stderr": "skipped because git switch main failed",
        "json": None,
    }
    output["commands"].extend([switch_main, pull_main])
    if switch_main["returncode"] != 0 or pull_main["returncode"] != 0:
        output["reasons"].append("merge succeeded but checkout main or pull --ff-only failed")
        return emit(output, args.pretty, 2)

    archive_result = run_command(
        [
            sys.executable,
            "scripts/orchestrator/archive_completed_ai_task.py",
            "--repo-root",
            str(repo_root),
            "--runtime-dir",
            str(runtime_dir),
            "--task-id",
            str(task.get("task_id")),
            "--pr-number",
            str(pr["number"]),
            "--pr-url",
            str(pr.get("url") or ""),
            "--branch-name",
            branch_name,
            "--base-branch",
            base_branch,
            "--merged-at",
            now_iso(),
            "--pretty",
        ],
        repo_root,
    )
    output["commands"].append(archive_result)
    output["archive"] = archive_result.get("json")
    if archive_result["returncode"] != 0:
        output["reasons"].append("archive failed after merge")
        return emit(output, args.pretty, 2)
    output["state"] = "archived"
    output["side_effects"]["runtime_queue_modified"] = True
    return emit(output, args.pretty, 0)


if __name__ == "__main__":
    raise SystemExit(main())
