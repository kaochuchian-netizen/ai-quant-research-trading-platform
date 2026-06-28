# Prediction Quality Review Daily Improvement V1

## Background And Purpose

Prediction Quality Review + Daily Improvement Loop V1 turns evaluated forecast
review records into a daily, fixture-only quality summary. It adds
horizon-level review, confidence calibration, error pattern analysis,
recommendations, and next forecast tuning hints.

This is a contract, deterministic dry-run helper, validator, templates, and
documentation package only. It does not change production forecast behavior.

## Relationship To AI-DEV-065 Forecast V1

AI-DEV-065 defines the original forecast contract. This task reviews the
quality of later evaluation records while preserving the original forecast
snapshot and assumptions.

## Relationship To AI-DEV-066 Review Ingestion

AI-DEV-066 creates prediction review records from Forecast V1 payloads. Those
records provide the lifecycle surface that later becomes evaluable after actual
outcomes are backfilled.

## Relationship To AI-DEV-072 Actual Outcome Backfill

AI-DEV-072 produces the required evaluation result shape:

- `records`
- `metrics`
- `backfill_summary`
- `evaluation_summary`
- `side_effects`

This task reads that shape through `source_evaluation_result` and does not
create a parallel evaluation schema.

## Input Schema

The input payload contains:

- `schema_version`
- `task_id`
- `run_id`
- `generated_at`
- `source_evaluation_result`
- `review_config`
- `quality_thresholds`
- `improvement_policy`
- `safety`

`review_config` includes:

- `review_window_days`
- `supported_horizons`
- `confidence_buckets`
- `minimum_records_for_strong_conclusion`
- `pending_policy`

## Output Schema

The result payload contains:

- `schema_version`
- `task_id`
- `run_id`
- `generated_at`
- `mode`
- `input_summary`
- `quality_review_summary`
- `horizon_reviews`
- `confidence_calibration`
- `error_patterns`
- `daily_improvement_recommendations`
- `next_forecast_tuning_hints`
- `side_effects`
- `safety`
- `ok`
- `decision`
- `next_recommendation`

Allowed decisions:

- `quality_review_completed`
- `quality_review_completed_with_insufficient_data`
- `no_evaluated_records`
- `validation_failed`
- `blocked`

## Horizon-Level Review Logic

For each supported horizon, the helper calculates:

- `total_records`
- `evaluated_records`
- `pending_records`
- `interval_hit_rate`
- `high_interval_hit_rate`
- `low_interval_hit_rate`
- `direction_hit_rate`
- `mean_absolute_error_pct`
- `median_absolute_error_pct`
- `max_absolute_error_pct`
- `pending_rate`
- `quality_grade`
- `quality_status`

Quality grades:

- `Insufficient Data`: evaluated records are below
  `minimum_records_for_strong_conclusion`
- `A`: interval hit rate >= 0.75 and mean absolute error <= 0.03
- `B`: interval hit rate >= 0.60 and mean absolute error <= 0.05
- `C`: interval hit rate >= 0.45
- `D`: all other evaluated cases

## Confidence Calibration Logic

The helper groups records by confidence bucket:

- `0-20`
- `21-40`
- `41-60`
- `61-80`
- `81-100`
- `unknown`

For each bucket it calculates record count, evaluated count, interval hit rate,
direction hit rate, mean absolute error, and calibration status.

Calibration status:

- `insufficient_data`
- `well_calibrated`
- `overconfident`
- `underconfident`

High confidence with low hit rate is overconfident. Low confidence with high
hit rate is underconfident. Buckets below the configured minimum sample count
remain insufficient.

## Error Pattern Analysis

The helper detects these pattern families:

- `high_forecast_too_low`
- `high_forecast_too_high`
- `low_forecast_too_low`
- `low_forecast_too_high`
- `range_too_narrow`
- `range_too_wide`
- `trend_mismatch`
- `missing_actuals`
- `confidence_mismatch`

Each pattern includes count, affected horizons, severity, example record ids,
and a recommendation.

## Daily Improvement Recommendation Policy

Recommendations are review-only. Every recommendation must set:

- `safe_to_apply_automatically: false`
- `requires_human_review: true`

Examples include increasing actuals coverage, reviewing direction misses,
separating one-month trend review from short-term interval review, and
continuing collection until the sample size is large enough.

## Why Production Forecast Weights Are Not Modified

This task intentionally does not modify production forecast weights or scoring.
The sample size may be insufficient, pending actuals can bias conclusions, and
forecast tuning changes require a separate reviewed task with explicit rollout,
rollback, and monitoring controls.

## Fixture-Only Safety Policy

The helper reads only repo fixture/example JSON. It does not read secrets,
external AI runtimes, market data APIs, production databases, notification
systems, trading systems, cron, systemd, timers, n8n, or real GitHub Issues.

All side effects in result artifacts must be false, including
`modified_forecast_runtime_weights`.

## Path To Dashboard And Daily Report Improvement

The sanitized result artifact can feed a future dashboard-ready export and
daily report improvement summary. The next task should package the review into
dashboard/report-friendly records without activating production delivery.

Recommended next task:

```text
AI-DEV-074: Dashboard-ready Prediction Review Summary + Report Export V1
```
