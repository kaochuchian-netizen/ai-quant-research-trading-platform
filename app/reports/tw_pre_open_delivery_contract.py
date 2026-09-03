"""Fail-closed TW 07:00 snapshot-to-dashboard-to-notification contract."""
from __future__ import annotations

from typing import Any, Callable

from app.dashboard.market_dashboard_alias import snapshot_parity_contract


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
    errors: list[str] = []

    if runtime.get("market") != "TW" or runtime.get("window") != "pre_open_0700":
        errors.append("runtime_market_window")
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
        try:
            results[channel] = sender(snapshot)
        except Exception as exc:  # runtime transport failures remain sanitized
            results[channel] = {
                "send_attempted": True,
                "send_status": "failed",
                "error_type": exc.__class__.__name__,
                "secret_values_printed": False,
            }
    return results
