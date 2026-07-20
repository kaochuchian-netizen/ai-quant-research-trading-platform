#!/usr/bin/env python3
"""Deterministic observed-market and channel-parity gate for US 23:00."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.dashboard.multi_market_dashboard import render_snapshot_archive_page, render_us_window_report
from app.dashboard.window_snapshot_archive import resolve_snapshots, same_window_change, write_snapshot
from app.reports.delivery_provenance import build_delivery_provenance
from app.runtime.operations_provenance import build_operations_provenance
from app.us_stock.intraday_observed import build_intraday_card, resolve_market_session, summarize_intraday, validate_intraday_payload
from scripts.orchestrator.approved_us_stock_delivery import build_email_body, line_text

TAIPEI = ZoneInfo("Asia/Taipei")


def fixture_card(symbol: str = "AAPL", *, current: float = 334.2, opened: float = 331.0, previous: float = 330.0, volume: float = 18_000_000, day_low: float = 330.5, market_data_as_of: str = "2026-07-17T11:00:00-04:00", price_source: str = "fixture.observed_quote") -> dict:
    reference = datetime(2026, 7, 17, 23, 0, tzinfo=TAIPEI)
    session = {**resolve_market_session(reference), "reference_taipei": reference.isoformat()}
    history = pd.DataFrame({"Volume": [42_000_000 + index * 250_000 for index in range(21)]})
    return build_intraday_card(
        entry={"symbol": symbol, "name": f"{symbol} Corp"},
        quote={
            "last_price": current, "previous_close": previous, "regular_market_open": opened,
            "day_low": day_low, "day_high": max(current, opened) + 1, "volume": volume,
            "market_data_as_of": market_data_as_of, "market_data_source": "deterministic_market_fixture",
            "last_price_source": price_source,
        },
        history=history,
        tactical={
            "entry_zone": {"low": 332.0, "high": 335.0}, "stop_reference": 327.8,
            "target_zone_1": {"low": 342.5, "high": 344.0}, "chase_risk": "medium",
            "gap_risk": "medium", "event_risk": "low", "action": "盤前觀察",
        },
        session=session,
        pre_open_snapshot={"snapshot_path": "temporary/pre-open.json", "pre_open_setup": {"action": "盤前觀察"}},
    )


def fixture_payload(cards: list[dict] | None = None) -> dict:
    cards = cards or [fixture_card("AAPL"), fixture_card("NVDA", current=175.0, opened=172.0, previous=170.0, volume=30_000_000, day_low=171.0)]
    return {
        "schema_version": "us_stock_live_runtime_v1", "market": "US", "window": "us_intraday_2300",
        "runtime_provenance": "scheduled_production", "run_kind": "scheduled", "fixture": False,
        "validation_only": False, "generated_at": "2026-07-17T23:01:00+08:00",
        "tracking_stock_count": len(cards),
        "runtime_watchlist_validation": {"enabled_stock_count": len(cards)},
        "session_context": {**resolve_market_session(datetime(2026, 7, 17, 23, 0, tzinfo=TAIPEI)), "reference_taipei": "2026-07-17T23:00:00+08:00"},
        "structured_intraday_cards": cards, "intraday_summary": summarize_intraday(cards),
        "dashboard_ready_contract": {"market_label": "美股", "cards": cards},
    }


def validate() -> dict:
    payload = fixture_payload()
    future_quote = fixture_card("FUTURE", market_data_as_of="2026-07-17T16:00:00-04:00")
    daily_fallback = fixture_card("DAILY", price_source="yfinance_daily_history.Close")
    with tempfile.TemporaryDirectory(prefix="ai185-us2300-") as temporary:
        archive = Path(temporary) / "archive"
        admission = write_snapshot(
            archive, market="US", window="us_intraday_2300", effective_trading_date="2026-07-17",
            generated_at=payload["generated_at"], source_payload=payload, status="completed", run_kind="scheduled",
            run_id="ai185-controlled-no-send", effective_batch_time="2026-07-17T23:00:00+08:00",
        )
        snapshot = resolve_snapshots(archive, "US", "us_intraday_2300").latest or {}
        artifact = snapshot.get("payload", {})
        dashboard = render_us_window_report("us_intraday_2300", [artifact])
        archive_html = render_snapshot_archive_page("US", "us_intraday_2300", "latest", snapshot, same_window_change(snapshot, None))
        email, line = build_email_body(artifact, "us_intraday_2300"), line_text(artifact, "us_intraday_2300")
        canonical = "/dashboard/archive/us/us_intraday_2300/latest/index.html"
        email_prov = build_delivery_provenance(market="US", window="us_intraday_2300", trading_date="2026-07-17", snapshot=snapshot, canonical_url=canonical, channel="email", content=email, delivery_result="dry_run_not_sent", delivery_attempted=False)
        line_prov = build_delivery_provenance(market="US", window="us_intraday_2300", trading_date="2026-07-17", snapshot=snapshot, canonical_url=canonical, channel="line", content=line, delivery_result="dry_run_not_sent", delivery_attempted=False)
        operations = build_operations_provenance(market="US", window="us_intraday_2300", runtime_status="completed", runtime_trading_date="2026-07-17", snapshot=snapshot, public_sync={}, email_result="dry_run_not_sent", line_result="dry_run_not_sent")
    card = payload["structured_intraday_cards"][0]
    source_hash = hashlib.sha256(json.dumps(snapshot.get("payload"), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    forbidden = ("待盤中量價確認", "等待盤中確認", "待開盤")
    checks = {
        "payload_valid": validate_intraday_payload(payload) == [], "admission_accepted": admission.get("written") is True,
        "regular_session_dst": payload["session_context"]["session_phase"] == "regular_session" and payload["session_context"]["dst_active"] is True,
        "current_price_bound": card["current_price"] == 334.2, "market_data_timestamp_bound": bool(card["market_data_as_of"]),
        "regular_open_bound": card["regular_session_open"] == 331.0, "gap_deterministic": card["gap_state"] == "gap_up_follow_through" and card["gap_open_pct"] == 0.303,
        "volume_ratio_deterministic": card["volume_ratio"] is not None and card["volume_confirmation_state"] in {"strong", "confirmed", "neutral", "weak"},
        "future_quote_rejected": future_quote["data_status"] == "invalid" and "market_data_time_after_batch_reference" in future_quote["missing_fields"],
        "daily_bar_not_intraday": daily_fallback["data_status"] == "stale" and "current_price_from_daily_bar" in daily_fallback["missing_fields"],
        "trigger_explicit": card["entry_trigger_state"] in {"inside_zone", "triggered"},
        "distances_present": card["distance_to_stop_pct"] is not None and card["distance_to_target_pct"] is not None,
        "adjustment_observed": card["tactical_adjustment"] != "data_unavailable" and any(token in card["adjustment_reason"] for token in ("目前價", "價格")),
        "dashboard_observed": all(marker in dashboard for marker in ("334.20", "Volume ratio", "Trigger status", "距停損", "距目標")),
        "archive_observed": "334.20" in archive_html and "行情時間" in archive_html,
        "email_observed": all(marker in email for marker in ("目前 334.20", "Gap", "量能", "距停損", canonical)),
        "line_summary": all(marker in line for marker in ("已觸發", "取消追價", "量能確認", canonical)),
        "generic_placeholder_absent": not any(marker in dashboard + archive_html + email + line for marker in forbidden),
        "source_hash_parity": email_prov["source_payload_hash"] == line_prov["source_payload_hash"] == source_hash,
        "operations_counts": operations.get("tracking_count") == operations.get("structured_card_count") == 2 and operations.get("intraday_payload_status") == "valid",
        "no_send": not email_prov["delivery_attempted"] and not line_prov["delivery_attempted"],
    }
    return {"ok": all(checks.values()), "checks": checks, "card": card, "summary": payload["intraday_summary"], "snapshot_id": snapshot.get("snapshot_id"), "source_payload_hash": source_hash, "email_attempted": False, "line_attempted": False, "production_publish": False}


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--pretty", action="store_true"); args = parser.parse_args()
    result = validate(); print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True)); return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
