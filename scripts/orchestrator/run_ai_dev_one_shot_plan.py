#!/usr/bin/env python3
"""Build a dry-run AI-DEV one-shot orchestration plan.

This script is intentionally read-only. It reads repo templates and prints a
plan. It does not call GitHub, n8n, Dify, ChatGPT/OpenAI, notification services,
production systems, or runtime queues.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

DEFAULT_TASK_REQUEST = Path("templates/chatgpt_ai_dev_task_request.example.json")
DEFAULT_CODEX_REQUEST = Path("templates/codex_ai_dev_one_shot_execution_request.example.json")
DEFAULT_CODEX_PLAN = Path("templates/codex_ai_dev_one_shot_execution_plan.example.json")


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} root must be an object")
    return data


def build_plan(repo_root: Path, task_request_path: Path, codex_request_path: Path, codex_plan_path: Path) -> dict[str, Any]:
    task_request = load_json(repo_root / task_request_path)
    codex_request = load_json(repo_root / codex_request_path)
    codex_plan = load_json(repo_root / codex_plan_path)

    task_id = str(task_request.get("task_id"))
    safety_constraints = task_request.get("safety_constraints", {})
    stop_gates = task_request.get("stop_gates", [])

    role_steps = {
        "ChatGPT": [
            "Create task request with scope, acceptance criteria, safety constraints, stop gates, and GitHub-facing metadata.",
            "Provide final review surface or blocker decision when a safety gate stops the run.",
        ],
        "GitHub": [
            "Provide branch, PR, changed files, checks, mergeStateStatus, and merge commit source of truth.",
        ],
        "n8n": [
            "Receive task_request by webhook or manual trigger in a future approved runtime workflow.",
            "Route safety gate outcomes and collect status summaries without production mutation.",
        ],
        "Dify": [
            "Generate review package and ChatGPT-ready report in future approved summary workflow.",
        ],
        "Codex": [
            "Implement scoped repo changes, run validators, create PR, gate-check, conditionally auto-merge, post-merge validate, and close out runtime completed queue.",
        ],
    }

    gate_conditions = [
        "PR state OPEN",
        "mergeStateStatus CLEAN",
        "GitHub checks successful",
        "validators ok:true",
        "git diff --check passed",
        "git status clean",
        "allowed paths only",
        "no forbidden paths",
        "no secrets or credential values",
        "no notification send",
        "no trading or order execution",
        "no production DB or scheduler changes",
        "scope remains inside task request",
    ]

    result = {
        "ok": True,
        "dry_run": True,
        "task_id": task_id,
        "branch": task_request.get("scope", {}).get("branch"),
        "pr_title": task_request.get("scope", {}).get("pr_title"),
        "external_calls": {
            "github_api_called": False,
            "n8n_started": False,
            "dify_runtime_called": False,
            "chatgpt_openai_api_called": False,
            "notification_sent": False,
        },
        "runtime_mutation": {
            "runtime_queue_modified": False,
            "production_db_modified": False,
            "cron_systemd_timer_modified": False,
        },
        "role_steps": role_steps,
        "conditional_auto_merge_policy": {
            "allowed_when_all_gates_pass": True,
            "gate_conditions": gate_conditions,
            "stop_gates": stop_gates,
        },
        "codex_execution_steps": codex_request.get("required_steps", []),
        "closeout_policy": codex_plan.get("closeout_policy", {}),
        "safety_constraints": safety_constraints,
        "next_action": "Use this dry-run plan as the local orchestration contract; do not call external runtimes from this runner.",
        "side_effects": {
            "files_modified": False,
            "commit_created": False,
            "push_run": False,
            "merge_run": False,
            "n8n_started": False,
            "dify_called": False,
            "chatgpt_openai_api_called": False,
            "notification_sent": False,
            "runtime_queue_modified": False,
            "trading_execution_run": False,
        },
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a dry-run AI-DEV one-shot orchestration plan.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--task-request", default=str(DEFAULT_TASK_REQUEST))
    parser.add_argument("--codex-request", default=str(DEFAULT_CODEX_REQUEST))
    parser.add_argument("--codex-plan", default=str(DEFAULT_CODEX_PLAN))
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    try:
        result = build_plan(repo_root, Path(args.task_request), Path(args.codex_request), Path(args.codex_plan))
    except Exception as exc:
        result = {"ok": False, "dry_run": True, "error": str(exc)}
        json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
        sys.stdout.write("\n")
        return 2

    json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
