"""Fail-closed TW 07:00 snapshot-to-dashboard-to-notification contract."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from app.dashboard.market_dashboard_alias import snapshot_parity_contract

ACCEPTABLE_UNIVERSE_STATES = {"READY"}
CHANNEL_RECEIPT_SCHEMA_VERSION = "tw_preopen_channel_receipt_v1"


def universe_eligibility(runtime: dict[str, Any]) -> dict[str, Any]:
    """Classify the live watchlist evidence; internal symbol parity is not freshness."""
    evidence = runtime.get("stock_universe_evidence")
    if not isinstance(evidence, dict):
        return {"state": "UNKNOWN", "eligible": False, "reason": "stock_universe_evidence_missing"}
    source_status = str(evidence.get("source_status") or "UNKNOWN").upper()
    drift = str(evidence.get("symbol_drift_status") or "UNKNOWN").upper()
    fallback = bool(evidence.get("fallback_used"))
    fallback_age = evidence.get("fallback_snapshot_age")
    if drift == "DRIFT_DETECTED" or evidence.get("missing_symbols") or evidence.get("extra_symbols"):
        state, reason = "DRIFT_DETECTED", "watchlist_symbol_drift"
    elif drift in {"UNKNOWN", "NOT_EVALUATED", ""}:
        state, reason = "UNKNOWN", "watchlist_drift_unknown"
    elif fallback:
        state, reason = "DEGRADED_STALE_FALLBACK", "watchlist_fallback_not_authoritative"
    elif source_status not in {"READY", "LIVE_GOOGLE_SHEET_SUCCESS"}:
        state, reason = "UNKNOWN", "watchlist_source_not_authoritative"
    else:
        state, reason = "READY", None
    return {
        "state": state,
        "eligible": state in ACCEPTABLE_UNIVERSE_STATES,
        "reason": reason,
        "source_status": source_status,
        "fallback_used": fallback,
        "fallback_snapshot_age": fallback_age,
        "symbol_drift_status": drift,
    }


def delivery_identity(snapshot: dict[str, Any], channel: str) -> dict[str, Any]:
    identity = snapshot_parity_contract(snapshot)
    if channel not in {"email", "line"} or not identity:
        raise ValueError("invalid_delivery_identity")
    return {
        "market": "TW", "window": "pre_open_0700",
        "effective_trading_date": snapshot.get("effective_trading_date"),
        "snapshot_id": identity["snapshot_id"], "revision": int(identity["revision"]),
        "payload_hash": identity["payload_hash"], "channel": channel,
    }


def _receipt_path(root: Path, identity: dict[str, Any]) -> Path:
    raw = json.dumps(identity, sort_keys=True, separators=(",", ":"))
    return root / (hashlib.sha256(raw.encode()).hexdigest() + ".json")


def _valid_sent_receipt(retained: Any, expected_identity: dict[str, Any]) -> bool:
    return (
        isinstance(retained, dict)
        and retained.get("schema_version") == CHANNEL_RECEIPT_SCHEMA_VERSION
        and retained.get("delivery_result") == "sent"
        and retained.get("send_attempted") is True
        and retained.get("identity") == expected_identity
    )


def _channel_delivery(channel: str, sender: Callable[[dict[str, Any]], dict[str, Any]], snapshot: dict[str, Any], receipt_root: Path | None) -> dict[str, Any]:
    identity = delivery_identity(snapshot, channel)
    path = _receipt_path(receipt_root, identity) if receipt_root else None
    if path and path.exists():
        try:
            retained = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return {"send_attempted": False, "send_status": "failed", "error_type": "InvalidDeliveryReceipt", "delivery_identity": identity, "secret_values_printed": False}
        if _valid_sent_receipt(retained, identity):
            return {"send_attempted": False, "send_status": "already_delivered", "delivery_identity": identity, "secret_values_printed": False}
        return {"send_attempted": False, "send_status": "failed", "error_type": "InvalidDeliveryReceipt", "delivery_identity": identity, "secret_values_printed": False}
    try:
        result = dict(sender(snapshot))
    except Exception as exc:
        result = {"send_attempted": True, "send_status": "failed", "error_type": exc.__class__.__name__, "secret_values_printed": False}
    if result.get("send_status") == "sent" and result.get("send_attempted") is not True:
        result = {"send_attempted": False, "send_status": "failed", "error_type": "InvalidTransportEvidence", "secret_values_printed": False}
    result["delivery_identity"] = identity
    if path and result.get("send_status") == "sent" and result.get("send_attempted") is True:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps({"schema_version": CHANNEL_RECEIPT_SCHEMA_VERSION, "delivery_result": "sent", "send_attempted": True, "identity": identity}, sort_keys=True) + "\n", encoding="utf-8")
        temporary.replace(path)
    return result


def _symbols(payload: dict[str, Any]) -> list[str]:
    return [str(value) for value in payload.get("tracking_symbols", [])]


def _card_symbols(payload: dict[str, Any]) -> list[str]:
    cards = payload.get("structured_pre_open_cards")
    if not isinstance(cards, list):
        return []
    return [str(card.get("symbol") or card.get("stock_id") or "") for card in cards if isinstance(card, dict)]


def evaluate_pre_open_delivery(
    *,
    runtime: dict[str, Any],
    archive_write: dict[str, Any],
    snapshot: dict[str, Any],
    public_sync: dict[str, Any],
    effective_trading_date: str,
) -> dict[str, Any]:
    """Verify one authoritative identity across generation, admission and publication."""
    payload = snapshot.get("payload") if isinstance(snapshot.get("payload"), dict) else {}
    selected = [str(value) for value in runtime.get("selected_symbols", runtime.get("tracking_symbols", []))]
    runtime_symbols = _symbols(runtime)
    runtime_cards = _card_symbols(runtime)
    snapshot_symbols = _symbols(payload)
    snapshot_cards = _card_symbols(payload)
    rendered_symbols = [str(value) for value in public_sync.get("rendered_symbols", [])]
    identity = snapshot_parity_contract(snapshot)
    universe = universe_eligibility(runtime)
    snapshot_universe = payload.get("stock_universe_evidence")
    errors: list[str] = []

    if runtime.get("market") != "TW" or runtime.get("window") != "pre_open_0700":
        errors.append("runtime_market_window")
    if not universe["eligible"]:
        errors.append("universe_" + universe["state"].lower())
    if snapshot_universe != runtime.get("stock_universe_evidence"):
        errors.append("snapshot_universe_evidence")
    if not selected or selected != runtime_symbols or runtime_symbols != runtime_cards:
        errors.append("runtime_symbol_identity")
    if archive_write.get("written") is not True:
        errors.append("snapshot_not_admitted")
    if not identity or identity.get("market") != "TW" or identity.get("active_window") != "pre_open_0700":
        errors.append("snapshot_identity_missing")
    if str(runtime.get("effective_trading_date") or "") != effective_trading_date:
        errors.append("runtime_trading_date")
    if str(snapshot.get("effective_trading_date") or "") != effective_trading_date:
        errors.append("snapshot_trading_date")
    if selected != snapshot_symbols or snapshot_symbols != snapshot_cards:
        errors.append("snapshot_symbol_identity")
    if public_sync.get("status") != "verified":
        errors.append("dashboard_parity_not_verified")
    if rendered_symbols != snapshot_symbols:
        errors.append("dashboard_symbol_identity")
    if identity:
        expected_sync = {
            "snapshot_id": identity["snapshot_id"],
            "revision": int(identity["revision"]),
            "source_payload_hash": identity["payload_hash"],
        }
        if any(str(public_sync.get(key)) != str(value) for key, value in expected_sync.items()):
            errors.append("dashboard_snapshot_identity")
        for key in ("snapshot_id", "revision"):
            if archive_write.get(key) is not None and str(archive_write.get(key)) != str(identity[key]):
                errors.append("archive_snapshot_identity")
                break

    return {
        "schema_version": "tw_pre_open_delivery_consistency_v1",
        "eligible": not errors,
        "errors": list(dict.fromkeys(errors)),
        "effective_trading_date": effective_trading_date,
        "selected_symbols": selected,
        "runtime_symbols": runtime_symbols,
        "snapshot_symbols": snapshot_symbols,
        "dashboard_symbols": rendered_symbols,
        "notification_symbols": snapshot_symbols if not errors else [],
        "snapshot_identity": identity or {},
        "universe_eligibility": universe,
    }


def deliver_admitted_pre_open_snapshot(
    *,
    runtime: dict[str, Any],
    archive_write: dict[str, Any],
    snapshot: dict[str, Any],
    public_sync: dict[str, Any],
    effective_trading_date: str,
    email_sender: Callable[[dict[str, Any]], dict[str, Any]],
    line_sender: Callable[[dict[str, Any]], dict[str, Any]],
    receipt_root: Path | None = None,
) -> dict[str, Any]:
    """Invoke channels only after the immutable/public consistency gate passes."""
    gate = evaluate_pre_open_delivery(
        runtime=runtime,
        archive_write=archive_write,
        snapshot=snapshot,
        public_sync=public_sync,
        effective_trading_date=effective_trading_date,
    )
    if not gate["eligible"]:
        suppressed = {
            "send_attempted": False,
            "send_status": "suppressed_delivery_consistency_failure",
            "reason": ",".join(gate["errors"]),
            "secret_values_printed": False,
        }
        return {"gate": gate, "email": dict(suppressed), "line": dict(suppressed)}
    results: dict[str, Any] = {"gate": gate}
    for channel, sender in (("email", email_sender), ("line", line_sender)):
        results[channel] = _channel_delivery(channel, sender, snapshot, receipt_root)
    return results
