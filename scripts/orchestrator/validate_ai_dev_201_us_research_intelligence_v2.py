#!/usr/bin/env python3
"""Deterministic AI-DEV-201 research, continuity, and calibration gate."""
from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.dashboard.multi_market_dashboard import render_us_window_report
from app.runtime.operations_provenance import build_operations_provenance
from app.us_stock.institutional_research import aggregate_bundles, build_bundle, validate_bundle
from app.us_stock.research_intelligence_v2 import (
    BOUNDARY, classify_sec_filing, evolve_intraday, evolve_post_close,
    normalize_news, prediction_evaluation, validate_projection,
)
from scripts.orchestrator.approved_us_stock_delivery import build_email_body, line_text


OBSERVED = "2026-08-07T20:00:00+08:00"


def research_fixture(symbol: str, direction: str = "neutral", *, filing: dict | None = None, news: bool = True) -> dict:
    item = {
        "english_headline": f"{symbol} demand outlook update",
        "chinese_summary": f"{symbol} 需求展望更新",
        "event_type": "guidance", "direction": direction,
        "materiality": "high", "relevance": "high", "official_source": False,
        "provenance": {"published_at": "2026-08-07T07:00:00-04:00", "source_reference": f"wire-{symbol}"},
    }
    return {
        "sec": {"ok": True, "provenance": {"retrieved_at": OBSERVED}, "filings": [filing or {"form": "10-Q", "filing_date": "2026-08-06", "item": "Results of Operations", "accession": f"{symbol}-10q"}]},
        "official_sources": {"investor_relations_url": f"https://example.com/{symbol}/ir", "sec_company_page": "https://www.sec.gov/edgar/"},
        "fundamentals": {"metrics": {"revenue": {"value": 100}}, "comparison": {"trend_direction": direction}},
        "earnings": {"latest_earnings": {"actual_eps": 1.2, "actual_revenue": 100, "reported_date": "2026-08-01"}},
        "material_news": {"items": [item] if news else []},
    }


def context(*, spy: float = 0.02, qqq: float = 0.01, soxx: float = 1.55) -> dict:
    return {
        "spy": {"change_pct": spy, "timestamp": "2026-08-07T08:00:00-04:00"},
        "qqq": {"change_pct": qqq, "timestamp": "2026-08-07T08:00:00-04:00"},
        "soxx": {"change_pct": soxx, "timestamp": "2026-08-07T08:00:00-04:00"},
    }


def card(symbol: str, bundle: dict, *, window: str) -> dict:
    base = {
        "symbol": symbol, "name": symbol, "institutional_research": bundle,
        "research_identity": bundle["research_identity"], "eligibility": {"watch_only": True},
        "trade_plan": {"status": "watch"}, "daily_tactical_summary": {}, "research_sections": {},
        "prediction_range_result": "pending", "trade_outcome": "pending",
        "canonical_outcome": "pending", "trade_review_outcome": "pending_evidence", "review": {},
        "source_trade_plan": {}, "intraday_evidence": {}, "plan_status": "watch", "data_status": "complete",
    }
    base["window_research_identity"] = (bundle.get("research_intelligence_v2") or {}).get("window_research_identity")
    return base


def artifact_for(window: str, cards: list[dict]) -> dict:
    summary = aggregate_bundles(cards)
    artifact = {
        "market": "US", "window": window, "generated_at": OBSERVED,
        "session_context": {"session_date": "2026-08-07", "reference_new_york": "2026-08-07T08:00:00-04:00"},
        "runtime_watchlist_validation": {"enabled_stock_count": len(cards)},
        "dashboard_ready_contract": {"cards": cards}, "institutional_research_summary": summary,
        "premarket_summary": {"tracking_count": len(cards), "top_opportunity_count": 0, "entry_ready_count": 0, "watch_only_count": len(cards), "no_trade_count": 0, "groups": {"top_opportunity": [], "watch_only": [x["symbol"] for x in cards], "no_trade": []}, "market_context": {}},
        "premarket_contract": {"valid": True},
        "structured_intraday_cards": cards if window == "us_intraday_2300" else [],
        "intraday_summary": {"tracking_count": len(cards), "structured_card_count": len(cards), "active_plan_count": 0, "watch_only_count": len(cards), "no_trade_count": 0, "groups": {"top_opportunity": [], "still_actionable": [], "invalidated": [], "watch_only": [x["symbol"] for x in cards], "no_trade": []}} if window == "us_intraday_2300" else None,
        "structured_review_cards": cards if window == "us_post_close_review_0630" else [],
    }
    return artifact


def function_ast(path: str, name: str, revision: str = "main") -> bool:
    current = (ROOT / path).read_text(encoding="utf-8")
    baseline = subprocess.run(["git", "show", f"{revision}:{path}"], cwd=ROOT, text=True, capture_output=True, check=True).stdout
    def find(source: str) -> str:
        tree = ast.parse(source)
        node = next(x for x in tree.body if isinstance(x, ast.FunctionDef) and x.name == name)
        return ast.dump(node, include_attributes=False)
    return find(current) == find(baseline)


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--pretty", action="store_true"); args = parser.parse_args()

    nvda = build_bundle("NVDA", research_fixture("NVDA", "bullish"), context(), OBSERVED)
    tsla = build_bundle("TSLA", research_fixture("TSLA", "bearish"), context(soxx=-0.4), OBSERVED)
    aapl = build_bundle("AAPL", research_fixture("AAPL", "neutral", filing={"form": "8-K", "filing_date": "2026-08-07", "item": "2.02 Results of Operations", "summary": "Earnings release furnished", "accession": "aapl-8k"}, news=False), context(soxx=0.1), OBSERVED)
    nvda_origin = nvda["research_intelligence_v2"]
    tsla_origin = tsla["research_intelligence_v2"]
    nvda_observed = {"data_status": "complete", "gap_current_pct": 1.25, "gap_state": "gap_up_follow_through", "volume_ratio": 1.45, "volume_confirmation_state": "strong", "source": "yfinance"}
    tsla_observed = {"data_status": "complete", "gap_current_pct": 2.6, "gap_state": "gap_up_follow_through", "volume_ratio": 1.94, "volume_confirmation_state": "strong", "source": "yfinance"}
    insufficient_observed = {"data_status": "stale", "gap_current_pct": None, "gap_state": "unavailable", "volume_ratio": None, "source": "yfinance"}
    nvda_intraday = evolve_intraday(nvda_origin, nvda_observed, observed_at="2026-08-07T23:00:00+08:00")
    tsla_intraday = evolve_intraday(tsla_origin, tsla_observed, observed_at="2026-08-07T23:00:00+08:00")
    missing_intraday = evolve_intraday(aapl["research_intelligence_v2"], insufficient_observed, observed_at="2026-08-07T23:00:00+08:00")
    prediction = {"predicted_session_low": 175.0, "predicted_session_high": 185.0, "reference_price": 179.0, "direction_forecast": "bullish", "direction_probability": 65, "direction_probability_method": "deterministic_fixture_v1"}
    review = {"actual_low": 176.0, "actual_high": 184.0, "actual_close": 181.0, "prediction_range_result": "hit", "high_error": -1.0, "low_error": 1.0, "trade_review_outcome": "no_trade"}
    post = evolve_post_close(nvda_origin, nvda_observed, prediction, review, observed_at="2026-08-08T06:30:00+08:00")
    evaluation = prediction_evaluation(prediction, review)

    duplicate_news = normalize_news([
        {"headline": "Apple launches service", "published_at": "2026-08-07T10:00:00-04:00", "source_url": "wire-a", "direction": "bullish"},
        {"headline": "Apple launches service", "published_at": "2026-08-07T10:30:00-04:00", "source_url": "wire-b", "direction": "bullish"},
    ], OBSERVED)
    missing_news = normalize_news([], OBSERVED)

    intraday_nvda_bundle = json.loads(json.dumps(nvda)); intraday_nvda_bundle["research_intelligence_v2"] = nvda_intraday
    review_nvda_bundle = json.loads(json.dumps(nvda)); review_nvda_bundle["research_intelligence_v2"] = post
    windows = {
        "us_pre_market_2000": [card("NVDA", nvda, window="us_pre_market_2000")],
        "us_intraday_2300": [card("NVDA", intraday_nvda_bundle, window="us_intraday_2300")],
        "us_post_close_review_0630": [card("NVDA", review_nvda_bundle, window="us_post_close_review_0630")],
    }
    channel_checks = []
    public_outputs: list[str] = []
    for window, cards in windows.items():
        artifact = artifact_for(window, cards)
        dashboard = render_us_window_report(window, [artifact])
        email = build_email_body(artifact, window)
        line = line_text(artifact, window)
        public_outputs.extend((dashboard, email, line))
        summary = artifact["institutional_research_summary"]
        window_identity = cards[0]["institutional_research"]["research_intelligence_v2"]["window_research_identity"]
        snapshot = {"snapshot_id": f"snapshot-{window}", "effective_trading_date": "2026-08-07", "revision": 1, "payload": artifact}
        operations = build_operations_provenance(market="US", window=window, runtime_status="completed", runtime_trading_date="2026-08-07", snapshot=snapshot, public_sync={"status": "verified", "source_payload_hash": "hash"}, email_result="not_attempted", line_result="not_attempted")
        binding = operations["research_identity_bindings"][0]
        channel_checks.append(window_identity in dashboard and window_identity in email and summary["research_summary_hash"][:12] in line and binding["window_research_identity"] == window_identity)

    filing = classify_sec_filing({"form": "8-K", "item": "1.05", "summary": "Material cybersecurity incident"})
    unknown_filing = classify_sec_filing({"form": "8-K"})
    projection_errors = validate_projection(nvda_origin) + validate_projection(nvda_intraday) + validate_projection(post)
    bundle_errors = validate_bundle(nvda) + validate_bundle(tsla) + validate_bundle(aapl)
    checks = {
        "evidence_v2_contract": all(all(key in item for key in ("source", "source_class", "source_quality", "published_at", "observed_at", "freshness", "stale", "materiality", "direction", "role", "provenance", "fact", "interpretation", "evidence_nature")) and item.get("source") and item.get("observed_at") for item in nvda["evidence"]),
        "missing_not_neutral": not build_bundle("AAPL", {"sec": {"ok": False}, "official_sources": {}, "fundamentals": {}, "earnings": {}, "material_news": {"items": []}}, {}, OBSERVED)["evidence"],
        "sec_classification": filing["classification"] == "cybersecurity" and filing["materiality"] == "high",
        "sec_safe_fallback": unknown_filing["classification"] == "other" and unknown_filing["direction"] == "neutral" and not unknown_filing["direction_inferred"],
        "news_dedup": duplicate_news["deduplicated_count"] == 1 and sum(x["counted"] for x in duplicate_news["items"]) == 1,
        "news_missing_explicit": missing_news["status"] == "MISSING" and missing_news["missing_reason"] and missing_news["fabricated"] is False,
        "sector_not_flattened": nvda_origin["market_sector_context"]["sector"] == "bullish" and nvda_origin["market_sector_context"]["broad_market"] != nvda_origin["market_sector_context"]["sector"],
        "weighted_effective_coverage": nvda_origin["effective_coverage"]["used_as_trade_score"] is False and nvda_origin["effective_coverage"]["duplicate_evidence_counted"] is False,
        "secondary_context_contracts": all(key in nvda_origin["context_contracts"] for key in ("news", "macro", "options", "analyst", "insider")) and all(nvda_origin["context_contracts"][key]["status"] in {"AVAILABLE", "PARTIAL", "CONTRADICTORY", "STALE", "MISSING", "FAILED"} for key in ("news", "macro", "options", "analyst", "insider")),
        "research_differentiation": len({nvda_origin["research_stance"], tsla_origin["research_stance"], aapl["research_intelligence_v2"]["research_stance"]}) >= 2 and len({nvda_origin["window_research_identity"], tsla_origin["window_research_identity"], aapl["research_intelligence_v2"]["window_research_identity"]}) == 3,
        "no_universal_default_score": nvda_origin["research_score"] != tsla_origin["research_score"] and nvda_origin["research_score_is_trade_score"] is False,
        "nvda_strengthened": nvda_intraday["hypothesis"]["state"] in {"confirmed", "strengthened"},
        "tsla_contradicted": tsla_intraday["hypothesis"]["state"] in {"contradicted", "invalidated"},
        "insufficient_evidence_state": missing_intraday["hypothesis"]["state"] == "insufficient_new_evidence",
        "decision_ownership_preserved": all(not BOUNDARY[key] for key in ("action_exported", "eligibility_modified", "ranking_modified", "scoring_modified", "strategy_weights_modified", "prediction_model_modified", "auto_learning")),
        "prediction_evaluation": evaluation["range"]["interval_width"] == 10.0 and evaluation["range"]["midpoint_error"] == 0.0 and evaluation["direction"]["hit"] is True and evaluation["calibration"]["brier_score"] is not None,
        "wide_interval_truthfulness": evaluation["wide_interval_not_sufficient_success"] is True,
        "no_trade_learning": post["no_trade_learning"]["no_trade_still_evaluated"] is True and post["no_trade_learning"]["auto_learning"] is False,
        "carryforward": bool(post["next_session_carryforward"]["carryforward_reason"] and post["next_session_carryforward"]["missing_critical_sources"]),
        "origin_identity_immutable": all(x["origin_research_identity"] == nvda["research_identity"] for x in (nvda_origin, nvda_intraday, post)),
        "window_identity_evolves": len({nvda_origin["window_research_identity"], nvda_intraday["window_research_identity"], post["window_research_identity"]}) == 3,
        "channel_identity_parity": all(channel_checks),
        "public_research_state_localized": not any(marker in output for output in public_outputs for marker in (">strengthened<", ">contradicted<", ">invalidated<", ">insufficient_evidence<", "研究更新：strengthened", "研究更新：invalidated")),
        "projection_valid": not projection_errors and not bundle_errors,
        "decision_functions_unchanged": all(function_ast("app/us_stock/live_pipeline.py", name) for name in ("rating_action", "score_symbol", "prediction_for_symbol")),
        "market_isolation": all(item["market"] == "US" for bundle in (nvda, tsla, aapl) for item in bundle["evidence"]),
    }
    result = {
        "task_id": "AI-DEV-201", "ok": all(checks.values()), "checks": checks,
        "errors": sorted(set(projection_errors + bundle_errors)),
        "fixture_evidence": {
            "nvda_hypothesis": nvda_intraday["hypothesis"]["state"],
            "tsla_hypothesis": tsla_intraday["hypothesis"]["state"],
            "aapl_sec": [x.get("filing_intelligence") for x in aapl["evidence"] if x.get("filing_intelligence")],
            "post_close": post["prediction_evaluation"], "no_trade_learning": post["no_trade_learning"],
        },
        "safety": {"production_pipeline": False, "controlled_publish": False, "email_attempted": False, "line_attempted": False, "trading": False, "scheduler_changed": False, "secrets_accessed": False, "immutable_history_rewritten": False},
    }
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
