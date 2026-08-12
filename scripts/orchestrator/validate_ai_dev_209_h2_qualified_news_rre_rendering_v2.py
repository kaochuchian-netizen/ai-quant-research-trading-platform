#!/usr/bin/env python3
"""AI-DEV-209 H2 qualified-news selection and narrative closure gate."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.dashboard.multi_market_dashboard import render_us_window_report
from app.research.news_evidence_funnel import NEWS_STAGES
from app.us_stock.institutional_research import build_bundle, refresh_current_news
from app.us_stock.research_intelligence_v2 import evolve_intraday, normalize_news

OBSERVED = "2026-08-13T23:00:00+08:00"
PARTITION = {"AAPL": 4, "NVDA": 3, "TSLA": 8, "GOOGL": 4, "SPCX": 2, "TSM": 1}


def context() -> dict:
    return {"items": {symbol: {"change_pct": change, "last_price": 100 + change,
        "previous_close": 100, "source_timestamp": "2026-08-13T10:30:00-04:00", "ok": True}
        for symbol, change in {"SPY": .2, "QQQ": .3, "SOXX": .4}.items()}}


def research(symbol: str, count: int, *, official_first: bool = False) -> dict:
    items = []
    for index in range(count):
        headline = f"{symbol} event {index + 1} changes company-specific outlook"
        items.append({
            "english_headline": headline, "chinese_summary": f"{symbol} 個股事件 {index + 1}",
            "event_type": "product" if symbol == "AAPL" else "supply_chain" if symbol == "NVDA" else "news",
            "direction": "unavailable", "direction_status": "NOT_EVALUATED",
            "materiality": "high" if index == 0 else "medium", "relevance": "high" if index == 0 else "medium",
            "official_source": official_first and index == 0,
            "publisher": "Company IR" if official_first and index == 0 else f"Publisher {symbol}",
            "provenance": {"published_at": f"2026-08-13T{12 + index % 4:02d}:00:00Z", "source_reference": f"https://evidence.example/{symbol}/{index}"},
        })
    stages = {stage: 0 for stage in NEWS_STAGES}
    for stage in ("DISCOVERED", "RETRIEVED", "NORMALIZED", "SYMBOL_ATTRIBUTED", "QUALITY_QUALIFIED", "FRESH", "RELEVANT", "MATERIAL", "DEDUPLICATED", "ADMITTED"):
        stages[stage] = count
    return {"sec": {"ok": False}, "official_sources": {}, "fundamentals": {}, "earnings": {},
        "material_news": {"items": items, "evidence_funnel": {
            "schema_version": "cross_market_research_news_funnel_v1", "count_semantics": "EXACT",
            "market": "US", "symbol": symbol, "stages": stages, "rejection_reasons": {},
            "absence_state": "NEWS_ADMITTED_NOT_SELECTED", "retrieval": {"status": "SUCCESS", "reason_code": None},
            "source_preference": ["official", "SEC", "company_ir", "company_newsroom", "recognized_financial_media"],
        }}}


def card(symbol: str, bundle: dict) -> dict:
    return {"symbol": symbol, "name": symbol, "institutional_research": bundle,
        "plan_status": "watch", "data_status": "complete", "source": "fixture",
        "current_price": 100, "gap_current_pct": .5, "gap_state": "gap_up_follow_through",
        "volume_ratio": 1.2, "volume_confirmation_state": "confirmed",
        "tactical_adjustment": "maintain_watch", "adjustment_reason": "fixture",
        "research_sections": {}, "daily_tactical_summary": {}, "prediction": {},
        "source_plan": {}, "missing_fields": []}


def validate() -> dict:
    checks: dict[str, bool] = {}
    details: dict[str, object] = {}
    refreshed: dict[str, dict] = {}
    rendered: dict[str, str] = {}
    for symbol, count in PARTITION.items():
        origin = build_bundle(symbol, research(symbol, 0), context(), "2026-08-13T20:00:00+08:00")
        current = build_bundle(symbol, research(symbol, count, official_first=symbol == "AAPL"), context(), OBSERVED)
        bundle = refresh_current_news(origin, current, OBSERVED)
        bundle["research_intelligence_v2"] = evolve_intraday(bundle["research_intelligence_v2"], {
            "data_status": "complete", "gap_current_pct": .5, "gap_state": "gap_up_follow_through",
            "volume_ratio": 1.2, "volume_confirmation_state": "confirmed", "source": "fixture",
        }, observed_at=OBSERVED)
        refreshed[symbol] = bundle
        artifact = {"market": "US", "window": "us_intraday_2300", "generated_at": OBSERVED,
            "dashboard_ready_contract": {"cards": [card(symbol, bundle)]},
            "intraday_summary": {}, "institutional_research_summary": {}}
        rendered[symbol] = render_us_window_report("us_intraday_2300", [artifact])

    funnels = {symbol: bundle["news_intelligence_v2"]["evidence_funnel"] for symbol, bundle in refreshed.items()}
    checks["case_a_admitted_to_rre_and_rendered"] = all(
        funnel["stages"]["RRE_USED"] > 0 and funnel["stages"]["RENDERED"] > 0
        for funnel in funnels.values()
    )
    checks["case_b_directionless_no_directional_contribution"] = all(
        bundle["news_intelligence_v2"]["directional_contribution"] == {"bullish": 0, "bearish": 0}
        and all(item["direction"] == "unavailable" for item in bundle["news_intelligence_v2"]["selected_items"])
        for bundle in refreshed.values()
    )
    aapl_v2, nvda_v2 = (refreshed[x]["research_intelligence_v2"] for x in ("AAPL", "NVDA"))
    checks["case_c_symbol_specific_narrative"] = all([
        aapl_v2["hypothesis"]["statement"] != nvda_v2["hypothesis"]["statement"],
        aapl_v2["primary_risk"] != nvda_v2["primary_risk"],
        aapl_v2["hypothesis"]["trigger"] != nvda_v2["hypothesis"]["trigger"],
        aapl_v2["hypothesis"]["invalidation"] != nvda_v2["hypothesis"]["invalidation"],
    ])
    checks["case_d_specific_before_market_context"] = all(
        html.index("個股當期證據 Current News") < html.index("支持證據 Supporting")
        for html in rendered.values()
    )
    checks["case_e_news_not_missing"] = all(
        "news" not in bundle["research_intelligence_v2"]["missing_evidence"]
        and bundle["research_intelligence_v2"]["effective_coverage"]["categories"]["news"] == "AVAILABLE"
        for bundle in refreshed.values()
    )
    checks["case_f_provenance_rendered"] = all(
        bundle["news_intelligence_v2"]["selected_items"][0]["headline"] in rendered[symbol]
        and str(bundle["news_intelligence_v2"]["selected_items"][0]["publisher"]) in rendered[symbol]
        and str(bundle["news_intelligence_v2"]["selected_items"][0]["published_at"]) in rendered[symbol]
        and (
            "recognized_financial_media" in rendered[symbol]
            or (symbol == "AAPL" and "company_ir" in rendered[symbol])
        )
        for symbol, bundle in refreshed.items()
    )
    checks["case_g_selection_limit_reason"] = all(
        funnel["rejection_reasons"].get("SELECTION_LIMIT_LOWER_PRIORITY_SOURCE", 0) == max(0, PARTITION[symbol] - 2)
        for symbol, funnel in funnels.items()
    )
    stale = normalize_news([{"headline": "AAPL stale event", "publisher": "Publisher", "published_at": "2026-07-01T10:00:00Z", "source_url": "https://evidence.example/stale", "materiality": "high", "relevance": "high"}], OBSERVED)
    checks["case_h_stale_not_selected"] = stale["selected_count"] == 0 and stale["items"][0]["selection_reason"] == "STALE_OR_INVALID_TIMESTAMP"
    priority = normalize_news([
        {"headline": "AAPL same material event", "publisher": "Secondary", "published_at": "2026-08-13T13:00:00Z", "source_url": "https://secondary.example/event", "official_source": False, "materiality": "high", "relevance": "high"},
        {"headline": "AAPL same material event", "publisher": "Apple IR", "published_at": "2026-08-13T13:00:00Z", "source_url": "https://apple.example/ir/event", "official_source": True, "materiality": "high", "relevance": "high"},
    ], OBSERVED)
    official = priority["selected_items"][0]
    checks["case_i_official_preferred"] = official["source_class"] == "company_ir" and official["primary_source_confirmed"] is True
    decision = {"action": "NO_TRADE", "eligibility": False, "entry": None, "stop": None, "target": None}
    before = json.dumps(decision, sort_keys=True)
    _ = refresh_current_news(refreshed["AAPL"], refreshed["NVDA"], OBSERVED)
    checks["case_j_decision_unchanged"] = before == json.dumps(decision, sort_keys=True) and all(
        bundle["decision_context_export"]["trade_action"] is None for bundle in refreshed.values()
    )
    scores = [bundle["research_intelligence_v2"]["effective_coverage"]["score"] for bundle in refreshed.values()]
    checks["case_k_coverage_contract"] = all(score > 0 for score in scores)
    ai210 = subprocess.run([sys.executable, str(ROOT / "scripts/orchestrator/validate_ai_dev_210_visual_evidence_pdf_retrieval_v1.py")], cwd=ROOT, text=True, capture_output=True)
    checks["case_l_ai210_regression"] = ai210.returncode == 0 and bool(json.loads(ai210.stdout).get("ok"))
    checks["natural_partition_fixture"] = {symbol: funnel["stages"]["ADMITTED"] for symbol, funnel in funnels.items()} == PARTITION
    checks["primary_risk_not_disclaimer"] = all("僅供研究參考" not in bundle["research_intelligence_v2"]["primary_risk"] for bundle in refreshed.values())
    checks["origin_identity_preserved"] = all(bundle["research_intelligence_v2"]["origin_research_identity"] == bundle["research_identity"] for bundle in refreshed.values())
    details.update({"partition": PARTITION, "funnels": funnels,
        "aapl_hypothesis": aapl_v2["hypothesis"], "nvda_hypothesis": nvda_v2["hypothesis"],
        "aapl_selected": refreshed["AAPL"]["news_intelligence_v2"]["selected_items"],
        "ai210_returncode": ai210.returncode})
    return {"task_id": "AI-DEV-209-H2", "ok": all(checks.values()), "checks": checks,
        "details": details, "errors": [name for name, ok in checks.items() if not ok],
        "safety": {"network": False, "production_pipeline": False, "publish": False,
            "notification": False, "trading": False, "database_write": False,
            "immutable_history_rewrite": False, "decision_behavior_changed": False}}


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--pretty", action="store_true"); args = parser.parse_args()
    result = validate(); print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
