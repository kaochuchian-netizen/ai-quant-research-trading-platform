"""Read-only backtest and calibration engine for deterministic_baseline_v1."""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from statistics import mean, median, pstdev
from typing import Any

from analysis.forecast.formal_forecast_value_engine import (
    MODEL_VERSION,
    OhlcvRow,
    _mean,
    _round_price,
    _trend_bias,
    _trend_from_signals,
    load_historical_rows,
    normalize_stock_id,
    stable_json,
)

DEFAULT_LOOKBACK_DAYS = 120

@dataclass(frozen=True)
class BacktestPrediction:
    stock_id: str
    stock_name: str | None
    prediction_date: date
    same_day_high_prediction: float | None
    same_day_low_prediction: float | None
    next_day_high_prediction: float | None
    next_day_low_prediction: float | None
    one_month_trend: str
    three_month_trend: str
    confidence_score: int | None
    confidence_level: str
    base_range_pct: float | None
    interval_width_pct: float | None
    missing_fields: tuple[str, ...]
    insufficient_data_reasons: tuple[str, ...]


def _pct(numerator: float, denominator: float) -> float | None:
    if denominator <= 0:
        return None
    value = numerator / denominator
    return value if math.isfinite(value) else None


def _rate(count: int, total: int) -> float | None:
    return round(count * 100 / total, 4) if total else None


def _confidence_level(score: int | None) -> str:
    if score is None:
        return "insufficient_data"
    if score < 40:
        return "low"
    if score < 60:
        return "medium"
    return "medium_high"


def _volatility_regime(base_range_pct: float | None) -> str:
    if base_range_pct is None:
        return "insufficient_data"
    if base_range_pct < 0.025:
        return "low_volatility"
    if base_range_pct < 0.05:
        return "medium_volatility"
    return "high_volatility"


def compute_prediction_from_rows(stock_id: str, stock_name: str | None, rows_until_prediction_day: list[OhlcvRow]) -> BacktestPrediction:
    """Replay deterministic_baseline_v1 from a historical cutoff without mutating the V1 engine."""
    if not rows_until_prediction_day:
        return BacktestPrediction(stock_id, stock_name, date.min, None, None, None, None, "uncertain", "uncertain", None, "insufficient_data", None, None, ("historical_ohlcv",), ("missing_historical_ohlcv",))
    prediction_day = rows_until_prediction_day[-1].day
    if len(rows_until_prediction_day) < 20:
        missing = ("same_day_high_prediction", "same_day_low_prediction", "next_day_high_prediction", "next_day_low_prediction", "required_historical_ohlcv_20d")
        return BacktestPrediction(stock_id, stock_name, prediction_day, None, None, None, None, "uncertain", "uncertain", None, "insufficient_data", None, None, missing, ("historical_ohlcv_less_than_20_days",))

    rows = rows_until_prediction_day
    latest = rows[-1]
    closes = [r.close for r in rows]
    last20 = rows[-20:]
    daily_range_pct = median([_pct(r.high - r.low, r.close) or 0 for r in last20])
    log_returns = [math.log(rows[i].close / rows[i - 1].close) for i in range(max(1, len(rows) - 20), len(rows)) if rows[i - 1].close > 0]
    return_volatility_pct = pstdev(log_returns) if len(log_returns) >= 2 else 0.0
    true_ranges: list[float] = []
    for i in range(max(1, len(rows) - 20), len(rows)):
        prev_close = rows[i - 1].close
        true_range = max(rows[i].high - rows[i].low, abs(rows[i].high - prev_close), abs(rows[i].low - prev_close))
        true_ranges.append(_pct(true_range, rows[i].close) or 0)
    atr_like_range_pct = median(true_ranges) if true_ranges else daily_range_pct
    base_range_pct = median([daily_range_pct, return_volatility_pct, atr_like_range_pct])
    if base_range_pct <= 0:
        return BacktestPrediction(stock_id, stock_name, prediction_day, None, None, None, None, "uncertain", "uncertain", None, "insufficient_data", base_range_pct, None, ("range_statistics",), ("non_positive_range_statistics",))

    ma20 = _mean(closes[-20:]) if len(closes) >= 20 else None
    ma60 = _mean(closes[-60:]) if len(closes) >= 60 else None
    ma20_slope = (ma20 - (_mean(closes[-21:-1]) or ma20)) if len(closes) >= 21 and ma20 is not None else (latest.close - closes[-5] if len(closes) >= 5 else None)
    ma60_slope = (ma60 - (_mean(closes[-61:-1]) or ma60)) if len(closes) >= 61 and ma60 is not None else None
    ret20 = _pct(latest.close - closes[-20], closes[-20]) if len(closes) >= 20 else None
    ret60 = _pct(latest.close - closes[-60], closes[-60]) if len(closes) >= 60 else None
    one_month_trend = _trend_from_signals(latest.close, ma20, ma20_slope, ret20)
    missing: list[str] = []
    insufficient: list[str] = []
    if len(rows) < 120:
        three_month_trend = "uncertain"
        missing.append("three_month_trend")
        insufficient.append("insufficient_120d_history")
    else:
        three_month_trend = _trend_from_signals(latest.close, ma60, ma60_slope, ret60)

    up_bias, down_bias = _trend_bias(one_month_trend)
    next_day_multiplier = 1.15
    same_high = _round_price(latest.close * (1 + base_range_pct * up_bias))
    same_low = _round_price(latest.close * (1 - base_range_pct * down_bias))
    next_high = _round_price(latest.close * (1 + base_range_pct * up_bias * next_day_multiplier))
    next_low = _round_price(latest.close * (1 - base_range_pct * down_bias * next_day_multiplier))
    if same_high < same_low or next_high < next_low:
        return BacktestPrediction(stock_id, stock_name, prediction_day, None, None, None, None, one_month_trend, three_month_trend, None, "insufficient_data", base_range_pct, None, ("forecast_interval",), ("invalid_high_low_order_after_rounding",))

    data_completeness_score = 25 if len(rows) >= 60 else 20
    freshness_score = 15
    volatility_stability_score = max(0, min(20, int(round(20 * (1 - min(base_range_pct / 0.10, 1))))))
    confidence_score = min(75, data_completeness_score + freshness_score + volatility_stability_score + 15)
    interval_width_pct = _pct(same_high - same_low, latest.close)
    return BacktestPrediction(stock_id, stock_name, prediction_day, same_high, same_low, next_high, next_low, one_month_trend, three_month_trend, confidence_score, _confidence_level(confidence_score), base_range_pct, interval_width_pct, tuple(sorted(set(missing))), tuple(sorted(set(insufficient))))


def _interval_status(actual: OhlcvRow | None, predicted_high: float | None, predicted_low: float | None) -> str:
    if actual is None or predicted_high is None or predicted_low is None:
        return "insufficient_data"
    high_ok = actual.high <= predicted_high
    low_ok = actual.low >= predicted_low
    if high_ok and low_ok:
        return "hit"
    if high_ok or low_ok:
        return "partial_hit"
    return "miss"


def _direction_result(prediction: BacktestPrediction, actual: OhlcvRow | None, previous: OhlcvRow | None) -> str:
    if actual is None or previous is None or prediction.one_month_trend not in {"bullish", "bearish", "neutral"}:
        return "insufficient_data"
    actual_direction = "bullish" if actual.close > previous.close else "bearish" if actual.close < previous.close else "neutral"
    if prediction.one_month_trend == "neutral" or actual_direction == "neutral":
        return "neutral"
    return "correct" if prediction.one_month_trend == actual_direction else "incorrect"


def _evaluate_case(stock_id: str, stock_name: str | None, rows: list[OhlcvRow], idx: int) -> dict[str, Any]:
    prediction = compute_prediction_from_rows(stock_id, stock_name, rows[: idx + 1])
    same_actual = rows[idx] if idx < len(rows) else None
    next_actual = rows[idx + 1] if idx + 1 < len(rows) else None
    previous_actual = rows[idx - 1] if idx > 0 else None
    high_error = low_error = high_error_pct = low_error_pct = None
    if same_actual and prediction.same_day_high_prediction is not None and prediction.same_day_low_prediction is not None:
        high_error = same_actual.high - prediction.same_day_high_prediction
        low_error = same_actual.low - prediction.same_day_low_prediction
        high_error_pct = _pct(high_error, prediction.same_day_high_prediction)
        low_error_pct = _pct(low_error, prediction.same_day_low_prediction)
    missing = list(prediction.missing_fields)
    insufficient = list(prediction.insufficient_data_reasons)
    if next_actual is None:
        missing.append("next_day_actual")
        insufficient.append("next_day_actual_not_available")
    return {
        "stock_id": stock_id,
        "stock_name": stock_name,
        "prediction_date": prediction.prediction_date.isoformat(),
        "same_day_interval_status": _interval_status(same_actual, prediction.same_day_high_prediction, prediction.same_day_low_prediction),
        "next_day_interval_status": _interval_status(next_actual, prediction.next_day_high_prediction, prediction.next_day_low_prediction),
        "direction_result": _direction_result(prediction, same_actual, previous_actual),
        "same_day_high_prediction": prediction.same_day_high_prediction,
        "same_day_low_prediction": prediction.same_day_low_prediction,
        "next_day_high_prediction": prediction.next_day_high_prediction,
        "next_day_low_prediction": prediction.next_day_low_prediction,
        "actual_high": same_actual.high if same_actual else None,
        "actual_low": same_actual.low if same_actual else None,
        "actual_close": same_actual.close if same_actual else None,
        "high_error_abs": abs(high_error) if high_error is not None else None,
        "low_error_abs": abs(low_error) if low_error is not None else None,
        "high_error_pct": abs(high_error_pct) if high_error_pct is not None else None,
        "low_error_pct": abs(low_error_pct) if low_error_pct is not None else None,
        "interval_width_pct": prediction.interval_width_pct,
        "one_month_trend": prediction.one_month_trend,
        "three_month_trend": prediction.three_month_trend,
        "volatility_regime": _volatility_regime(prediction.base_range_pct),
        "confidence_score": prediction.confidence_score,
        "confidence_level": prediction.confidence_level,
        "missing_fields": sorted(set(missing)),
        "insufficient_data_reasons": sorted(set(insufficient)),
    }


def _mean_or_none(values: list[float]) -> float | None:
    return round(mean(values), 4) if values else None


def _summarize_cases(cases: list[dict[str, Any]]) -> dict[str, Any]:
    eligible = [c for c in cases if c.get("same_day_interval_status") != "insufficient_data"]
    next_eligible = [c for c in cases if c.get("next_day_interval_status") != "insufficient_data"]
    direction_eligible = [c for c in cases if c.get("direction_result") in {"correct", "incorrect"}]
    widths = [float(c["interval_width_pct"]) for c in eligible if isinstance(c.get("interval_width_pct"), (int, float))]
    high_errors = [float(c["high_error_abs"]) for c in eligible if isinstance(c.get("high_error_abs"), (int, float))]
    low_errors = [float(c["low_error_abs"]) for c in eligible if isinstance(c.get("low_error_abs"), (int, float))]
    high_error_pct = [float(c["high_error_pct"]) for c in eligible if isinstance(c.get("high_error_pct"), (int, float))]
    low_error_pct = [float(c["low_error_pct"]) for c in eligible if isinstance(c.get("low_error_pct"), (int, float))]
    same_hits = sum(1 for c in eligible if c.get("same_day_interval_status") == "hit")
    next_hits = sum(1 for c in next_eligible if c.get("next_day_interval_status") == "hit")
    partials = sum(1 for c in eligible if c.get("same_day_interval_status") == "partial_hit")
    misses = sum(1 for c in eligible if c.get("same_day_interval_status") == "miss")
    return {
        "sample_count": len(cases),
        "eligible_sample_count": len(eligible),
        "same_day_interval_hit_rate": _rate(same_hits, len(eligible)),
        "next_day_interval_hit_rate": _rate(next_hits, len(next_eligible)),
        "partial_hit_rate": _rate(partials, len(eligible)),
        "under_covered_rate": _rate(misses, len(eligible)),
        "high_error_abs_mean": _mean_or_none(high_errors),
        "low_error_abs_mean": _mean_or_none(low_errors),
        "high_error_pct_mean": round(mean(high_error_pct) * 100, 4) if high_error_pct else None,
        "low_error_pct_mean": round(mean(low_error_pct) * 100, 4) if low_error_pct else None,
        "interval_width_pct_mean": round(mean(widths) * 100, 4) if widths else None,
        "over_wide_rate": _rate(sum(1 for w in widths if w > 0.12), len(widths)),
        "direction_accuracy": _rate(sum(1 for c in direction_eligible if c.get("direction_result") == "correct"), len(direction_eligible)),
    }


def _group_rates(cases: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for case in cases:
        groups.setdefault(str(case.get(key) or "unknown"), []).append(case)
    return [{key: name, **_summarize_cases(groups[name])} for name in sorted(groups)]


def _confidence_bucket_rates(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for name, midpoint in [("low", 19.5), ("medium", 49.5), ("medium_high", 67.5)]:
        bucket_cases = [c for c in cases if c.get("confidence_level") == name]
        eligible = [c for c in bucket_cases if c.get("same_day_interval_status") != "insufficient_data"]
        hit_rate = _rate(sum(1 for c in eligible if c.get("same_day_interval_status") == "hit"), len(eligible))
        out.append({
            "confidence_bucket": name,
            "sample_count": len(bucket_cases),
            "eligible_sample_count": len(eligible),
            "hit_rate": hit_rate,
            "bucket_midpoint": midpoint,
            "confidence_calibration_gap": round(hit_rate - midpoint, 4) if hit_rate is not None else None,
            "status": "ok" if len(eligible) >= 10 else "insufficient_sample_size",
        })
    return out


def _calibration_recommendations(metrics: dict[str, Any], confidence_buckets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    recommendations: list[dict[str, Any]] = []
    hit = metrics.get("same_day_interval_hit_rate")
    under = metrics.get("under_covered_rate")
    over = metrics.get("over_wide_rate")
    if hit is None:
        recommendations.append({"recommendation_id": "calibration_insufficient_samples", "recommendation_type": "data_collection", "proposal": "累積更多正式 forecast / actual outcome 後再調整 deterministic_baseline_v1。", "rationale": "eligible samples are insufficient.", "production_formula_changed": False})
    elif under is not None and under > 35:
        recommendations.append({"recommendation_id": "consider_wider_range_multiplier", "recommendation_type": "range_multiplier_proposal", "proposal": "評估提高 range multiplier，但需另開任務回測後才可套用。", "rationale": f"under_covered_rate={under}% suggests intervals may be too narrow.", "production_formula_changed": False})
    elif over is not None and over > 70:
        recommendations.append({"recommendation_id": "consider_narrower_range_multiplier", "recommendation_type": "range_multiplier_proposal", "proposal": "評估降低 range multiplier 或依 volatility regime 分層，但本任務不改公式。", "rationale": f"over_wide_rate={over}% suggests intervals may be too wide.", "production_formula_changed": False})
    else:
        recommendations.append({"recommendation_id": "retain_formula_pending_longer_backtest", "recommendation_type": "monitoring_proposal", "proposal": "暫不調整 deterministic_baseline_v1，持續累積正式 artifact 與 actual outcome。", "rationale": "Current backtest did not trigger a severe width warning.", "production_formula_changed": False})
    for bucket in confidence_buckets:
        if bucket.get("status") == "ok" and isinstance(bucket.get("confidence_calibration_gap"), (int, float)) and bucket["confidence_calibration_gap"] < -15:
            recommendations.append({"recommendation_id": "review_confidence_cap_or_formula", "recommendation_type": "confidence_cap_proposal", "proposal": "評估降低 V1 confidence cap 或提高 evidence coverage 門檻。", "rationale": f"{bucket['confidence_bucket']} bucket trails midpoint by {abs(bucket['confidence_calibration_gap'])} points.", "production_formula_changed": False})
    return recommendations


def build_backtest_report(stock_universe: list[dict[str, Any]], *, start_date: date | None = None, end_date: date | None = None, lookback_days: int = DEFAULT_LOOKBACK_DAYS, generated_at: str | None = None) -> dict[str, Any]:
    end_date = end_date or date(2026, 7, 6)
    start_date = start_date or (end_date - timedelta(days=lookback_days))
    generated_at = generated_at or datetime(2026, 7, 7, 9, 30).isoformat() + "+08:00"
    all_cases: list[dict[str, Any]] = []
    per_stock: list[dict[str, Any]] = []
    insufficient_stocks: list[dict[str, Any]] = []
    for stock in stock_universe:
        stock_id = str(stock.get("stock_id"))
        stock_name = stock.get("stock_name")
        rows = load_historical_rows(stock_id)
        indexes = [idx for idx, row in enumerate(rows) if start_date <= row.day <= end_date]
        if len(rows) < 20 or not indexes:
            insufficient_stocks.append({"stock_id": stock_id, "stock_name": stock_name, "available_history_rows": len(rows), "selected_sample_count": len(indexes), "status": "insufficient_data", "insufficient_data_reasons": ["historical_ohlcv_less_than_20_days" if len(rows) < 20 else "no_rows_in_backtest_window"]})
            continue
        stock_cases = [_evaluate_case(stock_id, stock_name, rows, idx) for idx in indexes]
        all_cases.extend(stock_cases)
        per_stock.append({"stock_id": stock_id, "stock_name": stock_name, **_summarize_cases(stock_cases)})

    metrics = _summarize_cases(all_cases)
    confidence_buckets = _confidence_bucket_rates(all_cases)
    gaps = [b["confidence_calibration_gap"] for b in confidence_buckets if isinstance(b.get("confidence_calibration_gap"), (int, float))]
    metrics["confidence_bucket_hit_rate"] = confidence_buckets
    metrics["confidence_calibration_gap"] = round(mean(gaps), 4) if gaps else None
    metrics["per_stock_hit_rate"] = per_stock
    metrics["per_trend_regime_hit_rate"] = _group_rates(all_cases, "one_month_trend")
    metrics["per_volatility_regime_hit_rate"] = _group_rates(all_cases, "volatility_regime")
    recommendations = _calibration_recommendations(metrics, confidence_buckets)
    return {
        "schema_version": "formal_forecast_backtest_report_v1",
        "artifact_type": "formal_forecast_backtest_report",
        "task_id": "AI-DEV-153",
        "generated_at": generated_at,
        "method_under_test": MODEL_VERSION,
        "backtest_window": {"start_date": start_date.isoformat(), "end_date": end_date.isoformat(), "requested_lookback_days": lookback_days, "available_sample_count": len(all_cases), "window_degraded_to_available_data": bool(insufficient_stocks)},
        "stock_universe_count": len(stock_universe),
        "stock_universe": stock_universe,
        "data_source_policy": {"read_only_historical_ohlcv_csv": True, "read_only_sqlite_inspection_allowed": True, "external_api_called": False, "external_credentialed_api_called": False, "secrets_read": False, "db_write": False, "production_pipeline_executed": False},
        "metrics": metrics,
        "per_stock_results": per_stock,
        "insufficient_data": insufficient_stocks,
        "calibration_analysis": {"forecast_interval_too_narrow": bool(metrics.get("under_covered_rate") is not None and metrics["under_covered_rate"] > 35), "forecast_interval_too_wide": bool(metrics.get("over_wide_rate") is not None and metrics["over_wide_rate"] > 70), "bullish_bearish_bias_review": "Use per_trend_regime_hit_rate; proposals only, no formula mutation.", "confidence_score_over_optimistic": any((b.get("confidence_calibration_gap") or 0) < -15 for b in confidence_buckets if b.get("status") == "ok"), "confidence_score_over_conservative": any((b.get("confidence_calibration_gap") or 0) > 15 for b in confidence_buckets if b.get("status") == "ok"), "stocks_most_likely_to_miss": sorted(per_stock, key=lambda r: (r.get("under_covered_rate") is None, -(r.get("under_covered_rate") or 0), r.get("stock_id")))[:5], "volatility_regime_most_likely_to_miss": sorted(metrics["per_volatility_regime_hit_rate"], key=lambda r: (r.get("under_covered_rate") is None, -(r.get("under_covered_rate") or 0), r.get("volatility_regime")))[:3], "recommendations": recommendations},
        "sample_cases_preview": all_cases[:20],
        "source_evidence": [{"source_type": "historical_ohlcv_csv", "paths": [f"data/historical/{normalize_stock_id(str(s.get('stock_id')))}_daily.csv" for s in stock_universe], "read_mode": "read_only"}],
        "safety_policy": {"no_fake_metrics": True, "insufficient_data_explicit": True, "production_forecast_engine_mutated": False, "production_rating_action_confidence_weight_mutated": False, "db_write": False, "notification_sent": False, "scheduler_modified": False, "python_main_executed": False, "trading_or_order_executed": False, "secrets_read": False, "external_credentialed_api_called": False},
    }


def render_markdown(report: dict[str, Any]) -> str:
    metrics = report["metrics"]
    lines = [
        "# Formal Forecast Backtest & Calibration Report V1",
        "",
        f"Task: {report['task_id']}",
        f"Method under test: `{report['method_under_test']}`",
        f"Generated at: {report['generated_at']}",
        f"Window: {report['backtest_window']['start_date']} to {report['backtest_window']['end_date']}",
        "",
        "## Summary Metrics",
        "",
        f"- Stock universe count: {report['stock_universe_count']}",
        f"- Eligible sample count: {metrics.get('eligible_sample_count')}",
        f"- Same-day interval hit rate: {metrics.get('same_day_interval_hit_rate')}",
        f"- Next-day interval hit rate: {metrics.get('next_day_interval_hit_rate')}",
        f"- Under-covered rate: {metrics.get('under_covered_rate')}",
        f"- Over-wide rate: {metrics.get('over_wide_rate')}",
        f"- Direction accuracy: {metrics.get('direction_accuracy')}",
        "",
        "## Calibration Recommendations",
        "",
    ]
    for rec in report["calibration_analysis"]["recommendations"]:
        lines.append(f"- {rec['recommendation_id']}: {rec['proposal']} Production formula changed: {rec['production_formula_changed']}.")
    lines.extend(["", "## Safety", "", "This report is read-only. It does not mutate deterministic_baseline_v1, production ratings, actions, confidence, weights, DB, scheduler, notifications, or trading behavior.", ""])
    return "\n".join(lines)
