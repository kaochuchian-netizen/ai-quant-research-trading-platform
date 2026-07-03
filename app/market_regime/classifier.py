from __future__ import annotations
from typing import Any
from app.market_regime.schemas import MarketRegimeResult, SUPPORTED_REASON_CODES, SUPPORTED_REGIMES

MIN_SAMPLE_SIZE = 10
HIGH_VOL_THRESHOLD = 0.28
TREND_UP_THRESHOLD = 0.04
TREND_DOWN_THRESHOLD = -0.04
RISK_ON_BREADTH = 1.20
RISK_OFF_BREADTH = 0.85
DRAWDOWN_RISK_OFF = -0.08

def _num(metrics: dict[str, Any], key: str) -> float | None:
    value = metrics.get(key)
    if isinstance(value, (int, float)):
        return float(value)
    return None

def clamp_confidence(value: float) -> float:
    return max(0.0, min(1.0, round(value, 4)))

def classify_market_regime(payload: dict[str, Any]) -> MarketRegimeResult:
    metrics = payload.get("metrics") if isinstance(payload.get("metrics"), dict) else {}
    sample_size = int(payload.get("sample_size") or 0)
    required = ["index_return_20d", "realized_volatility_20d", "advance_decline_ratio", "max_drawdown_20d"]
    missing = [key for key in required if _num(metrics, key) is None]
    if sample_size < MIN_SAMPLE_SIZE or missing:
        reasons = []
        if sample_size < MIN_SAMPLE_SIZE:
            reasons.append("sample_size_below_minimum")
        if missing:
            reasons.append("missing_required_metrics")
        return MarketRegimeResult(
            regime="insufficient_data",
            confidence=0.0,
            reason_codes=reasons,
            metrics_used={key: metrics.get(key) for key in required},
            limitations=["insufficient deterministic market history for regime classification"],
        )

    ret20 = _num(metrics, "index_return_20d") or 0.0
    vol20 = _num(metrics, "realized_volatility_20d") or 0.0
    breadth = _num(metrics, "advance_decline_ratio") or 1.0
    drawdown = _num(metrics, "max_drawdown_20d") or 0.0
    above_ma20 = _num(metrics, "above_ma20_ratio")

    reason_codes: list[str] = []
    regime = "range_bound"
    confidence = 0.55

    if vol20 >= HIGH_VOL_THRESHOLD:
        regime = "high_volatility"
        confidence = 0.62 + min(0.25, (vol20 - HIGH_VOL_THRESHOLD) * 1.5)
        reason_codes.append("volatility_above_threshold")
    elif ret20 >= TREND_UP_THRESHOLD and breadth >= RISK_ON_BREADTH:
        regime = "risk_on" if drawdown > DRAWDOWN_RISK_OFF and breadth >= 1.35 else "trend_up"
        confidence = 0.64 + min(0.25, ret20 * 1.5) + min(0.08, (breadth - 1.0) * 0.08)
        reason_codes.extend(["positive_trend_strength", "breadth_positive", "momentum_positive"])
    elif ret20 <= TREND_DOWN_THRESHOLD and (breadth <= RISK_OFF_BREADTH or drawdown <= DRAWDOWN_RISK_OFF):
        regime = "risk_off" if drawdown <= DRAWDOWN_RISK_OFF else "trend_down"
        confidence = 0.64 + min(0.25, abs(ret20) * 1.5) + min(0.08, abs(min(0.0, drawdown)) * 0.8)
        reason_codes.extend(["negative_trend_strength", "breadth_negative", "momentum_negative"])
        if drawdown <= DRAWDOWN_RISK_OFF:
            reason_codes.append("drawdown_elevated")
    else:
        regime = "range_bound"
        confidence = 0.58
        reason_codes.extend(["low_trend_strength", "volatility_below_threshold"])

    if above_ma20 is not None and above_ma20 >= 0.60 and regime in {"trend_up", "risk_on"}:
        confidence += 0.03
    if above_ma20 is not None and above_ma20 <= 0.40 and regime in {"trend_down", "risk_off"}:
        confidence += 0.03

    reason_codes = [code for code in dict.fromkeys(reason_codes) if code in SUPPORTED_REASON_CODES]
    if regime not in SUPPORTED_REGIMES:
        regime = "insufficient_data"
        reason_codes = ["missing_required_metrics"]
        confidence = 0.0

    return MarketRegimeResult(
        regime=regime,
        confidence=clamp_confidence(confidence),
        reason_codes=reason_codes,
        metrics_used={
            "index_return_20d": ret20,
            "realized_volatility_20d": vol20,
            "advance_decline_ratio": breadth,
            "max_drawdown_20d": drawdown,
            "above_ma20_ratio": above_ma20,
        },
        limitations=["offline deterministic classifier; no live API or production strategy mutation"],
    )
