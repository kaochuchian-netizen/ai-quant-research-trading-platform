#!/usr/bin/env python3
"""Parse a local approval reply text into an Orchestrator approval state JSON.

This parser is intentionally local-only:
- It reads a provided text file or stdin.
- It accepts only the first actionable reply token: continue or pause.
- It writes an approval-state JSON to /tmp by default.
- It does not read a mailbox, send mail, start Codex, run Git, or execute tasks.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


VALID_ACTIONS = {"continue", "pause"}
DEFAULT_TIMEZONE = "Asia/Taipei"
DEFAULT_TMP_PREFIX = "stock_ai_orchestrator_approval_"
QUOTE_PREFIXES = (">", "On ", "From:", "Sent:", "To:", "Subject:", "-----Original Message-----")


def now_iso(timezone_name: str) -> str:
    return datetime.now(ZoneInfo(timezone_name)).replace(microsecond=0).isoformat()


def load_text(path: str | None) -> str:
    if not path or path == "-":
        return sys.stdin.read()
    return Path(path).expanduser().read_text(encoding="utf-8")


def load_task_state(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    with Path(path).expanduser().open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("task state must be a JSON object")
    return data


def first_actionable_line(reply_text: str) -> str | None:
    for raw_line in reply_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if any(line.startswith(prefix) for prefix in QUOTE_PREFIXES):
            continue
        return line
    return None


def normalize_action(line: str | None) -> str | None:
    if line is None:
        return None
    token = line.strip().lower()
    token = token.replace("。", "").replace(".", "").strip()
    if token in VALID_ACTIONS:
        return token
    return None


def default_output_path(task_id: str | None) -> Path:
    safe_task_id = task_id or "unknown_task"
    safe_task_id = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in safe_task_id)
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    return Path(tempfile.gettempdir()) / f"{DEFAULT_TMP_PREFIX}{safe_task_id}_{timestamp}.json"


def build_approval_state(
    reply_text: str,
    task_state: dict[str, Any],
    sender: str | None,
    allowed_sender: str | None,
    timezone_name: str,
) -> dict[str, Any]:
    task_id = task_state.get("task_id")
    task_name = task_state.get("task_name")
    reply_line = first_actionable_line(reply_text)
    action = normalize_action(reply_line)

    sender_allowed = True
    if allowed_sender:
        sender_allowed = bool(sender and sender.strip().lower() == allowed_sender.strip().lower())

    ok = action in VALID_ACTIONS and sender_allowed
    blocked_reason = None
    if action not in VALID_ACTIONS:
        blocked_reason = "reply action must be exactly continue or pause"
    elif not sender_allowed:
        blocked_reason = "sender is not allowed"

    return {
        "ok": ok,
        "task_id": task_id,
        "task_name": task_name,
        "parsed_at": now_iso(timezone_name),
        "reply": {
            "sender": sender,
            "allowed_sender": allowed_sender,
            "sender_allowed": sender_allowed,
            "first_actionable_line": reply_line,
            "selected_action": action,
        },
        "approval": {
            "state": f"approved_{action}" if ok else "blocked",
            "allowed_actions": sorted(VALID_ACTIONS),
            "selected_action": action if ok else None,
        },
        "blocked_reason": blocked_reason,
        "side_effects": {
            "mailbox_read": False,
            "email_sent": False,
            "git_command_run": False,
            "task_started": False,
            "production_command_run": False,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Parse local continue/pause approval reply text.")
    parser.add_argument("--reply-file", help="Reply text file. Use '-' or omit to read stdin.")
    parser.add_argument("--task-state", help="Optional task state JSON path.")
    parser.add_argument("--sender", help="Reply sender email or identifier for allowlist checking.")
    parser.add_argument("--allowed-sender", help="Only accept reply when sender matches this value exactly, case-insensitive.")
    parser.add_argument("--output", help="Output JSON path. Defaults to a /tmp file.")
    parser.add_argument("--timezone", default=DEFAULT_TIMEZONE)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        task_state = load_task_state(args.task_state)
        reply_text = load_text(args.reply_file)
        approval_state = build_approval_state(
            reply_text=reply_text,
            task_state=task_state,
            sender=args.sender,
            allowed_sender=args.allowed_sender,
            timezone_name=args.timezone,
        )
    except Exception as exc:
        approval_state = {
            "ok": False,
            "approval": {"state": "error", "selected_action": None},
            "blocked_reason": str(exc),
        }

    output_path = Path(args.output).expanduser() if args.output else default_output_path(approval_state.get("task_id"))
    if not output_path.is_absolute():
        output_path = Path.cwd() / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)

    approval_state["output_path"] = str(output_path)
    output_text = json.dumps(approval_state, ensure_ascii=False, indent=2 if args.pretty else None)
    output_path.write_text(output_text + "\n", encoding="utf-8")
    sys.stdout.write(output_text + "\n")

    return 0 if approval_state.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
