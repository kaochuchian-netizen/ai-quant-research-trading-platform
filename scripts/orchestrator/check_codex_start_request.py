#!/usr/bin/env python3
"""Check whether a runtime Codex start request is valid.

This script is read-only. It does not start Codex, modify runtime files, run Git,
send notifications, or run production workflows.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


DEFAULT_RUNTIME_DIR = "~/.local/state/stock-ai-orchestrator"
DEFAULT_TIMEZONE = "Asia/Taipei"
REQUEST_FILENAME = "codex_start_request.json"


def now(timezone_name: str) -> datetime:
    return datetime.now(ZoneInfo(timezone_name)).replace(microsecond=0)


def parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"ok": False, "state": "missing", "path": str(path), "error": "start request missing"}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"ok": False, "state": "invalid", "path": str(path), "error": "JSON root is not an object"}
        return {"ok": True, "state": "loaded", "path": str(path), "data": data}
    except Exception as exc:
        return {"ok": False, "state": "invalid", "path": str(path), "error": str(exc)}


def check_request(request: dict[str, Any], checked_at: datetime) -> dict[str, Any]:
    blocked: list[str] = []

    if request.get("status") != "active":
        blocked.append("status must be active")
    if request.get("manual_review_completed") is not True:
        blocked.append("manual_review_completed must be true")
    if request.get("operator_approved") is not True:
        blocked.append("operator_approved must be true")
    if request.get("codex_start_allowed") is not True:
        blocked.append("codex_start_allowed must be true")
    if request.get("codex_autostart_allowed") is not False:
        blocked.append("codex_autostart_allowed must remain false")

    expires_at = parse_datetime(request.get("expires_at"))
    if expires_at is None:
        blocked.append("expires_at must be a valid ISO datetime")
    elif expires_at <= checked_at:
        blocked.append("start request is expired")

    required_preconditions = request.get("required_preconditions", {})
    if not isinstance(required_preconditions, dict):
        blocked.append("required_preconditions must be an object")
    else:
        for key in [
            "loop_status_ok",
            "git_working_tree_clean",
            "timer_active",
            "queue_gate_passed",
            "handoff_materialized",
            "manual_start_ready",
        ]:
            if required_preconditions.get(key) is not True:
                blocked.append(f"required_preconditions.{key} must be true")

    allowed_scope = request.get("allowed_scope", {})
    if not isinstance(allowed_scope, dict):
        blocked.append("allowed_scope must be an object")
    else:
        if allowed_scope.get("task_type") != "orchestrator_low_risk":
            blocked.append("allowed_scope.task_type must be orchestrator_low_risk")
        if not isinstance(allowed_scope.get("allowed_paths"), list) or not allowed_scope.get("allowed_paths"):
            blocked.append("allowed_scope.allowed_paths must be a non-empty list")
        if not isinstance(allowed_scope.get("blocked_paths"), list) or not allowed_scope.get("blocked_paths"):
            blocked.append("allowed_scope.blocked_paths must be a non-empty list")

    if not isinstance(request.get("safety_acknowledgements"), list) or not request.get("safety_acknowledgements"):
        blocked.append("safety_acknowledgements must be a non-empty list")

    return {
        "ok": True,
        "request_present": True,
        "start_request_valid": not blocked,
        "codex_start_allowed": False,
        "blocked_reasons": blocked,
        "request_id": request.get("request_id"),
        "handoff_id": request.get("handoff_id"),
        "task_id": request.get("task_id"),
        "status": request.get("status"),
        "operator_approved": request.get("operator_approved"),
        "manual_review_completed": request.get("manual_review_completed"),
        "expires_at": request.get("expires_at"),
        "notes": "Valid request only means a future start step may be considered. This checker never starts Codex.",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check Codex start request file.")
    parser.add_argument("--runtime-dir", default=DEFAULT_RUNTIME_DIR)
    parser.add_argument("--timezone", default=DEFAULT_TIMEZONE)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    runtime_dir = Path(args.runtime_dir).expanduser().resolve()
    request_path = runtime_dir / REQUEST_FILENAME
    checked_at = now(args.timezone)
    loaded = load_json(request_path)

    base = {
        "runtime_dir": str(runtime_dir),
        "request_path": str(request_path),
        "checked_at": checked_at.isoformat(),
        "codex_start_allowed": False,
        "codex_started": False,
        "side_effects": {
            "codex_started": False,
            "runtime_modified": False,
            "git_command_run": False,
            "notification_sent": False,
            "production_command_run": False,
        },
    }

    if not loaded.get("ok"):
        result = {
            **base,
            "ok": loaded.get("state") == "missing",
            "request_present": False,
            "start_request_valid": False,
            "request_state": loaded.get("state"),
            "blocked_reasons": [loaded.get("error")],
            "notes": "No active start request. Codex is not started.",
        }
        json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
        sys.stdout.write("\n")
        return 0 if result["ok"] else 1

    result = {**base, **check_request(loaded["data"], checked_at)}
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
