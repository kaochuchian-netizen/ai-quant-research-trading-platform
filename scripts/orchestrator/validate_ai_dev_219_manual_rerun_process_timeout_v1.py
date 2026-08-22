#!/usr/bin/env python3
"""AI-DEV-219 process-group timeout containment and observability validator."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.runtime.manual_rerun_process_supervisor import run_process_group
from scripts.orchestrator import manual_rerun_runtime_bridge as bridge


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def python_command(source: str) -> list[str]:
    return [sys.executable, "-c", source]


def process_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def main() -> int:
    cases: dict[str, str] = {}
    with tempfile.TemporaryDirectory(prefix="ai-dev-219-") as directory:
        root = Path(directory)

        updates: list[dict[str, object]] = []
        success = run_process_group(
            python_command(
                "from app.runtime.manual_rerun_progress import report_manual_rerun_stage as r;"
                "r('runtime_started');r('market_data');print('healthy runtime', flush=True);"
                "r('market_data','completed');r('completed','completed')"
            ),
            cwd=ROOT,
            task_id="success",
            log_path=root / "success.log",
            progress_path=root / "success.jsonl",
            timeout_seconds=5,
            heartbeat_seconds=0.05,
            update=lambda item: updates.append(dict(item)),
        )
        require(success.stage_timings["market_data"].get("elapsed_seconds") is not None, "stage elapsed time missing")
        require(success.returncode == 0 and not success.timed_out, "successful control runtime failed")
        require(success.pid == success.pgid, "runtime did not start in an isolated process session")
        require(not success.termination, "successful runtime received a termination signal")
        require("healthy runtime" in (root / "success.log").read_text(encoding="utf-8"), "successful output missing")
        require(success.stage == "completed", "successful stage did not reach completed")
        require(any(item.get("runtime_heartbeat") for item in updates), "runtime heartbeat missing")
        require({"runtime_started", "market_data", "completed"}.issubset(success.stage_timings), "stage timing missing")
        cases["successful_runtime"] = "PASS"

        inherited_source = (
            "import subprocess,sys,time;"
            "p=subprocess.Popen([sys.executable,'-c',"
            "'import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);time.sleep(60)']);"
            "print('DESCENDANT_PID='+str(p.pid),flush=True);time.sleep(60)"
        )
        started = time.monotonic()
        inherited = run_process_group(
            python_command(inherited_source),
            cwd=ROOT,
            task_id="inherited-pipe",
            log_path=root / "inherited.log",
            progress_path=root / "inherited.jsonl",
            timeout_seconds=0.35,
            terminate_grace_seconds=0.15,
            kill_grace_seconds=1,
            heartbeat_seconds=0.05,
        )
        elapsed = time.monotonic() - started
        require(inherited.timed_out, "descendant inherited-pipe fixture did not time out")
        require(elapsed < 3, "timeout cleanup was not bounded")
        signals = [entry.get("signal") for entry in inherited.termination if entry.get("sent")]
        require("SIGTERM" in signals and "SIGKILL" in signals, "TERM/KILL process-group sequence missing")
        text = (root / "inherited.log").read_text(encoding="utf-8")
        descendant_pid = int(text.split("DESCENDANT_PID=", 1)[1].splitlines()[0])
        deadline = time.monotonic() + 2
        while process_exists(descendant_pid) and time.monotonic() < deadline:
            time.sleep(0.05)
        require(not process_exists(descendant_pid), "orphan descendant survived process-group cleanup")
        cases["descendant_inherited_pipe"] = "PASS"

        ignore_term = run_process_group(
            python_command(
                "import signal,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);"
                "print('ignoring term',flush=True);time.sleep(60)"
            ),
            cwd=ROOT,
            task_id="hung-child",
            log_path=root / "hung.log",
            progress_path=root / "hung.jsonl",
            timeout_seconds=0.3,
            terminate_grace_seconds=0.1,
            kill_grace_seconds=1,
            heartbeat_seconds=0.05,
        )
        require(ignore_term.timed_out, "hung child did not time out")
        require(any(item.get("signal") == "SIGKILL" and item.get("sent") for item in ignore_term.termination), "hung child did not escalate to KILL")
        cases["hung_child"] = "PASS"

        status_dir = root / "status"
        bridge.persist_status(
            {
                "job_id": "fixture-task",
                "status": "running",
                "stage": "news_acquisition",
                "started_at": "2026-08-21T14:44:16+08:00",
                "last_heartbeat_at": "2026-08-21T14:44:21+08:00",
                "pid": 123,
                "pgid": 123,
                "failure_class": None,
            },
            status_dir,
        )
        before = time.monotonic()
        public = bridge.status_payload("fixture-task", status_dir)
        require(time.monotonic() - before < 0.2, "status endpoint contract blocked")
        require(public["stage"] == "news_acquisition" and public["status"] == "running", "status stage lost")
        require("updated_at" in public and public.get("pid") == public.get("pgid"), "safe runtime status fields missing")
        cases["status_responsiveness"] = "PASS"

        old_lock = bridge.ACTIVE_JOB_LOCK_PATH
        try:
            bridge.ACTIVE_JOB_LOCK_PATH = root / "active.json"
            bridge._write_active_job_lock("fixture-task")
            require(bridge.ACTIVE_JOB_LOCK_PATH.exists(), "active lock not persisted")
            require(not bridge._release_active_job_lock("other-task"), "foreign task released active lock")
            require(bridge._release_active_job_lock("fixture-task"), "owner failed to release active lock")
            require(not bridge.ACTIVE_JOB_LOCK_PATH.exists(), "active lock survived terminal cleanup")
        finally:
            bridge.ACTIVE_JOB_LOCK_PATH = old_lock
        cases["lock_release"] = "PASS"

        source = (ROOT / "app/runtime/manual_rerun_process_supervisor.py").read_text(encoding="utf-8")
        bridge_source = (ROOT / "scripts/orchestrator/manual_rerun_runtime_bridge.py").read_text(encoding="utf-8")
        require("start_new_session=True" in source and "os.killpg" in source, "process-group containment mutation detected")
        require("capture_output=True" not in bridge_source, "unbounded bridge capture_output regression detected")
        require("failure_class=\"runtime_timeout\"" in bridge_source, "terminal timeout classification missing")
        require("finally:" in bridge_source and "_release_active_job_lock" in bridge_source, "lock-finally mutation detected")
        cases["mutation_guards"] = "PASS"

    result = {
        "schema_version": "ai_dev_219_manual_rerun_process_timeout_validator_v1",
        "status": "PASS",
        "cases": cases,
        "case_count": len(cases),
        "production_rerun_executed": False,
        "notification_sent": False,
        "trading_or_order_executed": False,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
