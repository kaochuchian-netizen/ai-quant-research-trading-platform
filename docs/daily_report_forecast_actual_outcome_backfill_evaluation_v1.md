# Daily Report Forecast Actual Outcome Backfill Evaluation V1

## Background And Purpose

AI-DEV-072 adds a repo-only, fixture-only contract for turning pending Daily
Report Forecast review records into evaluated records when deterministic market
actuals are available. It covers actual outcome backfill, per-record metrics,
aggregate metrics, a sanitized result artifact, and validation.

This does not enable production runtime behavior. It does not read secrets,
call external AI services, call market data APIs, send notifications, trade,
place orders, write production databases, mutate GitHub Issues, or modify cron,
systemd, timers, n8n, LINE, Email, Google Sheet, or broker settings.

## Relationship To AI-DEV-065 Forecast V1

AI-DEV-065 defines the source forecast payload and forecast snapshots. This
contract preserves the Forecast V1 assumptions and evaluates later outcomes
without editing the original forecast.

The backfill helper can consume normalized records that carry:

- `forecast_version`
- `run_date`
- `horizon`
- forecast high/low intervals or one-month trend interval
- confidence and signal metadata
- advisory-only safety flags

## Relationship To AI-DEV-066 Review Ingestion

AI-DEV-066 creates prediction review ingestion records with
`pending_actual_outcome` status. This contract is the next repo-side step:

```text
Forecast V1 payload
-> review ingestion records
-> pending_actual_outcome
-> fixture actual outcome backfill
-> evaluation metrics
```

The dry-run helper accepts the direct AI-DEV-072 input shape and also normalizes
AI-DEV-066-style fields such as `forecast_horizon`, `forecast_snapshot`,
`record_status`, and `source_metadata.signals_used`.

## Input Schema

The input payload contains:

- `schema_version`
- `task_id`
- `run_id`
- `forecast_version`
- `generated_at`
- `review_records`
- `market_actuals`
- `evaluation_config`
- `safety`

Each review record contains:

- `record_id`
- `stock_id`
- `stock_name`
- `forecast_version`
- `run_date`
- `horizon`: `same_day`, `next_day`, or `one_month`
- `target_date`
- `target_window_start`
- `target_window_end`
- `forecast`
- `confidence`
- `signals`
- `status`
- `advisory_only`

Each market actual row contains:

- `stock_id`
- `date`
- `open`
- `high`
- `low`
- `close`
- `volume`
- `source`: `fixture` or `repo_example`

Rows with any other source are ignored by the helper and rejected by the
validator if they appear in result artifacts.

## Output Schema

The result payload contains:

- `schema_version`
- `task_id`
- `run_id`
- `generated_at`
- `mode`
- `input_summary`
- `backfill_summary`
- `evaluation_summary`
- `records`
- `metrics`
- `side_effects`
- `safety`
- `ok`
- `decision`
- `next_recommendation`

Allowed decisions are:

- `backfill_evaluation_completed`
- `partial_pending_actuals`
- `no_evaluable_records`
- `validation_failed`
- `blocked`

All `side_effects` fields must be false.

## Same-Day Backfill Logic

For `horizon = same_day`, the helper uses fixture OHLC on the forecast
`target_date`:

- `actual_high = market_actuals[target_date].high`
- `actual_low = market_actuals[target_date].low`
- `actual_close = market_actuals[target_date].close`

If target-date OHLC is missing, the record remains
`pending_actual_outcome` with `pending_reason =
missing_target_date_actual`.

## Next-Day Backfill Logic

For `horizon = next_day`, the helper selects the next trading date from fixture
actuals after `run_date` for the same `stock_id`:

- `actual_high`
- `actual_low`
- `actual_close`

If no next fixture trading date exists, the record remains
`pending_actual_outcome` with `pending_reason =
missing_next_trading_day_actual`.

## One-Month Backfill Logic

For `horizon = one_month`, the helper uses fixture OHLC rows within
`target_window_start` and `target_window_end`.

It calculates:

- `actual_window_high`
- `actual_window_low`
- `actual_start_close`
- `actual_end_close`
- `actual_return_pct`
- `actual_trend`
- `max_upside_pct`
- `max_drawdown_pct`

Trend classification:

- return greater than `+3%`: `up`
- return less than `-3%`: `down`
- otherwise: `flat`

If fewer than two fixture rows exist in the target window, the record remains
`pending_actual_outcome` with `pending_reason =
insufficient_window_actuals`.

## Evaluation Metrics

Per evaluated record:

- `interval_hit`
- `high_interval_hit`
- `low_interval_hit`
- `close_in_interval`
- `direction_hit`
- `absolute_error`
- `absolute_error_pct`
- `range_width_pct`
- `confidence_bucket`
- `evaluation_status`

For same-day and next-day records without a direction forecast,
`direction_hit` is `null` and `skipped_reason` is
`no_direction_forecast`.

For one-month records, `direction_hit` compares normalized forecast trend with
`actual_trend`.

Aggregate metrics include:

- `total_records`
- `evaluated_records`
- `pending_records`
- `same_day_count`
- `next_day_count`
- `one_month_count`
- `interval_hit_rate`
- `high_interval_hit_rate`
- `low_interval_hit_rate`
- `direction_hit_rate`
- `mean_absolute_error_pct`
- `median_absolute_error_pct`
- `coverage_by_horizon`
- `pending_by_reason`
- `confidence_bucket_metrics`

Confidence buckets are `0-20`, `21-40`, `41-60`, `61-80`, `81-100`, and
`unknown`.

## Pending Policy

Pending records are preserved instead of inferred when fixture data is missing
or insufficient. Pending records are included in coverage counts but excluded
from hit-rate and error-rate denominators.

## Fixture-Only Safety Policy

Only fixture input data and repo example data are allowed. The helper does not
fetch missing OHLC values from any external or production source. Result
artifacts must not contain secrets, tokens, credentials, `.env` content, live
runtime source names, or production payloads.

## Production Integration Is Out Of Scope

This task does not integrate with production forecast jobs, production
databases, broker APIs, live market data, Dify, OpenAI, Gemini, LINE, Email,
Dashboard runtime, n8n, cron, or systemd. Production integration must be a
separate reviewed task with explicit data source, permission, storage, and
runtime controls.

## Path To Prediction Quality Review And Dashboard

The sanitized result artifact can feed a future Prediction Quality Review and
Daily Improvement Loop. Dashboard work can later show pending and evaluated
records, interval hit rates, direction hit rates, confidence calibration, and
missing-data reasons while preserving the research-only boundary.

Recommended next task:

```text
AI-DEV-073: Prediction Quality Review + Daily Improvement Loop V1
```
