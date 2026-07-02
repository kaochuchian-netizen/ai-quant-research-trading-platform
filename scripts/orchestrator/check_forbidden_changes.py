#!/usr/bin/env python3
"""Check a branch diff for forbidden files and high-risk code patterns.

This checker is intended for PR validation. It reads Git diff metadata and patch
content between a base ref and a head ref. It does not modify files, commit,
push, merge, send notifications, or run production workflows.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


DEFAULT_BLOCKED_PATHS = [
    ".env",
    "data/stock_analysis.db",
    "data/backups/",
    "analysis/output/",
]

DEFAULT_BLOCKED_KEYWORDS = [
    "send_line_report(",
    "line_bot_api.push_message",
    "api.place_order",
    "place_order(",
    "shioaji.Order",
    "StockPriceType",
]

CONTROLLED_SINOPAC_TEST_PATHS = [
    "scripts/orchestrator/sinopac_api_test_application.py",
    "scripts/orchestrator/validate_sinopac_api_test_application_result.py",
    "docs/ai_dev_116_sinopac_api_test_application_v1.md",
    "templates/sinopac_api_test_application_request.example.json",
    "templates/sinopac_api_test_application_result.example.json",
]

DEFAULT_KEYWORD_PATH_ALLOWLIST = {
    DEFAULT_BLOCKED_KEYWORDS[2]: CONTROLLED_SINOPAC_TEST_PATHS,
    DEFAULT_BLOCKED_KEYWORDS[3]: CONTROLLED_SINOPAC_TEST_PATHS,
    DEFAULT_BLOCKED_KEYWORDS[4]: CONTROLLED_SINOPAC_TEST_PATHS,
    DEFAULT_BLOCKED_KEYWORDS[5]: CONTROLLED_SINOPAC_TEST_PATHS,
}


def run_git(args: list[str], repo_root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(repo_root),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def is_blocked_path(path: str, blocked_paths: list[str]) -> bool:
    normalized = path.strip()
    for blocked in blocked_paths:
        if blocked.endswith("/"):
            if normalized.startswith(blocked):
                return True
        elif normalized == blocked or normalized.startswith(blocked + "/"):
            return True
    return False


def is_keyword_allowed(path: str | None, keyword: str, allowlist: dict[str, list[str]]) -> bool:
    if not path:
        return False
    return path in allowlist.get(keyword, [])


def collect_keyword_hits(
    patch_text: str,
    blocked_keywords: list[str],
    allowlist: dict[str, list[str]],
) -> list[dict[str, str]]:
    hits: list[dict[str, str]] = []
    current_path: str | None = None
    for line in patch_text.splitlines():
        if line.startswith("+++ b/"):
            current_path = line.removeprefix("+++ b/")
            continue
        if not line.startswith("+") or line.startswith("+++"):
            continue
        for keyword in blocked_keywords:
            if keyword in line and not is_keyword_allowed(current_path, keyword, allowlist):
                hits.append({"keyword": keyword, "path": current_path or "<unknown>"})
    return hits


def main() -> int:
    parser = argparse.ArgumentParser(description="Check forbidden file changes and code patterns.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--base", default="main")
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--blocked-path", action="append", default=[])
    parser.add_argument("--blocked-keyword", action="append", default=[])
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    blocked_paths = DEFAULT_BLOCKED_PATHS + args.blocked_path
    blocked_keywords = DEFAULT_BLOCKED_KEYWORDS + args.blocked_keyword
    reasons: list[str] = []

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
    blocked_file_changes = [path for path in changed_files if is_blocked_path(path, blocked_paths)]
    for path in blocked_file_changes:
        reasons.append(f"blocked path changed: {path}")

    patch_proc = run_git(["diff", "--unified=0", f"{args.base}...{args.head}"], repo_root)
    patch_text = patch_proc.stdout if patch_proc.returncode == 0 else ""
    keyword_hits = collect_keyword_hits(patch_text, blocked_keywords, DEFAULT_KEYWORD_PATH_ALLOWLIST)
    for hit in keyword_hits:
        reasons.append(f"blocked keyword found in diff: {hit['keyword']} ({hit['path']})")

    result = {
        "ok": True,
        "passed": not reasons,
        "base": args.base,
        "head": args.head,
        "changed_files": changed_files,
        "changed_file_count": len(changed_files),
        "blocked_paths": blocked_paths,
        "blocked_file_changes": blocked_file_changes,
        "blocked_keywords": blocked_keywords,
        "keyword_hits": keyword_hits,
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
