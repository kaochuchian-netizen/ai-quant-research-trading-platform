#!/usr/bin/env python3
"""Deterministic semantic gate for AI-DEV-199 Research Reasoning Engine V1."""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))

from app.research.evidence import normalize_evidence, normalize_many
from app.research.hypothesis import build_hypothesis
from app.research.projection import MODEL_BOUNDARY, build_research_reasoning_projection, validate_projection
from app.us_stock.institutional_research import evidence_record


def _item(market: str, symbol: str, klass: str, source: str, summary: str, direction: str, *, cluster: str | None = None, reliability: float = .9, confidence: float = .8) -> dict:
    return {"market": market, "symbol": symbol, "evidence_class": klass, "source_name": source,
            "source_type": "official" if source in {"TWSE", "SEC"} else "market_data",
            "source_reference": f"fixture:{source}:{symbol}", "published_at": "2026-07-30T01:00:00+00:00",
            "observed_at": "2026-07-30T07:00:00+08:00", "freshness": "fresh",
            "reliability": reliability, "confidence": confidence, "coverage_status": "AVAILABLE",
            "summary": summary, "direction": direction, "materiality": "high", "event_cluster_id": cluster}


def validate() -> dict:
    errors: list[str] = []; details: dict = {"negative_tests": {}}
    tw = {
        "2330": [
            _item("TW", "2330", "adr", "Market Data", "TSM ADR走弱，台股開盤可能承壓", "bearish"),
            _item("TW", "2330", "technical", "TWSE", "價格仍守住中期支撐", "bullish"),
            _item("TW", "2330", "sector", "TWSE", "半導體族群動能分歧", "neutral"),
        ],
        "2337": [
            _item("TW", "2337", "news", "Company IR", "車用記憶體需求改善", "bullish", cluster="memory-demand"),
            _item("TW", "2337", "news", "General Media", "同一需求事件轉載", "bullish", cluster="memory-demand", reliability=.6),
            _item("TW", "2337", "technical", "TWSE", "趨勢尚未轉強", "bearish"),
        ],
    }
    triggers = {"2330": {"expected_trigger": "ADR壓力緩解且技術支撐維持", "invalidation": "跌破中期支撐"},
                "2337": {"expected_trigger": "需求證據獲官方確認", "invalidation": "技術趨勢續弱且需求未實現"}}
    projection = build_research_reasoning_projection("TW", "2026-07-30", tw, triggers)
    errors.extend(validate_projection(projection))
    bundles = {x["symbol"]: x for x in projection["bundles"]}
    if bundles["2330"]["reasoning"]["conflict"]["level"] != "HIGH": errors.append("conflict_not_detected")
    if sum(x["counted_in_reasoning"] for x in bundles["2337"]["evidence"] if x["event_cluster_id"] == "memory-demand") != 1: errors.append("duplicate_counted")
    if not bundles["2330"]["reasoning"]["supporting_evidence_ids"] or not bundles["2330"]["reasoning"]["opposing_evidence_ids"]: errors.append("supporting_opposing_missing")
    if any(not step.get("evidence_id") for row in bundles.values() for step in row["reasoning"]["reasoning_chain"]): errors.append("chain_untraceable")
    if any(not row["hypothesis"]["invalidation"] for row in bundles.values()): errors.append("invalidation_missing")
    if any(row["hypothesis"]["trade_signal"] for row in bundles.values()): errors.append("hypothesis_became_signal")
    if projection["model_boundary"] != MODEL_BOUNDARY or any(MODEL_BOUNDARY[key] for key in ("strategy_modified", "scoring_modified", "ranking_modified", "prediction_modified", "trade_action_exported", "auto_learning")): errors.append("model_boundary")
    if projection["market_narrative"]["method"] != "cross_symbol_reasoning_synthesis_not_headline_concatenation": errors.append("narrative_method")
    if bundles["2330"]["knowledge"]["dynamic_daily_data"] is not False: errors.append("knowledge_not_long_lived")

    us = {"AAPL": [_item("US", "AAPL", "fundamental", "SEC", "服務營收具韌性", "bullish"),
                    _item("US", "AAPL", "macro", "Federal Reserve", "高利率壓抑估值", "bearish")]}
    us_projection = build_research_reasoning_projection("US", "2026-07-30", us, {"AAPL": {"expected_trigger": "服務營收韌性延續", "invalidation": "需求與指引同步轉弱"}})
    errors.extend(validate_projection(us_projection))
    if any(x["market"] != "US" for x in us_projection["bundles"][0]["evidence"]): errors.append("us_isolation")
    legacy = evidence_record("AAPL", "sec_edgar", "A", "8-K filing", "Official filing", "2026-07-30T06:30:00-04:00", "filing", published_at="2026-07-29", official=True, confidence=.98)
    legacy_normalized = normalize_many([legacy], market="US")
    if legacy_normalized[0]["evidence_class"] != "corporate" or legacy_normalized[0]["source_name"] != "sec_edgar": errors.append("ai197_evidence_adapter")

    negative = [
        ("missing_source", lambda: normalize_evidence({k: v for k, v in tw["2330"][0].items() if k != "source_name"}, market="TW")),
        ("naive_timestamp", lambda: normalize_evidence({**tw["2330"][0], "observed_at": "2026-07-30T07:00:00"}, market="TW")),
        ("invalid_reliability", lambda: normalize_evidence({**tw["2330"][0], "reliability": 1.2}, market="TW")),
        ("cross_market", lambda: normalize_evidence(tw["2330"][0], market="US")),
        ("missing_invalidation", lambda: build_hypothesis(bundles["2330"]["reasoning"], expected_trigger="確認", invalidation="")),
    ]
    for name, operation in negative:
        try: operation(); details["negative_tests"][name] = "unexpected_pass"; errors.append(f"negative:{name}")
        except ValueError: details["negative_tests"][name] = "PASS"

    corrupt = copy.deepcopy(projection); corrupt["bundles"][0]["reasoning"]["trade_action"] = "buy"
    boundary_errors = validate_projection(corrupt); details["negative_tests"]["trade_boundary"] = boundary_errors
    if not any("research_decision_boundary" in x for x in boundary_errors): errors.append("negative:trade_boundary")
    details.update({"tw_identity": projection["research_reasoning_identity"], "us_identity": us_projection["research_reasoning_identity"],
                    "tw_symbols": list(bundles), "market_narrative": projection["market_narrative"], "model_boundary": MODEL_BOUNDARY})
    return {"ok": not errors, "validator": "validate_ai_dev_199_research_reasoning_engine_v1", "errors": sorted(set(errors)), "details": details}


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--pretty", action="store_true"); args = parser.parse_args()
    result = validate(); print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["ok"] else 2


if __name__ == "__main__": raise SystemExit(main())
