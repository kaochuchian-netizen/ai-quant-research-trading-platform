#!/usr/bin/env python3
"""Print an Orchestrator stage report from JSON input files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("expected JSON object")
    return data


def value(data: dict[str, Any], *keys: str, default: str = "N/A") -> str:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
    if current is None:
        return default
    text = str(current).strip()
    return text if text else default


def list_from_stdout(data: dict[str, Any], *keys: str) -> list[str]:
    raw = value(data, *keys, default="")
    return [line.strip() for line in raw.splitlines() if line.strip()]


def bullet(items: list[str]) -> str:
    if not items:
        return "- N/A"
    return "\n".join(f"- {item}" for item in items)


def render(task: dict[str, Any], snapshot: dict[str, Any]) -> str:
    task_id = value(task, "task_id", default="unknown_task")
    task_name = value(task, "task_name", default="Untitled task")
    changed = list_from_stdout(snapshot, "git", "diff_name_only", "stdout")
    forbidden = snapshot.get("forbidden_path_changes", [])
    if not isinstance(forbidden, list):
        forbidden = []
    validations = []
    for item in snapshot.get("python_syntax_validation", []):
        if isinstance(item, dict):
            status = "passed" if item.get("ok") else "failed"
            validations.append(f"{item.get('path')}: {status}")

    return f"""# Orchestrator Stage Report

## Task

- Task ID: {task_id}
- Task name: {task_name}

## Changed files

{bullet(changed)}

## Validation

{bullet(validations)}

## Repository state

- Branch: {value(snapshot, 'git', 'branch', 'stdout')}
- HEAD: {value(snapshot, 'git', 'head', 'stdout')}
- Working tree: {value(snapshot, 'git', 'status_short', 'stdout', default='clean')}
- Forbidden path changes: {', '.join(str(x) for x in forbidden) if forbidden else 'none'}

## Next step choices

- continue next defined task
- pause after current stage
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-state", required=True)
    parser.add_argument("--validation-snapshot", required=True)
    args = parser.parse_args()
    print(render(load_json(Path(args.task_state)), load_json(Path(args.validation_snapshot))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
