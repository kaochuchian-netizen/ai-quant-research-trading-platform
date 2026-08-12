"""TW production evidence and independently evaluable prediction contracts.

This module is deliberately pure.  It does not fetch, publish, notify, mutate
strategy state, or authorize a trade.  It turns an already admitted evidence
card into a research/prediction projection which remains reviewable when the
Decision Layer abstains.
"""
from __future__ import annotations

import hashlib
import json
import math
from datetime import date, datetime
from typing import Any

from app.market.instrument_master import instrument_metadata
from app.runtime.intelligence_quality import completeness_v2, intelligence_health, semantic_degradation, validate_no_lookahead_v2

SCHEMA_VERSION = "tw_production_intelligence_v2"
PREDICTION_METHOD = "tw_ohlcv_range_direction_v2"
TECHNICAL_METHOD = "tw_daily_ohlcv_features_v2"
MIN_PREDICTION_BARS = 10
FULL_TECHNICAL_BARS = 20

FAILURE_REASONS = {
    "NO_SOURCE_CONFIGURED", "AUTH_UNAVAILABLE", "TIMEOUT", "UPSTREAM_ERROR",
    "PARSER_ERROR", "SYMBOL_MAPPING_FAILED", "STALE", "INSUFFICIENT_LOOKBACK",
    "SESSION_NOT_AVAILABLE", "NOT_APPLICABLE", "ADMISSION_REJECTED",
    "NORMALIZATION_FAILED", "NO_MATERIAL_EVENT", "NO_RELIABLE_NEWS", "UNKNOWN",
}

def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _hash(value: Any, prefix: str) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    return prefix + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def instrument_context(symbol: str) -> dict[str, Any]:
    symbol = str(symbol)
    row = instrument_metadata("TW", symbol)
    return {
        **row,
        "kind": row.get("instrument_type") or "unknown",
        "sector": row.get("sector") or "未分類",
        "industry": row.get("industry") or "未分類",
        "peer": row.get("peer_group") or "未分類",
        "adr": row.get("adr_symbol"),
        "fundamentals_applicability": str(row.get("fundamentals_applicability") or "NOT_APPLICABLE").lower(),
        "company_events_applicability": str(row.get("company_events_applicability") or "NOT_APPLICABLE").lower(),
        "adr_applicability": str(row.get("adr_applicability") or "NOT_APPLICABLE").lower(),
    }


def technical_evidence(card: dict[str, Any]) -> dict[str, Any]:
    technical = card.get("technical_data") if isinstance(card.get("technical_data"), dict) else {}
    tactical = ((card.get("strategies") or {}).get("daily_tactical") or {}) if isinstance(card.get("strategies"), dict) else {}
    factors = tactical.get("technical_factors") if isinstance(tactical.get("technical_factors"), dict) else {}
    bars = int(technical.get("history_bars") or factors.get("history_days") or 0)
    latest = technical.get("history_end") or factors.get("history_end") or factors.get("latest_date")
    source = technical.get("source") or factors.get("source") or "canonical_historical_csv"
    available_features = {
        name: _number(factors.get(name))
        for name in ("latest_close", "ma5", "ma10", "ma20", "ma60", "rsi14", "atr14", "atr_pct", "relative_volume", "macd", "macd_signal", "range20_high", "range20_low")
        if _number(factors.get(name)) is not None
    }
    sufficient = bars >= FULL_TECHNICAL_BARS and available_features.get("ma20") is not None
    reason = None if sufficient else "INSUFFICIENT_LOOKBACK" if bars else "NO_SOURCE_CONFIGURED"
    return {
        "status": "available" if sufficient else "partial" if bars else "missing",
        "history_bars": bars, "required_bars": FULL_TECHNICAL_BARS,
        "history_start": technical.get("history_start") or factors.get("history_start"),
        "history_end": latest, "source": source, "freshness": technical.get("freshness") or "unknown",
        "method_version": TECHNICAL_METHOD, "features": available_features,
        "analysis_eligible": sufficient, "reason_code": reason,
        "provenance": {"source": source, "period_end": latest, "calculation_method": TECHNICAL_METHOD},
    }


def effective_coverage(card: dict[str, Any]) -> dict[str, Any]:
    symbol = str(card.get("symbol") or card.get("stock_id") or "")
    instrument = instrument_context(symbol)
    tech = technical_evidence(card)
    news = card.get("news_evidence") if isinstance(card.get("news_evidence"), dict) else {}
    news_items = news.get("evidence") if isinstance(news.get("evidence"), list) else card.get("news_items") or []
    usable_news = [item for item in news_items if isinstance(item, dict) and item.get("direction") in {"bullish", "bearish", "neutral"} and item.get("freshness") != "stale"]
    raw_news = len([item for item in news_items if isinstance(item, dict)])
    categories = {
        "market_price_history": {"status": "available" if tech["history_bars"] else "missing", "weight": .25, "reason_code": tech["reason_code"]},
        "technical": {"status": tech["status"], "weight": .20, "reason_code": tech["reason_code"]},
        "market_regime": {"status": "available" if card.get("market_context") or card.get("overnight_context") else "missing", "weight": .10, "reason_code": None if card.get("market_context") or card.get("overnight_context") else "NO_SOURCE_CONFIGURED"},
        "sector_peer": {"status": "available" if instrument.get("sector") not in {None, "未分類"} else "missing", "weight": .10, "reason_code": None if instrument.get("sector") not in {None, "未分類"} else "SYMBOL_MAPPING_FAILED"},
        "fundamentals": {"status": "not_applicable" if instrument["kind"] == "etf" else "available" if card.get("fundamental_context") or card.get("fundamental_summary") else "missing", "weight": .10, "reason_code": "NOT_APPLICABLE" if instrument["kind"] == "etf" else None if card.get("fundamental_context") or card.get("fundamental_summary") else "NO_SOURCE_CONFIGURED"},
        "official_events": {"status": "not_applicable" if instrument["kind"] == "etf" else "available" if card.get("official_events") else "missing", "weight": .10, "reason_code": "NOT_APPLICABLE" if instrument["kind"] == "etf" else None if card.get("official_events") else "NO_MATERIAL_EVENT"},
        "news": {"status": "available" if usable_news else "partial" if raw_news else "missing", "weight": .10, "reason_code": None if usable_news else "NO_RELIABLE_NEWS"},
        "external_adr": {"status": "not_applicable" if not instrument.get("adr") else "available" if card.get("adr_context") not in (None, "", "尚未取得", "本批次尚未取得") else "missing", "weight": .05, "reason_code": "NOT_APPLICABLE" if not instrument.get("adr") else None if card.get("adr_context") else "NO_SOURCE_CONFIGURED"},
    }
    applicable = [value for value in categories.values() if value["status"] != "not_applicable"]
    denominator = sum(float(value["weight"]) for value in applicable) or 1.0
    factor = {"available": 1.0, "partial": .45, "contradictory": .5, "stale": .2, "missing": 0.0, "failed": 0.0}
    score = round(100 * sum(value["weight"] * factor.get(value["status"], 0) for value in applicable) / denominator, 2)
    return {
        "schema_version": "tw_effective_research_coverage_v2", "score": score,
        "categories": categories,
        "available": [key for key, value in categories.items() if value["status"] == "available"],
        "partial": [key for key, value in categories.items() if value["status"] == "partial"],
        "missing": [key for key, value in categories.items() if value["status"] in {"missing", "failed", "stale"}],
        "not_applicable": [key for key, value in categories.items() if value["status"] == "not_applicable"],
        "policy": "category_weighted_usefulness_v2; not_applicable excluded; duplicates do not add coverage",
    }


def build_prediction_snapshot(card: dict[str, Any], *, effective_date: str | None = None, generated_at: str | None = None) -> dict[str, Any]:
    symbol = str(card.get("symbol") or card.get("stock_id") or "")
    tech = technical_evidence(card)
    factors = tech["features"]
    current = _number(card.get("current_price") or factors.get("latest_close"))
    bars = int(tech["history_bars"])
    atr = _number(factors.get("atr14"))
    if atr is None and current is not None:
        high, low = _number(card.get("session_high")), _number(card.get("session_low"))
        atr = None if high is None or low is None else max(high - low, current * .005)
    ma5, ma10 = _number(factors.get("ma5")), _number(factors.get("ma10"))
    available = bars >= MIN_PREDICTION_BARS and current is not None and atr is not None and atr > 0
    if not available:
        direction = "insufficient_data"
        regime = "insufficient_data"
        low = high = None
        confidence = None
        reason = "INSUFFICIENT_LOOKBACK" if bars < MIN_PREDICTION_BARS else "NORMALIZATION_FAILED"
    else:
        if ma5 is not None and ma10 is not None and ma5 > ma10 * 1.002:
            direction = "bullish"
        elif ma5 is not None and ma10 is not None and ma5 < ma10 * .998:
            direction = "bearish"
        else:
            direction = "neutral"
        regime = "trend_continuation" if direction != "neutral" else "range"
        low, high = round(current - atr, 4), round(current + atr, 4)
        completeness = min(1.0, bars / FULL_TECHNICAL_BARS)
        confidence = round(35 + 30 * completeness + (5 if ma5 is not None and ma10 is not None else 0), 2)
        reason = None
    research_identity = card.get("research_identity") or card.get("research_reasoning_identity")
    evidence_identity = _hash({"symbol": symbol, "technical": tech, "date": effective_date}, "twev_")
    hypothesis = {"direction": direction, "trigger": "下一交易時段價格與量價證據確認" if available else "補足最低行情證據", "invalidation": "實際方向與預測相反或價格超出預測區間" if available else "不適用"}
    hypothesis_identity = _hash({"symbol": symbol, "hypothesis": hypothesis, "evidence": evidence_identity}, "twhyp_")
    generated = generated_at or card.get("generated_at")
    source_timestamp = (card.get("technical_data") or {}).get("source_timestamp") or generated
    if isinstance(source_timestamp, str) and len(source_timestamp) == 10:
        source_timestamp = source_timestamp + "T13:30:00+08:00"
    core = {
        "schema_version": "tw_prediction_snapshot_v2", "market": "TW", "symbol": symbol,
        "window": "pre_open_0700", "effective_trading_date": effective_date or card.get("trading_date"),
        "generated_at": generated, "method_version": PREDICTION_METHOD,
        "prediction_status": "evaluable" if available else "insufficient_data",
        "direction_forecast": direction, "range_forecast": {"low": low, "high": high, "interval_width": None if low is None or high is None else round(high - low, 4), "method": "latest_close_plus_minus_atr14"},
        "regime_forecast": regime, "setup_forecast": {"class": "not_estimated", "probability": None, "reason": "no validated probability model"},
        "confidence": confidence, "confidence_method": "data_sufficiency_and_ma_alignment_v1" if available else None,
        "reason_code": reason, "research_identity": research_identity, "evidence_identity": evidence_identity,
        "hypothesis": hypothesis, "hypothesis_identity": hypothesis_identity,
        "decision_linkage": {"action": card.get("action"), "eligibility": card.get("entry_readiness"), "no_trade": bool(card.get("no_trade") or card.get("entry_readiness") == "no_trade"), "decision_ownership_preserved": True},
        "no_lookahead": {
            "schema_version": "no_lookahead_v2", "prediction_generated_at": generated,
            "prediction_data_cutoff": generated, "last_input_market_timestamp": source_timestamp,
            "first_outcome_observation_timestamp": None, "outcome_data_cutoff": None,
            "review_generated_at": None, "status": "pre_outcome",
        },
    }
    core["prediction_identity"] = _hash(core, "twpred_")
    return core


def evaluate_prediction(snapshot: dict[str, Any], actual: dict[str, Any], *, reviewed_at: str | None = None) -> dict[str, Any]:
    low = _number((snapshot.get("range_forecast") or {}).get("low")); high = _number((snapshot.get("range_forecast") or {}).get("high"))
    actual_open, actual_high = _number(actual.get("open")), _number(actual.get("high"))
    actual_low, actual_close = _number(actual.get("low")), _number(actual.get("close"))
    complete = None not in (actual_open, actual_high, actual_low, actual_close)
    evaluable = snapshot.get("prediction_status") == "evaluable" and low is not None and high is not None and complete
    if not evaluable:
        result = "not_applicable" if snapshot.get("prediction_status") != "evaluable" else "pending_evidence"
        direction_result = "not_applicable" if snapshot.get("direction_forecast") == "insufficient_data" else "pending_evidence"
        high_error = low_error = midpoint_error = None
    else:
        overlap = max(low, actual_low) <= min(high, actual_high)
        contains = low <= actual_low and actual_high <= high
        result = "hit" if contains else "partial_hit" if overlap else "miss"
        high_error = round(high - actual_high, 4); low_error = round(low - actual_low, 4)
        midpoint_error = round(((low + high) / 2) - ((actual_low + actual_high) / 2), 4)
        move = actual_close - actual_open
        actual_direction = "bullish" if move > 0 else "bearish" if move < 0 else "neutral"
        direction_result = "hit" if snapshot.get("direction_forecast") == actual_direction else "miss"
    decision = snapshot.get("decision_linkage") or {}
    no_trade_classification = None
    if decision.get("no_trade"):
        no_trade_classification = "inconclusive" if not evaluable else "risk_appropriate_abstention" if direction_result == "miss" else "correctly_avoided"
    timing = dict(snapshot.get("no_lookahead") or {})
    timing.update({
        "first_outcome_observation_timestamp": actual.get("first_observation_timestamp"),
        "outcome_data_cutoff": actual.get("outcome_data_cutoff") or reviewed_at,
        "review_generated_at": reviewed_at,
    })
    no_lookahead = validate_no_lookahead_v2(timing)
    core = {
        "schema_version": "tw_prediction_evaluation_v2", "prediction_identity": snapshot.get("prediction_identity"),
        "symbol": snapshot.get("symbol"), "evaluation_status": "evaluated" if evaluable else result,
        "range_result": result, "direction_result": direction_result,
        "interval_width": (snapshot.get("range_forecast") or {}).get("interval_width"),
        "high_error": high_error, "low_error": low_error, "midpoint_error": midpoint_error,
        "regime_result": "inconclusive", "setup_result": "not_applicable",
        "confidence_bucket": _confidence_bucket(snapshot.get("confidence")),
        "no_trade": bool(decision.get("no_trade")), "no_trade_classification": no_trade_classification,
        "actual": {"open": actual_open, "high": actual_high, "low": actual_low, "close": actual_close},
        "reviewed_at": reviewed_at, "no_lookahead_v2": {**timing, **no_lookahead},
        "no_lookahead_status": "pass" if no_lookahead["status"] == "PASS" else "not_verifiable",
    }
    core["review_identity"] = _hash(core, "twreview_")
    return core


def _confidence_bucket(value: Any) -> str:
    score = _number(value)
    if score is None: return "not_applicable"
    if score < 40: return "0_39"
    if score < 60: return "40_59"
    if score < 80: return "60_79"
    return "80_100"


def verification_record(snapshot: dict[str, Any], evaluation: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "schema_version": "tw_model_verifiability_record_v1", "model_version": snapshot.get("method_version"),
        "market": "TW", "symbol": snapshot.get("symbol"), "window": snapshot.get("window"),
        "prediction_timestamp": snapshot.get("generated_at"), "effective_trading_date": snapshot.get("effective_trading_date"),
        "evidence_identity": snapshot.get("evidence_identity"), "research_identity": snapshot.get("research_identity"),
        "prediction_identity": snapshot.get("prediction_identity"), "decision_identity": (snapshot.get("decision_linkage") or {}).get("decision_identity"),
        "direction_forecast": snapshot.get("direction_forecast"), "range_forecast": snapshot.get("range_forecast"),
        "confidence": snapshot.get("confidence"), "actual_outcome": (evaluation or {}).get("actual"),
        "evaluation_status": (evaluation or {}).get("evaluation_status", "pending"),
        "no_trade_status": bool((snapshot.get("decision_linkage") or {}).get("no_trade")),
        "review_identity": (evaluation or {}).get("review_identity"), "append_policy": "immutable_prediction_append_safe_review_link",
    }


def verification_health(records: list[dict[str, Any]]) -> dict[str, Any]:
    unique = {str(item.get("prediction_identity")): item for item in records if item.get("prediction_identity")}
    values = list(unique.values()); n = len(values)
    evaluated = sum(item.get("evaluation_status") == "evaluated" for item in values)
    stage = "NO_SAMPLE" if n == 0 else "EARLY_SAMPLE" if n < 30 else "DEVELOPING_SAMPLE" if n < 50 else "MINIMUM_REVIEWABLE_SAMPLE" if n < 100 else "MEANINGFUL_FORWARD_SAMPLE"
    return {
        "stage": stage, "predictions": n, "evaluated": evaluated, "pending": n - evaluated,
        "direction_evaluable": sum(item.get("direction_forecast") not in {None, "insufficient_data"} for item in values),
        "range_evaluable": sum(isinstance(item.get("range_forecast"), dict) and (item.get("range_forecast") or {}).get("low") is not None for item in values),
        "trade_evaluable": sum(not item.get("no_trade_status") for item in values),
        "no_trade_evaluable": sum(bool(item.get("no_trade_status")) for item in values),
        "claim": "architecture_validated_forward_sample_collection_enabled",
    }


def source_inventory() -> list[dict[str, Any]]:
    return [
        {"source_id": "shioaji_kbars", "category": "market_price_history", "runtime": "configured_runtime_path", "auth": "required", "fallback": "yfinance_then_existing_csv", "reaches_research": True, "failure_reason": "AUTH_UNAVAILABLE"},
        {"source_id": "twse_tpex_quotes", "category": "intraday_market", "runtime": "existing_pipeline", "auth": "none_or_existing", "fallback": "explicit_missing", "reaches_research": True, "failure_reason": "UPSTREAM_ERROR"},
        {"source_id": "google_news_rss", "category": "news", "runtime": "connected", "auth": "none", "fallback": "explicit_unclassified_metadata", "reaches_research": True, "failure_reason": "NO_RELIABLE_NEWS"},
        {"source_id": "mops_twse_tpex_official", "category": "official_events", "runtime": "registry_or_fixture_only", "auth": "none", "fallback": "explicit_missing", "reaches_research": False, "failure_reason": "NO_SOURCE_CONFIGURED"},
        {"source_id": "yfinance_tw_reference", "category": "historical_fallback", "runtime": "adapter_available", "auth": "none", "fallback": "existing_csv", "reaches_research": True, "failure_reason": "UPSTREAM_ERROR"},
        {"source_id": "adr_yfinance", "category": "external_adr", "runtime": "connected_applicable_symbols_only", "auth": "none", "fallback": "not_applicable", "reaches_research": True, "failure_reason": "NOT_APPLICABLE"},
    ]


def source_health(cards: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(cards)
    tech = [technical_evidence(card) for card in cards]
    coverage = [effective_coverage(card) for card in cards]
    full = sum(item["analysis_eligible"] for item in tech)
    quote_available = sum(any(_number(card.get(key)) is not None for key in ("current_price", "session_open", "session_high", "session_low")) for card in cards)
    history_valid = sum(bool(((card.get("technical_data") or {}).get("history_admission") or {}).get("admission_success")) for card in cards)
    completeness = completeness_v2(
        market_data="COMPLETE" if quote_available == total and total else "PARTIAL",
        technical="COMPLETE" if full == total and total else "PARTIAL" if full else "MISSING",
        research="COMPLETE" if all(not item["missing"] for item in coverage) else "PARTIAL",
        decision_input="SUFFICIENT", prediction_input="SUFFICIENT" if any(item["history_bars"] >= MIN_PREDICTION_BARS for item in tech) else "INSUFFICIENT",
        research_score=round(sum(item["score"] for item in coverage) / total, 2) if total else 0,
        missing_categories=sorted({key for item in coverage for key in item["missing"]}),
    )
    degradation = semantic_degradation(
        quote_total=total, quote_available=quote_available,
        history_claimed_valid=history_valid, technical_executable=full,
        completeness=completeness,
    )
    return {
        "schema_version": "tw_source_health_summary_v1", "symbol_count": total,
        "sources": source_inventory(),
        "category_health": {
            "historical": {"usable_symbols": sum(item["history_bars"] > 0 for item in tech), "admitted_symbols": history_valid, "full_symbols": full, "failure_reason": "INSUFFICIENT_LOOKBACK" if any(not item["analysis_eligible"] for item in tech) else None},
            "news": {"usable_symbols": sum("news" in item["available"] for item in coverage), "partial_symbols": sum("news" in item["partial"] for item in coverage), "failure_reason": "NO_RELIABLE_NEWS" if not any("news" in item["available"] for item in coverage) else None},
        },
        "completeness_v2": completeness,
        "semantic_degradation": degradation,
        "intelligence_health": intelligence_health(
            runtime_status="SUCCESS", data_quality_status="DEGRADED" if degradation["status"] == "DEGRADED" else "HEALTHY",
            research_status=completeness["research_evidence_completeness"],
            prediction_status="AVAILABLE" if completeness["prediction_input_completeness"] == "SUFFICIENT" else "DEGRADED",
            decision_status="AVAILABLE", degradation=degradation,
        ),
        "public_summary": "來源健康摘要僅顯示可用證據與原因碼，不包含憑證或原始除錯資訊。",
    }
