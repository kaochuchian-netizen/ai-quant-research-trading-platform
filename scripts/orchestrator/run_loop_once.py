#!/usr/bin/env python3
"""Run one safe Orchestrator loop iteration.

This script checks local runtime state, repository state, timer health, optional remote Git
availability, Codex handoff queue state, and Codex queue gate state. It writes
loop_status.json unless --dry-run is used.

It does not pull, start Codex, send notifications, or run production workflows.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


DEFAULT_RUNTIME_DIR = "~/.local/state/stock-ai-orchestrator"
DEFAULT_TIMEZONE = "Asia/Taipei"
DEFAULT_CODEX_QUEUE_PATH = "orchestrator/templates/codex_handoff_queue.example.json"
TIMER_NAME = "stock-ai-orchestrator-loop.timer"
SERVICE_NAME = "stock-ai-orchestrator-loop.service"
ALLOWED_CODEX_TASK_TYPES = {"orchestrator_low_risk"}
REQUIRED_CODEX_BLOCKED_PATHS = {
    ".env",
    "data/stock_analysis.db",
    "data/backups/",
    "analysis/output/",
}
REQUIRED_CODEX_BOUNDARIES = [
    "Do not run production workflows.",
    "Do not read local secret files.",
    "Do not change scheduler settings.",
]


def now_iso(timezone_name: str) -> str:
    return datetime.now(ZoneInfo(timezone_name)).replace(microsecond=0).isoformat()


def run_command(args: list[str], repo_root: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=str(repo_root) if repo_root else None,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def command_summary(name: str, completed: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    return {
        "name": name,
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def load_json_if_exists(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"ok": False, "state": "missing", "path": str(path)}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
        return {"ok": False, "state": "invalid", "reason": "not an object", "path": str(path)}
    except Exception as exc:
        return {"ok": False, "state": "invalid", "reason": str(exc), "path": str(path)}


def read_text_status(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False, "path": str(path)}
    try:
        text = path.read_text(encoding="utf-8")
        return {
            "exists": True,
            "path": str(path),
            "bytes": len(text.encode("utf-8")),
            "has_content": bool(text.strip()),
        }
    except Exception as exc:
        return {"exists": True, "path": str(path), "error": str(exc)}


def check_git_state(repo_root: Path, expected_branch: str) -> dict[str, Any]:
    branch = run_command(["git", "rev-parse", "--abbrev-ref", "HEAD"], repo_root)
    status = run_command(["git", "status", "--short"], repo_root)
    head = run_command(["git", "rev-parse", "HEAD"], repo_root)

    current_branch = branch.stdout.strip() if branch.returncode == 0 else None
    status_short = status.stdout.strip() if status.returncode == 0 else ""
    ok = branch.returncode == 0 and status.returncode == 0 and current_branch == expected_branch and status_short == ""

    reasons: list[str] = []
    if branch.returncode != 0:
        reasons.append("branch check failed")
    elif current_branch != expected_branch:
        reasons.append(f"branch mismatch: {current_branch} != {expected_branch}")
    if status.returncode != 0:
        reasons.append("git status failed")
    elif status_short:
        reasons.append("working tree is not clean")

    return {
        "ok": ok,
        "expected_branch": expected_branch,
        "current_branch": current_branch,
        "head": head.stdout.strip() if head.returncode == 0 else None,
        "status_short": status_short,
        "blocked_reasons": reasons,
    }


def check_remote_state(repo_root: Path, remote: str) -> dict[str, Any]:
    fetch_dry_run = run_command(["git", "fetch", "--dry-run", remote], repo_root)
    output = "\n".join(part for part in [fetch_dry_run.stdout.strip(), fetch_dry_run.stderr.strip()] if part)
    has_remote_changes = bool(output.strip())
    return {
        "ok": fetch_dry_run.returncode == 0,
        "remote": remote,
        "check_mode": "fetch_dry_run",
        "has_remote_changes": has_remote_changes,
        "fetch_dry_run": command_summary("fetch_dry_run", fetch_dry_run),
        "notes": "This check does not pull, merge, or modify the working tree.",
    }


def check_timer_state() -> dict[str, Any]:
    timer_enabled = run_command(["systemctl", "--user", "is-enabled", TIMER_NAME])
    timer_active = run_command(["systemctl", "--user", "is-active", TIMER_NAME])
    service_active = run_command(["systemctl", "--user", "is-active", SERVICE_NAME])
    list_timers = run_command(["systemctl", "--user", "list-timers", "--all", TIMER_NAME, "--no-pager"])

    enabled_value = timer_enabled.stdout.strip()
    active_value = timer_active.stdout.strip()
    service_value = service_active.stdout.strip()

    ok = enabled_value == "enabled" and active_value == "active"

    return {
        "ok": ok,
        "timer_name": TIMER_NAME,
        "service_name": SERVICE_NAME,
        "timer_enabled": enabled_value,
        "timer_active": active_value,
        "service_active": service_value,
        "commands": {
            "timer_enabled": command_summary("timer_enabled", timer_enabled),
            "timer_active": command_summary("timer_active", timer_active),
            "service_active": command_summary("service_active", service_active),
            "list_timers": command_summary("list_timers", list_timers),
        },
    }


def safe_codex_item_summary(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "handoff_id": item.get("handoff_id"),
        "task_id": item.get("task_id"),
        "task_name": item.get("task_name"),
        "status": item.get("status"),
        "priority": item.get("priority"),
        "manual_start_required": item.get("manual_start_required"),
        "agent_started": item.get("agent_started"),
        "agent_finished": item.get("agent_finished"),
        "allowed_task_type": item.get("allowed_task_type"),
    }


def evaluate_codex_queue_gate(item: dict[str, Any] | None) -> dict[str, Any]:
    if item is None:
        return {
            "ok": True,
            "gate_passed": False,
            "codex_start_allowed": False,
            "blocked_reasons": ["no pending queue item"],
            "next_pending_item": None,
            "notes": "No pending item. Codex is not started by this loop.",
        }

    blocked: list[str] = []
    if item.get("allowed_task_type") not in ALLOWED_CODEX_TASK_TYPES:
        blocked.append("allowed_task_type is not permitted")
    if item.get("manual_start_required") is not True:
        blocked.append("manual_start_required must be true")
    if item.get("agent_started") is not False:
        blocked.append("agent_started must be false")
    if item.get("agent_finished") is not False:
        blocked.append("agent_finished must be false")

    allowed_paths = item.get("allowed_paths", [])
    if not isinstance(allowed_paths, list) or not allowed_paths:
        blocked.append("allowed_paths must be a non-empty list")
    else:
        for path in allowed_paths:
            if not isinstance(path, str):
                blocked.append("allowed_paths contains non-string value")
                break
            if path.startswith("/") or ".." in path.split("/"):
                blocked.append("allowed_paths must be relative safe paths")
                break

    blocked_paths = item.get("blocked_paths", [])
    if not isinstance(blocked_paths, list):
        blocked.append("blocked_paths must be a list")
    else:
        missing = sorted(REQUIRED_CODEX_BLOCKED_PATHS.difference(set(blocked_paths)))
        if missing:
            blocked.append("missing required blocked paths: " + ", ".join(missing))

    validation_commands = item.get("validation_commands", [])
    if not isinstance(validation_commands, list) or not validation_commands:
        blocked.append("validation_commands must be a non-empty list")

    safety_boundaries = item.get("safety_boundaries", [])
    if not isinstance(safety_boundaries, list):
        blocked.append("safety_boundaries must be a list")
    else:
        for phrase in REQUIRED_CODEX_BOUNDARIES:
            if phrase not in safety_boundaries:
                blocked.append("missing safety boundary: " + phrase)

    return {
        "ok": True,
        "gate_passed": not blocked,
        "codex_start_allowed": False,
        "blocked_reasons": blocked,
        "next_pending_item": safe_codex_item_summary(item),
        "notes": "Gate pass only marks structural readiness. Codex is not started by this loop.",
    }


def summarize_codex_queue(queue_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    queue = load_json_if_exists(queue_path)
    if not queue.get("ok", True) and queue.get("state") in {"missing", "invalid"}:
        queue_state = {
            "ok": queue.get("state") == "missing",
            "queue_path": str(queue_path),
            "state": queue.get("state"),
            "error": queue.get("reason"),
            "item_count": 0,
            "pending_count": 0,
            "manual_start_required_count": 0,
            "agent_started_count": 0,
            "next_pending_item": None,
            "codex_start_allowed": False,
            "notes": "Queue is read-only in this phase. Codex is not started by this loop.",
        }
        return queue_state, evaluate_codex_queue_gate(None)

    items = queue.get("items", [])
    if not isinstance(items, list):
        queue_state = {
            "ok": False,
            "queue_path": str(queue_path),
            "state": "invalid",
            "error": "items is not a list",
            "item_count": 0,
            "pending_count": 0,
            "manual_start_required_count": 0,
            "agent_started_count": 0,
            "next_pending_item": None,
            "codex_start_allowed": False,
        }
        gate_state = {
            "ok": False,
            "gate_passed": False,
            "codex_start_allowed": False,
            "blocked_reasons": ["queue items is not a list"],
            "next_pending_item": None,
        }
        return queue_state, gate_state

    pending_items = [item for item in items if isinstance(item, dict) and item.get("status") == "pending"]
    manual_required = [item for item in items if isinstance(item, dict) and item.get("manual_start_required") is True]
    agent_started = [item for item in items if isinstance(item, dict) and item.get("agent_started") is True]
    pending_items_sorted = sorted(pending_items, key=lambda item: int(item.get("priority", 999999)))
    next_item = pending_items_sorted[0] if pending_items_sorted else None

    safe_next_item = safe_codex_item_summary(next_item) if isinstance(next_item, dict) else None
    queue_state = {
        "ok": True,
        "queue_path": str(queue_path),
        "schema_version": queue.get("schema_version"),
        "queue_id": queue.get("queue_id"),
        "queue_status": queue.get("status"),
        "item_count": len(items),
        "pending_count": len(pending_items),
        "manual_start_required_count": len(manual_required),
        "agent_started_count": len(agent_started),
        "next_pending_item": safe_next_item,
        "codex_start_allowed": False,
        "notes": "Queue is read-only in this phase. Codex is not started by this loop.",
    }
    return queue_state, evaluate_codex_queue_gate(next_item if isinstance(next_item, dict) else None)


def write_json(path: Path, data: dict[str, Any], pretty: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2 if pretty else None) + "\n", encoding="utf-8")


def append_log(path: Path, message: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(message + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one safe Orchestrator loop iteration.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--runtime-dir", default=DEFAULT_RUNTIME_DIR)
    parser.add_argument("--expected-branch", default="main")
    parser.add_argument("--timezone", default=DEFAULT_TIMEZONE)
    parser.add_argument("--check-remote", action="store_true", help="Check remote availability using git fetch --dry-run.")
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--codex-queue-path", default=DEFAULT_CODEX_QUEUE_PATH)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print loop status without writing loop_status.json or loop.log.",
    )
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    runtime_dir = Path(args.runtime_dir).expanduser().resolve()
    codex_queue_path = Path(args.codex_queue_path)
    if not codex_queue_path.is_absolute():
        codex_queue_path = repo_root / codex_queue_path

    if not args.dry_run:
        runtime_dir.mkdir(parents=True, exist_ok=True)

    paths = {
        "current_task_state": runtime_dir / "current_task_state.json",
        "current_codex_handoff": runtime_dir / "current_codex_handoff.md",
        "latest_approval_state": runtime_dir / "latest_approval_state.json",
        "latest_validation_result": runtime_dir / "latest_validation_result.json",
        "latest_decision_summary": runtime_dir / "latest_decision_summary.json",
        "latest_notice": runtime_dir / "latest_notice.md",
        "loop_status": runtime_dir / "loop_status.json",
        "loop_log": runtime_dir / "loop.log",
    }

    git_state = check_git_state(repo_root, args.expected_branch)
    remote_state = check_remote_state(repo_root, args.remote) if args.check_remote else {
        "ok": True,
        "check_mode": "disabled",
        "has_remote_changes": False,
    }
    timer_state = check_timer_state()
    codex_queue_state, codex_queue_gate_state = summarize_codex_queue(codex_queue_path)
    task_state = load_json_if_exists(paths["current_task_state"])
    approval_state = load_json_if_exists(paths["latest_approval_state"])
    validation_result = load_json_if_exists(paths["latest_validation_result"])
    decision_summary = load_json_if_exists(paths["latest_decision_summary"])
    handoff_status = read_text_status(paths["current_codex_handoff"])
    notice_status = read_text_status(paths["latest_notice"])

    status = {
        "ok": bool(
            git_state.get("ok")
            and timer_state.get("ok")
            and remote_state.get("ok")
            and codex_queue_state.get("ok")
            and codex_queue_gate_state.get("ok")
        ),
        "checked_at": now_iso(args.timezone),
        "mode": "dry_run" if args.dry_run else "single_iteration",
        "dry_run": bool(args.dry_run),
        "runtime_dir": str(runtime_dir),
        "repo_root": str(repo_root),
        "loop_running": False,
        "codex_running": False,
        "git_state": git_state,
        "remote_state": remote_state,
        "timer_state": timer_state,
        "codex_queue_state": codex_queue_state,
        "codex_queue_gate_state": codex_queue_gate_state,
        "runtime_state": {
            "current_task_state": task_state,
            "latest_approval_state": approval_state,
            "latest_validation_result": validation_result,
            "latest_decision_summary": decision_summary,
            "current_codex_handoff": handoff_status,
            "latest_notice": notice_status,
        },
        "actions": {
            "git_pull_run": False,
            "git_fetch_dry_run": bool(args.check_remote),
            "codex_queue_read": True,
            "codex_gate_checked": True,
            "codex_started": False,
            "notification_sent": False,
            "production_command_run": False,
            "timer_modified": False,
            "loop_status_written": False,
            "loop_log_written": False,
        },
        "next_action": "ready_for_codex_handoff_materializer",
    }

    if not args.dry_run:
        write_json(paths["loop_status"], status, args.pretty)
        append_log(
            paths["loop_log"],
            f"{status['checked_at']} single_iteration ok={status['ok']} remote_changes={remote_state.get('has_remote_changes')} queue_pending={codex_queue_state.get('pending_count')} gate_passed={codex_queue_gate_state.get('gate_passed')}",
        )
        status["actions"]["loop_status_written"] = True
        status["actions"]["loop_log_written"] = True
        write_json(paths["loop_status"], status, args.pretty)

    json.dump(status, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    return 0 if status["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
