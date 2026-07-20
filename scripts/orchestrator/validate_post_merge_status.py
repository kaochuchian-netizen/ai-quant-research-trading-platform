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
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    from .inspect_ai_platform_status import build_report as build_platform_status_report
except ImportError:  # Direct script execution keeps the sibling directory on sys.path.
    from inspect_ai_platform_status import build_report as build_platform_status_report


DEFAULT_TASK_BRANCH_PREFIX = "ai-dev/"

TW_WINDOWS = ("pre_open_0700", "intraday_1305", "pre_close_1335", "post_close_1500")
US_WINDOWS = ("us_pre_market_2000", "us_intraday_2300", "us_post_close_review_0630")

PRESERVED_EXACT_PATHS = {
    "artifacts/archive/formal_forecast_snapshots/index/formal_forecast_snapshot_index_latest.json",
    "artifacts/archive/formal_forecast_snapshots/index/formal_forecast_snapshot_index_latest.md",
    "artifacts/runtime/delivery_progress_pre_open_0700_latest.json",
    "artifacts/runtime/delivery_progress_intraday_1305_latest.json",
    "artifacts/runtime/delivery_progress_pre_close_1335_latest.json",
    "artifacts/runtime/delivery_progress_prediction_review_1500_latest.json",
    "artifacts/runtime/formal_prediction_review_runtime_latest.json",
    "artifacts/runtime/formal_prediction_runtime_latest.json",
    "artifacts/runtime/manual_rerun/manual_rerun_latest.json",
    "artifacts/runtime/manual_rerun/manual_rerun_status_latest.json",
    "artifacts/runtime/pre_open_stage_timing_latest.json",
    "artifacts/runtime/production_scheduler_dashboard_url_contract/production_scheduler_dashboard_url_contract_latest.json",
    "artifacts/runtime/production_scheduler_dashboard_url_contract/production_scheduler_dashboard_url_contract_latest.md",
    "templates/four_window_dashboard_production_runtime_export.example.json",
    "templates/four_window_dashboard_route_preview.example.html",
    "templates/multi_market_dashboard_v2/index.html",
    "templates/multi_market_dashboard_v2/manifest.json",
    "templates/multi_market_dashboard_v2/old_four_window_index.html",
    "templates/multi_market_dashboard_v2/tw_index.html",
    "templates/multi_market_dashboard_v2/us_index.html",
}

PRESERVED_PATH_PATTERNS = tuple(
    re.compile(pattern)
    for pattern in (
        r"artifacts/archive/formal_forecast_snapshots/(actual_outcome/formal_actual_outcome|prediction/formal_prediction_runtime|review/formal_prediction_review)_\d{4}-\d{2}-\d{2}\.json",
        rf"artifacts/runtime/delivery_provenance/(?:tw_(?:{'|'.join(TW_WINDOWS)})|us_(?:{'|'.join(US_WINDOWS)}))_(?:email|line)_latest\.json",
        rf"artifacts/runtime/operations_provenance/(?:tw_(?:{'|'.join(TW_WINDOWS)})|us_(?:{'|'.join(US_WINDOWS)}))_latest\.json",
        rf"artifacts/runtime/public_latest_sync/(?:tw_(?:{'|'.join(TW_WINDOWS)})|us_(?:{'|'.join(US_WINDOWS)}))_latest\.json",
        rf"artifacts/runtime/stage_timing/(?:tw_(?:{'|'.join(TW_WINDOWS)})|us_(?:{'|'.join(US_WINDOWS)}))_latest\.json",
        rf"artifacts/runtime/tw_window_decision/(?:{'|'.join(TW_WINDOWS)})_latest\.json",
        rf"templates/multi_market_dashboard_v2/dashboard/archive/(?:tw/(?:{'|'.join(TW_WINDOWS)})|us/(?:{'|'.join(US_WINDOWS)}))/(?:latest|previous)/index\.html",
    )
)

BLOCKING_SOURCE_PREFIXES = (
    "app/", "scripts/", "tests/", "docs/", "config/", "configs/", "schemas/",
    ".github/", "analysis/", "reports/", "orchestrator/", "templates/",
)
BLOCKING_ROOT_FILES = {
    "AGENTS.md", "AGENTS.override.md", "main.py", "run_stock_analysis.sh",
    "requirements.txt", "pyproject.toml", "setup.cfg", "tox.ini", "Makefile",
}


def status_path(status_entry: str) -> str:
    """Extract a path from one `git status --short` line without touching git."""
    raw = str(status_entry).rstrip()
    if raw.startswith("?? ") or raw.startswith("!! "):
        path = raw[3:]
    elif len(raw) >= 2 and raw[1] == " ":
        path = raw[2:]
    elif len(raw) >= 3 and raw[2] == " ":
        path = raw[3:]
    else:
        path = raw
    if " -> " in path:
        path = path.split(" -> ", 1)[1]
    return path.strip().strip('"')


def is_preserved_runtime_artifact(path: str) -> bool:
    return path in PRESERVED_EXACT_PATHS or any(pattern.fullmatch(path) for pattern in PRESERVED_PATH_PATTERNS)


def is_blocking_task_source(path: str) -> bool:
    if path in BLOCKING_ROOT_FILES:
        return True
    return path.startswith(BLOCKING_SOURCE_PREFIXES)


def classify_dirty_paths(status_entries: list[str]) -> dict[str, list[str]]:
    result = {"blocking_task_residue": [], "preserved_runtime_artifacts": [], "unknown_dirty_paths": []}
    for entry in status_entries:
        path = status_path(entry)
        if is_preserved_runtime_artifact(path):
            result["preserved_runtime_artifacts"].append(path)
        elif is_blocking_task_source(path):
            result["blocking_task_residue"].append(path)
        else:
            result["unknown_dirty_paths"].append(path)
    return {key: sorted(set(values)) for key, values in result.items()}


def collect_expanded_git_status(repo_root: Path) -> tuple[list[str], str | None]:
    """Read every dirty file; never collapse an untracked directory into an allowlisted prefix."""
    proc = subprocess.run(
        ["git", "status", "--short", "--untracked-files=all"],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return [], proc.stderr.strip() or proc.stdout.strip() or "git status failed"
    return proc.stdout.splitlines(), None


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
    status_entries = list(git.get("status_short", []) or [])
    dirty = classify_dirty_paths(status_entries)
    worktree_governance_safe = not dirty["blocking_task_residue"] and not dirty["unknown_dirty_paths"]
    main_sync = dict(git.get("main_origin_main_sync", {}))
    local_branches = list(git.get("local_branches", []) or [])
    remote_branches = list(git.get("remote_branches", []) or [])
    task_branch_refs = {
        "local": collect_task_branch_refs(local_branches, task_branch_prefix),
        "remote": collect_task_branch_refs(remote_branches, task_branch_prefix),
    }
    task_branch_cleanup_complete = not task_branch_refs["local"] and not task_branch_refs["remote"]
    open_pr_count = int(platform_status.get("open_pr_count") or 0)

    pending_queue = dict(runtime.get("pending_queue", {}))
    pending_count = pending_queue.get("pending_count")
    if pending_count is None:
        pending_count = pending_queue.get("count")
    pending_count = int(pending_count or 0)

    handoff = dict(runtime.get("handoff_diagnostics", {}))
    classification = handoff.get("classification")
    warnings = list(platform_status.get("warnings", []) or [])
    non_clean_warnings = [warning for warning in warnings if warning != "git working tree is not clean"]
    if dirty["preserved_runtime_artifacts"]:
        warnings = non_clean_warnings + [
            f"approved preserved production/runtime/generated artifacts remain dirty: {len(dirty['preserved_runtime_artifacts'])}"
        ]
    else:
        warnings = non_clean_warnings
    errors: list[str] = []

    checks = {
        "current_branch_is_main": evaluate_check(
            "current_branch_is_main",
            current_branch == "main",
            expected="main",
            actual=current_branch,
            notes=[] if current_branch == "main" else ["post-merge validation expects main"],
        ),
        "worktree_governance_safe": evaluate_check(
            "worktree_governance_safe",
            worktree_governance_safe,
            expected={"blocking_task_residue": [], "unknown_dirty_paths": []},
            actual={key: dirty[key] for key in ("blocking_task_residue", "unknown_dirty_paths")},
            notes=[] if worktree_governance_safe else status_entries,
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
        "open_prs_closed": evaluate_check(
            "open_prs_closed", open_pr_count == 0, expected=0, actual=open_pr_count,
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
        "no_blocking_warnings": evaluate_check(
            "no_blocking_warnings", not non_clean_warnings, expected=[], actual=non_clean_warnings,
        ),
    }

    for check in checks.values():
        if not check["passed"]:
            errors.append(f"{check['name']} failed")

    git_summary = {
        "current_branch": current_branch,
        "clean": clean,
        "status_short": status_entries,
        "main_origin_main_sync": main_sync,
        "local_branches": local_branches,
        "remote_branches": remote_branches,
        "task_branch_prefix": task_branch_prefix,
        "task_branch_refs": task_branch_refs,
        "task_branch_cleanup_complete": task_branch_cleanup_complete,
        "open_pr_count": open_pr_count,
    }

    return {
        "ok": not errors,
        "main_sync_ok": checks["main_origin_main_in_sync"]["passed"],
        "branch_cleanup_ok": checks["task_branches_cleaned"]["passed"],
        "inspector_ok": checks["inspector_ok"]["passed"],
        "blocking_task_residue": dirty["blocking_task_residue"],
        "preserved_runtime_artifacts": dirty["preserved_runtime_artifacts"],
        "unknown_dirty_paths": dirty["unknown_dirty_paths"],
        "worktree_clean": clean,
        "worktree_governance_safe": worktree_governance_safe,
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
    expanded_status, status_error = collect_expanded_git_status(repo_root)
    if status_error:
        platform_status = dict(platform_status)
        platform_status["warnings"] = list(platform_status.get("warnings", [])) + [
            f"unable to expand dirty paths: {status_error}"
        ]
    else:
        platform_status = dict(platform_status)
        git = dict(platform_status.get("git", {}))
        git["status_short"] = expanded_status
        git["clean"] = not expanded_status
        platform_status["git"] = git
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
