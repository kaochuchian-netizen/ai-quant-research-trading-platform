# AI-DEV-152 Formal Forecast Value Engine V1

## Purpose
AI-DEV-152 introduces the first deterministic baseline forecast value engine for formal prediction runtime artifacts. It advances the platform from null-safe artifact wiring to explainable, reviewable baseline forecast values.

## Method Overview
The V1 method is deterministic_baseline_v1. It is not a black-box AI forecast and does not claim to be a final calibrated production model.

For each stock, the engine reads local historical OHLCV CSV files in read-only mode. It requires at least 20 trading rows for high/low value generation. If the minimum data requirement is not met, price prediction fields remain null and the artifact records missing_fields and insufficient_data_reasons.

## Baseline Formula
For the latest available close, the engine computes:

- 20D median daily_range_pct = median((high - low) / close)
- 20D log-return volatility = population standard deviation of log returns
- 20D median ATR-like range = median(true_range / close)
- base_range_pct = median of those three range components

The same-day range is derived from latest_close and a trend bias. The next-day range uses the documented next_day_multiplier of 1.15. Price rounding is deterministic: prices >= 1000 round to integer, prices >= 100 round to one decimal, otherwise two decimals.

## Trend Classification
one_month_trend uses close vs MA20, MA20 slope, and 20D return. three_month_trend requires longer history; if 120D history is unavailable it remains uncertain and records insufficient_120d_history.

Trend values are controlled: bullish, neutral, bearish, uncertain.

## Confidence Score
This is artifact-level forecast confidence only. It does not modify production scoring confidence, rating, action, or factor weights.

The V1 score combines:

- data_completeness_score
- freshness_score
- volatility_stability_score
- evidence_coverage_score

V1 confidence_score is capped at 75. It may emit low, medium, or medium_high. It does not emit high or very_high.

## Review Evaluation
The review builder compares formal prediction artifacts with read-only historical actual outcomes when an actual row exists for the review date. It calculates actual_high, actual_low, actual_close, high/low forecast error, hit_miss_status, and direction_result.

Seven-day hit rate remains null until enough formal prediction/actual pairs are available. The engine must not fabricate hit rates or review metrics.

## Dashboard Binding
The Dashboard displays formal prediction values when non-null. Missing values remain 資料待接. It also displays deterministic_baseline_v1, confidence, data quality, source evidence, risk notes, and review results when available.

## Safety Boundaries
No external API calls. No secrets or .env reads. No DB writes. No scheduler changes. No LINE or Email delivery. No python3 main.py. No production pipeline execution. No broker/order/trading. No production rating/action/confidence/weight mutation.

## Future Calibration Roadmap
Future work should add historical backtest calibration, model comparison, market-regime-specific calibration, and human-reviewed confidence thresholds before raising confidence caps or enabling production decision influence.
