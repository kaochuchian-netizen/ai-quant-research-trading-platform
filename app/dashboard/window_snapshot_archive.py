"""Immutable window snapshot archive schema and resolver."""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from app.us_stock.runtime_provenance import ADMITTED_PROVENANCE, provenance_admission

SCHEMA_VERSION = "window_snapshot_archive_v1"
MARKET_WINDOWS = {
    "TW": ("pre_open_0700", "intraday_1305", "pre_close_1335", "post_close_1500"),
    "US": ("us_pre_market_2000", "us_intraday_2300", "us_post_close_review_0630"),
}
REJECTED_RUN_KINDS = {"fixture", "validator", "test", "failed", "incomplete"}


@dataclass(frozen=True)
class SnapshotSelection:
    market: str
    window: str
    latest: dict[str, Any] | None
    previous: dict[str, Any] | None


def canonical_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
    """Return the immutable renderer payload, detached from mutable runtime files."""
    return json.loads(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def snapshot_id(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def admission_errors(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    market = payload.get("market")
    window = payload.get("window") or payload.get("scheduler_window")
    trading_date = payload.get("effective_trading_date")
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append("schema_version")
    if market not in MARKET_WINDOWS:
        errors.append("market")
    elif window not in MARKET_WINDOWS[market]:
        errors.append("window")
    try:
        date.fromisoformat(str(trading_date))
    except ValueError:
        errors.append("effective_trading_date")
    if payload.get("status") not in {"complete", "success"}:
        errors.append("status")
    if payload.get("run_kind") in REJECTED_RUN_KINDS or payload.get("is_fixture") is True:
        errors.append("run_kind")
    if not isinstance(payload.get("payload"), dict):
        errors.append("payload")
    if not payload.get("generated_at"):
        errors.append("generated_at")
    provenance = provenance_admission(payload.get("payload"), run_kind=str(payload.get("run_kind") or ""))
    recorded_provenance = str(payload.get("runtime_provenance") or provenance["runtime_provenance"])
    recorded_admitted = payload.get("admitted", provenance["admitted"])
    if (
        provenance["admitted"] is not True
        or recorded_admitted is not True
        or recorded_provenance not in ADMITTED_PROVENANCE
        or recorded_provenance != provenance["runtime_provenance"]
    ):
        errors.append("runtime_provenance")
    return errors


def _normalized_admission_metadata(item: dict[str, Any]) -> dict[str, Any]:
    normalized = canonical_snapshot(item)
    decision = provenance_admission(normalized.get("payload"), run_kind=str(normalized.get("run_kind") or ""))
    normalized.setdefault("runtime_provenance", decision["runtime_provenance"])
    normalized.setdefault("admission_reason", decision["admission_reason"])
    normalized.setdefault("admitted", decision["admitted"])
    return normalized


def load_admitted_snapshots(archive_root: Path) -> list[dict[str, Any]]:
    admitted: list[dict[str, Any]] = []
    if not archive_root.exists():
        return admitted
    for path in sorted(archive_root.rglob("*.json")):
        try:
            item = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(item, dict):
            continue
        item = _normalized_admission_metadata(item)
        if admission_errors(item):
            continue
        item["snapshot_id"] = item.get("snapshot_id") or snapshot_id(item)
        item["archive_path"] = str(path)
        admitted.append(item)
    return admitted


def resolve_snapshots(archive_root: Path, market: str, window: str) -> SnapshotSelection:
    candidates = [
        item for item in load_admitted_snapshots(archive_root)
        if item.get("market") == market and (item.get("window") or item.get("scheduler_window")) == window
    ]
    by_date: dict[str, dict[str, Any]] = {}
    for item in candidates:
        trading_date = str(item["effective_trading_date"])
        rank = (int(item.get("revision") or 0), str(item.get("generated_at") or ""), str(item["snapshot_id"]))
        current = by_date.get(trading_date)
        current_rank = (-1, "", "") if current is None else (
            int(current.get("revision") or 0), str(current.get("generated_at") or ""), str(current["snapshot_id"])
        )
        if rank > current_rank:
            by_date[trading_date] = item
    dates = sorted(by_date, reverse=True)
    return SnapshotSelection(
        market=market,
        window=window,
        latest=by_date[dates[0]] if dates else None,
        previous=by_date[dates[1]] if len(dates) > 1 else None,
    )


def revisions_for_snapshot(archive_root: Path, market: str, window: str, effective_trading_date: str) -> list[dict[str, Any]]:
    return sorted(
        [item for item in load_admitted_snapshots(archive_root)
         if item.get("market") == market
         and (item.get("window") or item.get("scheduler_window")) == window
         and item.get("effective_trading_date") == effective_trading_date],
        key=lambda item: (int(item.get("revision") or 0), str(item.get("revision_created_at") or item.get("generated_at") or "")),
    )


def same_window_change(current: dict[str, Any] | None, previous: dict[str, Any] | None) -> dict[str, Any]:
    if not current or not previous:
        return {"available": False, "empty_state": "尚無同市場、同時段、不同有效交易日的 previous snapshot。", "changes": []}
    left = current.get("payload", {})
    right = previous.get("payload", {})
    keys = sorted(set(left) | set(right))
    changes = [{"field": key, "previous": right.get(key), "current": left.get(key)} for key in keys if left.get(key) != right.get(key)]
    return {"available": True, "previous_trading_date": previous["effective_trading_date"], "current_trading_date": current["effective_trading_date"], "changes": changes}


def _source_is_admissible(source: dict[str, Any], status: str, run_kind: str) -> bool:
    rejected_flags = ("fixture", "is_fixture", "validation_only", "validator", "incomplete")
    mode = " ".join(str(source.get(key) or "") for key in ("artifact_type", "artifact_mode", "runtime_mode", "data_source_mode", "run_kind")).lower()
    decision = provenance_admission(source, run_kind=run_kind)
    return (
        status in {"complete", "completed", "success"}
        and not any(source.get(key) is True for key in rejected_flags)
        and not any(token in mode for token in REJECTED_RUN_KINDS)
        and decision["runtime_provenance"] not in {"fixture", "validator", "preview", "dry_run", "controlled_no_send", "unclassified"}
    )


def write_snapshot(
    archive_root: Path,
    *,
    market: str,
    window: str,
    effective_trading_date: str,
    generated_at: str,
    source_payload: dict[str, Any],
    status: str,
    run_kind: str = "scheduled",
    run_id: str | None = None,
    source_artifact_path: str | None = None,
    rebuild_routes: bool = False,
    effective_batch_time: str | None = None,
) -> dict[str, Any]:
    """Admit and atomically write one immutable snapshot; never infers batch date from wall clock."""
    canonical_window = "post_close_1500" if market == "TW" and window == "prediction_review_1500" else window
    if market not in MARKET_WINDOWS or canonical_window not in MARKET_WINDOWS[market]:
        return {"written": False, "reason": "unsupported_market_window"}
    try:
        date.fromisoformat(effective_trading_date)
    except ValueError:
        return {"written": False, "reason": "invalid_effective_trading_date"}
    if run_kind not in {"scheduled", "manual_rerun", "backfill"}:
        return {"written": False, "reason": "rejected_run_kind"}
    if market == "TW" and canonical_window == "pre_open_0700" and (
        int(source_payload.get("tracking_stock_count") or 0) > 0
        or "structured_pre_open_cards" in source_payload
    ):
        from app.reports.tw_pre_open_structured import validate_payload

        structured_errors = validate_payload(source_payload)
        if structured_errors:
            return {
                "written": False,
                "reason": "structured_pre_open_payload_invalid",
                "validation_errors": structured_errors,
            }
    if market == "TW" and canonical_window in {"intraday_1305", "pre_close_1335", "post_close_1500"} and (
        isinstance(source_payload.get("tw_window_summary"), dict)
        or any(
            card.get("schema_version") == "tw_four_window_decision_closure_v1"
            for key in ("structured_intraday_cards", "structured_pre_close_cards", "structured_review_cards")
            for card in (source_payload.get(key) if isinstance(source_payload.get(key), list) else [])
            if isinstance(card, dict)
        )
    ):
        from app.reports.tw_four_window_decision import validate_payload as validate_tw_four_window_payload

        structured_errors = validate_tw_four_window_payload(canonical_window, source_payload)
        if structured_errors:
            reason_by_error = {
                "all_observed_market_data_unavailable": "tw_observed_market_data_all_unavailable",
                "all_pre_close_proximity_unavailable": "tw_pre_close_proximity_all_unavailable",
                "all_post_close_actual_ohlc_unavailable": "tw_post_close_actual_ohlc_all_unavailable",
            }
            reason = next((reason_by_error[item] for item in structured_errors if item in reason_by_error), "tw_four_window_structured_payload_invalid")
            return {"written": False, "reason": reason, "validation_errors": structured_errors}
    if market == "US" and canonical_window == "us_intraday_2300" and (
        "structured_intraday_cards" in source_payload
        or source_payload.get("schema_version") == "us_intraday_observed_market_v1"
    ):
        from app.us_stock.intraday_observed import validate_intraday_payload

        structured_errors = validate_intraday_payload(source_payload)
        if structured_errors:
            reason = (
                "intraday_market_data_all_unavailable"
                if "all_intraday_market_data_unavailable" in structured_errors
                else "structured_intraday_payload_invalid"
            )
            return {"written": False, "reason": reason, "validation_errors": structured_errors}
    if not _source_is_admissible(source_payload, status, run_kind):
        return {"written": False, "reason": "source_not_admissible"}
    existing = [
        item for item in load_admitted_snapshots(archive_root)
        if item.get("market") == market
        and (item.get("window") or item.get("scheduler_window")) == canonical_window
        and item.get("effective_trading_date") == effective_trading_date
    ]
    revision = max([int(item.get("revision") or 0) for item in existing] or [0]) + 1
    original_batch_time = min(
        [str(item.get("original_batch_time") or item.get("generated_at")) for item in existing if item.get("original_batch_time") or item.get("generated_at")]
        or [effective_batch_time or generated_at]
    )
    source_for_admission = canonical_snapshot(source_payload)
    if run_kind == "manual_rerun":
        source_for_admission["runtime_provenance"] = "manual_rerun"
    elif not source_for_admission.get("runtime_provenance"):
        source_for_admission["runtime_provenance"] = "scheduled_production"
    admission = provenance_admission(source_for_admission, run_kind=run_kind)
    snapshot = {
        "schema_version": SCHEMA_VERSION,
        "market": market,
        "window": canonical_window,
        "effective_trading_date": effective_trading_date,
        "generated_at": generated_at,
        "revision": revision,
        "manual_rerun": run_kind == "manual_rerun",
        "batch_window": canonical_window,
        "revision_created_at": generated_at,
        "original_batch_time": original_batch_time,
        "is_latest_revision": True,
        "status": "complete",
        "run_kind": run_kind,
        "runtime_provenance": admission["runtime_provenance"],
        "admission_reason": admission["admission_reason"],
        "admitted": admission["admitted"],
        "run_id": run_id,
        "source_artifact_path": source_artifact_path,
        "effective_batch_time_policy": "explicit_batch_reference_not_write_time",
        "payload": source_for_admission,
    }
    snapshot["snapshot_id"] = snapshot_id(snapshot)
    errors = admission_errors(snapshot)
    if errors:
        return {"written": False, "reason": "admission_failed", "errors": errors}
    target = archive_root / market.lower() / canonical_window / effective_trading_date / f"revision-{revision:04d}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(f".tmp-{os.getpid()}")
    temporary.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(target)
    if rebuild_routes:
        from app.dashboard.multi_market_dashboard import publish_manual_rerun_update
        publish_result = publish_manual_rerun_update(market, canonical_window)
    else:
        publish_result = None
    return {"written": True, "path": str(target), "snapshot_id": snapshot["snapshot_id"], "revision": revision, "market": market, "window": canonical_window, "effective_trading_date": effective_trading_date, "routes_rebuilt": rebuild_routes, "publish_result": publish_result}
