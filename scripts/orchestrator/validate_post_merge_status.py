#!/usr/bin/env python3
"""Validate post-merge repository and platform status in read-only mode.

This helper standardizes merge-after-main checks without changing the existing
PR branch validator. It reuses the platform inspector output and adds a
post-merge focused summary for:

- main branch state
- git cleanliness
- main / origin/main synchronization
- task branch cleanup
- pending queue emptiness
- active handoff / warning / blocker detection

The script is read-only and does not modify files, databases, production
pipelines, cron jobs, secrets, notifications, or trading systems.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from inspect_ai_platform_status import build_report as build_platform_status_report


DEFAULT_TASK_BRANCH_PREFIX = "ai-dev/"


def is_task_branch(ref_name: str, prefix: str) -> bool:
    return ref_name.startswith(prefix)


def collect_task_branch_refs(branches: list[str], prefix: str) -> list[str]:
    return sorted(branch for branch in branches if is_task_branch(branch, prefix))


def apply_simulated_post_merge_state(report: dict[str, Any]) -> dict[str, Any]:
    """Return a shallow copy with a mocked clean post-merge main state."""

    simulated = dict(report)
    simulated["warnings"] = []
    git = dict(simulated.get("git", {}))
    git.update(
        {
            "current_branch": "main",
            "clean": True,
            "status_short": [],
            "main_origin_main_sync": {
                **dict(git.get("main_origin_main_sync", {})),
                "status": "in_sync",
                "ahead": 0,
                "behind": 0,
            },
            "local_branches": ["main"],
            "remote_branches": ["origin/main"],
        }
    )
    simulated["git"] = git
    return simulated


def evaluate_check(name: str, passed: bool, *, expected: Any = None, actual: Any = None, notes: list[str] | None = None) -> dict[str, Any]:
    return {
        "name": name,
        "passed": passed,
        "expected": expected,
        "actual": actual,
        "notes": notes or [],
    }


def summarize_post_merge_status(
    platform_status: dict[str, Any],
    *,
    task_branch_prefix: str = DEFAULT_TASK_BRANCH_PREFIX,
) -> dict[str, Any]:
    git = dict(platform_status.get("git", {}))
    runtime = dict(platform_status.get("runtime", {}))

    current_branch = git.get("current_branch")
    clean = bool(git.get("clean"))
    main_sync = dict(git.get("main_origin_main_sync", {}))
    local_branches = list(git.get("local_branches", []) or [])
    remote_branches = list(git.get("remote_branches", []) or [])
    task_branch_refs = {
        "local": collect_task_branch_refs(local_branches, task_branch_prefix),
        "remote": collect_task_branch_refs(remote_branches, task_branch_prefix),
    }
    task_branch_cleanup_complete = not task_branch_refs["local"] and not task_branch_refs["remote"]

    pending_queue = dict(runtime.get("pending_queue", {}))
    pending_count = pending_queue.get("pending_count")
    if pending_count is None:
        pending_count = pending_queue.get("count")
    pending_count = int(pending_count or 0)

    handoff = dict(runtime.get("handoff_diagnostics", {}))
    classification = handoff.get("classification")
    warnings = list(platform_status.get("warnings", []) or [])
    errors: list[str] = []

    checks = {
        "current_branch_is_main": evaluate_check(
            "current_branch_is_main",
            current_branch == "main",
            expected="main",
            actual=current_branch,
            notes=[] if current_branch == "main" else ["post-merge validation expects main"],
        ),
        "git_status_clean": evaluate_check(
            "git_status_clean",
            clean,
            expected=True,
            actual=clean,
            notes=[] if clean else list(git.get("status_short", []) or []),
        ),
        "main_origin_main_in_sync": evaluate_check(
            "main_origin_main_in_sync",
            main_sync.get("status") == "in_sync" and main_sync.get("ahead") == 0 and main_sync.get("behind") == 0,
            expected={"status": "in_sync", "ahead": 0, "behind": 0},
            actual={
                "status": main_sync.get("status"),
                "ahead": main_sync.get("ahead"),
                "behind": main_sync.get("behind"),
            },
            notes=[] if main_sync.get("status") == "in_sync" else [str(main_sync.get("notes") or "main and origin/main are not synchronized")],
        ),
        "task_branches_cleaned": evaluate_check(
            "task_branches_cleaned",
            task_branch_cleanup_complete,
            expected={"local": [], "remote": []},
            actual=task_branch_refs,
            notes=[] if task_branch_cleanup_complete else ["task branches are still present"],
        ),
        "inspector_ok": evaluate_check(
            "inspector_ok",
            platform_status.get("ok") is True,
            expected=True,
            actual=platform_status.get("ok"),
        ),
        "pending_queue_empty": evaluate_check(
            "pending_queue_empty",
            pending_count == 0,
            expected=0,
            actual=pending_count,
        ),
        "no_active_handoff": evaluate_check(
            "no_active_handoff",
            classification == "no_active_handoff",
            expected="no_active_handoff",
            actual=classification,
        ),
        "no_warnings": evaluate_check(
            "no_warnings",
            not warnings,
            expected=[],
            actual=warnings,
        ),
    }

    for check in checks.values():
        if not check["passed"]:
            errors.append(f"{check['name']} failed")

    git_summary = {
        "current_branch": current_branch,
        "clean": clean,
        "status_short": git.get("status_short", []),
        "main_origin_main_sync": main_sync,
        "local_branches": local_branches,
        "remote_branches": remote_branches,
        "task_branch_prefix": task_branch_prefix,
        "task_branch_refs": task_branch_refs,
        "task_branch_cleanup_complete": task_branch_cleanup_complete,
    }

    return {
        "ok": not errors,
        "checks": checks,
        "warnings": warnings,
        "errors": errors,
        "git": git_summary,
        "platform_status": platform_status,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate post-merge status in read-only mode.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--runtime-dir", default="~/.local/state/stock-ai-orchestrator")
    parser.add_argument("--task-branch-prefix", default=DEFAULT_TASK_BRANCH_PREFIX)
    parser.add_argument(
        "--simulate-post-merge-success",
        action="store_true",
        help="Return a mocked clean main-branch state for format testing without switching branches.",
    )
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    runtime_dir = Path(args.runtime_dir).expanduser().resolve()

    platform_status = build_platform_status_report(repo_root, runtime_dir)
    if args.simulate_post_merge_success:
        platform_status = apply_simulated_post_merge_state(platform_status)

    report = summarize_post_merge_status(
        platform_status,
        task_branch_prefix=args.task_branch_prefix,
    )
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
