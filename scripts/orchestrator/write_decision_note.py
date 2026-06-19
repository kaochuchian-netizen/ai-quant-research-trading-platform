#!/usr/bin/env python3
"""Write a markdown note from an Orchestrator decision summary JSON."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


DEFAULT_TIMEZONE = "Asia/Taipei"
DEFAULT_TMP_PREFIX = "stock_ai_orchestrator_decision_note_"


def now_iso(timezone_name: str) -> str:
    return datetime.now(ZoneInfo(timezone_name)).replace(microsecond=0).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("JSON file must contain an object")
    return data


def nested_get(data: dict[str, Any], *keys: str) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def safe_name(value: str | None) -> str:
    raw = value or "unknown"
    return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in raw)


def default_output_path(task_id: str | None) -> Path:
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    return Path(tempfile.gettempdir()) / f"{DEFAULT_TMP_PREFIX}{safe_name(task_id)}_{timestamp}.md"


def render_note(decision: dict[str, Any], timezone_name: str) -> str:
    task_id = decision.get("task_id") or "unknown"
    task_name = decision.get("task_name") or "unknown"
    value = decision.get("decision") or "unknown"
    next_id = nested_get(decision, "next_task", "suggested_task_id") or "not_defined"
    next_name = nested_get(decision, "next_task", "suggested_task_name") or "not_defined"
    should_continue = nested_get(decision, "next_task", "should_start_next_task")
    blocked_reason = decision.get("blocked_reason") or "none"

    return f"""# Orchestrator decision note

Created at: {now_iso(timezone_name)}

- Current ID: {task_id}
- Current name: {task_name}
- Decision: {value}
- Suggested ID: {next_id}
- Suggested name: {next_name}
- Continue flag: {should_continue}
- Blocked reason: {blocked_reason}
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write a decision note markdown file.")
    parser.add_argument("--decision-summary", required=True)
    parser.add_argument("--output")
    parser.add_argument("--timezone", default=DEFAULT_TIMEZONE)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        decision = load_json(Path(args.decision_summary).expanduser())
        task_id = str(decision.get("task_id") or "unknown")
        output_path = Path(args.output).expanduser() if args.output else default_output_path(task_id)
        if not output_path.is_absolute():
            output_path = Path.cwd() / output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(render_note(decision, args.timezone), encoding="utf-8")
        result = {
            "ok": True,
            "decision": decision.get("decision"),
            "task_id": task_id,
            "output_path": str(output_path),
        }
    except Exception as exc:
        result = {
            "ok": False,
            "blocked_reason": str(exc),
        }

    json.dump(result, sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
