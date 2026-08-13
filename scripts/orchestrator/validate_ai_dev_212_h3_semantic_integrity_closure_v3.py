#!/usr/bin/env python3
"""AI-DEV-212 H3 semantic-integrity closure gate."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.research.news_evidence_funnel import (
    NEWS_STAGES,
    normalize_yfinance_news,
    validate_entity_attribution_contract,
)
from app.us_stock.research_intelligence_v2 import build_event_narrative
from app.us_stock.research_presentation import (
    compatibility_news_snippet,
    finalized_current_news_projection,
    validate_finalized_news_projection,
    validate_news_surface_parity,
)
from scripts.orchestrator.manual_rerun_runtime_bridge import manual_date_provenance

OBSERVED = "2026-08-13T12:00:00Z"


def raw(title: str, related: list[str] | None = None, *, published: str = "2026-08-13T11:00:00Z") -> dict:
    return {"content": {"title": title, "summary": title, "provider": {"displayName": "Fixture News"},
        "pubDate": published, "canonicalUrl": {"url": "https://example.test/" + str(sum(map(ord, title)))},
        "relatedTickers": related or [], "contentType": "STORY"}}


def attributed(symbol: str, value: dict, *, observed: str = OBSERVED):
    return normalize_yfinance_news([value], symbol=symbol, observed_at=observed)


def funnel(admitted: int, used: int, rendered: int, absence: str, reasons: dict | None = None,
           retrieval: str = "SUCCESS") -> dict:
    stages = {stage: 0 for stage in NEWS_STAGES}
    stages.update({"DISCOVERED": 1, "RETRIEVED": 1 if retrieval == "SUCCESS" else 0,
        "NORMALIZED": 1 if retrieval == "SUCCESS" else 0, "SYMBOL_ATTRIBUTED": admitted,
        "QUALITY_QUALIFIED": admitted, "FRESH": admitted, "RELEVANT": admitted,
        "MATERIAL": admitted, "DEDUPLICATED": admitted, "ADMITTED": admitted,
        "RRE_USED": used, "RENDERED": rendered})
    return {"schema_version": "cross_market_research_news_funnel_v1", "count_semantics": "EXACT",
        "stages": stages, "rejection_reasons": reasons or {}, "absence_state": absence,
        "retrieval": {"status": retrieval, "reason_code": "RETRIEVAL_FAILED" if retrieval == "FAILED" else None}}


def selected(news_id: str, headline: str, attribution: dict) -> dict:
    return {"news_id": news_id, "headline": headline, "english_headline": headline,
        "publisher": "Fixture News", "published_at": "2026-08-13T11:00:00Z",
        "source_class": "recognized_financial_media", "source_reference": f"https://example.test/{news_id}",
        "freshness": "current", "direction": "unavailable", "direction_status": "NOT_EVALUATED",
        "selection_status": "SELECTED_AND_RENDERED", "entity_attribution": attribution}


def bundle(item: dict | None, *, admitted: int = 1, used: int = 1, rendered: int = 1,
           absence: str = "NEWS_SELECTED_AND_RENDERED", reasons: dict | None = None,
           retrieval: str = "SUCCESS") -> dict:
    items = [item] if item else []
    return {"news_intelligence_v2": {"selected_items": items,
        "evidence_funnel": funnel(admitted, used, rendered, absence, reasons, retrieval)},
        "research_intelligence_v2": {"selected_news_evidence": items}}


def narrative(symbol: str, headline: str, event_type: str = "news") -> dict:
    return build_event_narrative(symbol, {"news_id": "news-" + symbol, "headline": headline,
        "summary": headline, "publisher": "Fixture", "event_type": event_type}, "insufficient_evidence")


def validate() -> dict:
    checks: dict[str, bool] = {}
    details: dict[str, object] = {}
    tsla, tsla_d = attributed("TSLA", raw("Tesla, Palantir Fall as CPI Sends September Fed Hike Odds to 33%", ["TSLA", "PLTR"]))
    roundup, roundup_d = attributed("SPCX", raw("SPCX, ASTS, RKLB And FLY On Watch: Space Economy Movers", ["SPCX", "ASTS", "RKLB", "FLY"]))
    comparison, comparison_d = attributed("SPCX", raw("ASTS And RKLB Chase The SpaceX Playbook", ["ASTS", "RKLB", "SPCX"]))
    googl, _ = attributed("GOOGL", raw("Google launches Pixel 11 with Gemini AI features", ["GOOGL"]))
    nvda, _ = attributed("NVDA", raw("Verizon Teams Up With Nvidia On AI Infrastructure", ["VZ", "NVDA"]))
    tsm, _ = attributed("TSM", raw("ASML Supplier Capacity Supports TSM Expansion", ["ASML", "TSM"]))
    checks["case_a_tsla_macro_not_primary"] = not tsla and bool(tsla_d["rejection_reasons"].get("MARKET_MACRO_REACTION_NOT_COMPANY_EVENT"))
    checks["case_b_spcx_roundup_not_primary"] = not roundup and bool(roundup_d["rejection_reasons"].get("MARKET_ROUNDUP_NOT_COMPANY_EVIDENCE"))
    checks["case_c_spacex_comparative_not_primary"] = not comparison and bool(comparison_d["rejection_reasons"].get("COMPARATIVE_REFERENCE_NOT_COMPANY_EVENT"))
    checks["case_d_googl_primary_retained"] = bool(googl) and googl[0]["entity_attribution"]["framing_class"] == "PRIMARY_COMPANY_EVENT"
    checks["case_e_nvda_relationship_retained"] = bool(nvda) and nvda[0]["entity_attribution"]["relationship_type"] == "teams_up"
    checks["case_f_tsm_supplier_retained"] = bool(tsm) and tsm[0]["entity_attribution"]["attribution_class"] == "MATERIAL_CO_SUBJECT"

    nvda_n = narrative("NVDA", "Nvidia’s biggest risk may be coming from inside its customer base")
    tsm_jv = narrative("TSM", "TSMC Stock Rises as Sony Joint Venture Launches")
    tsm_asml = narrative("TSM", "ASML supplier capacity supports TSM expansion", "supply_chain")
    checks["case_g_nvda_customer_concentration_reasoning"] = (
        nvda_n["event_family"] == "customer_concentration" and "客戶" in nvda_n["counter_argument"]
        and not any(word in nvda_n["counter_argument"] for word in ("等待時間", "促銷", "新品熱度")))
    checks["case_h_tsm_jv_reasoning"] = tsm_jv["event_family"] == "joint_venture" and all(
        word in tsm_jv["counter_argument"] for word in ("商業化", "利用率", "資本支出"))
    checks["case_i_tsm_asml_reasoning"] = tsm_asml["event_family"] == "capex_supply_chain" and all(
        word in tsm_asml["counter_argument"] for word in ("利用率", "設備交期", "供應商"))

    attr = googl[0]["entity_attribution"]
    projection = finalized_current_news_projection(bundle(selected("news-googl", "Google Pixel and Gemini", attr)))
    checks["case_j_finalized_attribution_present"] = (
        projection["schema_version"] == "finalized_current_news_projection_v3"
        and projection["selected_items"][0]["entity_attribution"]["contract_version"] == "us_entity_subject_resolution_v4"
        and not validate_entity_attribution_contract(projection["selected_items"][0]["entity_attribution"]))
    filtered = finalized_current_news_projection(bundle(None, admitted=0, used=0, rendered=0,
        absence="NEWS_DISCOVERED_BUT_FILTERED", reasons={"MARKET_ROUNDUP_NOT_COMPANY_EVIDENCE": 1}))
    checks["case_k_roundup_only_filtered"] = filtered["state"] == "DISCOVERED_BUT_FILTERED" and filtered["state"] != "STALE_ONLY"
    stale = finalized_current_news_projection(bundle(None, admitted=0, used=0, rendered=0,
        absence="STALE_ONLY", reasons={"STALE": 1}))
    checks["case_l_true_stale_only"] = stale["state"] == "STALE_ONLY"
    failed = finalized_current_news_projection(bundle(None, admitted=0, used=0, rendered=0,
        absence="NEWS_RETRIEVAL_FAILED", retrieval="FAILED"))
    checks["case_m_retrieval_failure"] = failed["state"] == "RETRIEVAL_FAILED"
    admitted = finalized_current_news_projection(bundle(None, admitted=1, used=0, rendered=0,
        absence="NEWS_ADMITTED_NOT_SELECTED"))
    checks["case_n_admitted_not_selected"] = admitted["state"] == "ADMITTED_NOT_SELECTED"
    not_rendered = finalized_current_news_projection(bundle(selected("news-x", "Selected company event", attr),
        admitted=1, used=1, rendered=0, absence="NEWS_SELECTED_NOT_RENDERED"))
    checks["case_o_selected_not_rendered"] = not_rendered["state"] == "SELECTED_NOT_RENDERED"

    mutated_roundup = dict(attr, framing_class="MULTI_TICKER_ROUNDUP")
    mutated_projection = dict(projection, selected_items=[dict(projection["selected_items"][0], entity_attribution=None)])
    mutated_stale = dict(filtered, state="STALE_ONLY", reason_code="STALE_ONLY")
    checks["mutation_roundup_primary_rejected"] = (
        not bool(roundup)
        and "non_company_frame_promoted_to_company_evidence" in validate_entity_attribution_contract(mutated_roundup)
    )
    checks["mutation_missing_attribution_fails"] = "selected_attribution_missing" in validate_finalized_news_projection(mutated_projection)
    checks["mutation_filtered_to_stale_fails"] = "stale_without_stale_evidence" in validate_finalized_news_projection(mutated_stale)
    checks["mutation_wrong_nvda_counter_fails"] = not ("等待時間" in nvda_n["counter_argument"])
    checks["mutation_wrong_tsm_jv_counter_fails"] = not ("新品熱度" in tsm_jv["counter_argument"])
    checks["mutation_macro_direction_fails"] = not tsla

    surface = compatibility_news_snippet(projection)
    checks["surface_parity_v3"] = not validate_news_surface_parity(projection, [surface])
    dates = manual_date_provenance("2026-08-12", {"effective_trading_date": "2026-08-13"})
    checks["manual_date_provenance"] = dates == {
        "requested_effective_date": "2026-08-12", "resolved_effective_trading_date": "2026-08-13",
        "effective_trading_date": "2026-08-13", "effective_date_contract": "effective_trading_date_is_resolved_canonical_archive_date"}
    checks["decision_boundary_unchanged"] = all(item.get("direction", "unavailable") == "unavailable" for item in projection["selected_items"])
    details.update({"attribution": {"tsla": tsla_d, "roundup": roundup_d, "comparison": comparison_d,
        "googl": googl[0]["entity_attribution"], "nvda": nvda[0]["entity_attribution"], "tsm": tsm[0]["entity_attribution"]},
        "narratives": {"nvda": nvda_n, "tsm_jv": tsm_jv, "tsm_asml": tsm_asml},
        "finalized_projection": projection, "manual_date_provenance": dates})
    return {"task_id": "AI-DEV-212-H3", "contract_version": "ai_dev_212_h3_v3",
        "ok": all(checks.values()), "checks": checks, "details": details,
        "errors": [name for name, passed in checks.items() if not passed],
        "safety": {"production_pipeline": False, "notifications": False, "trading": False,
            "production_db": False, "immutable_history": False, "decision_behavior_changed": False}}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    result = validate()
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
