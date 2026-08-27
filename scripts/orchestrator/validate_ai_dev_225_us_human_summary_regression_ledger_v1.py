#!/usr/bin/env python3
"""AI-DEV-225 Phase B human-summary, news-integrity and ledger gate."""
from __future__ import annotations

import ast
import copy
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))

from app.dashboard.multi_market_dashboard import _us_window_card
from app.research.news_evidence_funnel import normalize_yfinance_news
from app.us_stock.evidence_regression import append_regression_records, build_regression_records, leave_one_out_research, validate_regression_record
from app.us_stock.human_summary import build_us_human_summary, validate_us_human_summary


def require(value: bool, message: str) -> None:
    if not value: raise AssertionError(message)


def raw(title: str, publisher: str, url: str, *, published: str = "2026-08-26T12:00:00Z", related: list[str] | None = None) -> dict:
    return {"content": {"title": title, "provider": {"displayName": publisher}, "pubDate": published, "canonicalUrl": {"url": url}, "relatedTickers": related or ["NVDA"], "contentType": "STORY"}}


def bundle(selected: list[dict] | None = None, candidates: list[dict] | None = None) -> dict:
    selected = selected or []
    evidence = [{
        "evidence_id": "ev-news-1", "event_cluster_id": selected[0].get("news_event_id") if selected else "event-none",
        "news_event_id": selected[0].get("news_event_id") if selected else None,
        "headline": selected[0].get("english_headline") if selected else "Official filing",
        "summary": "evidence", "provider": "yfinance", "provider_tier": "C", "quality_score": 78,
        "confidence": .7, "direction": "unavailable", "materiality": "medium", "relevance": "high",
        "freshness": "fresh", "event_type": "news", "official_confirmation": False,
        "counted_in_synthesis": True, "direction_ownership": "contextual_confirmation_only",
    }]
    stages = {name: 0 for name in ("DISCOVERED","RETRIEVED","NORMALIZED","SYMBOL_ATTRIBUTED","QUALITY_QUALIFIED","FRESH","RELEVANT","MATERIAL","DEDUPLICATED","ADMITTED","RRE_USED","RENDERED")}
    stages.update({"DISCOVERED": len(candidates or selected), "RETRIEVED": len(candidates or selected), "NORMALIZED": len(candidates or selected), "ADMITTED": len(selected), "RRE_USED": len(selected), "RENDERED": len(selected)})
    return {
        "research_identity": "research-origin", "providers": [], "knowledge": {"status": "AVAILABLE"},
        "evidence": evidence, "coverage": {"score": 80}, "conflict": {"level": "none"},
        "synthesis": {"research_stance": "neutral", "research_confidence": 54},
        "research_intelligence_v2": {"window_research_identity": "research-window", "hypothesis_identity": "hyp-1", "hypothesis": {"state": "confirmed"}, "supporting_evidence": ["ev-news-1"], "opposing_evidence": [], "primary_risk": "需求與事件落差風險"},
        "news_intelligence_v2": {"selected_items": selected, "items": selected, "evidence_funnel": {"schema_version": "cross_market_research_news_funnel_v1", "count_semantics": "EXACT", "stages": stages, "rejection_reasons": {}, "candidate_records": candidates or []}},
    }


def card20(selected: list[dict] | None = None, candidates: list[dict] | None = None) -> dict:
    b = bundle(selected, candidates)
    finalized_items = [{**item, "headline": item.get("english_headline"), "news_id": "n1", "selection_status": "SELECTED_AND_RENDERED", "source_class": "recognized_financial_media"} for item in (selected or [])]
    return {
        "market_label": "US", "symbol": "NVDA", "name": "Nvidia", "confidence": 61,
        "daily_tactical_summary": {"direction": "bullish", "action": "watch"},
        "research_position_summary": {"rating": "research_neutral"}, "institutional_research": b,
        "finalized_current_news_projection_v3": {"schema_version": "finalized_current_news_projection_v3", "state": "AVAILABLE" if finalized_items else "NO_RELEVANT", "state_label": "當期個股新聞可用" if finalized_items else "無相關新聞", "reason_code": None, "selected_count": len(finalized_items), "selected_items": finalized_items, "primary_item": finalized_items[0] if finalized_items else None, "compact_summary": f"當期個股新聞：{len(finalized_items)} 筆" if finalized_items else "無相關新聞", "funnel": b["news_intelligence_v2"]["evidence_funnel"]},
        "us_premarket_product_projection_v1": {"direction": "BULLISH", "target_price": 105, "predicted_low": 98, "predicted_high": 110, "reference_price": 100},
        "us_news_product_projection_v1": {"retrieved_count": len(selected or []), "qualified_count": len(selected or []), "selected_count": len(selected or []), "selected_items": finalized_items},
        "premarket": {}, "eligibility": {"watch_only": True}, "trade_plan": {}, "event_risk": {}, "news_evidence": {}, "sec_evidence": {}, "relative_strength": {},
    }


def function_ast(text: str, name: str) -> str:
    node = next(item for item in ast.parse(text).body if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == name)
    return ast.dump(node, include_attributes=False)


def main() -> int:
    checks: dict[str, str] = {}
    observed = "2026-08-26T13:00:00Z"
    syndicated, diag = normalize_yfinance_news([
        raw("Nvidia expands AI infrastructure partnership", "Reuters", "https://reuters.example/a"),
        raw("Nvidia expands AI infrastructure partnership", "Bloomberg", "https://bloomberg.example/b"),
        raw("Nvidia expands second AI capacity program", "CNBC", "https://cnbc.example/c"),
    ], symbol="NVDA", observed_at=observed)
    require(len(syndicated) == 2 and diag["rejection_reasons"].get("DUPLICATE") == 1, "syndicated event did not collapse")
    require(len(syndicated[0]["duplicate_sources"]) == 1, "duplicate provenance lost")
    require(syndicated[0]["news_event_id"] != syndicated[1]["news_event_id"], "distinct update collapsed")
    checks["publisher_independent_event_identity"] = "PASS"

    stale, stale_diag = normalize_yfinance_news([raw("Nvidia old event", "Reuters", "https://example.com/old", published="2026-08-20T01:00:00Z")], symbol="NVDA", observed_at=observed)
    require(not stale and stale_diag["rejection_reasons"].get("STALE") == 1, "stale evidence admitted")
    macro, macro_diag = normalize_yfinance_news([raw("Nvidia and Palantir fall as CPI shifts Fed rate odds", "Reuters", "https://example.com/macro", related=["NVDA", "PLTR"])], symbol="NVDA", observed_at=observed)
    macro_record = macro_diag["candidate_records"][0]
    require(not macro and macro_record["entity_attribution"]["framing_class"] == "MARKET_MACRO_REACTION", "macro context classification lost")
    require(macro_record["admission_status"] == "REJECTED", "contextual macro became company-direction evidence")
    roundup, _ = normalize_yfinance_news([raw("Investment Ideas feature highlights: NVIDIA, Microsoft and Apple", "Zacks", "https://example.com/round", related=["NVDA", "MSFT", "AAPL"])], symbol="NVDA", observed_at=observed)
    require(not roundup, "editorial roundup became company evidence")
    relation, _ = normalize_yfinance_news([raw("Verizon teams up with Nvidia on AI network platform", "Reuters", "https://example.com/relation", related=["VZ", "NVDA"])], symbol="NVDA", observed_at=observed)
    require(relation and relation[0]["entity_attribution"]["relationship_type"] == "teams_up", "relationship provenance lost")
    checks["news_integrity_and_context"] = "PASS"

    base = card20(syndicated, diag["candidate_records"])
    summary20 = build_us_human_summary(base, "us_pre_market_2000")
    base["us_human_decision_summary_v1"] = summary20
    require(not validate_us_human_summary(summary20), "20:00 summary invalid")
    html20 = _us_window_card(base, "us_pre_market_2000")
    order = [html20.index(token) for token in ("方向", "信心", "預測目標", "預測區間", "Research / Position", "Daily Tactical", "關鍵理由", "主要風險", "今日重要消息")]
    require(order == sorted(order) and 1 <= len(summary20["important_news"]) <= 4, "20:00 hierarchy/news bound wrong")
    require("impact" not in json.dumps(summary20, ensure_ascii=False).lower() or all(item.get("impact_summary") for item in summary20["important_news"]), "news impact missing")
    checks["human_summary_2000"] = "PASS"

    card23 = copy.deepcopy(base)
    card23.update({"source_plan": {"source_snapshot_id": "snap-20", "source_revision": 2, "confidence": 57, "forecast": base["us_premarket_product_projection_v1"]}, "current_price": 104, "confidence": 60, "entry_trigger_state": "triggered", "data_status": "complete", "market_data_as_of": observed, "us_intraday_research_continuity_v1": {"source_snapshot_id": "snap-20", "source_revision": 2, "lineage_sufficiency": "COMPLETE"}})
    summary23 = build_us_human_summary(card23, "us_intraday_2300")
    card23["us_human_decision_summary_v1"] = summary23
    require(not validate_us_human_summary(summary23) and summary23["range_position"] == "WITHIN_RANGE" and summary23["confidence_change"] == 3, "23:00 delta invalid")
    require("20:00 → 23:00 變化摘要" in _us_window_card(card23, "us_intraday_2300"), "23:00 summary not rendered")
    missing = copy.deepcopy(card23); missing["us_intraday_research_continuity_v1"] = {"lineage_sufficiency": "INSUFFICIENT"}; missing["source_plan"] = {}
    require(build_us_human_summary(missing, "us_intraday_2300")["continuity_state"] == "INSUFFICIENT_EVIDENCE", "missing lineage did not fail closed")
    checks["human_summary_2300"] = "PASS"

    card06 = copy.deepcopy(base)
    card06.update({"source_trade_plan": {"forecast": base["us_premarket_product_projection_v1"]}, "review": {"actual_high": 108, "actual_low": 99, "actual_close": 106, "mfe": "+5%", "mae": "-1%", "trade_review_outcome": "no_trade", "prediction_evaluation_v2": {"range": {"status": "evaluated", "hit": True, "high_error": -2, "low_error": 1, "midpoint_error": .5}, "direction": {"result": "hit", "predicted_direction": "BULLISH"}}}, "prediction_range_result": "hit", "trade_review_outcome": "no_trade", "research_review_diagnosis": {"research_diagnosis": "事件證據有效但未改變 no-trade ownership", "next_session_carryforward": {"question": "需求是否延續"}}})
    summary06 = build_us_human_summary(card06, "us_post_close_review_0630")
    card06["us_human_decision_summary_v1"] = summary06
    require(summary06["range_result"] == "hit" and summary06["trade_outcome"] == "no_trade" and summary06["direction_result"] == "hit", "06:30 prediction/trade semantics collapsed")
    html06 = _us_window_card(card06, "us_post_close_review_0630")
    require("預測結果與研究學習" in html06 and "交易結果（獨立）" in html06 and "MFE / MAE" in html06, "06:30 learning summary missing")
    checks["human_summary_0630"] = "PASS"

    runtime_item = {"symbol": "NVDA", "prediction": {"predicted_session_low": 98, "predicted_session_high": 110, "model_version": "fixture"}}
    records = build_regression_records(card=base, runtime_item=runtime_item, window="us_pre_market_2000", trading_date="2026-08-26", generated_at=observed)
    require(records and any(row["admission_status"] == "ADMITTED" for row in records) and any(row["admission_status"] == "REJECTED" for row in records), "admitted/rejected ledger coverage missing")
    require(all(not validate_regression_record(row) for row in records), "ledger record invalid")
    require(all(not ({"article_body", "full_text", "raw_html"} & set(row)) for row in records), "copyright body persisted")
    with tempfile.TemporaryDirectory(prefix="ai225-ledger-") as tmp:
        first = append_regression_records(records, Path(tmp)); second = append_regression_records(records, Path(tmp))
        require(first["written"] == len(records) and second["existing"] == len(records), "append-only replay not idempotent")
        mutated = copy.deepcopy(records[0]); mutated["publisher"] = "mutated"
        try: append_regression_records([mutated], Path(tmp))
        except ValueError: pass
        else: raise AssertionError("historical mutation accepted")
    loo = leave_one_out_research(base["institutional_research"], "ev-news-1")
    require(loo["status"] == "EVALUATED" and not loo["production_applied"] and not loo["weights_modified"], "offline leave-one-out unsafe")
    require(leave_one_out_research({}, "missing")["status"] == "FAIL_CLOSED", "insufficient replay fabricated")
    checks["ledger_and_offline_evaluation"] = "PASS"

    live_path = ROOT / "app/us_stock/live_pipeline.py"
    baseline = subprocess.run(["git", "show", "origin/main:app/us_stock/live_pipeline.py"], cwd=ROOT, check=True, capture_output=True, text=True).stdout
    current = live_path.read_text(encoding="utf-8")
    for name in ("score_symbol", "prediction_for_symbol", "rating_action"):
        require(function_ast(current, name) == function_ast(baseline, name), f"protected function changed: {name}")
    require("send_line" not in (ROOT / "app/us_stock/human_summary.py").read_text() and "send_email" not in (ROOT / "app/us_stock/evidence_regression.py").read_text(), "notification side effect introduced")
    checks["protected_contracts"] = "PASS"

    print(json.dumps({"schema_version": "ai_dev_225_phase_b_validator_v1", "status": "PASS", "checks": checks, "check_count": len(checks), "production_rerun": False, "notifications_sent": False, "trading": False, "production_db_write": False}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__": raise SystemExit(main())
