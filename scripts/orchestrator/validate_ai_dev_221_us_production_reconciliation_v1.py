#!/usr/bin/env python3
"""AI-DEV-221 US trading-date, product activation and archive parity gate."""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.dashboard.multi_market_dashboard import _us_window_card
from app.dashboard.public_latest_sync import identity_parity
from app.dashboard.window_snapshot_archive import resolve_snapshots, write_snapshot
from app.us_stock.live_pipeline import session_context
from app.us_stock.product_continuity import forecast_projection, validate_us_product
from app.us_stock.research_intelligence_v2 import research_direction_explanation
from app.us_stock.trading_calendar import is_us_trading_day, resolve_us_effective_trading_date
from scripts.orchestrator.approved_us_stock_delivery import line_text

TAIPEI = ZoneInfo("Asia/Taipei")


def require(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def fixture_card() -> dict:
    prediction = {"reference_price": 100, "predicted_session_low": 96, "predicted_session_high": 106}
    forecast = forecast_projection({"market_label": "US", "price": 100, "daily_tactical_summary": {"direction": "bullish"}}, prediction)
    news = {"schema_version": "us_news_product_projection_v1", "market": "US", "retrieved_count": 4, "qualified_count": 2, "selected_count": 1, "state": "AVAILABLE", "state_label": "有可用當期新聞", "selected_items": [{"headline": "Nvidia expands AI infrastructure partnership", "publisher": "Reuters", "published_at": "2026-08-21T18:00:00Z", "direction_status": "NOT_EVALUATED"}]}
    return {"market_label": "US", "symbol": "NVDA", "name": "Nvidia", "price": 100, "daily_tactical_summary": {"direction": "bullish"}, "premarket": {}, "eligibility": {"actionable": False, "watch_only": True, "reason_codes": ["RR_BELOW_THRESHOLD"]}, "trade_plan": {}, "event_risk": {}, "news_evidence": {}, "sec_evidence": {}, "relative_strength": {}, "institutional_research": {}, "us_premarket_product_projection_v1": forecast, "us_news_product_projection_v1": news}


def main() -> int:
    cases: dict[str, str] = {}
    saturday = datetime(2026, 8, 22, 13, 35, tzinfo=TAIPEI)
    sunday = datetime(2026, 8, 23, 13, 35, tzinfo=TAIPEI)
    require(resolve_us_effective_trading_date(saturday, "us_pre_market_2000") == date(2026, 8, 21), "Saturday admitted as trading date")
    require(resolve_us_effective_trading_date(sunday, "us_pre_market_2000") == date(2026, 8, 21), "Sunday admitted as trading date")
    require(not is_us_trading_day(date(2026, 7, 3)), "observed US holiday admitted")
    require(resolve_us_effective_trading_date(datetime(2026, 7, 3, 20, tzinfo=TAIPEI), "us_pre_market_2000") == date(2026, 7, 2), "holiday did not roll back")
    cases["weekend_holiday_trading_date"] = "PASS"

    pre_session = datetime(2026, 8, 21, 15, 0, tzinfo=TAIPEI)  # 03:00 New York
    context = session_context("us_pre_market_2000", pre_session)
    require(context["session_availability"]["state"] == "PREMARKET_SESSION_NOT_STARTED", "off-session not explicit")
    require(context["session_availability"]["reason"] != "ACQUISITION_FAILURE", "off-session became transport failure")
    weekend_context = session_context("us_pre_market_2000", saturday)
    require(weekend_context["session_availability"]["state"] == "OFF_SESSION_VERIFICATION", "weekend verification state wrong")
    cases["off_session_semantics"] = "PASS"

    card = fixture_card()
    forecast = card["us_premarket_product_projection_v1"]
    require(forecast["direction"] == "BULLISH" and forecast["target_price"] == 101, "canonical forecast unavailable")
    require(forecast["execution_target"] is False and card["eligibility"]["actionable"] is False, "forecast target coupled to execution")
    require(not validate_us_product(forecast, expected_window="us_pre_market_2000"), "valid interval rejected")
    require("forecast_interval" in validate_us_product({**forecast, "target_price": 120}, expected_window="us_pre_market_2000"), "out-of-range target escaped")
    require("market_lineage" in validate_us_product({**forecast, "market": "TW"}, expected_window="us_pre_market_2000"), "TW injection escaped")
    cases["forecast_and_market_isolation"] = "PASS"

    card["session_context"] = session_context("us_pre_market_2000", pre_session)
    html = _us_window_card(card, "us_pre_market_2000")
    artifact = {"market": "US", "window": "us_pre_market_2000", "dashboard_ready_contract": {"cards": [card]}, "premarket_summary": {"groups": {}}, "institutional_research_summary": {}}
    line = line_text(artifact, "us_pre_market_2000")
    ordered = [html.index(token) for token in ("方向", "預測目標", "預測區間", "短評", "新聞抓取", "今日行動")]
    require(ordered == sorted(ordered), "Dashboard primary ordering regressed")
    for token in ("偏多 ↑", "101", "96", "106", "Reuters", "尚未進入美股盤前資料可用時段"):
        require(token in html, f"Dashboard projection missing {token}")
    weekend_card = fixture_card()
    weekend_card["session_context"] = weekend_context
    require("美股非交易時段" in _us_window_card(weekend_card, "us_pre_market_2000"), "weekend controlled message missing")
    for token in ("方向：偏多 ↑", "目標：101.00", "區間：96.00～106.00", "新聞：抓取 4｜通過 2｜可用 1"):
        require(token in line, f"LINE parity missing {token}")
    cases["production_renderer_activation"] = "PASS"

    explanation = research_direction_explanation(coverage_score=94.29, stance="insufficient_evidence", supporting_count=0, opposing_count=0)
    require("覆蓋高" in explanation and "公司方向性證據" in explanation, "high coverage contradiction unexplained")
    require("覆蓋高" not in research_direction_explanation(coverage_score=94.29, stance="bullish", supporting_count=2, opposing_count=0), "valid binding mislabeled")
    cases["research_semantic_explanation"] = "PASS"

    with tempfile.TemporaryDirectory(prefix="ai221-") as tmp:
        root = Path(tmp)
        payload = {"market": "US", "window": "us_pre_market_2000", "effective_trading_date": "2026-08-21", "runtime_provenance": "manual_rerun", "fixture": False, "validation_only": False, "tracking_stock_count": 1, "dashboard_ready_contract": {"cards": [card]}}
        written = write_snapshot(root, market="US", window="us_pre_market_2000", effective_trading_date="2026-08-21", generated_at="2026-08-22T13:35:00+08:00", source_payload=payload, status="completed", run_kind="manual_rerun", run_id="manual-ai221")
        require(written["written"] is True, "valid Friday snapshot not admitted")
        rejected = write_snapshot(root, market="US", window="us_pre_market_2000", effective_trading_date="2026-08-22", generated_at="2026-08-22T13:36:00+08:00", source_payload=payload, status="completed", run_kind="manual_rerun")
        require(rejected["reason"] == "us_non_trading_effective_date", "Saturday snapshot did not fail closed")
        latest = resolve_snapshots(root, "US", "us_pre_market_2000").latest or {}
        identity = {"market": latest.get("market"), "window": latest.get("window"), "effective_trading_date": latest.get("effective_trading_date"), "snapshot_id": latest.get("snapshot_id"), "revision": latest.get("revision"), "payload_hash": latest.get("source_payload_hash")}
        require(identity_parity(identity, dict(identity))["status"] == "verified", "latest/overview parity failed")
        stale = {**identity, "effective_trading_date": "2026-08-20"}
        require(identity_parity(identity, stale)["status"] == "failed_verification", "stale overview mutation escaped")
    cases["archive_latest_overview_parity"] = "PASS"

    runner = (ROOT / "scripts/orchestrator/approved_us_stock_delivery.py").read_text(encoding="utf-8")
    require("resolve_us_effective_trading_date(batch_reference, args.window)" in runner, "approved runtime bypasses calendar")
    require("production_approved and not args.manual_rerun" in runner and "send_email_if_allowed" in runner and "send_line_if_allowed" in runner, "manual no-send safety regressed")
    require("python3 main.py" not in runner, "unsafe entrypoint introduced")
    cases["manual_rerun_safety_and_runtime_path"] = "PASS"

    print(json.dumps({"schema_version": "ai_dev_221_validator_v1", "status": "PASS", "cases": cases, "case_count": len(cases), "production_rerun": False, "notifications_sent": False, "trading": False}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
