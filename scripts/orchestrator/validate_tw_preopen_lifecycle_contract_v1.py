#!/usr/bin/env python3
"""Durable TW_PREOPEN_LIFECYCLE_CONTRACT using fakes and temporary storage."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.dashboard.market_dashboard_alias import snapshot_parity_contract
from app.reports.delivery_provenance import build_delivery_provenance, transport_delivery_result
from app.reports.tw_pre_open_delivery_contract import deliver_admitted_pre_open_snapshot, universe_eligibility
from app.reports.tw_pre_open_structured import aggregate, seal_card_source_payload_hash, unavailable_card
from scripts.orchestrator import build_formal_prediction_runtime_artifact as forecast

SYMBOLS = ["2330", "009816", "2337", "2353", "6873", "4743", "2305", "00878", "1409", "3293"]


def card(symbol: str, unavailable: bool = False) -> dict:
    value = unavailable_card(symbol, "TEST-" + symbol, "2026-09-04", "historical_unavailable")
    if not unavailable:
        value.update({"availability_status": "partial", "entry_readiness": "watch", "opportunity_group": "watch", "action": "觀察"})
    return seal_card_source_payload_hash(value)


def fixture(*, evidence=None, dashboard=True, unavailable=()):
    cards = [card(s, s in unavailable) for s in SYMBOLS]
    evidence = evidence or {"source_status": "READY", "fallback_used": False, "symbol_drift_status": "NO_DRIFT", "missing_symbols": [], "extra_symbols": []}
    runtime = {"market": "TW", "window": "pre_open_0700", "effective_trading_date": "2026-09-04", "selected_symbols": SYMBOLS, "tracking_symbols": SYMBOLS, "structured_pre_open_cards": cards, "stock_universe_evidence": evidence}
    payload = {"market": "TW", "window": "pre_open_0700", "effective_trading_date": "2026-09-04", "selected_symbols": SYMBOLS, "tracking_symbols": SYMBOLS, "tracking_stock_count": 10, "structured_pre_open_cards": cards, "cards": cards, "structured_card_count": 10, "rendered_card_count": 10, "pre_open_summary": aggregate(cards, SYMBOLS), "stock_universe_evidence": evidence}
    snapshot = {"market": "TW", "window": "pre_open_0700", "effective_trading_date": "2026-09-04", "snapshot_id": "snap-234", "revision": 1, "payload": payload}
    identity = snapshot_parity_contract(snapshot)
    sync = {"status": "verified" if dashboard else "failed", "snapshot_id": identity["snapshot_id"], "revision": identity["revision"], "source_payload_hash": identity["payload_hash"], "rendered_symbols": SYMBOLS}
    return runtime, {"written": True, "snapshot_id": "snap-234", "revision": 1}, snapshot, sync


def deliver(root: Path, values, outcomes):
    runtime, archive, snapshot, sync = values
    calls = []
    def sender(channel):
        def invoke(_snapshot):
            calls.append(channel)
            status = outcomes[channel].pop(0)
            return {"send_attempted": True, "send_status": status}
        return invoke
    result = deliver_admitted_pre_open_snapshot(runtime=runtime, archive_write=archive, snapshot=snapshot, public_sync=sync, effective_trading_date="2026-09-04", email_sender=sender("email"), line_sender=sender("line"), receipt_root=root)
    return result, calls


def main() -> int:
    checks = {}
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        result, calls = deliver(root, fixture(), {"email": ["sent"], "line": ["sent"]})
        checks["a_authoritative_complete_lifecycle"] = result["gate"]["eligible"] and calls == ["email", "line"]

        stale = {"source_status": "FALLBACK", "fallback_used": True, "fallback_snapshot_age": 2, "symbol_drift_status": "NO_DRIFT", "missing_symbols": [], "extra_symbols": []}
        result, calls = deliver(root / "stale", fixture(evidence=stale), {"email": ["sent"], "line": ["sent"]})
        checks["b_stale_fallback_fails_closed"] = not calls and result["gate"]["universe_eligibility"]["state"] == "DEGRADED_STALE_FALLBACK"
        unknown = {"source_status": "READY", "fallback_used": False, "symbol_drift_status": "UNKNOWN", "missing_symbols": [], "extra_symbols": []}
        checks["c_unknown_drift_fails_closed"] = universe_eligibility({"stock_universe_evidence": unknown})["eligible"] is False
        drift = {"source_status": "READY", "fallback_used": False, "symbol_drift_status": "DRIFT_DETECTED", "missing_symbols": ["X"], "extra_symbols": []}
        checks["d_detected_drift_fails_closed"] = universe_eligibility({"stock_universe_evidence": drift})["state"] == "DRIFT_DETECTED"

        partial = root / "partial-email"
        first, calls1 = deliver(partial, fixture(), {"email": ["sent"], "line": ["failed"]})
        second, calls2 = deliver(partial, fixture(), {"email": ["sent"], "line": ["sent"]})
        checks["e_email_success_line_retry_only"] = calls1 == ["email", "line"] and calls2 == ["line"] and second["email"]["send_status"] == "already_delivered"
        partial = root / "partial-line"
        first, calls1 = deliver(partial, fixture(), {"email": ["failed"], "line": ["sent"]})
        second, calls2 = deliver(partial, fixture(), {"email": ["sent"], "line": ["sent"]})
        checks["f_line_success_email_retry_only"] = calls1 == ["email", "line"] and calls2 == ["email"] and second["line"]["send_status"] == "already_delivered"

        bad = {"send_attempted": False, "send_status": "sent"}
        checks["g_false_sent_never_provenance_sent"] = transport_delivery_result(bad) == "failed"
        try:
            build_delivery_provenance(market="TW", window="pre_open_0700", trading_date="2026-09-04", snapshot=fixture()[2], canonical_url="/", channel="line", content="x", delivery_result="sent", delivery_attempted=False)
            checks["g_provenance_invariant"] = False
        except ValueError:
            checks["g_provenance_invariant"] = True

        runtime_path = root / "runtime.json"
        runtime_path.write_text(json.dumps({"market": "TW", "window": "pre_open_0700", "tracking_symbols": SYMBOLS, "structured_pre_open_cards": [{"symbol": s, "name": "N" + s} for s in SYMBOLS]}), encoding="utf-8")
        original = forecast.latest_analysis_rows
        forecast.latest_analysis_rows = lambda _date: {}
        try:
            projection = forecast.build(forecast.parse_day("2026-09-04"), runtime_path)
        finally:
            forecast.latest_analysis_rows = original
        checks["h_forecast_audit_order_parity"] = projection["canonical_symbol_order"] == SYMBOLS and [s["stock_id"] for s in projection["stocks"]] == SYMBOLS and projection["symbol_exclusions"] == []

        result, calls = deliver(root / "unavailable", fixture(unavailable={"009816"}), {"email": ["sent"], "line": ["sent"]})
        checks["i_unavailable_retains_universe"] = result["gate"]["notification_symbols"] == SYMBOLS and len(calls) == 2
        checks["j_leading_zero_preserved"] = projection["canonical_symbol_order"][1] == "009816" and projection["canonical_symbol_order"][7] == "00878"
        result, calls = deliver(root / "bad-dashboard", fixture(dashboard=False), {"email": ["sent"], "line": ["sent"]})
        checks["k_dashboard_mismatch_no_notification"] = not calls and not result["gate"]["eligible"]

    changed = __import__("subprocess").run(["git", "diff", "--name-only", "origin/main"], cwd=ROOT, text=True, capture_output=True, check=True).stdout.splitlines()
    checks["l_us_unchanged"] = not any(p.startswith("app/us_stock/") for p in changed)
    report = {"schema_version": "tw_preopen_lifecycle_contract_v1", "contract": "TW_PREOPEN_LIFECYCLE_CONTRACT", "checks": checks, "passed": sum(checks.values()), "total": len(checks), "ok": all(checks.values()), "production_mutation": False}
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
