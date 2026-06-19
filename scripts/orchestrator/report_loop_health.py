#!/usr/bin/env python3
"""Report VM Orchestrator loop health.

This script reads local runtime status and user-level systemd status.
It does not modify files, start services, run Codex, pull Git, or send notifications.
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
TIMER_NAME = "stock-ai-orchestrator-loop.timer"
SERVICE_NAME = "stock-ai-orchestrator-loop.service"


def now_iso(timezone_name: str) -> str:
    return datetime.now(ZoneInfo(timezone_name)).replace(microsecond=0).isoformat()


def run_command(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
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


def load_json(path: Path) -> dict[str, Any]:
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


def read_log_tail(path: Path, lines: int) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False, "path": str(path), "tail": []}
    try:
        content = path.read_text(encoding="utf-8").splitlines()
        return {
            "exists": True,
            "path": str(path),
            "line_count": len(content),
            "tail": content[-lines:],
        }
    except Exception as exc:
        return {"exists": True, "path": str(path), "error": str(exc), "tail": []}


def systemd_health() -> dict[str, Any]:
    timer_enabled = run_command(["systemctl", "--user", "is-enabled", TIMER_NAME])
    timer_active = run_command(["systemctl", "--user", "is-active", TIMER_NAME])
    service_active = run_command(["systemctl", "--user", "is-active", SERVICE_NAME])
    list_timers = run_command(["systemctl", "--user", "list-timers", "--all", TIMER_NAME, "--no-pager"])

    return {
        "timer_name": TIMER_NAME,
        "service_name": SERVICE_NAME,
        "timer_enabled": timer_enabled.stdout.strip(),
        "timer_active": timer_active.stdout.strip(),
        "service_active": service_active.stdout.strip(),
        "commands": {
            "timer_enabled": command_summary("timer_enabled", timer_enabled),
            "timer_active": command_summary("timer_active", timer_active),
            "service_active": command_summary("service_active", service_active),
            "list_timers": command_summary("list_timers", list_timers),
        },
    }


def build_health_report(runtime_dir: Path, timezone_name: str, log_lines: int) -> dict[str, Any]:
    loop_status_path = runtime_dir / "loop_status.json"
    loop_log_path = runtime_dir / "loop.log"
    loop_status = load_json(loop_status_path)
    log_tail = read_log_tail(loop_log_path, log_lines)
    systemd = systemd_health()

    status_ok = bool(loop_status.get("ok"))
    timer_ok = systemd.get("timer_enabled") == "enabled" and systemd.get("timer_active") == "active"
    log_ok = bool(log_tail.get("exists")) and int(log_tail.get("line_count") or 0) > 0

    return {
        "ok": bool(status_ok and timer_ok and log_ok),
        "reported_at": now_iso(timezone_name),
        "runtime_dir": str(runtime_dir),
        "loop_status_path": str(loop_status_path),
        "loop_log_path": str(loop_log_path),
        "checks": {
            "loop_status_ok": status_ok,
            "timer_ok": timer_ok,
            "log_ok": log_ok,
        },
        "loop_status": loop_status,
        "systemd": systemd,
        "loop_log": log_tail,
        "side_effects": {
            "files_modified": False,
            "git_command_run": False,
            "codex_started": False,
            "notification_sent": False,
            "production_command_run": False,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Report VM Orchestrator loop health.")
    parser.add_argument("--runtime-dir", default=DEFAULT_RUNTIME_DIR)
    parser.add_argument("--timezone", default=DEFAULT_TIMEZONE)
    parser.add_argument("--log-lines", type=int, default=5)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    runtime_dir = Path(args.runtime_dir).expanduser().resolve()
    report = build_health_report(runtime_dir, args.timezone, args.log_lines)
    json.dump(report, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
