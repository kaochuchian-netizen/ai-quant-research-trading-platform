"""Bounded process-session supervisor used by the manual rerun bridge."""
from __future__ import annotations

import hashlib
import json
import os
import signal
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
from typing import Any, Callable

from app.runtime.manual_rerun_progress import CANONICAL_STAGES, PROGRESS_LOG_ENV


UpdateCallback = Callable[[dict[str, Any]], None]


@dataclass(frozen=True)
class ProcessResult:
    returncode: int
    timed_out: bool
    pid: int
    pgid: int
    elapsed_seconds: float
    termination: tuple[dict[str, Any], ...]
    log_path: str
    log_bytes: int
    log_truncated: bool
    stage: str
    stage_started_at: str | None
    stage_timings: dict[str, dict[str, Any]]


class _BoundedLogWriter:
    def __init__(self, source: Any, path: Path, max_bytes: int) -> None:
        self.source = source
        self.path = path
        self.max_bytes = max_bytes
        self.bytes_written = 0
        self.truncated = False

    def run(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("wb") as target:
            while True:
                chunk = self.source.read(65536)
                if not chunk:
                    break
                remaining = self.max_bytes - self.bytes_written
                if remaining > 0:
                    target.write(chunk[:remaining])
                    target.flush()
                    self.bytes_written += min(len(chunk), remaining)
                if len(chunk) > remaining:
                    self.truncated = True


def _read_progress(path: Path, offset: int, state: dict[str, Any]) -> int:
    if not path.exists():
        return offset
    with path.open("r", encoding="utf-8") as handle:
        handle.seek(offset)
        for line in handle:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            stage = str(event.get("stage") or "")
            status = str(event.get("status") or "started")
            at = event.get("at")
            if stage not in CANONICAL_STAGES:
                continue
            timing = state.setdefault("stage_timings", {}).setdefault(stage, {})
            if status == "started":
                timing.setdefault("started_at", at)
                timing["status"] = "running"
                state["stage"] = stage
                state["stage_started_at"] = timing.get("started_at")
            else:
                timing.setdefault("started_at", at)
                timing["finished_at"] = at
                timing["status"] = status
                try:
                    started_at = datetime.fromisoformat(str(timing["started_at"]))
                    finished_at = datetime.fromisoformat(str(at))
                    timing["elapsed_seconds"] = max((finished_at - started_at).total_seconds(), 0.0)
                except (TypeError, ValueError):
                    timing["elapsed_seconds"] = None
                if status == "completed" and stage == "completed":
                    state["stage"] = stage
                    state["stage_started_at"] = timing.get("started_at")
        return handle.tell()


def _group_alive(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _signal_group(pgid: int, sig: signal.Signals, termination: list[dict[str, Any]]) -> None:
    try:
        os.killpg(pgid, sig)
        termination.append({"pgid": pgid, "signal": sig.name, "sent": True})
    except ProcessLookupError:
        termination.append({"pgid": pgid, "signal": sig.name, "sent": False, "reason": "already_exited"})


def _wait_group_exit(pgid: int, seconds: float) -> bool:
    deadline = time.monotonic() + max(seconds, 0.0)
    while time.monotonic() < deadline:
        if not _group_alive(pgid):
            return True
        time.sleep(0.05)
    return not _group_alive(pgid)


def command_identity(command: list[str]) -> str:
    safe = " ".join(Path(part).name if index == 0 else part for index, part in enumerate(command))
    return hashlib.sha256(safe.encode("utf-8")).hexdigest()


def run_process_group(
    command: list[str],
    *,
    cwd: Path,
    task_id: str,
    log_path: Path,
    progress_path: Path,
    timeout_seconds: float,
    terminate_grace_seconds: float = 5.0,
    kill_grace_seconds: float = 5.0,
    heartbeat_seconds: float = 2.0,
    max_log_bytes: int = 2 * 1024 * 1024,
    update: UpdateCallback | None = None,
    extra_env: dict[str, str] | None = None,
) -> ProcessResult:
    started = time.monotonic()
    progress_path.parent.mkdir(parents=True, exist_ok=True)
    progress_path.unlink(missing_ok=True)
    env = dict(os.environ)
    env.update(extra_env or {})
    env[PROGRESS_LOG_ENV] = str(progress_path)
    env["PYTHONUNBUFFERED"] = "1"
    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        bufsize=0,
    )
    pgid = os.getpgid(process.pid)
    assert process.stdout is not None
    writer = _BoundedLogWriter(process.stdout, log_path, max_log_bytes)
    drain = threading.Thread(target=writer.run, name=f"manual-log-{task_id}", daemon=True)
    drain.start()
    state: dict[str, Any] = {
        "stage": "runtime_started",
        "stage_started_at": None,
        "stage_timings": {},
    }
    offset = 0
    termination: list[dict[str, Any]] = []
    timed_out = False
    last_heartbeat = 0.0
    if update:
        update({"pid": process.pid, "pgid": pgid, "runtime_command_identity": command_identity(command)})
    while process.poll() is None:
        now = time.monotonic()
        offset = _read_progress(progress_path, offset, state)
        if now - last_heartbeat >= heartbeat_seconds:
            if update:
                update({
                    "runtime_heartbeat": True,
                    "stage": state["stage"],
                    "stage_started_at": state["stage_started_at"],
                    "stage_timings": state["stage_timings"],
                })
            last_heartbeat = now
        if now - started >= timeout_seconds:
            timed_out = True
            _signal_group(pgid, signal.SIGTERM, termination)
            if not _wait_group_exit(pgid, terminate_grace_seconds):
                _signal_group(pgid, signal.SIGKILL, termination)
                _wait_group_exit(pgid, kill_grace_seconds)
            break
        time.sleep(min(0.1, max(heartbeat_seconds / 4.0, 0.02)))
    try:
        returncode = process.wait(timeout=max(kill_grace_seconds, 0.1))
    except subprocess.TimeoutExpired:
        _signal_group(pgid, signal.SIGKILL, termination)
        try:
            returncode = process.wait(timeout=max(kill_grace_seconds, 0.1))
        except subprocess.TimeoutExpired:
            returncode = -int(signal.SIGKILL)
    process.stdout.close()
    drain.join(timeout=max(kill_grace_seconds, 0.1))
    if drain.is_alive():
        writer.truncated = True
    _read_progress(progress_path, offset, state)
    elapsed = time.monotonic() - started
    return ProcessResult(
        returncode=returncode,
        timed_out=timed_out,
        pid=process.pid,
        pgid=pgid,
        elapsed_seconds=elapsed,
        termination=tuple(termination),
        log_path=str(log_path),
        log_bytes=writer.bytes_written,
        log_truncated=writer.truncated,
        stage=str(state["stage"]),
        stage_started_at=state.get("stage_started_at"),
        stage_timings=dict(state["stage_timings"]),
    )
