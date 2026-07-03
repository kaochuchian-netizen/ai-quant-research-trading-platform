"""Best-effort read-only process inspection for scheduler runtime guards."""
from __future__ import annotations
import os, subprocess, time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

PRE_OPEN_PATTERNS = (
    "run_stock_analysis.sh",
    "approved_pre_open_delivery.py --window pre_open_0700",
    "scripts/run_pipeline.py pre_open --production-approved",
    "main.py",
)

@dataclass(frozen=True)
class ProcessInfo:
    pid: int
    ppid: int | None
    command: str
    elapsed_seconds: int | None
    lstart: str | None
    stat: str | None
    cwd: str | None
    wchan: str | None
    fd_summary: list[str]
    network_sockets: list[str]
    attached_daily_log: bool
    attached_pipeline_artifact: bool
    looks_like_pre_open_production: bool
    stale: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

def _run(args: list[str]) -> str:
    proc = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False)
    return proc.stdout

def _cmdline(pid: int) -> str:
    try:
        return Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace").strip()
    except Exception:
        return ""

def _readlink(path: str) -> str | None:
    try:
        return os.readlink(path)
    except Exception:
        return None

def _read_text(path: str) -> str | None:
    try:
        return Path(path).read_text(errors="replace").strip()
    except Exception:
        return None

def _elapsed_seconds(pid: int) -> int | None:
    out = _run(["ps", "-o", "etimes=", "-p", str(pid)]).strip()
    try:
        return int(out)
    except Exception:
        return None

def _ps_field(pid: int, field: str) -> str | None:
    out = _run(["ps", "-o", f"{field}=", "-p", str(pid)]).strip()
    return out or None

def list_candidate_pids() -> list[int]:
    out = _run(["ps", "-eo", "pid=,args="])
    pids: list[int] = []
    for line in out.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        first, _, cmd = stripped.partition(" ")
        if any(pattern in cmd for pattern in PRE_OPEN_PATTERNS):
            try:
                pids.append(int(first))
            except Exception:
                pass
    return sorted(set(pids))

def inspect_process(pid: int, stale_threshold_seconds: int) -> ProcessInfo:
    command = _cmdline(pid) or (_ps_field(pid, "args") or "")
    ppid_text = _ps_field(pid, "ppid")
    try:
        ppid = int(ppid_text) if ppid_text else None
    except Exception:
        ppid = None
    fd_summary: list[str] = []
    attached_daily_log = False
    attached_artifact = False
    fd_dir = Path(f"/proc/{pid}/fd")
    if fd_dir.exists():
        for fd in sorted(fd_dir.iterdir(), key=lambda item: item.name):
            target = _readlink(str(fd))
            if not target:
                continue
            if "daily.log" in target:
                attached_daily_log = True
            if "/tmp/approved_" in target or "stock-ai-dashboard" in target:
                attached_artifact = True
            if any(token in target for token in ("daily.log", "/tmp/approved_", "stock-ai-dashboard", "socket:", "pipe:")):
                fd_summary.append(f"{fd.name}->{target}")
    socket_lines = [line for line in _run(["ss", "-tp"]).splitlines() if f"pid={pid}," in line]
    elapsed = _elapsed_seconds(pid)
    looks = (
        "approved_pre_open_delivery.py --window pre_open_0700" in command
        or "scripts/run_pipeline.py pre_open --production-approved" in command
        or "run_stock_analysis.sh" in command
        or ("main.py" in command and (ppid == 1 or ppid is None))
    )
    return ProcessInfo(
        pid=pid,
        ppid=ppid,
        command=command,
        elapsed_seconds=elapsed,
        lstart=_ps_field(pid, "lstart"),
        stat=_ps_field(pid, "stat"),
        cwd=_readlink(f"/proc/{pid}/cwd"),
        wchan=_read_text(f"/proc/{pid}/wchan"),
        fd_summary=fd_summary[:80],
        network_sockets=socket_lines[:80],
        attached_daily_log=attached_daily_log,
        attached_pipeline_artifact=attached_artifact,
        looks_like_pre_open_production=looks,
        stale=bool(looks and elapsed is not None and elapsed >= stale_threshold_seconds),
    )

def inspect_pre_open_processes(stale_threshold_seconds: int) -> list[ProcessInfo]:
    current = os.getpid()
    return [inspect_process(pid, stale_threshold_seconds) for pid in list_candidate_pids() if pid != current and Path(f"/proc/{pid}").exists()]

def terminate_process_tree(pid: int, grace_seconds: int = 10, kill_after_grace: bool = True) -> dict[str, Any]:
    children = []
    for line in _run(["pgrep", "-P", str(pid)]).splitlines():
        try:
            children.append(int(line.strip()))
        except Exception:
            pass
    targets = sorted(set(children + [pid]), reverse=True)
    actions = []
    for target in targets:
        try:
            os.kill(target, 15)
            actions.append({"pid": target, "signal": "TERM", "sent": True})
        except Exception as exc:
            actions.append({"pid": target, "signal": "TERM", "sent": False, "error_type": exc.__class__.__name__})
    deadline = time.time() + grace_seconds
    while time.time() < deadline and any(Path(f"/proc/{target}").exists() for target in targets):
        time.sleep(0.2)
    if kill_after_grace:
        for target in targets:
            if Path(f"/proc/{target}").exists():
                try:
                    os.kill(target, 9)
                    actions.append({"pid": target, "signal": "KILL", "sent": True})
                except Exception as exc:
                    actions.append({"pid": target, "signal": "KILL", "sent": False, "error_type": exc.__class__.__name__})
    return {"target_pid": pid, "actions": actions, "remaining": [target for target in targets if Path(f"/proc/{target}").exists()]}
