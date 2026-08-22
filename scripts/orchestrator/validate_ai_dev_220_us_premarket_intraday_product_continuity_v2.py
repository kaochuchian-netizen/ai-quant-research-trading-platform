#!/usr/bin/env python3
"""AI-DEV-220 US product parity, news reliability and lineage validator."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))

from app.research.news_evidence_funnel import normalize_yfinance_news, with_downstream_counts
from app.us_stock.product_continuity import forecast_projection, intraday_continuity, news_projection, validate_us_product
from app.us_stock.research_intelligence_v2 import effective_coverage
from app.us_stock.research_presentation import finalized_current_news_projection
from app.dashboard.multi_market_dashboard import _us_window_card
from scripts.orchestrator.approved_us_stock_delivery import line_text

def require(value: bool, message: str) -> None:
    if not value: raise AssertionError(message)

def raw(title: str, publisher: str | None = "Reuters") -> dict:
    return {"content": {"title": title, "provider": {"displayName": publisher} if publisher else {}, "pubDate": "2026-08-22T01:00:00Z", "canonicalUrl": {"url": "https://example.com/" + title[:8].replace(" ", "-")}, "relatedTickers": ["NVDA"], "contentType": "STORY"}}

def main() -> int:
    cases: dict[str, str] = {}
    observed = "2026-08-22T02:00:00Z"
    items, diag = normalize_yfinance_news([raw("Nvidia expands AI infrastructure partnership")], symbol="NVDA", observed_at=observed)
    require(len(items) == 1 and diag["retrieval"]["status"] == "SUCCESS", "baseline US provider path regressed")
    cases["provider_baseline"] = "PASS"
    unresolved, unresolved_diag = normalize_yfinance_news([raw("Nvidia expands AI infrastructure partnership", None)], symbol="NVDA", observed_at=observed)
    require(len(unresolved) == 1 and unresolved[0]["publisher_resolution_status"] == "unresolved", "publisher resolution destroyed candidate")
    require(unresolved_diag["absence_state"] != "NEWS_RETRIEVAL_FAILED", "publisher unresolved became acquisition failure")
    cases["publisher_non_destructive"] = "PASS"
    partial, partial_diag = normalize_yfinance_news([raw("Nvidia expands AI infrastructure partnership")], symbol="NVDA", observed_at=observed, retrieval_error="provider B timeout")
    require(partial and partial_diag["retrieval"]["status"] == "PARTIAL", "partial provider failure destroyed usable candidates")
    cases["partial_provider_failure"] = "PASS"
    failed, failed_diag = normalize_yfinance_news([], symbol="NVDA", observed_at=observed, retrieval_error="timeout")
    require(not failed and failed_diag["retrieval"]["status"] == "FAILED", "true acquisition failure not preserved")
    cases["true_acquisition_failure"] = "PASS"

    funnel = with_downstream_counts(diag, rre_used=1, rendered=1)
    bundle = {"news_intelligence_v2": {"selected_items": [{**items[0], "news_id": "n1", "headline": items[0]["english_headline"], "selected_for_rre": True, "selection_status": "SELECTED"}], "evidence_funnel": funnel}}
    final = finalized_current_news_projection(bundle)
    product_news = news_projection(final)
    require((product_news["retrieved_count"], product_news["qualified_count"], product_news["selected_count"]) == (1, 1, 1), "news counts disagree")
    require(product_news["selected_items"][0]["publisher"] == "Reuters", "headline/publisher identity diverged")
    cases["news_funnel_and_publisher"] = "PASS"

    card = {"market_label": "US", "price": 100, "daily_tactical_summary": {"direction": "bullish"}}
    forecast = forecast_projection(card, {"reference_price": 100, "predicted_session_low": 96, "predicted_session_high": 106})
    require(not validate_us_product(forecast, expected_window="us_pre_market_2000"), "valid US forecast rejected")
    require(forecast["direction"] == "BULLISH" and forecast["target_price"] == 101, "canonical forecast projection wrong")
    mutated = {**forecast, "target_price": 120}
    require("forecast_interval" in validate_us_product(mutated, expected_window="us_pre_market_2000"), "target mutation escaped")
    require("market_lineage" in validate_us_product({**forecast, "market": "TW"}, expected_window="us_pre_market_2000"), "TW injection escaped")
    cases["forecast_and_market_isolation"] = "PASS"

    visible_card = {**card, "symbol": "NVDA", "name": "Nvidia", "premarket": {}, "eligibility": {}, "trade_plan": {}, "event_risk": {}, "news_evidence": {}, "sec_evidence": {}, "relative_strength": {}, "institutional_research": bundle, "finalized_current_news_projection_v3": final, "us_news_product_projection_v1": product_news, "us_premarket_product_projection_v1": forecast}
    artifact = {"market": "US", "window": "us_pre_market_2000", "dashboard_ready_contract": {"cards": [visible_card]}, "premarket_summary": {"groups": {}}, "institutional_research_summary": {}}
    line = line_text(artifact, "us_pre_market_2000")
    html = _us_window_card(visible_card, "us_pre_market_2000")
    for token in ("方向：偏多 ↑", "目標：101.00", "新聞：抓取 1｜通過 1｜可用 1", "Reuters"):
        require(token in line, f"LINE missing canonical product token: {token}")
    for token in ("今日盤前判斷", "預測目標", "新聞抓取 1", "Reuters"):
        require(token in html, f"Dashboard missing canonical product token: {token}")
    cases["dashboard_line_parity"] = "PASS"

    origin = {"research_identity": "us-origin", "continuity": {"status": "inherited", "source_snapshot_id": "snap-us", "source_revision": 2}, "research_intelligence_v2": {"window_research_identity": "us-current", "hypothesis": {"state": "confirmed"}}, "news_intelligence_v2": {"selected_items": []}}
    continuity = intraday_continuity(origin, {"data_status": "complete"})
    require(continuity["continuity_state"] == "ON_TRACK" and continuity["market_data_sufficiency"] == "COMPLETE", "valid lineage continuity wrong")
    require(not validate_us_product(continuity, expected_window="us_intraday_2300"), "valid continuity rejected")
    missing = intraday_continuity({"research_identity": "us-fresh", "continuity": {"status": "source_bundle_unavailable"}, "research_intelligence_v2": {"hypothesis": {"state": "unchanged"}}}, {"data_status": "complete"})
    require(missing["continuity_state"] == "INSUFFICIENT_SOURCE_LINEAGE", "null source snapshot falsely unchanged")
    intraday_card = {"symbol": "NVDA", "name": "Nvidia", "institutional_research": origin, "us_intraday_research_continuity_v1": continuity, "finalized_current_news_projection_v3": final, "data_status": "complete", "source_plan": {}, "market_data_as_of": "2026-08-22T11:00:00-04:00"}
    intraday_html = _us_window_card(intraday_card, "us_intraday_2300")
    require("20:00 研究判斷延續" in intraday_html and "snap-us" in intraday_html, "23:00 lineage not visible")
    cases["lineage_fail_closed"] = "PASS"

    providers = [{"provider": "options", "capability": ["options"], "availability": "NOT_LICENSED"}, {"provider": "analyst", "capability": ["analyst"], "availability": "NOT_CONFIGURED"}]
    coverage = effective_coverage({"providers": providers, "evidence": [], "knowledge": {}})
    require(set(coverage["excluded_not_applicable"]) == {"options", "analyst"}, "non-applicable denominator not excluded")
    require(not coverage["not_applicable_penalized"], "non-applicable evidence penalized")
    cases["coverage_denominator"] = "PASS"

    source = (ROOT / "app/us_stock/product_continuity.py").read_text(encoding="utf-8")
    require("TW runtime" not in source and "artifacts/runtime/tw" not in source.lower(), "US projection reads TW artifacts")
    require(forecast["decision_authority"] is False and continuity["decision_authority"] is False, "Decision boundary changed")
    cases["renderer_and_decision_boundary"] = "PASS"
    print(json.dumps({"schema_version": "ai_dev_220_validator_v2", "status": "PASS", "cases": cases, "case_count": len(cases), "production_rerun": False, "notifications_sent": False, "trading": False}, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__": raise SystemExit(main())
