#!/usr/bin/env python3
"""Deterministic AI-DEV-197 institutional research layer validation."""
from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.dashboard.multi_market_dashboard import render_us_window_report
from app.runtime.operations_provenance import build_operations_provenance
from app.us_stock.institutional_research import (
    PROVIDERS, aggregate_bundles, build_bundle, deduplicate, evidence_record,
    resolve_bundle, validate_bundle,
)
from scripts.orchestrator.approved_us_stock_delivery import build_email_body, line_text


def fixture_research() -> dict:
    provenance = {"retrieved_at": "2026-07-30T19:55:00+08:00"}
    return {
        "sec": {"ok": True, "provenance": provenance, "filings": [{"form": "10-Q", "filing_date": "2026-07-29", "accession": "0001", "filing_url": "https://www.sec.gov/example"}]},
        "official_sources": {"investor_relations_url": "https://investor.apple.com/", "sec_company_page": "https://www.sec.gov/edgar/browse/"},
        "fundamentals": {"metrics": {"revenue": {"value": 100}, "operating_margin": {"value": .3}}, "comparison": {"trend_direction": "positive"}},
        "earnings": {"latest_earnings": {"actual_eps": 2.1, "actual_revenue": 100, "reported_date": "2026-07-28"}},
        "material_news": {"items": [{"english_headline": "Apple expands AI services", "chinese_summary": "公司擴大 AI 服務", "event_type": "ai", "direction": "bullish", "materiality": "high", "relevance": "high", "official_source": False, "provenance": {"published_at": "2026-07-30T10:00:00-04:00", "source_reference": "wire-1"}}]},
    }


def fixture_context() -> dict:
    return {"spy": {"change_pct": .2, "timestamp": "2026-07-30T08:00:00-04:00"}, "qqq": {"change_pct": .4, "timestamp": "2026-07-30T08:00:00-04:00"}, "soxx": {"change_pct": .6, "timestamp": "2026-07-30T08:00:00-04:00"}}


def card(symbol: str, bundle: dict) -> dict:
    return {"symbol": symbol, "name": symbol, "institutional_research": bundle,
            "research_identity": bundle["research_identity"], "eligibility": {"watch_only": True},
            "trade_plan": {"status": "watch"}, "daily_tactical_summary": {},
            "research_sections": {}, "prediction_range_result": "pending",
            "trade_review_outcome": "pending_evidence", "review": {}}


def ast_function(source: str, name: str) -> str:
    tree = ast.parse(source)
    node = next(item for item in tree.body if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == name)
    return ast.dump(node, include_attributes=False)


def decision_boundary_checks() -> dict:
    current = (ROOT / "app/us_stock/live_pipeline.py").read_text(encoding="utf-8")
    baseline = subprocess.run(["git", "show", "main:app/us_stock/live_pipeline.py"], cwd=ROOT, text=True, capture_output=True, check=True).stdout
    names = ("rating_action", "score_symbol", "prediction_for_symbol")
    return {name: ast_function(current, name) == ast_function(baseline, name) for name in names}


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--pretty", action="store_true"); args = parser.parse_args()
    observed_at = "2026-07-30T20:00:00+08:00"
    bundle = build_bundle("AAPL", fixture_research(), fixture_context(), observed_at)
    errors = validate_bundle(bundle)

    same = evidence_record("AAPL", "yfinance", "C", "Same official event", "secondary", observed_at, "product", published_at="2026-07-30T10:00:00-04:00", direction="bullish", reference="official-1")
    official = evidence_record("AAPL", "company_ir", "A", "Same official event", "official", observed_at, "product", published_at="2026-07-30T10:00:00-04:00", direction="bullish", confidence=.95, official=True, reference="official-1")
    deduped = deduplicate([same, official])
    conflict_positive = evidence_record("AAPL", "company_ir", "A", "Guidance raised", "positive", observed_at, "guidance", direction="bullish", materiality="high", official=True)
    conflict_negative = evidence_record("AAPL", "sec_edgar", "A", "Material litigation", "negative", observed_at, "litigation", direction="bearish", materiality="high", official=True)
    from app.us_stock.institutional_research import analyze_conflict
    conflict = analyze_conflict([conflict_positive, conflict_negative])
    low_quality = evidence_record("AAPL", "social_unverified", "D", "Unverified rumor", "rumor", observed_at, "sentiment", direction="bullish", confidence=.4)
    from app.us_stock.institutional_research import analyze_coverage, company_knowledge, provider_snapshot, synthesize
    low_coverage = analyze_coverage([low_quality], company_knowledge("AAPL", fixture_research()), provider_snapshot(fixture_research(), fixture_context()))
    low_synthesis = synthesize([low_quality], low_coverage, analyze_conflict([low_quality]))
    invalid_trade_export = json.loads(json.dumps(bundle)); invalid_trade_export["decision_context_export"]["trade_action"] = "BUY"
    invalid_market = json.loads(json.dumps(bundle)); invalid_market["market"] = "TW"
    invalid_evidence = json.loads(json.dumps(bundle)); invalid_evidence["evidence"][0]["provider"] = None

    with tempfile.TemporaryDirectory(prefix="ai197_") as tmp:
        archive = Path(tmp); folder = archive / "us/us_pre_market_2000/2026-07-30"; folder.mkdir(parents=True)
        wrapper = {"admitted": True, "effective_trading_date": "2026-07-30", "snapshot_id": "snapshot-20", "revision": 2, "admitted_at": observed_at, "source_payload_hash": "source-hash", "payload": {"dashboard_ready_contract": {"cards": [card("AAPL", bundle)]}}}
        (folder / "revision-2.json").write_text(json.dumps(wrapper), encoding="utf-8")
        inherited = resolve_bundle(archive, "2026-07-30", "AAPL")

    cards = [card("AAPL", bundle)]
    summary = aggregate_bundles(cards)
    fixture_symbols = ("AAPL", "NVDA", "TSLA", "GOOGL", "TSM", "SPCX")
    metric_cards = [
        card(symbol, build_bundle(symbol, fixture_research(), fixture_context(), observed_at))
        for symbol in fixture_symbols
    ]
    metric_summary = aggregate_bundles(metric_cards)
    artifact = {"market": "US", "window": "us_pre_market_2000", "generated_at": observed_at,
                "runtime_watchlist_validation": {"enabled_stock_count": 1},
                "dashboard_ready_contract": {"cards": cards},
                "premarket_summary": {"tracking_count": 1, "top_opportunity_count": 0, "entry_ready_count": 0, "watch_only_count": 1, "no_trade_count": 0, "groups": {"top_opportunity": [], "watch_only": ["AAPL"], "no_trade": []}, "market_context": {}},
                "premarket_contract": {"valid": True}, "institutional_research_summary": summary}
    dashboard = render_us_window_report("us_pre_market_2000", [artifact])
    email = build_email_body(artifact, "us_pre_market_2000")
    line = line_text(artifact, "us_pre_market_2000")
    snapshot = {"snapshot_id": "snapshot-20", "effective_trading_date": "2026-07-30", "revision": 1, "payload": artifact}
    operations = build_operations_provenance(market="US", window="us_pre_market_2000", runtime_status="completed", runtime_trading_date="2026-07-30", snapshot=snapshot, public_sync={"status": "verified", "source_payload_hash": "source-hash"}, email_result="not_attempted", line_result="not_attempted")
    three_window_outputs = {}
    for window in ("us_pre_market_2000", "us_intraday_2300", "us_post_close_review_0630"):
        window_card = card("AAPL", bundle)
        window_card.update({"plan_status": "watch", "data_status": "complete", "canonical_outcome": "pending", "trade_outcome": "pending", "trade_review_outcome": "pending_evidence", "source_trade_plan": {}, "intraday_evidence": {}})
        window_artifact = {**artifact, "window": window, "dashboard_ready_contract": {"cards": [window_card]}, "institutional_research_summary": summary}
        if window == "us_intraday_2300":
            window_artifact.update({"structured_intraday_cards": [window_card], "intraday_summary": {"tracking_count": 1, "structured_card_count": 1, "active_plan_count": 0, "watch_only_count": 1, "no_trade_count": 0, "groups": {"top_opportunity": [], "still_actionable": [], "invalidated": [], "watch_only": ["AAPL"], "no_trade": []}}})
        if window == "us_post_close_review_0630":
            window_artifact.update({"structured_review_cards": [window_card], "session_context": {"session_date": "2026-07-30"}})
        three_window_outputs[window] = {
            "dashboard": render_us_window_report(window, [window_artifact]),
            "email": build_email_body(window_artifact, window),
            "line": line_text(window_artifact, window),
        }
    boundary = decision_boundary_checks()
    checks = {
        "provider_registry": len(PROVIDERS) >= 20 and all(key in PROVIDERS[0] for key in ("provider_id", "tier", "license", "status", "capability")),
        "actual_connected_providers_truthful": {x["provider_id"] for x in bundle["providers"] if x["availability"] == "AVAILABLE"} == {"sec_edgar", "yfinance"} and next(x for x in bundle["providers"] if x["provider_id"] == "company_ir")["availability"] == "CONFIGURED",
        "registry_only_providers_visible": any(x["availability"] == "NOT_LICENSED" for x in bundle["providers"]) and any(x["availability"] == "NOT_CONFIGURED" for x in bundle["providers"]),
        "evidence_integrity": not errors and all(x.get("provider") and x.get("observed_at") and x.get("quality_score") for x in bundle["evidence"]),
        "duplicate_detection": len(deduped) == 2 and sum(x["counted_in_synthesis"] for x in deduped) == 1 and next(x for x in deduped if x["counted_in_synthesis"])["provider"] == "company_ir",
        "coverage_transparency": bundle["coverage"]["unlicensed_is_failure"] is False and bundle["coverage"]["categories"]["options"] == "NOT_CONFIGURED",
        "conflict_detection": conflict["level"] == "HIGH",
        "event_classification": evidence_record("AAPL", "yfinance", "C", "Product launch", "event", observed_at, "product_launch")["event_type"] == "product",
        "knowledge_layer": bundle["knowledge"]["status"] == "AVAILABLE" and all(key in bundle["knowledge"]["dimensions"] for key in ("business", "revenue_drivers", "risk_factors", "catalysts")),
        "six_symbol_knowledge_coverage": all(item["institutional_research"]["knowledge"]["status"] == "AVAILABLE" for item in metric_cards),
        "research_not_trade_score": bundle["synthesis"]["research_score_is_trade_score"] is False and bundle["decision_context_export"]["trade_action"] is None,
        "low_quality_cannot_dominate": low_synthesis["research_stance"] == "insufficient_evidence",
        "negative_trade_action_rejected": "trade_action_exported" in validate_bundle(invalid_trade_export),
        "negative_cross_market_rejected": "market_must_be_us" in validate_bundle(invalid_market),
        "negative_missing_source_rejected": "evidence_missing:provider" in validate_bundle(invalid_evidence),
        "three_window_identity_binding": inherited is not None and inherited["research_identity"] == bundle["research_identity"] and inherited["continuity"]["source_snapshot_id"] == "snapshot-20",
        "dashboard_render": bundle["research_identity"] in dashboard and "機構研究脈絡" in dashboard,
        "email_preview": bundle["research_identity"] in email and "非交易分數" in email,
        "line_preview": summary["research_summary_hash"][:12] in line,
        "operations_parity": operations["research_summary_hash"] == summary["research_summary_hash"] and operations["research_identity_bindings"][0]["research_identity"] == bundle["research_identity"],
        "three_window_channel_parity": all(
            bundle["research_identity"] in output["dashboard"]
            and bundle["research_identity"] in output["email"]
            and summary["research_summary_hash"][:12] in output["line"]
            for output in three_window_outputs.values()
        ),
        "decision_functions_unchanged": all(boundary.values()),
        "tw_isolation": bundle["market"] == "US" and all(x["market"] == "US" for x in bundle["evidence"]),
    }
    result = {"task_id": "AI-DEV-197", "ok": all(checks.values()), "checks": checks, "errors": errors,
              "metrics": {"symbol_count": len(metric_cards), "connected_providers": sorted(x["provider_id"] for x in bundle["providers"] if x["availability"] == "AVAILABLE"), "registry_only_providers": sorted(x["provider_id"] for x in bundle["providers"] if x["availability"] in {"NOT_CONFIGURED", "NOT_LICENSED"}), "average_coverage_score": metric_summary["average_coverage_score"], "average_deduplicated_event_count": metric_summary["average_deduplicated_event_count"], "single_source_stance_symbols": metric_summary["single_source_stance_symbols"]},
              "decision_boundary_ast": boundary,
              "safety": {"production_pipeline": False, "email_attempted": False, "line_attempted": False, "trading": False, "scheduler_changed": False, "secrets_accessed": False, "tw_pipeline_changed": False}}
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
