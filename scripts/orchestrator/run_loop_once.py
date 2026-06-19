#!/usr/bin/env python3
"""Run one safe Orchestrator loop iteration.

This loop checks local runtime state, repository state, timer health, optional remote Git
availability, Codex queue readiness, handoff materialization, and the manual Codex
start gate. It does not start Codex, send notifications, or run production workflows.
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


def now_iso(timezone_name: str) -> str:
    return datetime.now(ZoneInfo(timezone_name)).replace(microsecond=0).isoformat()


def run_command(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
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
    return {
        "ok": fetch_dry_run.returncode == 0,
        "remote": remote,
        "check_mode": "fetch_dry_run",
        "has_remote_changes": bool(output.strip()),
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
    return {
        "ok": enabled_value == "enabled" and active_value == "active",
        "timer_name": TIMER_NAME,
        "service_name": SERVICE_NAME,
        "timer_enabled": enabled_value,
        "timer_active": active_value,
        "service_active": service_active.stdout.strip(),
        "commands": {
            "timer_enabled": command_summary("timer_enabled", timer_enabled),
            "timer_active": command_summary("timer_active", timer_active),
            "service_active": command_summary("service_active", service_active),
            "list_timers": command_summary("list_timers", list_timers),
        },
    }


def summarize_codex_queue(queue_path: Path) -> dict[str, Any]:
    queue = load_json_if_exists(queue_path)
    if not queue.get("ok", True):
        return {
            "ok": queue.get("state") == "missing",
            "queue_path": str(queue_path),
            "state": queue.get("state"),
            "error": queue.get("reason"),
            "item_count": 0,
            "pending_count": 0,
            "next_pending_item": None,
            "codex_start_allowed": False,
        }

    items = queue.get("items", [])
    if not isinstance(items, list):
        return {
            "ok": False,
            "queue_path": str(queue_path),
            "state": "invalid",
            "error": "items is not a list",
            "item_count": 0,
            "pending_count": 0,
            "next_pending_item": None,
            "codex_start_allowed": False,
        }

    pending = [item for item in items if isinstance(item, dict) and item.get("status") == "pending"]
    pending_sorted = sorted(pending, key=lambda item: int(item.get("priority", 999999)))
    next_item = pending_sorted[0] if pending_sorted else None
    safe_next = None
    if isinstance(next_item, dict):
        safe_next = {
            "handoff_id": next_item.get("handoff_id"),
            "task_id": next_item.get("task_id"),
            "task_name": next_item.get("task_name"),
            "status": next_item.get("status"),
            "priority": next_item.get("priority"),
            "manual_start_required": next_item.get("manual_start_required"),
            "agent_started": next_item.get("agent_started"),
            "allowed_task_type": next_item.get("allowed_task_type"),
        }
    return {
        "ok": True,
        "queue_path": str(queue_path),
        "schema_version": queue.get("schema_version"),
        "queue_id": queue.get("queue_id"),
        "queue_status": queue.get("status"),
        "item_count": len(items),
        "pending_count": len(pending),
        "next_pending_item": safe_next,
        "codex_start_allowed": False,
        "notes": "Queue is read-only at this stage. Codex is not started by this loop.",
    }


def run_json_script(script_path: Path, args: list[str], repo_root: Path) -> dict[str, Any]:
    completed = run_command([sys.executable, str(script_path), *args], repo_root)
    try:
        parsed_data = json.loads(completed.stdout) if completed.stdout.strip() else {}
        parsed = parsed_data if isinstance(parsed_data, dict) else {"raw": parsed_data}
    except Exception as exc:
        parsed = {"parse_error": str(exc), "stdout": completed.stdout.strip()}
    parsed["command"] = command_summary(script_path.name, completed)
    parsed["ok"] = bool(parsed.get("ok", completed.returncode == 0))
    return parsed


def check_codex_queue_gate(repo_root: Path, queue_path: Path) -> dict[str, Any]:
    script_path = repo_root / "scripts" / "orchestrator" / "check_codex_queue_gate.py"
    if not script_path.exists():
        return {
            "ok": False,
            "gate_passed": False,
            "codex_start_allowed": False,
            "blocked_reasons": ["gate checker script missing"],
        }
    result = run_json_script(script_path, ["--queue-path", str(queue_path)], repo_root)
    result["codex_start_allowed"] = False
    return result


def materialize_codex_handoff(repo_root: Path, queue_path: Path, runtime_dir: Path, timezone_name: str, pretty: bool, dry_run: bool, gate_state: dict[str, Any]) -> dict[str, Any]:
    if not gate_state.get("gate_passed"):
        return {
            "ok": True,
            "materialized": False,
            "reason": "gate_not_passed",
            "runtime_files_written": False,
            "codex_started": False,
        }
    if dry_run:
        return {
            "ok": True,
            "materialized": False,
            "reason": "dry_run",
            "runtime_files_written": False,
            "codex_started": False,
        }

    script_path = repo_root / "scripts" / "orchestrator" / "materialize_codex_handoff.py"
    if not script_path.exists():
        return {
            "ok": False,
            "materialized": False,
            "reason": "materializer_script_missing",
            "runtime_files_written": False,
            "codex_started": False,
        }
    args = [
        "--queue-path",
        str(queue_path),
        "--runtime-dir",
        str(runtime_dir),
        "--timezone",
        timezone_name,
    ]
    if pretty:
        args.append("--pretty")
    result = run_json_script(script_path, args, repo_root)
    result["materialized"] = bool(result.get("ok") and result.get("side_effects", {}).get("runtime_files_written"))
    result["codex_started"] = False
    return result


def check_manual_codex_start_gate(repo_root: Path, runtime_dir: Path) -> dict[str, Any]:
    json_path = runtime_dir / "current_codex_handoff.json"
    if not json_path.exists():
        return {
            "ok": True,
            "manual_start_ready": False,
            "codex_start_allowed": False,
            "blocked_reasons": ["current_codex_handoff.json missing"],
            "codex_started": False,
            "notes": "No materialized handoff is available yet. Codex is not started by this loop.",
        }
    script_path = repo_root / "scripts" / "orchestrator" / "check_manual_codex_start_gate.py"
    if not script_path.exists():
        return {
            "ok": False,
            "manual_start_ready": False,
            "codex_start_allowed": False,
            "blocked_reasons": ["manual Codex start gate checker script missing"],
            "codex_started": False,
        }
    result = run_json_script(script_path, ["--runtime-dir", str(runtime_dir)], repo_root)
    result["codex_start_allowed"] = False
    result["codex_started"] = False
    return result


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
    parser.add_argument("--dry-run", action="store_true", help="Print loop status without writing loop_status.json or loop.log.")
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
        "current_codex_handoff_json": runtime_dir / "current_codex_handoff.json",
        "current_codex_handoff": runtime_dir / "current_codex_handoff.md",
        "latest_approval_state": runtime_dir / "latest_approval_state.json",
        "latest_validation_result": runtime_dir / "latest_validation_result.json",
        "latest_decision_summary": runtime_dir / "latest_decision_summary.json",
        "latest_notice": runtime_dir / "latest_notice.md",
        "loop_status": runtime_dir / "loop_status.json",
        "loop_log": runtime_dir / "loop.log",
    }

    git_state = check_git_state(repo_root, args.expected_branch)
    remote_state = check_remote_state(repo_root, args.remote) if args.check_remote else {"ok": True, "check_mode": "disabled", "has_remote_changes": False}
    timer_state = check_timer_state()
    codex_queue_state = summarize_codex_queue(codex_queue_path)
    codex_queue_gate_state = check_codex_queue_gate(repo_root, codex_queue_path)
    codex_handoff_materialize_state = materialize_codex_handoff(
        repo_root,
        codex_queue_path,
        runtime_dir,
        args.timezone,
        args.pretty,
        args.dry_run,
        codex_queue_gate_state,
    )
    manual_codex_start_gate_state = check_manual_codex_start_gate(repo_root, runtime_dir)

    task_state = load_json_if_exists(paths["current_task_state"])
    approval_state = load_json_if_exists(paths["latest_approval_state"])
    validation_result = load_json_if_exists(paths["latest_validation_result"])
    decision_summary = load_json_if_exists(paths["latest_decision_summary"])
    handoff_json_state = load_json_if_exists(paths["current_codex_handoff_json"])
    handoff_status = read_text_status(paths["current_codex_handoff"])
    notice_status = read_text_status(paths["latest_notice"])

    status = {
        "ok": bool(
            git_state.get("ok")
            and timer_state.get("ok")
            and remote_state.get("ok")
            and codex_queue_state.get("ok")
            and codex_queue_gate_state.get("ok")
            and codex_handoff_materialize_state.get("ok")
            and manual_codex_start_gate_state.get("ok")
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
        "codex_handoff_materialize_state": codex_handoff_materialize_state,
        "manual_codex_start_gate_state": manual_codex_start_gate_state,
        "runtime_state": {
            "current_task_state": task_state,
            "latest_approval_state": approval_state,
            "latest_validation_result": validation_result,
            "latest_decision_summary": decision_summary,
            "current_codex_handoff_json": handoff_json_state,
            "current_codex_handoff": handoff_status,
            "latest_notice": notice_status,
        },
        "actions": {
            "git_pull_run": False,
            "git_fetch_dry_run": bool(args.check_remote),
            "codex_queue_read": True,
            "codex_gate_checked": True,
            "codex_handoff_materialized": bool(codex_handoff_materialize_state.get("materialized")),
            "manual_codex_start_gate_checked": True,
            "manual_codex_start_ready": bool(manual_codex_start_gate_state.get("manual_start_ready")),
            "codex_started": False,
            "notification_sent": False,
            "production_command_run": False,
            "timer_modified": False,
            "loop_status_written": False,
            "loop_log_written": False,
        },
        "next_action": "manual_review_required_before_codex_start",
    }

    if not args.dry_run:
        write_json(paths["loop_status"], status, args.pretty)
        append_log(
            paths["loop_log"],
            f"{status['checked_at']} single_iteration ok={status['ok']} remote_changes={remote_state.get('has_remote_changes')} queue_pending={codex_queue_state.get('pending_count')} gate_passed={codex_queue_gate_state.get('gate_passed')} materialized={codex_handoff_materialize_state.get('materialized')} manual_start_ready={manual_codex_start_gate_state.get('manual_start_ready')}",
        )
        status["actions"]["loop_status_written"] = True
        status["actions"]["loop_log_written"] = True
        write_json(paths["loop_status"], status, args.pretty)

    json.dump(status, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    return 0 if status["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
