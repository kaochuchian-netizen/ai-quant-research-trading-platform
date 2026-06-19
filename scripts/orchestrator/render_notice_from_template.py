#!/usr/bin/env python3
"""Render a notice markdown file from the Orchestrator static template."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("expected JSON object")
    return data


def pick(data: dict[str, Any], *keys: str, default: str = "N/A") -> str:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
    if current is None:
        return default
    text = str(current).strip()
    return text if text else default


def lines_from(data: dict[str, Any], *keys: str) -> list[str]:
    raw = pick(data, *keys, default="")
    return [line.strip() for line in raw.splitlines() if line.strip()]


def as_block(items: list[str]) -> str:
    if not items:
        return "- N/A"
    return "\n".join(f"- {item}" for item in items)


def validation_block(snapshot: dict[str, Any]) -> str:
    rows: list[str] = []
    for item in snapshot.get("python_syntax_validation", []):
        if isinstance(item, dict):
            status = "passed" if item.get("ok") else "failed"
            rows.append(f"- Python syntax {item.get('path')}: {status}")
    return "\n".join(rows) if rows else "- N/A"


def summary_block(task: dict[str, Any]) -> str:
    stage_summary = task.get("stage_summary")
    if isinstance(stage_summary, dict):
        summary = stage_summary.get("summary")
        if summary:
            return f"- {summary}"
    return "- Stage report generated from task state and validation snapshot"


def decision_value(decision: dict[str, Any], *keys: str, default: str = "pending") -> str:
    if not decision:
        return default
    return pick(decision, *keys, default=default)


def render(
    template: str,
    task: dict[str, Any],
    snapshot: dict[str, Any],
    decision: dict[str, Any] | None = None,
) -> str:
    decision = decision or {}
    task_id = pick(task, "task_id", default="unknown_task")
    task_name = pick(task, "task_name", default="Untitled task")
    git_state = task.get("git", {}) if isinstance(task.get("git"), dict) else {}
    safety = task.get("safety_check", {}) if isinstance(task.get("safety_check"), dict) else {}
    next_task = task.get("next_task", {}) if isinstance(task.get("next_task"), dict) else {}
    changed = as_block(lines_from(snapshot, "git", "diff_name_only", "stdout"))
    forbidden = snapshot.get("forbidden_path_changes", [])
    if not isinstance(forbidden, list):
        forbidden = []

    replacements = {
        "<task_id>": task_id,
        "<task_name>": task_name,
        "<completed_at>": pick(snapshot, "created_at"),
        "<commit_hash_or_not_created>": pick(git_state, "commit_hash", default="not_created"),
        "<commit_message_or_not_applicable>": pick(git_state, "commit_message"),
        "- <path>": changed,
        "- <summary>": summary_block(task),
        "- <command_or_check>: <passed_failed_or_skipped>": validation_block(snapshot),
        "none / detected / blocked": pick(safety, "production_side_effect_detected", default="none"),
        "none / list paths": ", ".join(str(x) for x in forbidden) if forbidden else "none",
        "<reason_or_none>": pick(safety, "blocked_reason", default="none"),
        "<next_task_id>": pick(next_task, "suggested_task_id", default="not_defined"),
        "<next_task_name>": pick(next_task, "suggested_task_name", default="not_defined"),
        "<decision_or_pending>": decision_value(decision, "decision", default="pending"),
        "<next_task_allowed_or_false>": decision_value(decision, "approval_gate", "next_task_allowed", default="false"),
        "<pause_requested_or_false>": decision_value(decision, "approval_gate", "pause_requested", default="false"),
        "<should_start_next_task_or_false>": decision_value(decision, "next_task", "should_start_next_task", default="false"),
        "<decision_blocked_reason_or_none>": decision_value(decision, "blocked_reason", default="none"),
    }

    output = template
    for source, target in replacements.items():
        output = output.replace(source, target)
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--template", required=True)
    parser.add_argument("--task-state", required=True)
    parser.add_argument("--validation-snapshot", required=True)
    parser.add_argument("--decision-summary", help="Optional next-task decision summary JSON path.")
    parser.add_argument("--output")
    args = parser.parse_args()

    decision = load_json(Path(args.decision_summary)) if args.decision_summary else None
    result = render(
        Path(args.template).read_text(encoding="utf-8"),
        load_json(Path(args.task_state)),
        load_json(Path(args.validation_snapshot)),
        decision,
    )

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(result, encoding="utf-8")
    else:
        sys.stdout.write(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
