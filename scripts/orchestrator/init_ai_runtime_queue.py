#!/usr/bin/env python3
"""Initialize runtime AI task queue files from repository seed files.

This script only creates local runtime queue state. It does not create
branches, commit, push, open PRs, merge, run production workflows, send
notifications, place orders, or modify schedulers.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


DEFAULT_RUNTIME_DIR = "~/.local/state/stock-ai-orchestrator"
SEED_PENDING_QUEUE_PATH = "orchestrator/queue/pending_tasks.json"
SEED_COMPLETED_QUEUE_PATH = "orchestrator/queue/completed_tasks.json"


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be object: {path}")
    return data


def atomic_copy_json(source: Path, destination: Path) -> None:
    data = load_json(source)
    tmp_path = destination.with_name(destination.name + ".tmp")
    tmp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp_path, destination)


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize runtime AI queue files from repo seed files.")
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--runtime-dir", default=DEFAULT_RUNTIME_DIR)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    runtime_dir = Path(args.runtime_dir).expanduser().resolve()
    seed_pending_path = (repo_root / SEED_PENDING_QUEUE_PATH).resolve()
    seed_completed_path = (repo_root / SEED_COMPLETED_QUEUE_PATH).resolve()
    runtime_pending_path = runtime_dir / "pending_tasks.json"
    runtime_completed_path = runtime_dir / "completed_tasks.json"

    side_effects = {
        "runtime_dir_created": False,
        "runtime_pending_queue_written": False,
        "runtime_completed_queue_written": False,
        "source_files_modified": False,
        "branch_created": False,
        "commit_created": False,
        "push_run": False,
        "pr_created": False,
        "merge_run": False,
        "production_command_run": False,
        "notification_sent": False,
        "trading_execution_run": False,
        "scheduler_modified": False,
    }

    reasons: list[str] = []
    actions: list[dict[str, Any]] = []

    if not seed_pending_path.exists():
        reasons.append(f"missing seed pending queue: {seed_pending_path}")
    if not seed_completed_path.exists():
        reasons.append(f"missing seed completed queue: {seed_completed_path}")

    if not reasons:
        existed_before = runtime_dir.exists()
        runtime_dir.mkdir(parents=True, exist_ok=True)
        side_effects["runtime_dir_created"] = not existed_before

        for label, source, destination, side_effect_key in (
            ("pending", seed_pending_path, runtime_pending_path, "runtime_pending_queue_written"),
            ("completed", seed_completed_path, runtime_completed_path, "runtime_completed_queue_written"),
        ):
            if destination.exists() and not args.force:
                actions.append({
                    "queue": label,
                    "action": "skipped_existing",
                    "source": str(source),
                    "destination": str(destination),
                })
                continue
            destination_existed = destination.exists()
            atomic_copy_json(source, destination)
            side_effects[side_effect_key] = True
            actions.append({
                "queue": label,
                "action": "overwritten" if destination_existed else "written",
                "source": str(source),
                "destination": str(destination),
            })

    output = {
        "ok": not reasons,
        "runtime_dir": str(runtime_dir),
        "force": args.force,
        "seed_pending_queue_path": str(seed_pending_path),
        "seed_completed_queue_path": str(seed_completed_path),
        "runtime_pending_queue_path": str(runtime_pending_path),
        "runtime_completed_queue_path": str(runtime_completed_path),
        "actions": actions,
        "reasons": reasons,
        "side_effects": side_effects,
    }
    json.dump(output, fp=sys.stdout, ensure_ascii=False, indent=2 if args.pretty else None)
    sys.stdout.write("\n")
    return 0 if output["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
