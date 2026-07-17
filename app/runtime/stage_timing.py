"""Durable stage timing and failure evidence for production window runners."""
from __future__ import annotations

import json
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator
from zoneinfo import ZoneInfo

TAIPEI = ZoneInfo("Asia/Taipei")
FAILURE_CATEGORIES = {
    "scheduler_miss", "entrypoint_failure", "stage_timeout", "external_source_timeout",
    "pipeline_failure", "runtime_write_failure", "admission_rejected", "route_build_failure",
    "publish_failure", "public_verification_failure", "formatter_failure",
    "delivery_suppressed", "delivery_failure", "baseline_resolution_failure",
}


@dataclass(frozen=True)
class WindowRuntimeBudget:
    overall_hard_timeout_seconds: int
    stage_soft_timeout_seconds: int
    external_request_timeout_seconds: int
    max_retry_count: int
    retry_backoff_seconds: float
    heartbeat_interval_seconds: int


# Kept below the existing 600-second hard guard. Values are based on the
# observed 378-second nine-stock pre-open run and the former 15-second/source
# policy; they bound optional enrichment instead of extending the hard guard.
TW_INTRADAY_1305_BUDGET = WindowRuntimeBudget(
    overall_hard_timeout_seconds=600,
    stage_soft_timeout_seconds=90,
    external_request_timeout_seconds=12,
    max_retry_count=1,
    retry_backoff_seconds=0.5,
    heartbeat_interval_seconds=15,
)


def now_iso() -> str:
    return datetime.now(TAIPEI).replace(microsecond=0).isoformat()


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def record_stage_result(path: Path, stage: str, *, status: str, elapsed_seconds: float = 0.0, error_category: str | None = None, error_message_sanitized: str | None = None) -> None:
    """Append an approved-wrapper stage to an existing child timing artifact."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    timestamp = now_iso()
    payload.setdefault("stages", []).append({
        "stage": stage, "started_at": timestamp, "completed_at": timestamp,
        "elapsed_seconds": round(float(elapsed_seconds), 3), "status": status,
        "last_heartbeat_at": timestamp, "optional": False,
        "error_category": error_category, "error_message_sanitized": error_message_sanitized,
    })
    payload["last_heartbeat_at"] = timestamp
    payload["current_stage"] = stage
    _atomic_json(path, payload)


class StageTimingRecorder:
    def __init__(self, path: Path, *, market: str, window: str, run_id: str, budget: WindowRuntimeBudget) -> None:
        self.path = path
        self.payload: dict[str, Any] = {
            "schema_version": "production_stage_timing_v1",
            "market": market,
            "window": window,
            "run_id": run_id,
            "status": "running",
            "started_at": now_iso(),
            "completed_at": None,
            "last_heartbeat_at": now_iso(),
            "budget": asdict(budget),
            "stages": [],
            "failure": None,
        }
        self._persist()

    def _persist(self) -> None:
        self.payload["last_heartbeat_at"] = now_iso()
        _atomic_json(self.path, self.payload)

    def heartbeat(self, stage: str, detail: str | None = None) -> None:
        self.payload["current_stage"] = stage
        self.payload["heartbeat_detail"] = detail
        self._persist()

    @contextmanager
    def stage(self, name: str, *, optional: bool = False) -> Iterator[dict[str, Any]]:
        started_at = now_iso()
        started = time.monotonic()
        event: dict[str, Any] = {
            "stage": name, "started_at": started_at, "completed_at": None,
            "elapsed_seconds": None, "status": "running", "last_heartbeat_at": started_at,
            "optional": optional, "error_category": None, "error_message_sanitized": None,
        }
        self.payload["stages"].append(event)
        self.heartbeat(name)
        try:
            yield event
        except Exception as exc:
            event.update({
                "completed_at": now_iso(), "elapsed_seconds": round(time.monotonic() - started, 3),
                "status": "failed", "last_heartbeat_at": now_iso(),
                "error_category": "pipeline_failure",
                "error_message_sanitized": exc.__class__.__name__,
            })
            self._persist()
            raise
        else:
            event.update({
                "completed_at": now_iso(), "elapsed_seconds": round(time.monotonic() - started, 3),
                "status": "completed", "last_heartbeat_at": now_iso(),
            })
            self._persist()

    def fail(self, *, stage: str, category: str, reason: str, retry_count: int = 0) -> dict[str, Any]:
        if category not in FAILURE_CATEGORIES:
            category = "pipeline_failure"
        self.payload.update({
            "status": "failed", "completed_at": now_iso(),
            "failure": {
                "failure_category": category, "failure_stage": stage, "failure_time": now_iso(),
                "sanitized_reason": reason[:240], "retry_count": retry_count,
                "last_heartbeat": self.payload.get("last_heartbeat_at"),
                "runtime_persisted": False, "snapshot_admitted": False,
                "public_publish_attempted": False, "email_attempted": False, "line_attempted": False,
            },
        })
        self._persist()
        return self.payload

    def complete(self) -> dict[str, Any]:
        self.payload.update({"status": "completed", "completed_at": now_iso(), "current_stage": None})
        self._persist()
        return self.payload
