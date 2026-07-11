#!/usr/bin/env python3
"""Validate an AI development branch before PR review.

The validator enforces a conservative branch workflow:
- no direct main validation as the head branch
- limited changed-file count
- all changed files stay within allowed paths
- forbidden path and keyword checker passes

It performs read-only checks only.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


DEFAULT_ALLOWED_PATHS = [
    "docs/",
    "analysis/forecast/",
    "tests/",
    "scripts/orchestrator/",
    ".github/workflows/ai_dev_validation.yml",
    "app/trading/",
    "app/us_stock/",
    "app/loaders/",
    "app/prediction/",
    "app/prediction_context/",
    "app/evaluation/",
    "app/sources/",
    "app/explainability/",
    "app/calibration/",
    "app/recommendation/",
    "app/dashboard/",
    "app/dashboard_intelligence/",
    "app/dashboard_review/",
    "app/decision_feedback/",
    "app/official_sources/",
    "app/reports/",
    "app/strategy/",
    "reports/line_short_formatter.py",
    "app/report_assembly/",
    "app/runtime/",
    "app/market_regime/",
    "app/source_audit/",
    "app/source_roadmap/",
    "app/finmind_report/",
    "app/history/",
    "app/rolling/",
    "app/market/historical_price_loader.py",
    "app/market/historical_storage.py",
    "app/market/shioaji_client.py",
    "app/market/stock_name_loader.py",
    "app/pipelines/pre_open_pipeline.py",
    "app/pipelines/intraday_pipeline.py",
    "app/pipelines/pre_close_pipeline.py",
    "app/pipelines/post_close_pipeline.py",
    "app/pipelines/afternoon_report_pipeline.py",
    "scripts/run_pipeline.py",
    "scripts/update_historical_csv.py",
    "app/pipelines/runner.py",
    "run_stock_analysis.sh",
    "orchestrator/queue/",
    "orchestrator/templates/",
    "templates/",
    "artifacts/runtime/",
    "artifacts/archive/",
    "requirements.txt",
    "test_shioaji.py",
]

DEFAULT_MAX_CHANGED_FILES = 30


def run_command(args: list[str], repo_root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=str(repo_root),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def run_git(args: list[str], repo_root: Path) -> subprocess.CompletedProcess[str]:
    return run_command(["git", *args], repo_root)


def is_allowed_path(path: str, allowed_paths: list[str]) -> bool:
    normalized = path.strip()
    for allowed in allowed_paths:
        if allowed.endswith("/"):
            if normalized.startswith(allowed):
                return True
        elif normalized == allowed:
            return True
    return False


def parse_json_output(text: str) -> dict[str, Any]:
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {"ok": False, "error": "not an object"}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "raw": text}


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate AI branch safety before PR review.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--base", default="main")
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--allowed-path", action="append", default=[])
    parser.add_argument("--max-changed-files", type=int, default=DEFAULT_MAX_CHANGED_FILES)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    allowed_paths = DEFAULT_ALLOWED_PATHS + args.allowed_path
    reasons: list[str] = []

    branch_proc = run_git(["rev-parse", "--abbrev-ref", "HEAD"], repo_root)
    current_branch = branch_proc.stdout.strip() if branch_proc.returncode == 0 else None
    if current_branch == "main" and args.head == "HEAD":
        reasons.append("head branch must not be main for AI development validation")

    changed_proc = run_git(["diff", "--name-only", f"{args.base}...{args.head}"], repo_root)
    if changed_proc.returncode != 0:
        result = {
            "ok": False,
            "passed": False,
            "error": changed_proc.stderr.strip() or changed_proc.stdout.strip(),
            "side_effects": {"files_modified": False, "commit_created": False, "push_run": False},
        }
        json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
        sys.stdout.write("\n")
        return 1

    changed_files = [line.strip() for line in changed_proc.stdout.splitlines() if line.strip()]
    if len(changed_files) > args.max_changed_files:
        reasons.append(f"changed file count exceeds limit: {len(changed_files)} > {args.max_changed_files}")

    disallowed_files = [path for path in changed_files if not is_allowed_path(path, allowed_paths)]
    for path in disallowed_files:
        reasons.append(f"changed file outside allowed paths: {path}")

    forbidden_proc = run_command(
        [
            sys.executable,
            "scripts/orchestrator/check_forbidden_changes.py",
            "--repo-root",
            str(repo_root),
            "--base",
            args.base,
            "--head",
            args.head,
        ],
        repo_root,
    )
    forbidden_result = parse_json_output(forbidden_proc.stdout)
    if forbidden_proc.returncode not in (0, 2):
        reasons.append("forbidden changes checker failed to run")
    if not forbidden_result.get("passed", False):
        for reason in forbidden_result.get("reasons", []):
            reasons.append(str(reason))

    source_inventory_proc = run_command(
        [
            sys.executable,
            "scripts/orchestrator/audit_source_inventory_registry.py",
            "--pretty",
        ],
        repo_root,
    )
    source_inventory_result = parse_json_output(source_inventory_proc.stdout)
    if source_inventory_proc.returncode not in (0, 2):
        reasons.append("source inventory registry audit failed to run")
    if not source_inventory_result.get("passed", False):
        for reason in source_inventory_result.get("reasons", []):
            reasons.append(str(reason))

    result = {
        "ok": True,
        "passed": not reasons,
        "base": args.base,
        "head": args.head,
        "current_branch": current_branch,
        "allowed_paths": allowed_paths,
        "max_changed_files": args.max_changed_files,
        "changed_files": changed_files,
        "changed_file_count": len(changed_files),
        "disallowed_files": disallowed_files,
        "forbidden_changes": forbidden_result,
        "source_inventory_audit": source_inventory_result,
        "reasons": reasons,
        "side_effects": {
            "files_modified": False,
            "commit_created": False,
            "push_run": False,
            "merge_run": False,
            "production_command_run": False,
            "notification_sent": False,
            "trading_execution_run": False,
        },
    }
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    return 0 if result["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
