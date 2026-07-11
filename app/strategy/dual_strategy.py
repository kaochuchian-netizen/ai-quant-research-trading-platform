"""Dual-strategy contracts and deterministic daily tactical engine.

This module keeps Research / Position output separate from Daily Tactical output.
It is advisory-only and never creates orders or brokerage instructions.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

TAIPEI = ZoneInfo("Asia/Taipei")
RESEARCH_POSITION = "research_position"
DAILY_TACTICAL = "daily_tactical"
STRATEGY_TYPES = {RESEARCH_POSITION, DAILY_TACTICAL}
MARKETS = {"TW", "US"}
TW_RESEARCH_VERSION = "tw_research_position_existing_v1"
US_RESEARCH_VERSION = "us_research_position_v1"
TW_TACTICAL_VERSION = "tw_daily_tactical_v1"
US_TACTICAL_VERSION = "us_daily_tactical_v1"
TW_TACTICAL_FACTOR_VERSION = "tw_daily_tactical_factor_v1"
US_TACTICAL_FACTOR_VERSION = "us_daily_tactical_factor_v1"
TACTICAL_WEIGHT_VERSIONS = {
    "TW": {
        "version": TW_TACTICAL_FACTOR_VERSION,
        "weights": {
            "price_momentum": 0.16,
            "trend_strength": 0.15,
            "breakout_quality": 0.12,
            "volume_confirmation": 0.12,
            "chip_confirmation": 0.10,
            "mean_reversion_risk": 0.08,
            "volatility_risk": 0.09,
            "market_context": 0.08,
            "event_risk": 0.05,
            "data_completeness": 0.05,
        },
    },
    "US": {
        "version": US_TACTICAL_FACTOR_VERSION,
        "weights": {
            "premarket_gap": 0.10,
            "momentum": 0.14,
            "trend_strength": 0.14,
            "relative_volume": 0.09,
            "breakout_quality": 0.12,
            "mean_reversion_risk": 0.08,
            "volatility_risk": 0.09,
            "benchmark_context": 0.09,
            "sector_context": 0.05,
            "earnings_event_risk": 0.05,
            "official_news_catalyst": 0.05,
        },
    },
}


def now_taipei() -> str:
    return datetime.now(TAIPEI).replace(microsecond=0).isoformat()


def _num(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and value == value and value not in (float("inf"), float("-inf")):
        return float(value)
    return None


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return round(max(low, min(high, value)), 2)


def _score_to_direction(score: float | None) -> str:
    if score is None:
        return "neutral"
    if score >= 72:
        return "bullish"
    if score >= 58:
        return "mildly_bullish"
    if score <= 28:
        return "bearish"
    if score <= 42:
        return "mildly_bearish"
    return "neutral"


def _grade(score: float | None, status: str) -> str:
    if status == "insufficient_data" or score is None:
        return "資料不足"
    if score >= 72:
        return "A-Tactical"
    if score >= 58:
        return "B-Tactical"
    if score >= 45:
        return "C-Tactical"
    if score >= 35:
        return "D-Tactical"
    return "E-Tactical"


def _action(direction: str, setup_type: str, chase_risk: str, event_risk: str) -> str:
    if setup_type == "insufficient_data":
        return "資料不足"
    if setup_type == "no_trade" or event_risk == "high":
        return "暫不操作"
    if chase_risk == "high" and direction in {"bullish", "mildly_bullish"}:
        return "避免追高"
    if setup_type == "breakout":
        return "突破確認後偏多"
    if setup_type == "pullback":
        return "拉回承接"
    if setup_type == "trend_continuation":
        return "拉回觀察"
    if setup_type == "mean_reversion":
        return "反彈減碼" if direction in {"mildly_bearish", "bearish"} else "區間操作"
    if direction in {"mildly_bearish", "bearish"}:
        return "偏空防守"
    return "等待止穩"


def _confidence(score: float | None, data_ok: bool, volatility_state: str, event_risk: str) -> float | None:
    if score is None or not data_ok:
        return None
    conf = 38 + abs(score - 50) * 0.55
    if volatility_state == "high":
        conf -= 8
    if event_risk == "medium":
        conf -= 5
    if event_risk == "high":
        conf -= 14
    return round(max(20, min(75, conf)), 1)


def _factor(name: str, score: float | None, evidence: str, source_refs: list[str] | None = None, data_quality: str = "available") -> dict[str, Any]:
    return {
        "factor": name,
        "score": None if score is None else _clamp(score),
        "evidence": evidence,
        "source_references": source_refs or [],
        "data_quality": data_quality,
        "freshness": "runtime_window",
    }


def build_research_position_strategy(market: str, score_payload: dict[str, Any], prediction: dict[str, Any], *, generated_at: str | None = None, factor_version: str | None = None) -> dict[str, Any]:
    if market not in MARKETS:
        raise ValueError(f"unsupported market: {market}")
    score = _num(score_payload.get("total_score"))
    confidence = _num(score_payload.get("confidence_score"))
    return {
        "market": market,
        "strategy_type": RESEARCH_POSITION,
        "strategy_version": US_RESEARCH_VERSION if market == "US" else TW_RESEARCH_VERSION,
        "generated_at": generated_at or now_taipei(),
        "horizon": "days_to_months; 1M/3M trend",
        "score": score,
        "rating": score_payload.get("rating") or "資料待接",
        "action": score_payload.get("action") or "資料待接",
        "confidence": confidence,
        "confidence_level": score_payload.get("confidence_level") or score_payload.get("confidence_status") or "資料待接",
        "rationale": score_payload.get("rationale") or "沿用既有 Research / Position scoring，不由 Tactical 覆寫。",
        "risk_notes": ["Research / Position 用於持有與中短期趨勢判斷，不是自動交易指令。"],
        "data_quality": score_payload.get("confidence_status") or "available",
        "factor_version": factor_version or score_payload.get("research_factor_version") or score_payload.get("weight_version") or "existing_research_weight_version",
        "prediction": {
            "predicted_session_low": prediction.get("predicted_session_low"),
            "predicted_session_high": prediction.get("predicted_session_high"),
            "predicted_next_session_low": prediction.get("predicted_next_session_low"),
            "predicted_next_session_high": prediction.get("predicted_next_session_high"),
            "one_month_trend": prediction.get("one_month_trend"),
            "three_month_trend": prediction.get("three_month_trend"),
            "prediction_status": prediction.get("prediction_status"),
            "model_version": prediction.get("model_version"),
        },
    }


def _support_resistance(indicators: dict[str, Any], price: float, atr_pct: float) -> tuple[float, float]:
    lower_candidates = [_num(indicators.get("bollinger_lower")), _num(indicators.get("ma20")), price * (1 - atr_pct)]
    upper_candidates = [_num(indicators.get("bollinger_upper")), _num(indicators.get("ma20")), price * (1 + atr_pct)]
    support = max([x for x in lower_candidates if x is not None and x < price] or [price * (1 - atr_pct)])
    resistance = min([x for x in upper_candidates if x is not None and x > price] or [price * (1 + atr_pct)])
    return support, resistance


def _empty_levels(status: str) -> dict[str, Any]:
    return {
        "entry_zone": None,
        "invalidation_level": None,
        "stop_reference": None,
        "target_zone_1": None,
        "target_zone_2": None,
        "expected_move": None,
        "reward_risk_ratio": None,
        "prediction_status": status,
    }


def _ordered_levels(price: float, direction: str, setup_type: str, atr_pct: float, indicators: dict[str, Any], event_risk: str) -> dict[str, Any]:
    support, resistance = _support_resistance(indicators, price, atr_pct)
    atr = max(price * atr_pct, price * 0.003)
    if event_risk == "high" or setup_type in {"no_trade", "insufficient_data"}:
        return _empty_levels("suppressed_by_event_risk" if event_risk == "high" else "insufficient_data")
    if direction in {"bullish", "mildly_bullish"}:
        entry_low = min(price, max(support, price - 0.45 * atr))
        entry_high = max(entry_low, min(price + 0.15 * atr, resistance))
        stop = min(entry_low - 0.6 * atr, support - 0.15 * atr)
        target1_low = max(price + 0.55 * atr, resistance)
        target1_high = target1_low + 0.35 * atr
        target2_low = target1_high
        target2_high = target2_low + 0.65 * atr
    elif direction in {"bearish", "mildly_bearish"}:
        entry_high = max(price, min(resistance, price + 0.45 * atr))
        entry_low = min(entry_high, max(price - 0.15 * atr, support))
        stop = max(entry_high + 0.6 * atr, resistance + 0.15 * atr)
        target1_high = min(price - 0.55 * atr, support)
        target1_low = target1_high - 0.35 * atr
        target2_high = target1_low
        target2_low = target2_high - 0.65 * atr
    else:
        entry_low = max(support, price - 0.35 * atr)
        entry_high = min(resistance, price + 0.35 * atr)
        stop = support - 0.35 * atr
        target1_low = max(price + 0.35 * atr, entry_high)
        target1_high = target1_low + 0.25 * atr
        target2_low = target1_high
        target2_high = target2_low + 0.35 * atr
    risk = abs(((entry_low + entry_high) / 2) - stop)
    reward = abs(((target1_low + target1_high) / 2) - ((entry_low + entry_high) / 2))
    rr = None if risk <= 0 else round(reward / risk, 2)
    return {
        "entry_zone": {"low": round(entry_low, 2), "high": round(entry_high, 2)},
        "invalidation_level": round(stop, 2),
        "stop_reference": round(stop, 2),
        "target_zone_1": {"low": round(min(target1_low, target1_high), 2), "high": round(max(target1_low, target1_high), 2)},
        "target_zone_2": {"low": round(min(target2_low, target2_high), 2), "high": round(max(target2_low, target2_high), 2)},
        "expected_move": round(abs(target1_high - price), 2),
        "reward_risk_ratio": rr,
        "prediction_status": "available",
    }


def build_daily_tactical_strategy(market: str, quote: dict[str, Any], technical: dict[str, Any], *, market_context: dict[str, Any] | None = None, research: dict[str, Any] | None = None, generated_at: str | None = None, source_refs: list[str] | None = None) -> dict[str, Any]:
    if market not in MARKETS:
        raise ValueError(f"unsupported market: {market}")
    indicators = technical.get("indicators", {}) if isinstance(technical, dict) else {}
    price = _num(quote.get("last_price")) or _num(indicators.get("latest_close"))
    history_days = int((technical.get("data_quality") or {}).get("history_days") or 0) if isinstance(technical, dict) else 0
    atr_pct = _num(indicators.get("atr_like_range_pct")) or _num(indicators.get("daily_range_pct")) or _num(indicators.get("return_volatility_pct"))
    data_ok = bool(price and atr_pct and history_days >= 20)
    volatility_state = str(technical.get("volatility_state") or "insufficient_data") if isinstance(technical, dict) else "insufficient_data"
    trend_1m = str(technical.get("trend_1m") or "neutral") if isinstance(technical, dict) else "neutral"
    trend_3m = str(technical.get("trend_3m") or "neutral") if isinstance(technical, dict) else "neutral"
    rsi = _num(indicators.get("rsi14"))
    macd_hist = _num(indicators.get("macd_histogram"))
    market_score = _num((market_context or {}).get("market_environment_score")) or 50.0
    event_risk = str((research or {}).get("earnings", {}).get("event_risk_level") or "low")
    material_news = (research or {}).get("material_news", {}).get("items", []) if isinstance(research, dict) else []
    if not data_ok:
        score = None
        direction = "neutral"
        setup_type = "insufficient_data"
    else:
        score = 50.0
        score += 10 if trend_1m == "bullish" else -10 if trend_1m == "bearish" else 0
        score += 6 if trend_3m == "bullish" else -6 if trend_3m == "bearish" else 0
        if rsi is not None:
            score += 7 if 45 <= rsi <= 65 else -8 if rsi >= 75 else 4 if rsi <= 35 else 0
        if macd_hist is not None:
            score += 6 if macd_hist > 0 else -6
        score += (market_score - 50) * 0.22
        if material_news:
            score += 3
        if event_risk == "medium":
            score -= 5
        if event_risk == "high":
            score -= 14
        if volatility_state == "high":
            score -= 4
        score = _clamp(score)
        direction = _score_to_direction(score)
        if event_risk == "high":
            setup_type = "no_trade"
        elif direction in {"bullish", "mildly_bullish"} and rsi is not None and rsi > 70:
            setup_type = "pullback"
        elif direction in {"bullish", "mildly_bullish"}:
            setup_type = "trend_continuation" if trend_1m == "bullish" else "breakout"
        elif direction in {"bearish", "mildly_bearish"}:
            setup_type = "mean_reversion" if rsi is not None and rsi < 35 else "range_trade"
        else:
            setup_type = "range_trade"
    chase_risk = "high" if rsi is not None and rsi >= 72 else "medium" if volatility_state == "high" else "low"
    gap_risk = "medium" if _num(quote.get("pre_market_price")) is not None and _num(quote.get("previous_close")) not in (None, 0) else "low"
    levels = _ordered_levels(float(price), direction, setup_type, float(atr_pct), indicators, event_risk) if data_ok else _empty_levels("insufficient_data")
    tactical_score = score
    confidence = _confidence(tactical_score, data_ok, volatility_state, event_risk)
    if market == "US":
        factors = [
            _factor("premarket_gap", 52 if gap_risk != "low" else 50, f"pre-market availability={gap_risk}", source_refs),
            _factor("momentum", 56 if macd_hist and macd_hist > 0 else 44 if macd_hist and macd_hist < 0 else 50, "MACD histogram momentum", source_refs),
            _factor("trend_strength", 62 if trend_1m == "bullish" else 38 if trend_1m == "bearish" else 50, f"1M trend={trend_1m}", source_refs),
            _factor("relative_volume", 50, "relative volume reserved when intraday volume is available", source_refs, "partial"),
            _factor("breakout_quality", 58 if setup_type in {"breakout", "trend_continuation"} else 48, f"setup={setup_type}", source_refs),
            _factor("mean_reversion_risk", 42 if chase_risk == "high" else 55, f"chase_risk={chase_risk}", source_refs),
            _factor("volatility_risk", 40 if volatility_state == "high" else 56, f"volatility={volatility_state}", source_refs),
            _factor("benchmark_context", market_score, "SPY/QQQ/VIX context", ["market_context"]),
            _factor("sector_context", 50, "sector ETF context available when mapped", source_refs, "partial"),
            _factor("earnings_event_risk", 35 if event_risk == "high" else 45 if event_risk == "medium" else 55, f"event_risk={event_risk}", source_refs),
            _factor("official_news_catalyst", 57 if material_news else 50, "material news catalyst count", source_refs),
        ]
    else:
        factors = [
            _factor("price_momentum", 56 if macd_hist and macd_hist > 0 else 44 if macd_hist and macd_hist < 0 else 50, "TW price momentum from technical state", source_refs),
            _factor("trend_strength", 62 if trend_1m == "bullish" else 38 if trend_1m == "bearish" else 50, f"TW 1M trend={trend_1m}", source_refs),
            _factor("breakout_quality", 58 if setup_type in {"breakout", "trend_continuation"} else 48, f"setup={setup_type}", source_refs),
            _factor("volume_confirmation", 50, "TW volume confirmation reserved when runtime volume exists", source_refs, "partial"),
            _factor("chip_confirmation", 50, "TW chip/flow evidence scoped to TW only", ["tw_chip_flow"], "partial"),
            _factor("mean_reversion_risk", 42 if chase_risk == "high" else 55, f"chase_risk={chase_risk}", source_refs),
            _factor("volatility_risk", 40 if volatility_state == "high" else 56, f"volatility={volatility_state}", source_refs),
            _factor("market_context", market_score, "TW market/sector context only", ["tw_market_context"], "partial"),
            _factor("event_risk", 35 if event_risk == "high" else 50, f"event_risk={event_risk}", source_refs),
            _factor("data_completeness", 70 if data_ok else 25, f"history_days={history_days}", source_refs),
        ]
    return {
        "market": market,
        "strategy_type": DAILY_TACTICAL,
        "strategy_version": US_TACTICAL_VERSION if market == "US" else TW_TACTICAL_VERSION,
        "generated_at": generated_at or now_taipei(),
        "horizon": "current_session_next_session_1_to_5_trading_days",
        "score": tactical_score,
        "tactical_score": tactical_score,
        "tactical_grade": _grade(tactical_score, "available" if data_ok else "insufficient_data"),
        "tactical_direction": direction,
        "action": _action(direction, setup_type, chase_risk, event_risk),
        "confidence": confidence,
        "tactical_confidence": confidence,
        "setup_type": setup_type,
        "entry_zone": levels.get("entry_zone"),
        "invalidation_level": levels.get("invalidation_level"),
        "stop_reference": levels.get("stop_reference"),
        "target_zone_1": levels.get("target_zone_1"),
        "target_zone_2": levels.get("target_zone_2"),
        "expected_move": levels.get("expected_move"),
        "reward_risk_ratio": levels.get("reward_risk_ratio"),
        "chase_risk": chase_risk,
        "gap_risk": gap_risk,
        "event_risk": event_risk,
        "holding_horizon": "1-5 trading days",
        "tactical_rationale": "Daily Tactical uses price momentum, trend, volatility, market context, and event risk. It is independent from Research / Position score.",
        "risk_notes": ["研究參考，不是下單指令。", "若觸發條件未出現，不應把 setup 視為失敗交易。"],
        "prediction_status": levels.get("prediction_status"),
        "data_quality": "available" if data_ok else "insufficient_data",
        "factor_version": US_TACTICAL_FACTOR_VERSION if market == "US" else TW_TACTICAL_FACTOR_VERSION,
        "weight_version": TACTICAL_WEIGHT_VERSIONS[market]["version"],
        "factors": factors,
        "review_contract": {
            "strategy_type": DAILY_TACTICAL,
            "trigger_aware": True,
            "statuses": ["win", "loss", "breakeven", "not_triggered", "correctly_avoided", "invalid_data", "pending"],
            "not_triggered_is_not_loss": True,
            "metrics": ["direction_correctness", "entry_zone_touched", "stop_reference_breached", "target_zone_reached", "maximum_favorable_excursion", "maximum_adverse_excursion", "reward_risk_realized", "false_breakout", "missed_opportunity", "confidence_calibration", "action_effectiveness"],
        },
    }


def build_dual_strategies(market: str, score_payload: dict[str, Any], prediction: dict[str, Any], quote: dict[str, Any], technical: dict[str, Any], *, market_context: dict[str, Any] | None = None, research: dict[str, Any] | None = None, generated_at: str | None = None) -> dict[str, Any]:
    research_strategy = build_research_position_strategy(
        market,
        score_payload,
        prediction,
        generated_at=generated_at,
        factor_version=(research or {}).get("research_factors", {}).get("research_factor_version") if isinstance(research, dict) else None,
    )
    tactical_strategy = build_daily_tactical_strategy(
        market,
        quote,
        technical,
        market_context=market_context,
        research=research,
        generated_at=generated_at,
        source_refs=["live_market_data", "technical_indicators", "market_context", "research_intelligence"] if market == "US" else ["tw_runtime_artifact", "tw_technical_context"],
    )
    return {RESEARCH_POSITION: research_strategy, DAILY_TACTICAL: tactical_strategy}


def validate_strategy_payload(payload: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if payload.get("market") not in MARKETS:
        reasons.append("invalid market")
    if payload.get("strategy_type") not in STRATEGY_TYPES:
        reasons.append("invalid strategy_type")
    for field in ["strategy_version", "generated_at", "horizon", "action", "risk_notes", "data_quality", "factor_version"]:
        if field not in payload:
            reasons.append(f"missing {field}")
    return reasons
