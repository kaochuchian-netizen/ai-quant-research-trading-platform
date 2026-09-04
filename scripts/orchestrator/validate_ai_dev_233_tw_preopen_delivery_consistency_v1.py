#!/usr/bin/env python3
"""Subsystem-level AI-DEV-233 TW 07:00 delivery consistency gate."""
from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.dashboard.market_dashboard_alias import snapshot_parity_contract
from app.reports.tw_pre_open_delivery_contract import deliver_admitted_pre_open_snapshot
from app.reports.tw_pre_open_structured import aggregate, seal_card_source_payload_hash, unavailable_card, validate_payload


SYMBOLS = ["2330", "009816", "2337", "2353", "6873", "4743", "2305", "00878", "1409", "3293"]


def _card(symbol: str, *, unavailable: bool = False) -> dict:
    card = unavailable_card(symbol, f"TEST-{symbol}", "2026-09-04", "historical_unavailable")
    if not unavailable:
        card["availability_status"] = "partial"
        card["entry_readiness"] = "watch"
        card["opportunity_group"] = "watch"
        card["action"] = "觀察"
    return seal_card_source_payload_hash(card)


def _fixture(symbols=SYMBOLS, *, snapshot_symbols=None, date="2026-09-04", dashboard_ok=True, admitted=True, unavailable=()):
    runtime_cards = [_card(symbol, unavailable=symbol in unavailable) for symbol in symbols]
    runtime = {
        "market": "TW", "window": "pre_open_0700", "effective_trading_date": "2026-09-04",
        "selected_symbols": list(symbols), "tracking_symbols": list(symbols),
        "structured_pre_open_cards": runtime_cards,
        "stock_universe_evidence": {"source_status": "READY", "fallback_used": False, "symbol_drift_status": "NO_DRIFT", "missing_symbols": [], "extra_symbols": []},
    }
    chosen = list(snapshot_symbols if snapshot_symbols is not None else symbols)
    cards = [_card(symbol, unavailable=symbol in unavailable) for symbol in chosen]
    payload = {
        "market": "TW", "window": "pre_open_0700", "effective_trading_date": date,
        "tracking_stock_count": len(chosen), "selected_symbols": chosen,
        "tracking_symbols": chosen, "structured_card_count": len(cards),
        "rendered_card_count": len(cards), "structured_pre_open_cards": cards,
        "cards": cards, "pre_open_summary": aggregate(cards, chosen),
        "stock_universe_evidence": runtime["stock_universe_evidence"],
    }
    snapshot = {
        "market": "TW", "window": "pre_open_0700", "effective_trading_date": date,
        "snapshot_id": "snapshot-233", "revision": 3, "payload": payload,
    }
    identity = snapshot_parity_contract(snapshot)
    sync = {
        "status": "verified" if dashboard_ok else "failed_verification",
        "snapshot_id": identity["snapshot_id"], "revision": identity["revision"],
        "source_payload_hash": identity["payload_hash"], "rendered_symbols": chosen,
    }
    archive = {"written": admitted, "snapshot_id": "snapshot-233", "revision": 3}
    return runtime, archive, snapshot, sync


def _run(fixture):
    calls = []
    runtime, archive, snapshot, sync = fixture
    result = deliver_admitted_pre_open_snapshot(
        runtime=runtime, archive_write=archive, snapshot=snapshot, public_sync=sync,
        effective_trading_date="2026-09-04",
        email_sender=lambda admitted: calls.append(("email", admitted)) or {"send_attempted": True, "send_status": "sent"},
        line_sender=lambda admitted: calls.append(("line", admitted)) or {"send_attempted": True, "send_status": "sent"},
    )
    return result, calls


def main() -> int:
    checks: dict[str, bool] = {}

    result, calls = _run(_fixture())
    checks["a_ten_symbol_admitted_dashboard_notification_parity"] = (
        result["gate"]["eligible"] and len(calls) == 2
        and result["gate"]["notification_symbols"] == SYMBOLS
        and all(call[1]["payload"]["tracking_symbols"] == SYMBOLS for call in calls)
    )

    result, calls = _run(_fixture(admitted=False))
    checks["b_snapshot_admission_failure_suppresses_both_channels"] = not calls and not result["gate"]["eligible"]

    result, calls = _run(_fixture(dashboard_ok=False))
    checks["c_dashboard_parity_failure_suppresses_both_channels"] = not calls and "dashboard_parity_not_verified" in result["gate"]["errors"]

    result, calls = _run(_fixture(snapshot_symbols=SYMBOLS[:-1]))
    checks["d_runtime_ten_snapshot_nine_fails_closed"] = not calls and "snapshot_symbol_identity" in result["gate"]["errors"]

    result, calls = _run(_fixture(date="2026-09-03"))
    checks["e_stale_snapshot_date_cannot_notify_current_batch"] = not calls and "snapshot_trading_date" in result["gate"]["errors"]

    result, calls = _run(_fixture(unavailable={"009816", "00878"}))
    checks["f_unavailable_cards_retain_full_universe"] = result["gate"]["eligible"] and result["gate"]["snapshot_symbols"] == SYMBOLS and len(calls) == 2
    checks["g_leading_zero_etfs_and_sheet_order_preserved"] = result["gate"]["notification_symbols"] == SYMBOLS and result["gate"]["notification_symbols"][1] == "009816"

    pipeline_source = (ROOT / "app/pipelines/pre_open_pipeline.py").read_text(encoding="utf-8")
    wrapper_source = (ROOT / "scripts/orchestrator/approved_pre_open_delivery.py").read_text(encoding="utf-8")
    ast.parse(pipeline_source)
    ast.parse(wrapper_source)
    checks["single_delivery_owner_no_pipeline_transport"] = (
        "send_line_report" not in pipeline_source
        and "send_reports_in_batches" not in pipeline_source
        and "deliver_admitted_pre_open_snapshot(" in wrapper_source
    )
    checks["notification_content_accepts_explicit_admitted_snapshot"] = (
        "admitted_snapshot: dict[str, Any] | None" in wrapper_source
        and "snapshot,\n            )" in wrapper_source
    )

    hash_cards = [_card("009816", unavailable=True), _card("3293")]
    hash_payload = {
        "tracking_stock_count": 2, "tracking_symbols": ["009816", "3293"],
        "structured_card_count": 2, "rendered_card_count": 2,
        "structured_pre_open_cards": hash_cards, "cards": hash_cards,
        "pre_open_summary": aggregate(hash_cards, ["009816", "3293"]),
    }
    checks["final_presentation_projection_hash_is_admissible"] = validate_payload(hash_payload) == []

    changed = subprocess.run(
        ["git", "diff", "--name-only", "origin/main"], cwd=ROOT, text=True, capture_output=True, check=True,
    ).stdout.splitlines()
    checks["h_us_runtime_untouched"] = not any(path.startswith("app/us_stock/") for path in changed)
    checks["no_symbol_special_case"] = "3293" not in pipeline_source and "3293" not in (ROOT / "app/reports/tw_pre_open_delivery_contract.py").read_text(encoding="utf-8")

    report = {
        "schema_version": "validate_ai_dev_233_tw_preopen_delivery_consistency_v1",
        "checks": checks, "passed": sum(checks.values()), "total": len(checks),
        "ok": all(checks.values()), "production_mutation": False,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
