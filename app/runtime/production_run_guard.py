"""Overlapping and stale production pre-open run guard."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from typing import Any
from .process_guard import ProcessInfo, inspect_pre_open_processes
from .runtime_diagnostics import build_guard_result
from .timeout_policy import TimeoutPolicy, timeout_policy_from_env

@dataclass(frozen=True)
class GuardDecision:
    allowed: bool
    status: str
    reason: str
    active_processes: list[dict[str, Any]]
    stale_processes: list[dict[str, Any]]
    auto_kill_performed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

def _ancestor_pids(pid: int) -> set[int]:
    import subprocess
    ancestors: set[int] = set()
    current = pid
    for _ in range(20):
        proc = subprocess.run(["ps", "-o", "ppid=", "-p", str(current)], text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False)
        try:
            parent = int(proc.stdout.strip())
        except Exception:
            break
        if parent <= 1 or parent in ancestors:
            break
        ancestors.add(parent)
        current = parent
    return ancestors

def evaluate_pre_open_run_guard(policy: TimeoutPolicy | None = None, current_pid: int | None = None) -> GuardDecision:
    import os
    policy = policy or timeout_policy_from_env()
    current_pid = current_pid or os.getpid()
    ignored = {current_pid} | _ancestor_pids(current_pid)
    inspected = [p for p in inspect_pre_open_processes(policy.stale_process_threshold_seconds) if p.pid not in ignored]
    pre_open = [p for p in inspected if p.looks_like_pre_open_production]
    stale = [p for p in pre_open if p.stale]
    active_non_stale = [p for p in pre_open if not p.stale]
    if stale:
        return GuardDecision(False, "stale_process_detected", "stale pre_open production process must be reviewed manually", [p.to_dict() for p in pre_open], [p.to_dict() for p in stale])
    if active_non_stale:
        return GuardDecision(False, "overlapping_run_blocked", "another pre_open production process is already active", [p.to_dict() for p in active_non_stale], [])
    return GuardDecision(True, "success", "no overlapping or stale pre_open production process detected", [], [])

def guard_result(window: str = "pre_open_0700", policy: TimeoutPolicy | None = None) -> dict[str, Any]:
    decision = evaluate_pre_open_run_guard(policy)
    if decision.allowed:
        return build_guard_result("success", window, policy, diagnostics={"guard_decision": decision.to_dict()})
    return build_guard_result(decision.status, window, policy, diagnostics={"guard_decision": decision.to_dict()})
