"""Read-only completeness health for all seven formal production windows."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from app.dashboard.market_dashboard_alias import payload_hash
from app.dashboard.window_snapshot_archive import resolve_snapshots

TAIPEI = ZoneInfo("Asia/Taipei")


@dataclass(frozen=True)
class WindowHealthSpec:
    market: str
    window: str
    scheduled_time: time
    runtime_path: str
    progress_path: str | None
    public_sync_path: str
    provenance_dir: str
    operations_path: str
    card_keys: tuple[str, ...]
    effective_date_offset: int = 0


WINDOW_SPECS = (
    WindowHealthSpec("TW", "pre_open_0700", time(7, 0), "artifacts/runtime/tw_window_decision/pre_open_0700_latest.json", "artifacts/runtime/delivery_progress_pre_open_0700_latest.json", "artifacts/runtime/public_latest_sync/tw_pre_open_0700_latest.json", "artifacts/runtime/delivery_provenance", "artifacts/runtime/operations_provenance/tw_pre_open_0700_latest.json", ("structured_pre_open_cards", "cards")),
    WindowHealthSpec("TW", "intraday_1305", time(13, 5), "artifacts/runtime/tw_window_decision/intraday_1305_latest.json", "artifacts/runtime/delivery_progress_intraday_1305_latest.json", "artifacts/runtime/public_latest_sync/tw_intraday_1305_latest.json", "artifacts/runtime/delivery_provenance", "artifacts/runtime/operations_provenance/tw_intraday_1305_latest.json", ("structured_intraday_cards", "cards")),
    WindowHealthSpec("TW", "pre_close_1335", time(13, 35), "artifacts/runtime/tw_window_decision/pre_close_1335_latest.json", "artifacts/runtime/delivery_progress_pre_close_1335_latest.json", "artifacts/runtime/public_latest_sync/tw_pre_close_1335_latest.json", "artifacts/runtime/delivery_provenance", "artifacts/runtime/operations_provenance/tw_pre_close_1335_latest.json", ("structured_pre_close_cards", "cards")),
    WindowHealthSpec("TW", "post_close_1500", time(15, 0), "artifacts/runtime/tw_window_decision/post_close_1500_latest.json", "artifacts/runtime/delivery_progress_prediction_review_1500_latest.json", "artifacts/runtime/public_latest_sync/tw_post_close_1500_latest.json", "artifacts/runtime/delivery_provenance", "artifacts/runtime/operations_provenance/tw_post_close_1500_latest.json", ("structured_review_cards", "cards")),
    WindowHealthSpec("US", "us_pre_market_2000", time(20, 0), "artifacts/runtime/us_stock/us_pre_market_2000_latest.json", None, "artifacts/runtime/us_stock/public_latest_sync/us_pre_market_2000_latest.json", "artifacts/runtime/us_stock/delivery_provenance", "artifacts/runtime/us_stock/operations_provenance/us_pre_market_2000_latest.json", ("structured_pre_market_cards", "items")),
    WindowHealthSpec("US", "us_intraday_2300", time(23, 0), "artifacts/runtime/us_stock/us_intraday_2300_latest.json", None, "artifacts/runtime/us_stock/public_latest_sync/us_intraday_2300_latest.json", "artifacts/runtime/us_stock/delivery_provenance", "artifacts/runtime/us_stock/operations_provenance/us_intraday_2300_latest.json", ("structured_intraday_cards", "cards")),
    WindowHealthSpec("US", "us_post_close_review_0630", time(6, 30), "artifacts/runtime/us_stock/us_post_close_review_0630_latest.json", None, "artifacts/runtime/us_stock/public_latest_sync/us_post_close_review_0630_latest.json", "artifacts/runtime/us_stock/delivery_provenance", "artifacts/runtime/us_stock/operations_provenance/us_post_close_review_0630_latest.json", ("structured_review_cards", "cards"), -1),
)


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _cards(runtime: dict[str, Any], keys: tuple[str, ...]) -> list[dict[str, Any]]:
    for key in keys:
        value = runtime.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def _identity(value: dict[str, Any]) -> tuple[Any, Any, Any]:
    observed = value.get("observed_identity") if isinstance(value.get("observed_identity"), dict) else value
    source_hash = observed.get("source_payload_hash") or observed.get("payload_hash")
    if not source_hash and isinstance(observed.get("payload"), dict):
        source_hash = payload_hash(observed["payload"])
    return (
        observed.get("snapshot_id") or observed.get("latest_admitted_snapshot_id"),
        observed.get("revision"),
        source_hash,
    )


def _runtime_date(runtime: dict[str, Any]) -> str:
    direct = runtime.get("effective_trading_date") or runtime.get("trading_date")
    if direct:
        return str(direct)
    session = runtime.get("session_context") if isinstance(runtime.get("session_context"), dict) else {}
    return str(session.get("session_date") or "")


def assess_window(
    spec: WindowHealthSpec,
    *,
    expected_trading_date: str,
    now: datetime,
    progress: dict[str, Any],
    runtime: dict[str, Any],
    snapshot: dict[str, Any],
    public_sync: dict[str, Any],
    email: dict[str, Any],
    line: dict[str, Any],
    operations: dict[str, Any],
    soft_grace_minutes: int = 5,
    hard_grace_minutes: int = 10,
) -> dict[str, Any]:
    scheduled = datetime.combine(now.date(), spec.scheduled_time, tzinfo=TAIPEI)
    soft_deadline = scheduled + timedelta(minutes=soft_grace_minutes)
    hard_deadline = scheduled + timedelta(minutes=hard_grace_minutes)
    cards = _cards(runtime, spec.card_keys)
    runtime_date = _runtime_date(runtime)
    archive_date = str(snapshot.get("effective_trading_date") or "")
    snapshot_identity = _identity(snapshot)
    sync_identity = _identity(public_sync)
    current_runtime = runtime_date == expected_trading_date
    current_snapshot = archive_date == expected_trading_date
    stages = {
        "scheduler": "PASS" if progress.get("started_at") or current_runtime else "MISSING",
        "pipeline": "FAIL" if progress.get("status") in {"failed", "timed_out"} else "PASS" if current_runtime else "MISSING",
        "research": "PASS" if cards and current_runtime else "MISSING",
        "canonical_decision": "PASS" if cards and current_runtime else "MISSING",
        "artifact_builder": "PASS" if current_runtime else "MISSING",
        "admission": "PASS" if snapshot.get("admitted") is True and current_snapshot else "MISSING",
        "archive": "PASS" if current_snapshot else "MISSING",
        "dashboard_publish": "PASS" if current_snapshot and public_sync.get("status") == "verified" and sync_identity == snapshot_identity and all(snapshot_identity) else "MISSING",
        "line_content": "PASS" if current_snapshot and _identity(line) == snapshot_identity and all(snapshot_identity) else "MISSING",
        "email_content": "PASS" if current_snapshot and _identity(email) == snapshot_identity and all(snapshot_identity) else "MISSING",
        "operations": "PASS" if current_snapshot and _identity(operations) == snapshot_identity and all(snapshot_identity) else "MISSING",
    }
    failed = [stage for stage, status in stages.items() if status == "FAIL"]
    missing = [stage for stage, status in stages.items() if status == "MISSING"]
    if now < scheduled:
        status = "not_due"
    elif failed:
        status = "failed"
    elif not missing:
        status = "healthy"
    elif now < soft_deadline:
        status = "running"
    elif now < hard_deadline:
        status = "warning"
    else:
        status = "missing_batch"
    return {
        "market": spec.market, "window": spec.window,
        "expected_trading_date": expected_trading_date,
        "scheduled_at": scheduled.isoformat(), "soft_deadline": soft_deadline.isoformat(),
        "hard_deadline": hard_deadline.isoformat(), "status": status,
        "stages": stages, "failed_stages": failed, "missing_stages": missing,
        "runtime_effective_date": runtime_date or None, "archive_effective_date": archive_date or None,
        "snapshot_id": snapshot.get("snapshot_id"), "revision": snapshot.get("revision"),
        "card_count": len(cards), "notification_delivery_required": False,
    }


def expected_date(run_date: date, offset: int) -> str:
    value = run_date + timedelta(days=offset)
    while value.weekday() >= 5:
        value -= timedelta(days=1)
    return value.isoformat()


def inspect_repository(root: Path, now: datetime | None = None) -> dict[str, Any]:
    observed = now or datetime.now(TAIPEI)
    archive_root = root / "artifacts/archive/window_snapshots"
    windows = []
    for spec in WINDOW_SPECS:
        snapshot = resolve_snapshots(archive_root, spec.market, spec.window).latest or {}
        prefix = f"tw_{spec.window}" if spec.market == "TW" else spec.window
        windows.append(assess_window(
            spec, expected_trading_date=expected_date(observed.date(), spec.effective_date_offset), now=observed,
            progress=load_json(root / spec.progress_path) if spec.progress_path else {},
            runtime=load_json(root / spec.runtime_path), snapshot=snapshot,
            public_sync=load_json(root / spec.public_sync_path),
            email=load_json(root / spec.provenance_dir / f"{prefix}_email_latest.json"),
            line=load_json(root / spec.provenance_dir / f"{prefix}_line_latest.json"),
            operations=load_json(root / spec.operations_path),
        ))
    due_failures = [item for item in windows if item["status"] in {"failed", "missing_batch"}]
    return {
        "schema_version": "seven_window_batch_completeness_health_v1",
        "observed_at": observed.isoformat(), "ok": not due_failures,
        "windows": windows, "due_failure_count": len(due_failures),
        "failure_windows": [f"{item['market']}:{item['window']}" for item in due_failures],
        "monitoring_policy": {"soft_grace_minutes": 5, "hard_grace_minutes": 10, "independent_monitor_required_for_scheduler_absence": True},
        "safety": {"read_only": True, "notification_sent": False, "production_pipeline_executed": False, "scheduler_changed": False, "trading": False, "secrets_accessed": False},
    }
