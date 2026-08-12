#!/usr/bin/env python3
"""Deterministic semantic validation for AI-DEV-202 (no network/writes)."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import pandas as pd

from app.reports.tw_four_window_decision import aggregate_cards, build_observed_card, upgrade_pre_open_card
from app.reports.tw_decision_intelligence_v2 import build_tw_decision_intelligence_v2, compact_tw_v2_lines
from app.dashboard.multi_market_dashboard import _decision_intelligence_v4_html
from app.research.tw_production_intelligence_v2 import (
    build_prediction_snapshot, effective_coverage, evaluate_prediction, instrument_context,
    source_health, technical_evidence, verification_health, verification_record,
)
from scripts.update_historical_csv import fetch_yfinance_daily

SYMBOLS = ("2330", "009816", "2337", "2353", "6873", "4743", "2305", "00878", "1409")


def factors(index: int, bars: int = 60) -> dict:
    close = 80.0 + index * 13
    bias = (index % 3) - 1
    return {
        "history_days": bars, "history_start": "2026-05-15", "history_end": "2026-08-10", "latest_date": "2026-08-10",
        "source": "canonical_historical_csv", "latest_close": close, "ma5": close + bias * 1.2,
        "ma10": close, "ma20": close - bias * .6 if bars >= 20 else None, "ma60": close - bias if bars >= 60 else None,
        "rsi14": 45 + index, "atr14": max(1.0, close * .018), "atr_pct": .018,
        "relative_volume": .7 + index * .11, "macd": bias * .4, "macd_signal": bias * .2,
        "high_20d": close * 1.08, "low_20d": close * .92,
    }


def preopen_card(symbol: str, index: int, bars: int = 60) -> dict:
    tf = factors(index, bars)
    tactical = {
        "setup_type": "no_trade", "direction": "bullish" if index % 3 == 0 else "bearish" if index % 3 == 1 else "neutral",
        "data_quality": "complete", "technical_factors": tf, "reward_risk": .7,
        "risk_reasons": ["RR_BELOW_THRESHOLD"], "reasons": [f"{symbol} deterministic evidence"],
        "chase_risk": "unavailable", "event_risk": "unavailable", "action": "no_trade",
        "playbook": {"entry_condition": "等待既有策略條件"},
    }
    raw = {
        "symbol": symbol, "stock_id": symbol, "name": symbol, "stock_name": symbol,
        "trading_date": "2026-08-11", "generated_at": "2026-08-11T07:00:00+08:00",
        "gap_risk": "unavailable", "news_evidence": {"status": "partial", "evidence": [], "retrieval": {"failure_reason": "NO_RELIABLE_NEWS"}},
        "news_summary": "未取得可納入方向判斷的可靠新聞", "adr_context": "+1.20%" if symbol == "2330" else "不適用",
    }
    return upgrade_pre_open_card(raw, tactical, source_revision=1)


def quote(index: int) -> dict:
    base = 80.0 + index * 13
    direction = (index % 3) - 1
    opened = base
    close = base * (1 + direction * .012)
    return {"open": opened, "high": max(opened, close) * 1.01, "low": min(opened, close) * .99, "close": close, "total_volume": 1_000_000 + index * 50_000, "snapshot_time": "2026-08-11T13:05:00+08:00"}


def observed(window: str, setup: dict, index: int, prior: dict | None = None) -> dict:
    q = quote(index)
    if window == "pre_close_1335": q["snapshot_time"] = "2026-08-11T13:35:00+08:00"
    if window == "post_close_1500": q["snapshot_time"] = "2026-08-11T15:00:00+08:00"
    return build_observed_card(window=window, setup_card=setup, quote=q, trading_date="2026-08-11", generated_at=q["snapshot_time"], source_snapshot_id="admitted-0700", source_revision=1, source_payload_hash="source-hash", prior_card=prior)


def check(name: str, condition: bool, failures: list[str]) -> None:
    if not condition: failures.append(name)


def main() -> int:
    failures: list[str] = []
    cards = [preopen_card(symbol, index) for index, symbol in enumerate(SYMBOLS)]
    check("predictions_independent_no_trade", all(card["no_trade"] and card["prediction_snapshot_v2"]["prediction_status"] == "evaluable" for card in cards), failures)
    check("technical_generated_from_sufficient_ohlcv", all(technical_evidence(card)["analysis_eligible"] for card in cards), failures)
    check("technical_provenance", all(technical_evidence(card)["provenance"]["calculation_method"] == "tw_daily_ohlcv_features_v2" for card in cards), failures)

    insufficient = preopen_card("2330", 0, bars=19)
    check("insufficient_explicit", technical_evidence(insufficient)["reason_code"] == "INSUFFICIENT_LOOKBACK", failures)
    broken = copy.deepcopy(cards[0]); broken["technical_data"]["analysis_eligible"] = False
    check("sufficient_empty_negative_detectable", technical_evidence(broken)["analysis_eligible"] is True, failures)

    frame = pd.DataFrame({"Date": pd.bdate_range(end="2026-08-10", periods=60), "Open": range(2, 62), "High": range(3, 63), "Low": range(1, 61), "Close": range(2, 62), "Volume": [1000] * 60})
    downloaded, ticker, errors = fetch_yfinance_daily("2330", "2026-05-01", "2026-08-11", downloader=lambda *args, **kwargs: frame)
    check("safe_yfinance_fallback", ticker == "2330.TW" and len(downloaded) == 60 and not errors, failures)

    etf = effective_coverage(next(card for card in cards if card["symbol"] == "00878"))
    check("etf_not_applicable", etf["categories"]["fundamentals"]["status"] == "not_applicable" and etf["categories"]["official_events"]["status"] == "not_applicable", failures)
    check("adr_applicability", instrument_context("2330")["adr_applicability"] == "applicable" and instrument_context("2337")["adr_applicability"] == "not_applicable", failures)

    intraday = [observed("intraday_1305", card, index) for index, card in enumerate(cards)]
    preclose = [observed("pre_close_1335", card, index, intraday[index]) for index, card in enumerate(cards)]
    postclose = [observed("post_close_1500", card, index, preclose[index]) for index, card in enumerate(cards)]
    summary = aggregate_cards("post_close_1500", postclose)
    check("no_trade_preserved", summary["trade_outcome_counts"]["no_trade"] == 9, failures)
    check("no_trade_predictions_evaluated", summary["prediction_v2_evaluated_count"] == 9 and summary["no_trade_prediction_evaluated_count"] == 9, failures)
    check("prediction_results_nonzero", sum(summary["prediction_evaluation_counts"].get(key, 0) for key in ("hit", "partial_hit", "miss")) == 9, failures)
    check("error_metrics", all((card["prediction_evaluation_v2"].get("midpoint_error") is not None) for card in postclose), failures)
    check("no_lookahead", all(card["prediction_evaluation_v2"]["no_lookahead_status"] == "pass" for card in postclose), failures)

    payloads = {
        "pre_open_0700": {"effective_trading_date": "2026-08-11", "structured_pre_open_cards": cards},
        "intraday_1305": {"effective_trading_date": "2026-08-11", "structured_intraday_cards": intraday},
        "pre_close_1335": {"effective_trading_date": "2026-08-11", "structured_pre_close_cards": preclose},
        "post_close_1500": {"effective_trading_date": "2026-08-11", "structured_review_cards": postclose},
    }
    projections = {window: build_tw_decision_intelligence_v2(window, payload) for window, payload in payloads.items()}
    notes = projections["intraday_1305"]["research_reasoning_projection"]["research_notes"]
    check("intraday_price_evidence_consumed", all(any("盤中價格" in text for text in note["supporting"] + note["opposing"] + note.get("why", []) + note.get("why_not", [])) or note["hypothesis_lifecycle"]["state"] != "insufficient_new_evidence" for note in notes), failures)
    check("research_differentiation", len({note["research_summary"] for note in notes}) == 9, failures)
    check("hypothesis_continuity", {note["hypothesis_lifecycle"]["state"] for note in notes} <= {"strengthened", "weakened", "contradicted"}, failures)
    check("source_health_reason", source_health(cards)["category_health"]["news"]["failure_reason"] == "NO_RELIABLE_NEWS", failures)

    records = [verification_record(card["prediction_snapshot_v2"], card["prediction_evaluation_v2"]) for card in postclose]
    health = verification_health(records)
    check("verification_registry", health["predictions"] == 9 and health["evaluated"] == 9 and health["stage"] == "EARLY_SAMPLE", failures)
    check("identity_parity", all(card["prediction_snapshot_v2"]["prediction_identity"] == card["prediction_evaluation_v2"]["prediction_identity"] == card["verification_record_v1"]["prediction_identity"] for card in postclose), failures)
    tw_bundle = projections["pre_open_0700"]
    prediction_bundle_id = tw_bundle["prediction_identity"]
    line_preview = "\n".join(compact_tw_v2_lines(tw_bundle))
    dashboard_html = _decision_intelligence_v4_html("TW", "pre_open_0700", payloads["pre_open_0700"])
    check("five_channel_prediction_identity", prediction_bundle_id in line_preview and prediction_bundle_id in dashboard_html and len(tw_bundle["prediction_identities"]) == 9, failures)

    direct = build_prediction_snapshot(cards[0], effective_date="2026-08-11", generated_at="2026-08-11T07:00:00+08:00")
    reviewed = evaluate_prediction(direct, {"open": 80, "high": 82, "low": 79, "close": 81, "first_observation_timestamp": "2026-08-11T09:00:00+08:00", "outcome_data_cutoff": "2026-08-11T13:30:00+08:00"}, reviewed_at="2026-08-11T15:00:00+08:00")
    check("direct_no_trade_evaluable", reviewed["evaluation_status"] == "evaluated" and reviewed["no_trade"] is True, failures)

    result = {"validator": "validate_ai_dev_202_tw_production_intelligence_v1", "status": "PASS" if not failures else "FAIL", "checks": 18, "failures": failures, "replay": {"symbols": 9, "predictions": health["predictions"], "evaluated": health["evaluated"], "trades": 0, "no_trade": 9, "prediction_distribution": summary["prediction_evaluation_counts"], "research_summaries": len({note["research_summary"] for note in notes})}}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
