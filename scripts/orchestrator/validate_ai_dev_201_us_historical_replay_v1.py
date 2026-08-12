#!/usr/bin/env python3
"""Read-only deterministic 20:00 -> 23:00 -> 06:30 research replay."""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.us_stock.institutional_research import build_bundle, resolve_bundle
from app.us_stock.research_intelligence_v2 import evolve_intraday, evolve_post_close


def fixture() -> tuple[dict, dict]:
    observed = "2026-08-07T20:00:00+08:00"
    research = {
        "sec": {"ok": True, "provenance": {"retrieved_at": observed}, "filings": [{"form": "10-Q", "filing_date": "2026-08-06", "item": "Results of Operations", "accession": "nvda-10q"}]},
        "official_sources": {"investor_relations_url": "https://example.com/nvda/ir", "sec_company_page": "https://sec.gov/edgar"},
        "fundamentals": {"metrics": {"revenue": {"value": 100}}, "comparison": {"trend_direction": "bullish"}},
        "earnings": {"latest_earnings": {"actual_eps": 1.0, "reported_date": "2026-08-01"}},
        "material_news": {"items": []},
    }
    changes = {"SPY": .02, "QQQ": .01, "SOXX": 1.55, "DIA": 0., "^VIX": 0.}
    context = {"items": {symbol: {
        "change_pct": change, "last_price": 100 + change, "previous_close": 100,
        "source_timestamp": "2026-08-07T08:00:00-04:00", "ok": True,
        "premarket": {"change_pct": change, "timestamp": "2026-08-07T08:00:00-04:00", "source": "yfinance", "freshness": "fresh", "availability": "available"},
    } for symbol, change in changes.items()}, "market_environment_score": 50,
    "market_regime": "neutral", "risk_environment": "normal",
    "source_timestamp": "2026-08-07T08:00:00-04:00"}
    return research, context


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--pretty", action="store_true"); args = parser.parse_args()
    research, context = fixture(); observed = "2026-08-07T20:00:00+08:00"
    first = build_bundle("NVDA", research, context, observed)
    second = build_bundle("NVDA", research, context, observed)
    changed_context = json.loads(json.dumps(context)); changed_context["items"]["SOXX"]["change_pct"] = -1.2; changed_context["items"]["SOXX"]["premarket"]["change_pct"] = -1.2
    changed = build_bundle("NVDA", research, changed_context, observed)
    with tempfile.TemporaryDirectory(prefix="ai201_replay_") as tmp:
        root = Path(tmp); folder = root / "us/us_pre_market_2000/2026-08-07"; folder.mkdir(parents=True)
        wrapper = {"admitted": True, "effective_trading_date": "2026-08-07", "snapshot_id": "snapshot-2000", "revision": 1, "admitted_at": observed, "source_payload_hash": "source-hash-2000", "payload": {"dashboard_ready_contract": {"cards": [{"symbol": "NVDA", "institutional_research": first}]}}}
        (folder / "revision-1.json").write_text(json.dumps(wrapper), encoding="utf-8")
        inherited = resolve_bundle(root, "2026-08-07", "NVDA")
    observed_2300 = {"data_status": "complete", "gap_current_pct": 1.25, "gap_state": "gap_up_follow_through", "volume_ratio": 1.45, "volume_confirmation_state": "strong", "source": "fixture_market_evidence"}
    intraday = evolve_intraday(inherited["research_intelligence_v2"], observed_2300, observed_at="2026-08-07T23:00:00+08:00")
    prediction = {"predicted_session_low": 175, "predicted_session_high": 185, "reference_price": 179, "direction_forecast": "bullish"}
    review = {"actual_low": 176, "actual_high": 184, "actual_close": 181, "prediction_range_result": "hit", "high_error": -1, "low_error": 1, "trade_review_outcome": "no_trade"}
    post = evolve_post_close(inherited["research_intelligence_v2"], observed_2300, prediction, review, observed_at="2026-08-08T06:30:00+08:00")
    checks = {
        "same_evidence_same_origin_identity": first["research_identity"] == second["research_identity"],
        "same_evidence_same_window_identity": first["research_intelligence_v2"]["window_research_identity"] == second["research_intelligence_v2"]["window_research_identity"],
        "changed_evidence_changes_identity": changed["research_identity"] != first["research_identity"],
        "admitted_origin_binding": inherited["continuity"]["source_snapshot_id"] == "snapshot-2000" and inherited["continuity"]["source_hash"] == "source-hash-2000",
        "origin_identity_retained": intraday["origin_research_identity"] == first["research_identity"] == post["origin_research_identity"],
        "window_evolution": len({first["research_intelligence_v2"]["window_research_identity"], intraday["window_research_identity"], post["window_research_identity"]}) == 3,
        "intraday_explainable": bool(intraday["hypothesis"]["state"] in {"confirmed", "strengthened"} and intraday["window_update"]["new_evidence"]),
        "post_close_linked": post["prediction_evaluation"]["range"]["status"] == "evaluated" and post["no_trade_learning"]["no_trade_still_evaluated"],
        "no_auto_learning": post["no_trade_learning"]["auto_learning"] is False and post["no_trade_learning"]["auto_threshold_change"] is False,
    }
    result = {"task_id": "AI-DEV-201", "validator": "us_historical_replay_v1", "ok": all(checks.values()), "checks": checks, "identities": {"origin": first["research_identity"], "window_2000": first["research_intelligence_v2"]["window_research_identity"], "window_2300": intraday["window_research_identity"], "window_0630": post["window_research_identity"]}, "safety": {"temporary_directory_only": True, "notification_sent": False, "production_db_written": False, "archive_rewritten": False, "scheduler_triggered": False, "orders_placed": False}}
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
