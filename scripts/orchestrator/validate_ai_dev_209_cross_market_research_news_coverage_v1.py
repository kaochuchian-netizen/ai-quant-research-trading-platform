#!/usr/bin/env python3
"""AI-DEV-209 cross-market research/news coverage semantic gate."""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.reports.tw_pre_open_quality import news_contract
from app.research.news_evidence_funnel import NEWS_STAGES, normalize_yfinance_news, validate_funnel, with_downstream_counts
from app.research.tw_daily_generator import build_tw_daily_research
from app.us_stock.institutional_research import aggregate_bundles, build_bundle
from scripts.orchestrator.approved_us_stock_delivery import line_text

NOW = "2026-08-12T20:00:00+08:00"


def nested_news(*, title="Apple announces material product update", published="2026-08-12T08:00:00Z", url="https://finance.yahoo.com/news/apple-update"):
    return {"content": {"contentType": "STORY", "title": title, "summary": title,
        "pubDate": published, "provider": {"displayName": "Reuters"},
        "canonicalUrl": {"url": url}}}


def us_research(items, funnel):
    return {
        "sec": {"ok": False}, "official_sources": {}, "fundamentals": {}, "earnings": {},
        "material_news": {"items": [{
            "english_headline": item["english_headline"], "chinese_summary": item["chinese_summary"],
            "event_type": "news", "direction": item["direction"], "direction_status": item["direction_status"],
            "materiality": item["materiality"], "relevance": item["relevance"], "official_source": False,
            "provenance": {"published_at": item["published_at"], "source_reference": item["source_url"]},
        } for item in items], "evidence_funnel": funnel},
    }


def context():
    return {"items": {symbol: {"change_pct": change, "last_price": 100 + change,
        "previous_close": 100, "source_timestamp": "2026-08-12T08:00:00-04:00", "ok": True}
        for symbol, change in {"SPY": .1, "QQQ": .2, "SOXX": .3}.items()}}


def tw_card(news):
    return {"symbol": "2330", "stock_id": "2330", "stock_name": "台積電", "plan_status": "no_trade",
        "action": "暫不操作", "current_price": 100, "session_open": 99,
        "technical_data": {"analysis_eligible": True, "direction": "neutral", "history_bars": 60,
            "source": "fixture", "source_timestamp": "2026-08-11T13:30:00+08:00"},
        "news_evidence": news, "data_gaps": [], "confidence": 50}


def validate() -> dict:
    checks: dict[str, bool] = {}
    details: dict[str, object] = {}

    admitted, exact = normalize_yfinance_news([nested_news()], symbol="AAPL", observed_at=NOW)
    checks["case_a_us_nested_provider_admitted"] = len(admitted) == 1 and exact["stages"]["ADMITTED"] == 1 and not validate_funnel(exact)

    none, no_news = normalize_yfinance_news([], symbol="AAPL", observed_at=NOW)
    checks["case_b_no_relevant_news"] = not none and no_news["absence_state"] == "NO_RELEVANT_NEWS_DISCOVERED"

    failed_items, failed = normalize_yfinance_news([], symbol="AAPL", observed_at=NOW, retrieval_error="Timeout")
    checks["case_c_retrieval_failure_distinct"] = not failed_items and failed["absence_state"] == "NEWS_RETRIEVAL_FAILED" and failed["rejection_reasons"] == {"RETRIEVAL_FAILED": 1}

    irrelevant_items, filtered = normalize_yfinance_news([nested_news(title="Broad market rates update")], symbol="AAPL", observed_at=NOW)
    checks["case_d_filtered_attribution_visible"] = not irrelevant_items and filtered["absence_state"] == "NEWS_DISCOVERED_BUT_FILTERED" and filtered["rejection_reasons"].get("SYMBOL_ATTRIBUTION_FAILED") == 1

    stale_items, stale = normalize_yfinance_news([nested_news(published="2026-08-01T08:00:00Z")], symbol="AAPL", observed_at=NOW)
    checks["case_e_stale_only_excluded"] = not stale_items and stale["absence_state"] == "STALE_ONLY" and stale["stages"]["ADMITTED"] == 0

    research = us_research(admitted, exact)
    bundle = build_bundle("AAPL", research, context(), NOW)
    news_v2 = bundle["news_intelligence_v2"]
    checks["case_f_admitted_rre_rendered_trace"] = news_v2["evidence_funnel"]["stages"]["ADMITTED"] == news_v2["evidence_funnel"]["stages"]["RRE_USED"] == news_v2["evidence_funnel"]["stages"]["RENDERED"] == 1
    news_evidence = [item for item in bundle["evidence"] if item.get("event_type") == "news"]
    checks["case_g_directionless_visible_no_direction"] = (
        news_v2["items"][0]["direction"] == "unavailable"
        and len(news_evidence) == 1 and news_evidence[0]["direction"] == "unavailable"
        and news_evidence[0]["evidence_id"] not in bundle["synthesis"]["supporting_evidence"]
        and news_evidence[0]["evidence_id"] not in bundle["synthesis"]["contradicting_evidence"]
    )

    tw_now = "2026-08-12T15:00:00+08:00"
    tw_current = news_contract({"items": [{"headline": "公司公告重大更新", "publisher": "MOPS", "published_at": "2026-08-12T13:00:00+08:00", "source_url": "mops:2330:1", "official_source": True, "symbol_attributed": True, "relevance": "high", "materiality": "high", "direction": None}], "retrieval": {"result_count_discovered": 1}}, generated_at=tw_now)
    tw_projection = build_tw_daily_research("post_close_1500", {"generated_at": tw_now, "effective_trading_date": "2026-08-12"}, [tw_card(tw_current)], [{"symbol": "2330", "decision_category": "AVOID_CANDIDATE", "decision_category_label": "避免候選"}])
    tw_diag = tw_projection["research_notes"][0]["research_evidence_observability"]["news"]
    checks["case_h_tw_official_current_visible"] = tw_diag["stages"]["ADMITTED"] == tw_diag["stages"]["RRE_USED"] == tw_diag["stages"]["RENDERED"] == 1

    tw_stale = copy.deepcopy(tw_current)
    tw_stale.pop("evidence_funnel", None)
    tw_stale["evidence"][0]["published_at"] = "2026-07-01T10:00:00+08:00"
    stale_projection = build_tw_daily_research("post_close_1500", {"generated_at": tw_now, "effective_trading_date": "2026-08-12"}, [tw_card(tw_stale)], [{"symbol": "2330", "decision_category": "AVOID_CANDIDATE", "decision_category_label": "避免候選"}])
    stale_note = stale_projection["research_notes"][0]
    stale_diag_tw = stale_note["research_evidence_observability"]["news"]
    checks["case_i_tw_stale_cannot_reenter_rre"] = stale_diag_tw["stages"]["RRE_USED"] == stale_diag_tw["stages"]["RENDERED"] == 0 and stale_diag_tw["absence_state"] == "STALE_ONLY" and not stale_note["neutral_research_evidence"]

    card = {"symbol": "AAPL", "institutional_research": bundle}
    summary = aggregate_bundles([card])
    checks["case_j_coverage_denominator_canonical"] = summary["average_coverage_score"] == summary["average_effective_coverage_score_v2"] and summary["coverage_contract"]["denominator"] == "applicable_weighted_categories"
    artifact = {"dashboard_ready_contract": {"cards": [card]}, "institutional_research_summary": summary,
        "premarket_summary": {"groups": {}, "market_context": {}}, "runtime_watchlist_validation": {"enabled_stock_count": 1}}
    line = line_text(artifact, "us_pre_market_2000")
    checks["case_k_line_dashboard_coverage_parity"] = f"有效研究覆蓋 {summary['average_effective_coverage_score_v2']}%" in line

    selected_not_rendered = with_downstream_counts(exact, rre_used=1, rendered=0)
    checks["case_l_absence_state_partition"] = len({no_news["absence_state"], failed["absence_state"], filtered["absence_state"], stale["absence_state"], exact["absence_state"], selected_not_rendered["absence_state"]}) == 6

    checks["official_source_priority_declared"] = exact["source_preference"][:4] == ["official", "SEC", "company_ir", "company_newsroom"]
    checks["all_twelve_stages_present"] = all(stage in exact["stages"] for stage in NEWS_STAGES)
    checks["no_trade_or_strategy_export"] = bundle["decision_context_export"]["trade_action"] is None and bundle["decision_engine_boundary"]["trade_action_exported"] is False
    details.update({"us_exact_funnel": exact, "us_filtered": filtered, "us_stale": stale,
        "tw_current_funnel": tw_diag, "tw_stale_funnel": stale_diag_tw,
        "coverage": summary, "line_research_summary": next(x for x in line.splitlines() if "有效研究覆蓋" in x)})
    return {"task_id": "AI-DEV-209", "ok": all(checks.values()), "checks": checks, "details": details,
        "safety": {"network": False, "production_pipeline": False, "publish": False, "notification": False,
            "trading": False, "database_write": False, "immutable_history_rewrite": False}}


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--pretty", action="store_true"); args = parser.parse_args()
    result = validate(); print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
