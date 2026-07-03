"""Runtime diagnostic artifact builders for production scheduler guards."""
from __future__ import annotations
import json, subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from .process_guard import ProcessInfo, inspect_pre_open_processes
from .timeout_policy import TimeoutPolicy, timeout_policy_from_env

SCHEMA_VERSION = "production_pipeline_guard_v1"
STATUSES = {"success", "failed", "timed_out", "stale_process_detected", "overlapping_run_blocked", "no_fresh_artifact", "unknown"}

def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def file_state(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {"path": str(p), "exists": False, "size_bytes": None, "mtime": None, "is_zero_bytes": None}
    st = p.stat()
    return {"path": str(p), "exists": True, "size_bytes": st.st_size, "mtime": datetime.fromtimestamp(st.st_mtime, timezone.utc).replace(microsecond=0).isoformat(), "is_zero_bytes": st.st_size == 0}

def cron_evidence() -> list[str]:
    proc = subprocess.run(["journalctl", "-u", "cron", "--since", "today", "--no-pager"], text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False)
    return [line for line in proc.stdout.splitlines() if "run_stock_analysis.sh" in line][-20:]

def safety_summary() -> dict[str, bool]:
    return {
        "broker_login": False,
        "simulation_order": False,
        "production_order": False,
        "line_send": False,
        "email_send": False,
        "dashboard_production_publish": False,
        "var_www_dashboard_write": False,
        "scheduler_time_change": False,
        "cron_systemd_timer_mutation": False,
        "production_db_write": False,
        "secrets_read": False,
        "production_pipeline_run": False,
        "python3_main_py": False,
        "trading_execution": False,
        "production_publish_allowed": False,
        "stale_process_auto_kill": False,
    }

def build_guard_result(status: str, window: str, policy: TimeoutPolicy | None = None, **kwargs: Any) -> dict[str, Any]:
    policy = policy or timeout_policy_from_env()
    result = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now(),
        "window": window,
        "pipeline_command": kwargs.get("pipeline_command"),
        "pipeline_pid": kwargs.get("pipeline_pid"),
        "started_at": kwargs.get("started_at"),
        "ended_at": kwargs.get("ended_at"),
        "elapsed_seconds": kwargs.get("elapsed_seconds"),
        "status": status if status in STATUSES else "unknown",
        "timeout_seconds": kwargs.get("timeout_seconds", policy.production_pipeline_timeout_seconds),
        "timed_out": status == "timed_out",
        "return_code": kwargs.get("return_code"),
        "stdout_path": kwargs.get("stdout_path"),
        "stderr_path": kwargs.get("stderr_path"),
        "log_path": kwargs.get("log_path", "logs/daily.log"),
        "fresh_artifact_found": bool(kwargs.get("fresh_artifact_found", False)),
        "line_attempted": bool(kwargs.get("line_attempted", False)),
        "email_attempted": bool(kwargs.get("email_attempted", False)),
        "dashboard_attempted": bool(kwargs.get("dashboard_attempted", False)),
        "delivery_attempted": bool(kwargs.get("delivery_attempted", False)),
        "operator_action_required": status in {"timed_out", "stale_process_detected", "overlapping_run_blocked", "no_fresh_artifact", "unknown", "failed"},
        "diagnostics": kwargs.get("diagnostics", {}),
        "safety_summary": safety_summary(),
        "ok": status == "success",
    }
    return result

def build_runtime_diagnostics(window: str = "pre_open_0700", repo_root: Path | None = None, policy: TimeoutPolicy | None = None) -> dict[str, Any]:
    repo_root = repo_root or Path.cwd()
    policy = policy or timeout_policy_from_env()
    processes = [p.to_dict() for p in inspect_pre_open_processes(policy.stale_process_threshold_seconds)]
    stale = [p for p in processes if p.get("stale")]
    active = [p for p in processes if p.get("looks_like_pre_open_production")]
    log_path = repo_root / "logs" / "daily.log"
    approved_path = Path(f"/tmp/approved_{window}_delivery_result.json")
    manifest_path = Path("/var/www/stock-ai-dashboard/publish_manifest.json")
    zero_byte = file_state(log_path).get("is_zero_bytes") is True
    recommended = "no_action_required"
    if stale:
        recommended = "manual_review_and_TERM_stale_processes"
    elif active:
        recommended = "wait_or_review_active_pre_open_process"
    elif zero_byte:
        recommended = "review_zero_byte_scheduler_log"
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now(),
        "mode": "read_only_diagnostics",
        "window": window,
        "active_pre_open_processes": active,
        "stale_process_candidates": stale,
        "approved_delivery_result": file_state(approved_path),
        "daily_log": file_state(log_path),
        "dashboard_manifest": file_state(manifest_path),
        "cron_evidence": cron_evidence(),
        "warnings": (["logs/daily.log is zero bytes"] if zero_byte else []) + (["stale pre_open process candidates found"] if stale else []),
        "recommended_operator_action": recommended,
        "safety_summary": safety_summary(),
        "side_effects": {"read_only": True, "process_killed": False, "line_sent": False, "email_sent": False, "dashboard_published": False, "production_pipeline_run": False, "secrets_read": False},
        "ok": True,
    }

def write_json(path: str | Path, payload: dict[str, Any]) -> None:
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
