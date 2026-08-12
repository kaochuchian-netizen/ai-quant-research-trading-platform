#!/usr/bin/env python3
"""Deterministic semantic gate for AI-DEV-207 TW evidence observability."""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.dashboard.multi_market_dashboard import _tw_rre_production_html
from app.reports.tw_decision_intelligence_v2 import build_tw_decision_intelligence_v2
from app.reports.tw_pre_open_quality import news_contract
from app.research.tw_daily_generator import build_tw_daily_research, validate_tw_daily_research

NOW = "2026-08-12T13:05:00+08:00"


def item(**overrides):
    value = {
        "headline": "公司公告營運展望更新", "publisher": "MOPS",
        "published_at": "2026-08-12T11:00:00+08:00", "source_url": "mops:2330:1",
        "direction": "bullish", "relevance": "high", "materiality": "high",
        "official_source": True, "symbol_attributed": True,
    }
    value.update(overrides)
    return value


def contract(items, **retrieval):
    return news_contract({"items": items, "retrieval": {"result_count_discovered": len(items), **retrieval}}, generated_at=NOW)


def card(symbol="2330", *, news=None, plan="no_trade", action="暫不操作", price=True):
    value = {
        "symbol": symbol, "stock_id": symbol, "stock_name": f"測試{symbol}",
        "plan_status": plan, "action": action, "current_price": 100 if price else None,
        "session_open": 98 if price else None, "session_high": 101, "session_low": 97,
        "technical_data": {"analysis_eligible": True, "direction": "bullish", "history_bars": 60, "source": "fixture_daily", "source_timestamp": "2026-08-11T13:30:00+08:00"},
        "strategies": {"daily_tactical": {"setup_type": plan, "action": action}},
        "data_gaps": ["CHIP_UNAVAILABLE"], "confidence": 60,
    }
    if news is not None:
        value["news_evidence"] = news
        value["news_direction"] = (news.get("primary_evidence") or {}).get("direction")
    return value


def research(cards):
    rows = [{"symbol": c["symbol"], "decision_category": "WATCH_CANDIDATE" if c["plan_status"] == "watch" else "AVOID_CANDIDATE", "decision_category_label": "觀察候選" if c["plan_status"] == "watch" else "避免候選"} for c in cards]
    return build_tw_daily_research("intraday_1305", {"generated_at": NOW, "effective_trading_date": "2026-08-12"}, cards, rows)


def validate() -> dict:
    checks = {}
    details = {}

    none = contract([])
    checks["case_a_no_news"] = none["absence_state"] == "NO_RELEVANT_NEWS_DISCOVERED" and none["evidence_funnel"]["stages"]["DISCOVERED"] == 0

    filtered = contract([item(relevance="low"), item(source_url="mops:2", materiality="low")])
    checks["case_b_filtered"] = filtered["absence_state"] == "NEWS_DISCOVERED_BUT_FILTERED" and filtered["evidence_funnel"]["rejection_reasons"] == {"LOW_MATERIALITY": 1, "LOW_RELEVANCE": 1}

    official = contract([item()])
    checks["case_c_official_admitted"] = official["status"] == "available" and official["primary_evidence"]["source_tier"] == 1 and official["evidence_funnel"]["stages"]["ADMITTED"] == 1

    official_research = research([card(news=official)])
    note = official_research["research_notes"][0]
    funnel = note["research_evidence_observability"]["news"]
    html = _tw_rre_production_html({"research_reasoning_projection": official_research, "prediction_identity": "fixture"})
    checks["case_d_admitted_used_rendered"] = funnel["stages"]["ADMITTED"] == funnel["stages"]["RRE_USED"] == funnel["stages"]["RENDERED"] == 1 and "公司公告營運展望更新" in html

    duplicate = contract([item(), item(headline="轉載：公司公告營運展望更新", publisher="可信媒體")])
    checks["case_e_duplicate"] = duplicate["evidence_funnel"]["rejection_reasons"].get("DUPLICATE") == 1 and duplicate["evidence_funnel"]["stages"]["ADMITTED"] == 1

    stale = contract([item(published_at="2026-08-01T10:00:00+08:00")])
    checks["case_f_stale"] = stale["evidence_funnel"]["rejection_reasons"].get("STALE") == 1 and stale["evidence_funnel"]["stages"]["ADMITTED"] == 0

    market_only = research([card(news=none)])
    market_note = market_only["research_notes"][0]
    checks["case_g_market_not_research"] = market_note["conclusion"] == "insufficient_evidence" and not market_note["supporting"] and any(value.startswith("市場｜") for value in market_note["contextual_evidence"])
    checks["case_h_no_best_research"] = market_only["morning_or_window_brief"]["best_research_status"] == "NO_QUALIFIED_RESEARCH" and "無符合研究品質門檻" in market_only["morning_or_window_brief"]["best_research"]
    checks["case_i_qualified_best"] = official_research["morning_or_window_brief"]["best_research_status"] == "QUALIFIED" and note["research_quality"]["qualified"] and "2330" in official_research["morning_or_window_brief"]["best_research"]

    no_trade = card("2330", news=none, plan="no_trade", action="暫不操作")
    observe = card("6873", news=none, plan="watch", action="觀察等待")
    payload = {"generated_at": NOW, "effective_trading_date": "2026-08-12", "cards": [no_trade, observe]}
    decision = build_tw_decision_intelligence_v2("intraday_1305", payload)
    states = {row["symbol"]: (row["tomorrow_state"], row["tomorrow_watch"]) for row in decision["stock_intelligence"]}
    checks["case_j_tomorrow_semantics"] = states["2330"] == ("REASSESS", "明日重新評估") and states["6873"] == ("CONTINUE_OBSERVE", "明日延續觀察")

    directionless_item = item(direction=None, headline="公司公告新產品時程", source_url="mops:2330:directionless")
    directionless = contract([directionless_item])
    directionless_research = research([card(news=directionless)])
    directionless_note = directionless_research["research_notes"][0]
    directionless_funnel = directionless_note["research_evidence_observability"]["news"]
    directionless_html = _tw_rre_production_html({"research_reasoning_projection": directionless_research, "prediction_identity": "fixture"})
    checks["case_k_directionless_qualified_news_admitted"] = (
        directionless["evidence_funnel"]["stages"]["ADMITTED"] == 1
        and directionless["primary_evidence"]["direction"] == "unavailable"
        and directionless["primary_evidence"]["direction_status"] == "NOT_EVALUATED"
        and "UNSAFE_TO_CITE" not in directionless["evidence_funnel"]["rejection_reasons"]
    )
    checks["case_l_directionless_news_no_false_direction"] = (
        directionless_note["conclusion"] == "insufficient_evidence"
        and not directionless_note["supporting"]
        and not directionless_note["opposing"]
        and directionless_research["morning_or_window_brief"]["best_research_status"] == "NO_QUALIFIED_RESEARCH"
        and "0 檔具偏多研究證據" in directionless_research["morning_or_window_brief"]["market_narrative"]
        and "0 檔具偏空證據" in directionless_research["morning_or_window_brief"]["market_narrative"]
    )
    checks["case_m_directionless_news_visible"] = (
        directionless_funnel["stages"]["ADMITTED"] == 1
        and directionless_funnel["stages"]["RRE_USED"] == 1
        and directionless_funnel["stages"]["RENDERED"] == 1
        and "公司公告新產品時程" in directionless_html
    )

    legacy_news = copy.deepcopy(official)
    legacy_news.pop("evidence_funnel", None)
    legacy_research = research([card(news=legacy_news)])
    legacy_diag = legacy_research["research_notes"][0]["research_evidence_observability"]["news"]
    checks["case_n_legacy_funnel_lower_bound_truthful"] = (
        legacy_diag["count_semantics"] == "COMPATIBILITY_LOWER_BOUND"
        and bool(legacy_diag["inferred_stages"])
        and legacy_diag["stages"]["ADMITTED"] == 1
        and not validate_tw_daily_research(legacy_research, {"2330"})
    )
    checks["case_o_exact_funnel_marked"] = funnel["count_semantics"] == "EXACT" and not funnel["inferred_stages"]

    narrative = market_only["morning_or_window_brief"]["market_narrative"]
    checks["direction_counts_substantive"] = "0 檔具偏多研究證據" in narrative and "1 檔證據不足" in narrative
    boundary = decision["model_boundary"]
    checks["decision_boundary"] = all(boundary[key] is False for key in ("strategy_changed", "scoring_changed", "strategy_ranking_changed", "prediction_model_changed", "factor_weights_changed", "automatic_learning")) and all(row["tomorrow_state_presentation_only"] for row in decision["stock_intelligence"])
    checks["funnel_monotonic"] = all(
        official["evidence_funnel"]["stages"][left] >= official["evidence_funnel"]["stages"][right]
        for left, right in zip(("DISCOVERED", "RETRIEVED", "NORMALIZED", "SYMBOL_ATTRIBUTED", "RELEVANT", "MATERIAL", "QUALITY_QUALIFIED", "FRESH", "DEDUPLICATED"), ("RETRIEVED", "NORMALIZED", "SYMBOL_ATTRIBUTED", "RELEVANT", "MATERIAL", "QUALITY_QUALIFIED", "FRESH", "DEDUPLICATED", "ADMITTED"))
    )

    mutated = copy.deepcopy(market_only)
    mutated["morning_or_window_brief"]["best_research_status"] = "QUALIFIED"
    mutation_errors = validate_tw_daily_research(mutated, {"2330"})
    details.update({
        "none": none,
        "filtered": filtered,
        "official_funnel": funnel,
        "directionless": directionless,
        "directionless_note": directionless_note,
        "legacy_funnel": legacy_diag,
        "market_note": market_note,
        "tomorrow_states": states,
        "negative_best_research_mutation_errors": mutation_errors,
    })
    checks["negative_best_research_mutation"] = "best_research_without_qualified_candidate" in mutation_errors
    checks["canonical_research_validation"] = not validate_tw_daily_research(official_research, {"2330"}) and not validate_tw_daily_research(market_only, {"2330"})
    return {"ok": all(checks.values()), "validator": "validate_ai_dev_207_tw_research_evidence_coverage_news_visibility_v1", "checks": checks, "details": details, "safety": {"network": False, "production_pipeline": False, "notification": False, "trading": False, "archive_write": False}}


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--pretty", action="store_true"); args = parser.parse_args()
    result = validate(); print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True)); return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
