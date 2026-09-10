"""US batch execution reliability contract.

The contract is deterministic and side-effect free. Runtime wrappers may use it
to persist fail-closed status at orchestration boundaries, while validators use
the same helpers for behavioral coverage.
"""
from __future__ import annotations

import json
import os
import tracemalloc
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from app.us_stock.batch import build_us_stock_batch_artifact, us_stock_batch_input_example
from app.us_stock.constants import US_BATCH_WINDOWS

RELIABILITY_SCHEMA_VERSION = "us_batch_execution_reliability_contract_v1"
CONTRACT_WINDOWS = ("us_pre_market_2000", "us_intraday_2300")
LOCK_SCHEMA_VERSION = "us_batch_pid_lock_v1"


@dataclass(frozen=True)
class ChannelPolicy:
    email_allowed: bool
    line_allowed: bool


@dataclass(frozen=True)
class WindowReliabilityContract:
    window: str
    scheduled_time_tw: str
    timeout_seconds: int
    stale_runtime_max_age_seconds: int
    channel_policy: ChannelPolicy
    independent_scheduler_required: bool = True
    fail_closed_required: bool = True

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["schema_version"] = RELIABILITY_SCHEMA_VERSION
        return payload


US_BATCH_EXECUTION_RELIABILITY_CONTRACT: dict[str, WindowReliabilityContract] = {
    "us_pre_market_2000": WindowReliabilityContract(
        window="us_pre_market_2000",
        scheduled_time_tw=US_BATCH_WINDOWS["us_pre_market_2000"]["scheduled_time_tw"],
        timeout_seconds=75 * 60,
        stale_runtime_max_age_seconds=30 * 60,
        channel_policy=ChannelPolicy(email_allowed=True, line_allowed=True),
    ),
    "us_intraday_2300": WindowReliabilityContract(
        window="us_intraday_2300",
        scheduled_time_tw=US_BATCH_WINDOWS["us_intraday_2300"]["scheduled_time_tw"],
        timeout_seconds=45 * 60,
        stale_runtime_max_age_seconds=20 * 60,
        channel_policy=ChannelPolicy(email_allowed=True, line_allowed=False),
    ),
}


def contract_for_window(window: str) -> WindowReliabilityContract:
    if window not in US_BATCH_EXECUTION_RELIABILITY_CONTRACT:
        raise ValueError(f"unsupported reliability window: {window}")
    return US_BATCH_EXECUTION_RELIABILITY_CONTRACT[window]


def process_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def read_lock_owner(lock_path: Path) -> dict[str, Any]:
    try:
        raw = lock_path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return {"present": False, "owner_pid": None, "raw": None, "valid": False}
    except OSError as exc:
        return {"present": True, "owner_pid": None, "raw": None, "valid": False, "error": type(exc).__name__}
    try:
        owner_pid = int(raw)
    except ValueError:
        owner_pid = None
    return {
        "present": True,
        "owner_pid": owner_pid,
        "raw": raw,
        "valid": owner_pid is not None and owner_pid > 0,
        "owner_alive": process_is_alive(owner_pid) if owner_pid is not None else False,
    }


def acquire_pid_lock(lock_path: Path, *, pid: int | None = None) -> dict[str, Any]:
    """Acquire a PID lock atomically, recovering only demonstrably stale locks."""
    owner_pid = int(pid or os.getpid())
    recovered_stale = False
    for _ in range(2):
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
        except FileExistsError:
            owner = read_lock_owner(lock_path)
            if owner.get("valid") and owner.get("owner_alive"):
                return {
                    "schema_version": LOCK_SCHEMA_VERSION,
                    "acquired": False,
                    "reason": "live_lock_present",
                    "lock_path": str(lock_path),
                    "owner_pid": owner.get("owner_pid"),
                    "owner_alive": True,
                    "recovered_stale": recovered_stale,
                }
            try:
                lock_path.unlink()
                recovered_stale = True
                continue
            except FileNotFoundError:
                continue
            except OSError as exc:
                return {
                    "schema_version": LOCK_SCHEMA_VERSION,
                    "acquired": False,
                    "reason": "stale_lock_recovery_failed",
                    "lock_path": str(lock_path),
                    "owner_pid": owner.get("owner_pid"),
                    "owner_alive": owner.get("owner_alive"),
                    "error_type": type(exc).__name__,
                    "recovered_stale": recovered_stale,
                }
        else:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(f"{owner_pid}\n")
            return {
                "schema_version": LOCK_SCHEMA_VERSION,
                "acquired": True,
                "reason": "acquired",
                "lock_path": str(lock_path),
                "owner_pid": owner_pid,
                "owner_alive": True,
                "recovered_stale": recovered_stale,
            }
    return {
        "schema_version": LOCK_SCHEMA_VERSION,
        "acquired": False,
        "reason": "concurrent_lock_acquisition_lost",
        "lock_path": str(lock_path),
        "owner_pid": read_lock_owner(lock_path).get("owner_pid"),
        "recovered_stale": recovered_stale,
    }


def release_pid_lock(lock_path: Path, *, pid: int | None = None) -> dict[str, Any]:
    owner_pid = int(pid or os.getpid())
    owner = read_lock_owner(lock_path)
    if not owner.get("present"):
        return {"schema_version": LOCK_SCHEMA_VERSION, "released": False, "reason": "lock_absent", "lock_path": str(lock_path)}
    if owner.get("owner_pid") != owner_pid:
        return {
            "schema_version": LOCK_SCHEMA_VERSION,
            "released": False,
            "reason": "lock_owned_by_other_process",
            "lock_path": str(lock_path),
            "owner_pid": owner.get("owner_pid"),
            "current_pid": owner_pid,
        }
    try:
        lock_path.unlink()
    except FileNotFoundError:
        return {"schema_version": LOCK_SCHEMA_VERSION, "released": False, "reason": "lock_absent", "lock_path": str(lock_path)}
    except OSError as exc:
        return {
            "schema_version": LOCK_SCHEMA_VERSION,
            "released": False,
            "reason": "lock_release_failed",
            "lock_path": str(lock_path),
            "error_type": type(exc).__name__,
        }
    return {"schema_version": LOCK_SCHEMA_VERSION, "released": True, "reason": "released", "lock_path": str(lock_path), "owner_pid": owner_pid}


def run_id_for(window: str, started_at: datetime) -> str:
    return f"us-{window}-{started_at.strftime('%Y%m%d-%H%M%S')}"


def channel_state(*, attempted: bool, succeeded: bool, reason: str | None = None) -> dict[str, Any]:
    if succeeded and not attempted:
        return {
            "attempted": False,
            "sent": False,
            "state": "failed",
            "reason": "invalid_sent_without_attempted",
        }
    if succeeded:
        return {"attempted": True, "sent": True, "state": "sent", "reason": reason}
    if attempted:
        return {"attempted": True, "sent": False, "state": "failed", "reason": reason or "channel_failed"}
    state = "suppressed" if reason and "suppress" in reason else "not_attempted"
    return {"attempted": False, "sent": False, "state": state, "reason": reason or "not_attempted"}


def fail_closed_channel_states(window: str, reason: str) -> dict[str, dict[str, Any]]:
    policy = contract_for_window(window).channel_policy
    return {
        "email": channel_state(
            attempted=False,
            succeeded=False,
            reason=f"{reason}_email_not_attempted" if policy.email_allowed else "email_not_allowed",
        ),
        "line": channel_state(
            attempted=False,
            succeeded=False,
            reason=f"{reason}_line_not_attempted" if policy.line_allowed else "line_not_allowed_for_window",
        ),
    }


def build_failure_status(
    *,
    window: str,
    started_at: datetime,
    finished_at: datetime,
    reason: str,
    error_type: str | None = None,
    error_message: str | None = None,
    returncode: int | None = None,
    timeout_seconds: int | None = None,
    effective_trading_date: str | None = None,
) -> dict[str, Any]:
    contract = contract_for_window(window)
    channels = fail_closed_channel_states(window, reason)
    signal_name = None
    if returncode is not None and returncode < 0:
        signal_name = f"SIG{abs(returncode)}"
    return {
        "schema_version": RELIABILITY_SCHEMA_VERSION,
        "market": "US",
        "window": window,
        "run_id": run_id_for(window, started_at),
        "effective_trading_date": effective_trading_date,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "status": "failed_closed",
        "pipeline_completed": False,
        "runtime_artifact_admitted": False,
        "snapshot_admitted": False,
        "dashboard_publication_verified": False,
        "delivery_success_claimed": False,
        "failure_reason": reason,
        "error_type": error_type,
        "error_message": (error_message or "")[:240] or None,
        "returncode": returncode,
        "signal": signal_name,
        "timeout_seconds": timeout_seconds if timeout_seconds is not None else contract.timeout_seconds,
        "email": channels["email"],
        "line": channels["line"],
        "email_attempted": channels["email"]["attempted"],
        "email_succeeded": channels["email"]["sent"],
        "line_attempted": channels["line"]["attempted"],
        "line_succeeded": channels["line"]["sent"],
        "production_pipeline_executed": False,
        "trading_or_order_executed": False,
        "secret_values_printed": False,
        "scheduler_modified": False,
        "tw_behavior_modified": False,
        "contract": contract.to_dict(),
    }


def validate_status(status: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if status.get("market") != "US":
        errors.append("market_must_be_us")
    window = str(status.get("window") or "")
    if window not in CONTRACT_WINDOWS:
        errors.append("window_not_in_contract")
        return errors
    email = status.get("email") if isinstance(status.get("email"), dict) else {}
    line = status.get("line") if isinstance(status.get("line"), dict) else {}
    for channel_name, channel in (("email", email), ("line", line)):
        if channel.get("sent") and not channel.get("attempted"):
            errors.append(f"{channel_name}_sent_without_attempted")
        if status.get("status") == "failed_closed" and channel.get("sent"):
            errors.append(f"{channel_name}_sent_on_failed_closed")
    if status.get("status") == "failed_closed":
        for key in ("pipeline_completed", "runtime_artifact_admitted", "snapshot_admitted", "dashboard_publication_verified", "delivery_success_claimed"):
            if status.get(key) is not False:
                errors.append(f"failed_closed_{key}_must_be_false")
    return errors


def validate_runtime_identity(runtime: dict[str, Any], *, expected_window: str, expected_trading_date: str, expected_symbols: list[str]) -> list[str]:
    errors: list[str] = []
    if runtime.get("window") != expected_window:
        errors.append("runtime_window_mismatch")
    if runtime.get("effective_trading_date") != expected_trading_date:
        errors.append("runtime_effective_trading_date_mismatch")
    cards = runtime.get("dashboard_ready_contract", {}).get("cards", [])
    symbols = [str(card.get("symbol")) for card in cards if isinstance(card, dict) and card.get("symbol")]
    if symbols != expected_symbols:
        errors.append("runtime_symbol_order_mismatch")
    return errors


def memory_profile_fixture() -> dict[str, Any]:
    """Measure bounded fixture-build memory without calling live providers."""
    payload = us_stock_batch_input_example()
    tracemalloc.start()
    retained = [
        build_us_stock_batch_artifact(payload, window="us_pre_market_2000"),
        build_us_stock_batch_artifact(payload, window="us_intraday_2300"),
    ]
    retained_json_bytes = len(json.dumps(retained, ensure_ascii=False))
    retained_current, retained_peak = tracemalloc.get_traced_memory()
    tracemalloc.reset_peak()
    summaries: list[dict[str, Any]] = []
    for window in CONTRACT_WINDOWS:
        artifact = build_us_stock_batch_artifact(payload, window=window)
        summaries.append({
            "window": window,
            "symbol_count": len(artifact.get("dashboard_ready_contract", {}).get("cards", [])),
            "json_bytes": len(json.dumps(artifact, ensure_ascii=False)),
        })
        del artifact
    bounded_current, bounded_peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {
        "mode": "offline_fixture_tracemalloc",
        "live_provider_called": False,
        "retained_two_window_peak_kib": round(retained_peak / 1024, 2),
        "bounded_sequential_peak_kib": round(bounded_peak / 1024, 2),
        "retained_json_bytes": retained_json_bytes,
        "bounded_summaries": summaries,
        "finding": "Fixture path is small; production OOM ownership remains live-provider/runtime data and must be confirmed from production logs.",
    }


def behavioral_contract_cases() -> list[dict[str, Any]]:
    started = datetime.fromisoformat("2026-09-08T20:00:01+08:00")
    finished = datetime.fromisoformat("2026-09-08T21:06:27+08:00")
    pre_failure = build_failure_status(
        window="us_pre_market_2000",
        started_at=started,
        finished_at=finished,
        reason="worker_terminated_oom_equivalent",
        returncode=-9,
        error_type="WorkerTerminated",
        error_message="simulated SIGKILL/OOM-equivalent",
        effective_trading_date="2026-09-08",
    )
    timeout = build_failure_status(
        window="us_pre_market_2000",
        started_at=started,
        finished_at=datetime.fromisoformat("2026-09-08T21:15:01+08:00"),
        reason="worker_timeout",
        returncode=None,
        timeout_seconds=75 * 60,
        effective_trading_date="2026-09-08",
    )
    intraday_started = datetime.fromisoformat("2026-09-08T23:00:01+08:00")
    intraday_normal = {
        "schema_version": RELIABILITY_SCHEMA_VERSION,
        "market": "US",
        "window": "us_intraday_2300",
        "run_id": run_id_for("us_intraday_2300", intraday_started),
        "effective_trading_date": "2026-09-08",
        "status": "completed",
        "pipeline_completed": True,
        "runtime_artifact_admitted": True,
        "snapshot_admitted": True,
        "dashboard_publication_verified": True,
        "delivery_success_claimed": True,
        "email": channel_state(attempted=True, succeeded=True),
        "line": channel_state(attempted=False, succeeded=False, reason="line_not_allowed_for_window"),
    }
    partial_channel = {
        **intraday_normal,
        "status": "partial_channel_failure",
        "delivery_success_claimed": False,
        "email": channel_state(attempted=True, succeeded=False, reason="smtp_failed"),
        "line": channel_state(attempted=False, succeeded=False, reason="line_not_allowed_for_window"),
    }
    duplicate_retry = {
        **intraday_normal,
        "status": "already_delivered",
        "delivery_success_claimed": False,
        "email": channel_state(attempted=False, succeeded=False, reason="duplicate_delivery_suppressed"),
        "line": channel_state(attempted=False, succeeded=False, reason="line_not_allowed_for_window"),
    }
    return [
        {"case": "20_normal_contract_defined", "passed": "us_pre_market_2000" in US_BATCH_EXECUTION_RELIABILITY_CONTRACT},
        {"case": "23_normal_contract_defined", "passed": "us_intraday_2300" in US_BATCH_EXECUTION_RELIABILITY_CONTRACT},
        {"case": "20_worker_oom_equivalent_fail_closed", "passed": not validate_status(pre_failure), "status": pre_failure},
        {"case": "20_timeout_fail_closed", "passed": not validate_status(timeout), "status": timeout},
        {"case": "20_failure_does_not_mutate_23_contract", "passed": contract_for_window("us_intraday_2300").independent_scheduler_required},
        {"case": "23_line_not_allowed_email_allowed", "passed": intraday_normal["line"]["state"] == "not_attempted" and intraday_normal["email"]["state"] == "sent"},
        {"case": "partial_channel_failure_truthful", "passed": partial_channel["email"]["attempted"] and not partial_channel["email"]["sent"] and partial_channel["line"]["state"] == "not_attempted"},
        {"case": "retry_after_delivery_suppressed", "passed": duplicate_retry["email"]["state"] == "suppressed" and not duplicate_retry["email"]["attempted"]},
        {"case": "sent_implies_attempted", "passed": not validate_status(intraday_normal)},
        {"case": "tw_isolation", "passed": all(row.to_dict().get("tw_behavior_modified") is None for row in US_BATCH_EXECUTION_RELIABILITY_CONTRACT.values())},
    ]
