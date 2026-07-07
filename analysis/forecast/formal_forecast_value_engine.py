"""Deterministic baseline forecast value engine for AI-DEV-152."""
from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from statistics import median, pstdev
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
HISTORICAL_DIR = ROOT / "data" / "historical"
MODEL_VERSION = "deterministic_baseline_v1"
PRICE_FIELDS = ["same_day_high_prediction", "same_day_low_prediction", "next_day_high_prediction", "next_day_low_prediction"]
TREND_VALUES = {"bullish", "neutral", "bearish", "uncertain"}

@dataclass(frozen=True)
class OhlcvRow:
    day: date
    open: float
    high: float
    low: float
    close: float
    volume: float

def stable_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"

def normalize_stock_id(stock_id: str) -> str:
    raw = str(stock_id)
    return raw.zfill(4) if raw.isdigit() and len(raw) < 4 else raw

def _float(value: str) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None

def load_historical_rows(stock_id: str, historical_dir: Path = HISTORICAL_DIR) -> list[OhlcvRow]:
    path = historical_dir / f"{normalize_stock_id(stock_id)}_daily.csv"
    if not path.exists():
        return []
    rows: list[OhlcvRow] = []
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        for raw in csv.DictReader(fh):
            try:
                day = date.fromisoformat(str(raw.get("date", "")))
            except ValueError:
                continue
            vals = {k: _float(str(raw.get(k, ""))) for k in ["open", "high", "low", "close", "volume"]}
            if any(vals[k] is None for k in vals):
                continue
            high = float(vals["high"]); low = float(vals["low"]); close = float(vals["close"])
            if high <= 0 or low <= 0 or close <= 0 or high < low:
                continue
            rows.append(OhlcvRow(day=day, open=float(vals["open"]), high=high, low=low, close=close, volume=float(vals["volume"])))
    return sorted(rows, key=lambda row: row.day)

def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None

def _pct(numerator: float, denominator: float) -> float | None:
    if denominator <= 0:
        return None
    value = numerator / denominator
    return value if math.isfinite(value) else None

def _round_price(value: float) -> float:
    if value >= 1000:
        return round(value, 0)
    if value >= 100:
        return round(value, 1)
    return round(value, 2)

def _trend_from_signals(close: float, ma: float | None, slope: float | None, period_return: float | None) -> str:
    if ma is None or slope is None or period_return is None:
        return "uncertain"
    positives = [close > ma, slope > 0, period_return > 0]
    negatives = [close < ma, slope < 0, period_return < 0]
    if sum(positives) >= 2:
        return "bullish"
    if sum(negatives) >= 2:
        return "bearish"
    return "neutral"

def _trend_bias(trend: str) -> tuple[float, float]:
    if trend == "bullish":
        return 1.15, 0.85
    if trend == "bearish":
        return 0.85, 1.15
    return 1.0, 1.0

def _null_stock(stock_id: str, stock_name: str | None, run_date: date, rows: list[OhlcvRow], source_evidence: list[dict[str, Any]], reasons: list[str]) -> dict[str, Any]:
    latest = rows[-1] if rows else None
    missing = [*PRICE_FIELDS, "required_historical_ohlcv_20d"]
    return {
        "stock_id": str(stock_id), "stock_name": stock_name, "prediction_date": run_date.isoformat(), "next_trading_date": None,
        "same_day_high_prediction": None, "same_day_low_prediction": None, "next_day_high_prediction": None, "next_day_low_prediction": None,
        "one_month_trend": "uncertain", "three_month_trend": "uncertain", "confidence_score": None, "confidence_level": "insufficient_data",
        "evidence_summary": "insufficient_data: local historical OHLCV has fewer than 20 rows; no forecast values generated.",
        "key_factors": [], "risk_notes": ["資料不足，正式預測值維持資料待接。"], "source_evidence": source_evidence,
        "data_quality": {"completeness": "insufficient_data", "freshness": "missing" if latest is None else "partial", "latest_ohlcv_date": latest.day.isoformat() if latest else None, "history_row_count": len(rows), "confidence_basis": "insufficient 20D OHLCV history", "blocking_missing_fields": missing},
        "missing_fields": missing, "insufficient_data_reasons": reasons, "model_version": MODEL_VERSION,
        "method_metadata": {"method": MODEL_VERSION, "minimum_history_days": 20, "external_api_called": False},
        "created_at": datetime.combine(run_date, datetime.min.time()).replace(hour=7, minute=1).isoformat() + "+08:00",
    }

def compute_baseline(stock_id: str, stock_name: str | None, run_date: date, analysis_context: dict[str, Any] | None = None) -> dict[str, Any]:
    analysis_context = analysis_context or {}
    rows = load_historical_rows(stock_id)
    source_path = f"data/historical/{normalize_stock_id(stock_id)}_daily.csv"
    source_evidence: list[dict[str, Any]] = [
        {"source_type": "historical_ohlcv_csv", "path": source_path, "status": "available" if rows else "missing", "read_mode": "read_only", "row_count": len(rows)},
        {"source_type": "local_analysis_context", "status": "available_for_context_only" if analysis_context else "missing"},
    ]
    if len(rows) < 20:
        return _null_stock(stock_id, stock_name, run_date, rows, source_evidence, ["historical_ohlcv_less_than_20_days"])

    latest = rows[-1]
    closes = [r.close for r in rows]
    last20 = rows[-20:]
    daily_range_pct = median([_pct(r.high - r.low, r.close) or 0 for r in last20])
    log_returns = [math.log(rows[i].close / rows[i - 1].close) for i in range(max(1, len(rows) - 20), len(rows)) if rows[i - 1].close > 0]
    return_volatility_pct = pstdev(log_returns) if len(log_returns) >= 2 else 0.0
    true_ranges = []
    for i in range(max(1, len(rows) - 20), len(rows)):
        prev_close = rows[i - 1].close
        tr = max(rows[i].high - rows[i].low, abs(rows[i].high - prev_close), abs(rows[i].low - prev_close))
        true_ranges.append(_pct(tr, rows[i].close) or 0)
    atr_like_range_pct = median(true_ranges) if true_ranges else daily_range_pct
    base_range_pct = median([daily_range_pct, return_volatility_pct, atr_like_range_pct])
    if base_range_pct <= 0:
        return _null_stock(stock_id, stock_name, run_date, rows, source_evidence, ["non_positive_range_statistics"])

    ma20 = _mean(closes[-20:]) if len(closes) >= 20 else None
    ma60 = _mean(closes[-60:]) if len(closes) >= 60 else None
    ma20_slope = (ma20 - (_mean(closes[-21:-1]) or ma20)) if len(closes) >= 21 and ma20 is not None else (latest.close - closes[-5] if len(closes) >= 5 else None)
    ma60_slope = (ma60 - (_mean(closes[-61:-1]) or ma60)) if len(closes) >= 61 and ma60 is not None else None
    ret20 = _pct(latest.close - closes[-20], closes[-20]) if len(closes) >= 20 else None
    ret60 = _pct(latest.close - closes[-60], closes[-60]) if len(closes) >= 60 else None
    one_month_trend = _trend_from_signals(latest.close, ma20, ma20_slope, ret20)
    missing_fields: list[str] = []
    insufficient: list[str] = []
    if len(rows) < 120:
        three_month_trend = "uncertain"
        missing_fields.append("three_month_trend")
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
        return _null_stock(stock_id, stock_name, run_date, rows, source_evidence, ["invalid_high_low_order_after_rounding"])

    age_days = (run_date - latest.day).days
    freshness_score = 15 if age_days <= 1 else 8 if age_days <= 7 else 3
    data_completeness_score = 25 if len(rows) >= 60 else 20
    volatility_stability_score = max(0, min(20, int(round(20 * (1 - min(base_range_pct / 0.10, 1))))))
    evidence_coverage_score = 15
    confidence_score = min(75, data_completeness_score + freshness_score + volatility_stability_score + evidence_coverage_score)
    confidence_level = "low" if confidence_score < 40 else "medium" if confidence_score < 60 else "medium_high"
    source_evidence[0].update({"latest_ohlcv_date": latest.day.isoformat()})
    key_factors = [
        {"factor": "20d_median_daily_range_pct", "value": round(daily_range_pct, 6), "allowed_usage": "baseline_range"},
        {"factor": "20d_log_return_volatility_pct", "value": round(return_volatility_pct, 6), "allowed_usage": "baseline_range"},
        {"factor": "20d_median_atr_like_range_pct", "value": round(atr_like_range_pct, 6), "allowed_usage": "baseline_range"},
        {"factor": "one_month_trend_bias", "value": one_month_trend, "allowed_usage": "range_bias"},
    ]
    risk_notes = ["deterministic baseline V1，供決策參考，待回測校準。", "不修改 production rating/action/confidence/weight。"]
    if age_days > 1:
        risk_notes.append("歷史 OHLCV 非當日新鮮資料，forecast confidence 已降權。")
    if insufficient:
        risk_notes.append("部分長週期欄位資料不足，保留 uncertainty / missing_fields。")
    return {
        "stock_id": str(stock_id), "stock_name": stock_name, "prediction_date": run_date.isoformat(), "next_trading_date": None,
        "same_day_high_prediction": same_high, "same_day_low_prediction": same_low, "next_day_high_prediction": next_high, "next_day_low_prediction": next_low,
        "one_month_trend": one_month_trend, "three_month_trend": three_month_trend, "confidence_score": confidence_score, "confidence_level": confidence_level,
        "evidence_summary": f"{MODEL_VERSION}: 20D median range, log-return volatility, ATR-like range, MA/return trend bias from read-only historical OHLCV.",
        "key_factors": key_factors, "risk_notes": risk_notes, "source_evidence": source_evidence,
        "data_quality": {"completeness": "sufficient_for_baseline_range", "freshness": "fresh" if age_days <= 1 else "stale", "latest_ohlcv_date": latest.day.isoformat(), "history_row_count": len(rows), "confidence_basis": "artifact-level deterministic baseline formula capped at 75", "blocking_missing_fields": sorted(set(missing_fields))},
        "missing_fields": sorted(set(missing_fields)), "insufficient_data_reasons": sorted(set(insufficient)), "model_version": MODEL_VERSION,
        "method_metadata": {"method": MODEL_VERSION, "range_components": {"daily_range_pct_median_20d": round(daily_range_pct, 6), "return_volatility_pct_20d": round(return_volatility_pct, 6), "atr_like_range_pct_median_20d": round(atr_like_range_pct, 6), "base_range_pct": round(base_range_pct, 6)}, "trend_bias": {"one_month_trend": one_month_trend, "upside_multiplier": up_bias, "downside_multiplier": down_bias, "next_day_multiplier": next_day_multiplier}, "price_rounding": "round >=1000 to integer, >=100 to 1 decimal, else 2 decimals", "confidence_cap": 75, "external_api_called": False},
        "created_at": datetime.combine(run_date, datetime.min.time()).replace(hour=7, minute=1).isoformat() + "+08:00",
    }

def latest_actual_for(stock_id: str, review_date: date) -> tuple[OhlcvRow | None, OhlcvRow | None, int]:
    rows = load_historical_rows(stock_id)
    for idx, row in enumerate(rows):
        if row.day == review_date:
            return row, rows[idx - 1] if idx > 0 else None, len(rows)
    return None, None, len(rows)

def evaluate_prediction_stock(prediction: dict[str, Any], review_date: date) -> dict[str, Any]:
    stock_id = str(prediction.get("stock_id"))
    actual, prev, row_count = latest_actual_for(stock_id, review_date)
    missing: list[str] = []
    insufficient: list[str] = []
    source_evidence = [{"source_type": "formal_prediction_runtime", "status": "available", "model_version": prediction.get("model_version")}, {"source_type": "historical_ohlcv_csv_actual", "status": "available" if actual else "missing", "row_count": row_count, "read_mode": "read_only"}]
    actual_high = actual.high if actual else None; actual_low = actual.low if actual else None; actual_close = actual.close if actual else None
    pred_high = prediction.get("same_day_high_prediction"); pred_low = prediction.get("same_day_low_prediction")
    if actual and isinstance(pred_high, (int, float)) and isinstance(pred_low, (int, float)):
        high_ok = actual.high <= float(pred_high); low_ok = actual.low >= float(pred_low)
        hit_miss = "hit" if high_ok and low_ok else "partial_hit" if high_ok or low_ok else "miss"
        high_low_error = {"high_error_abs": round(actual.high - float(pred_high), 4), "low_error_abs": round(actual.low - float(pred_low), 4), "high_error_pct": round((actual.high - float(pred_high)) / float(pred_high), 6), "low_error_pct": round((actual.low - float(pred_low)) / float(pred_low), 6)}
    else:
        hit_miss = "insufficient_data"; high_low_error = None
        missing.extend(["actual_high", "actual_low", "actual_close", "high_low_forecast_error", "hit_miss_status"])
        insufficient.append("prediction_or_actual_missing")
    predicted_direction = prediction.get("one_month_trend")
    actual_direction = None
    if actual and prev and predicted_direction in {"bullish", "bearish", "neutral"}:
        actual_direction = "bullish" if actual.close > prev.close else "bearish" if actual.close < prev.close else "neutral"
        direction_result = "neutral" if predicted_direction == "neutral" or actual_direction == "neutral" else "correct" if predicted_direction == actual_direction else "incorrect"
    else:
        direction_result = "insufficient_data"
        missing.append("direction_result"); insufficient.append("direction_actual_or_prediction_missing")
    missing.extend(["seven_day_hit_rate", "confidence_calibration", "factor_effectiveness"])
    insufficient.append("insufficient_formal_prediction_actual_pairs_for_7d_review")
    return {
        "stock_id": stock_id, "stock_name": prediction.get("stock_name"), "review_date": review_date.isoformat(), "review_window_start": review_date.isoformat(), "review_window_end": review_date.isoformat(),
        "actual_high": actual_high, "actual_low": actual_low, "actual_close": actual_close, "direction_result": direction_result, "predicted_direction": predicted_direction, "actual_direction": actual_direction,
        "high_low_forecast_error": high_low_error, "hit_miss_status": hit_miss, "seven_day_hit_rate": None, "confidence_calibration": "insufficient_data", "factor_effectiveness": "insufficient_data",
        "error_reasons": [] if actual else ["actual outcome missing for review_date"], "recommendation_for_improvement": "資料不足，需累積更多正式 prediction / actual outcome artifact",
        "source_evidence": source_evidence,
        "data_quality": {"completeness": "reviewable_single_day" if actual and high_low_error else "insufficient_data", "freshness": "actual_available" if actual else "missing_actual_outcome", "confidence_basis": "single-day deterministic evaluation; seven-day review requires accumulated artifacts", "blocking_missing_fields": sorted(set(missing))},
        "missing_fields": sorted(set(missing)), "insufficient_data_reasons": sorted(set(insufficient)), "created_at": datetime.combine(review_date, datetime.min.time()).replace(hour=15, minute=1).isoformat() + "+08:00",
    }
