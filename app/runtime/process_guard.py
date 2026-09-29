"""Best-effort read-only process inspection for scheduler runtime guards."""
from __future__ import annotations
import os, re, subprocess, time
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
    start_ticks: str | None = None
    owner_identity_valid: bool = False

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

REPO_ROOT = Path(__file__).resolve().parents[2]


def production_entrypoint(argv: list[str], cwd: str | None, ppid: int | None,
                          repo_root: Path = REPO_ROOT) -> str | None:
    """Match executable argv positions and repository identity, never payload text.

    Inline Python/shell source, grep, editors, browser workers and foreign repos
    cannot become batch owners merely by mentioning a production filename.
    Returned diagnostics contain only governed entrypoint names, not raw argv.
    """
    if not argv:
        return None
    executable = Path(argv[0]).name
    index = 0
    if re.fullmatch(r"python(?:[0-9]+(?:\.[0-9]+)*)?", executable):
        index = 1
        while index < len(argv) and argv[index].startswith("-"):
            option = argv[index]
            if option in {"-c", "-m", "-"} or option.startswith(("-c", "-m")):
                return None
            if option in {"-W", "-X"}:
                index += 2
            elif option in {"-u", "-B", "-E", "-I", "-s", "-S", "-O", "-OO"}:
                index += 1
            else:
                return None
        if index >= len(argv):
            return None
    elif executable in {"bash", "sh", "dash"}:
        index = 1
        if index < len(argv) and argv[index] == "--":
            index += 1
        if index >= len(argv) or argv[index].startswith("-"):
            return None
    elif executable != "run_stock_analysis.sh":
        return None
    script = Path(argv[index])
    if not script.is_absolute():
        if not cwd:
            return None
        script = Path(cwd) / script
    try:
        relative = script.resolve().relative_to(repo_root.resolve()).as_posix()
    except (OSError, ValueError):
        return None
    args = argv[index+1:]
    if relative == "run_stock_analysis.sh":
        return relative
    if not re.fullmatch(r"python(?:[0-9]+(?:\.[0-9]+)*)?", executable):
        return None
    if relative == "scripts/orchestrator/approved_pre_open_delivery.py":
        if "--dry-run" in args:
            return None
        windows = [a.split("=",1)[1] for a in args if a.startswith("--window=")]
        windows += [args[i+1] for i,a in enumerate(args[:-1]) if a == "--window"]
        if windows == ["pre_open_0700"]:
            return relative + " --window pre_open_0700"
    if relative == "scripts/run_pipeline.py" and args and args[0] == "pre_open" and "--production-approved" in args and "--dry-run" not in args:
        return relative + " pre_open --production-approved"
    if relative == "main.py" and ppid == 1:
        return relative
    return None


def _argv(pid: int) -> list[str]:
    try:
        return [v.decode(errors="replace") for v in Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0") if v]
    except OSError:
        return []


def _identity(pid: int) -> tuple[int, str, str] | None:
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")",1)[1].split()
        return int(fields[1]), fields[19], fields[0]
    except (OSError, ValueError, IndexError):
        return None


def list_candidate_pids() -> list[int]:
    candidates = []
    for path in Path("/proc").glob("[0-9]*"):
        pid = int(path.name)
        identity = _identity(pid)
        if identity is None or identity[2] == "Z":
            continue
        if production_entrypoint(_argv(pid), _readlink(f"/proc/{pid}/cwd"), identity[0]):
            candidates.append(pid)
    return sorted(candidates)

def inspect_process(pid: int, stale_threshold_seconds: int) -> ProcessInfo:
    before = _identity(pid)
    argv = _argv(pid)
    cwd = _readlink(f"/proc/{pid}/cwd")
    command = production_entrypoint(argv, cwd, before[0] if before else None) or ""
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
    after = _identity(pid)
    stable = before is not None and after is not None and before[1] == after[1] and after[2] != "Z"
    looks = bool(command and stable)
    return ProcessInfo(
        pid=pid,
        ppid=ppid,
        command=command,
        elapsed_seconds=elapsed,
        lstart=_ps_field(pid, "lstart"),
        stat=_ps_field(pid, "stat"),
        cwd=cwd,
        wchan=_read_text(f"/proc/{pid}/wchan"),
        fd_summary=fd_summary[:80],
        network_sockets=socket_lines[:80],
        attached_daily_log=attached_daily_log,
        attached_pipeline_artifact=attached_artifact,
        looks_like_pre_open_production=looks,
        stale=bool(looks and elapsed is not None and elapsed >= stale_threshold_seconds),
        start_ticks=before[1] if stable else None,
        owner_identity_valid=stable,
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
