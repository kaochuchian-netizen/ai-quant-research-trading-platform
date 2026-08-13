#!/usr/bin/env python3
"""AI-DEV-212 H2 attribution, finalized-news and counter-argument gate."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.research.news_evidence_funnel import NEWS_STAGES, normalize_yfinance_news
from app.us_stock.research_intelligence_v2 import build_event_narrative, normalize_news
from app.us_stock.research_presentation import (
    apply_finalized_news_surfaces,
    compatibility_news_snippet,
    finalized_current_news_projection,
    validate_finalized_news_projection,
    validate_news_surface_parity,
)
from scripts.orchestrator.validate_ai_dev_211_chatgpt_artifact_transport_v1 import validate as validate_ai211
from scripts.orchestrator.validate_ai_dev_212_research_semantic_visual_integrity_v1 import validate as validate_ai212

OBSERVED = "2026-08-13T12:00:00Z"


def raw_news(title: str, *, related: list[str] | None = None, summary: str = "") -> dict:
    return {
        "content": {
            "title": title,
            "summary": summary,
            "provider": {"displayName": "Fixture Financial News"},
            "pubDate": "2026-08-13T11:00:00Z",
            "canonicalUrl": {"url": "https://example.test/" + str(sum(map(ord, title))),},
            "relatedTickers": related or [],
            "contentType": "STORY",
        }
    }


def attributed(symbol: str, item: dict) -> tuple[list[dict], dict]:
    return normalize_yfinance_news([item], symbol=symbol, observed_at=OBSERVED)


def funnel(*, admitted: int, used: int, rendered: int, absence: str, reasons: dict | None = None) -> dict:
    stages = {stage: 0 for stage in NEWS_STAGES}
    stages.update({"DISCOVERED": max(admitted, 1), "RETRIEVED": max(admitted, 1), "NORMALIZED": max(admitted, 1),
                   "SYMBOL_ATTRIBUTED": admitted, "QUALITY_QUALIFIED": admitted, "FRESH": admitted,
                   "RELEVANT": admitted, "MATERIAL": admitted, "DEDUPLICATED": admitted,
                   "ADMITTED": admitted, "RRE_USED": used, "RENDERED": rendered})
    return {
        "schema_version": "cross_market_research_news_funnel_v1",
        "count_semantics": "EXACT", "stages": stages,
        "rejection_reasons": reasons or {}, "absence_state": absence,
        "retrieval": {"status": "SUCCESS", "reason_code": None},
    }


def selected_item(news_id: str, headline: str) -> dict:
    return {
        "news_id": news_id, "headline": headline, "english_headline": headline,
        "publisher": "Fixture Financial News", "published_at": "2026-08-13T11:00:00Z",
        "source_class": "recognized_financial_media", "source_reference": f"https://example.test/{news_id}",
        "freshness": "current", "direction": "unavailable", "direction_status": "NOT_EVALUATED",
        "selection_status": "SELECTED_AND_RENDERED", "selected_for_rre": True, "rendered": True,
        "entity_attribution": {
            "contract_version": "us_entity_subject_resolution_v4",
            "classification": "PRIMARY_SUBJECT",
            "attribution_class": "PRIMARY_SUBJECT",
            "reason": "FIXTURE_PRIMARY_SUBJECT",
            "attribution_reason": "FIXTURE_PRIMARY_SUBJECT",
            "target_symbol": "FIXTURE",
            "target_entity": "Fixture Company",
            "headline_subject": "Fixture Company",
            "competing_entities": [],
            "relationship_type": None,
            "framing_class": "PRIMARY_COMPANY_EVENT",
            "confidence": "high",
            "status": "ACCEPTED",
        },
    }


def bundle_with_selected(item: dict) -> dict:
    return {
        "news_intelligence_v2": {
            "selected_items": [item],
            "evidence_funnel": funnel(admitted=1, used=1, rendered=1, absence="NEWS_SELECTED_AND_RENDERED"),
        },
        "research_intelligence_v2": {"selected_news_evidence": [item]},
    }


def narrative(symbol: str, headline: str, event_type: str) -> dict:
    return build_event_narrative(symbol, {
        "news_id": f"news-{symbol}", "headline": headline, "summary": headline,
        "publisher": "Fixture", "event_type": event_type,
    }, "insufficient_evidence")


def validate() -> dict:
    checks: dict[str, bool] = {}
    details: dict[str, object] = {}

    googl_roundup, googl_roundup_diag = attributed(
        "GOOGL", raw_news("S&P and Nasdaq react after CPI; GOOGL, TSLA, NVDA stocks in focus", related=["GOOGL", "TSLA", "NVDA"]),
    )
    googl_product, _ = attributed("GOOGL", raw_news("Google launches new Pixel and Gemini product features", related=["GOOGL"]))
    tsm_asml, _ = attributed("TSM", raw_news("TSM and ASML expand advanced-node capacity partnership", related=["TSM", "ASML"]))
    nvda_partner, _ = attributed("NVDA", raw_news("Nvidia partners with Verizon on AI infrastructure", related=["NVDA", "VZ"]))
    weak, weak_diag = attributed("GOOGL", raw_news("Abbott Laboratories announces clinical results", summary="GOOGL appeared in a contextual market list"))
    checks["case_a_googl_roundup_contextual_not_company"] = not googl_roundup and bool(googl_roundup_diag["rejection_reasons"].get("MARKET_ROUNDUP_NOT_COMPANY_EVIDENCE"))
    checks["case_b_googl_product_primary"] = bool(googl_product) and googl_product[0]["entity_attribution"]["attribution_class"] == "PRIMARY_SUBJECT"
    checks["case_c_tsm_asml_material_co_subject"] = bool(tsm_asml) and tsm_asml[0]["entity_attribution"]["attribution_class"] == "MATERIAL_CO_SUBJECT"
    checks["case_d_nvda_partnership_material_co_subject"] = bool(nvda_partner) and nvda_partner[0]["entity_attribution"]["attribution_class"] == "MATERIAL_CO_SUBJECT"
    checks["case_e_summary_only_comention_rejected"] = not weak and bool(weak_diag["rejection_reasons"].get("WEAK_CONTEXTUAL_COMENTION"))

    primary = selected_item("news-a", "Company-specific News A")
    projection = finalized_current_news_projection(bundle_with_selected(primary))
    surface = compatibility_news_snippet(projection)
    mutation_b = dict(surface, canonical_news_id="news-b")
    mutation_none = dict(surface, canonical_news_state="NO_RELEVANT")
    checks["case_f_dual_headline_mutation_fails"] = bool(validate_news_surface_parity(projection, [mutation_b]))
    checks["case_g_available_no_news_mutation_fails"] = bool(validate_news_surface_parity(projection, [mutation_none]))

    filtered_bundle = {"news_intelligence_v2": {"selected_items": [], "evidence_funnel": funnel(
        admitted=0, used=0, rendered=0, absence="NEWS_DISCOVERED_BUT_FILTERED",
        reasons={"SYMBOL_ATTRIBUTION_FAILED": 1},
    )}, "research_intelligence_v2": {}}
    filtered_projection = finalized_current_news_projection(filtered_bundle)
    filtered_mutation = dict(compatibility_news_snippet(filtered_projection), canonical_news_state="STALE_ONLY")
    checks["case_h_filtered_stale_mutation_fails"] = bool(validate_news_surface_parity(filtered_projection, [filtered_mutation]))
    false_stale = dict(filtered_projection, state="STALE_ONLY", reason_code="STALE_ONLY")
    checks["case_i_stale_requires_evidence"] = "stale_without_stale_evidence" in validate_finalized_news_projection(false_stale)
    checks["case_j_spcx_filtered_truthful_label"] = (
        filtered_projection["state"] == "DISCOVERED_BUT_FILTERED"
        and "相關性／品質" in filtered_projection["state_label"]
        and "過期" not in filtered_projection["state_label"]
    )

    narratives = {
        "AAPL": narrative("AAPL", "Apple signs publisher partnership for Siri", "partnership"),
        "NVDA": narrative("NVDA", "Nvidia partners with Verizon on AI infrastructure", "partnership"),
        "TSLA": narrative("TSLA", "Tesla delivery wait times lengthen", "product"),
        "TSM": narrative("TSM", "TSM and ASML expand advanced-node capacity", "supply_chain"),
    }
    checks["case_k_aapl_event_counter"] = "商業規模" in narratives["AAPL"]["counter_argument"]
    checks["case_l_nvda_event_counter"] = "營收實現" in narratives["NVDA"]["counter_argument"]
    checks["case_m_tsla_event_counter"] = "供應限制" in narratives["TSLA"]["counter_argument"]
    checks["case_n_tsm_event_counter"] = "利用率" in narratives["TSM"]["counter_argument"]
    checks["case_o_boundary_is_not_counter"] = all(
        value["research_boundary_note"] != value["counter_argument"] for value in narratives.values()
    )
    semantic_tuples = {
        (value["event_family"], value["mechanism"], value["uncertainty_family"], value["evidence_reference"])
        for value in narratives.values()
    }
    checks["case_p_semantic_event_family_anti_cheat"] = len(semantic_tuples) == len(narratives)

    base212 = validate_ai212()
    directionless = normalize_news([{
        "english_headline": "Google product update without safe direction", "publisher": "Fixture",
        "published_at": "2026-08-13T11:00:00Z", "source_url": "https://example.test/directionless",
        "direction": "unavailable", "materiality": "high", "relevance": "high",
    }], OBSERVED, funnel(admitted=1, used=0, rendered=0, absence="NEWS_ADMITTED_NOT_SELECTED"))
    checks["case_q_market_only_direction_regression"] = base212["checks"].get("case_2_market_context_cannot_establish_company_direction") is True
    checks["case_r_directionless_zero_direction"] = directionless["directional_contribution"] == {"bullish": 0, "bearish": 0}
    checks["case_s_six_symbol_natural_shaped_replay"] = all((
        checks["case_b_googl_product_primary"], checks["case_a_googl_roundup_contextual_not_company"],
        checks["case_c_tsm_asml_material_co_subject"], checks["case_j_spcx_filtered_truthful_label"],
        checks["case_k_aapl_event_counter"], checks["case_m_tsla_event_counter"],
    ))
    checks["case_t_cjk_visual_regression"] = (
        base212["checks"].get("case_7_real_chromium_cjk_visual_gate") is True
        and base212["checks"].get("case_7_png_pdf_manifest_hash_integrity") is True
    )
    production_card, production_research = {"research_sections": {}}, {}
    applied = apply_finalized_news_surfaces(production_card, production_research, bundle_with_selected(primary))
    checks["case_u_coverage_and_news_projection_parity"] = (
        not validate_news_surface_parity(applied, [production_card["bilingual_news_snippet"]])
        and production_card["research_sections"]["material_news"]["canonical_news_id"] == "news-a"
        and production_research["material_news"]["compatibility_source"] == "finalized_current_news_projection_v3"
    )
    checks["case_v_decision_ownership_unchanged"] = base212["checks"].get("case_8_decision_boundary_unchanged") is True
    ai211 = validate_ai211()
    checks["case_w_ai211_transport_regression"] = ai211.get("ok") is True

    details.update({
        "attribution": {
            "roundup_rejections": googl_roundup_diag["rejection_reasons"],
            "googl_product": googl_product[0]["entity_attribution"] if googl_product else None,
            "tsm_asml": tsm_asml[0]["entity_attribution"] if tsm_asml else None,
            "nvda_partner": nvda_partner[0]["entity_attribution"] if nvda_partner else None,
        },
        "finalized_projection": projection,
        "filtered_projection": filtered_projection,
        "narratives": narratives,
        "ai212_regression": base212.get("ok"),
        "ai211_regression": ai211.get("ok"),
    })
    return {
        "task_id": "AI-DEV-212-H2", "contract_version": "ai_dev_212_h2_v2",
        "ok": all(checks.values()), "checks": checks, "details": details,
        "errors": [name for name, passed in checks.items() if not passed],
        "safety": {
            "production_pipeline": False, "network": False, "notifications": False,
            "trading": False, "production_db": False, "immutable_history": False,
            "decision_behavior_changed": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    result = validate()
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
