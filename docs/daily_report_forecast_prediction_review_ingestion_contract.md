# Daily Report Forecast Prediction Review Ingestion Contract

## Purpose

Daily Report Forecast Prediction Review Ingestion V1 defines a repo-only,
fixture-validatable contract for converting Daily Report Forecast V1 result
payloads into prediction review and future backtest evaluation ingestion
records.

This contract is a schema, example, validator, and deterministic dry-run helper
only. It does not connect to production databases, call external AI runtimes,
send notifications, trade, place orders, run production pipelines, modify cron,
systemd, timers, n8n, LINE, Email, Google Sheet, or GitHub Issues.

## Input Contract

The ingestion input payload must be a JSON object with:

- `schema_version`
- `ingestion_version`
- `run_id`
- `generated_at`
- `source_forecast_result`
- `ingestion_options`
- `safety`

`source_forecast_result` must be a valid Daily Report Forecast V1 result shape.
The ingestion helper preserves these source fields:

- `stock_id`
- `stock_name`
- `forecast_version`
- `run_id`
- `run_date`
- `timezone`
- `report_window`
- target horizon and review due dates
- forecast intervals or trend bands
- confidence score and confidence bucket
- basis signal ids and `signals_used`
- advisory-only safety fields

## Output Contract

The ingestion result payload must be a JSON object with:

- `schema_version`
- `ingestion_version`
- `run_id`
- `generated_at`
- `source_forecast_run_id`
- `source_forecast_version`
- `run_date`
- `timezone`
- `review_records`
- `aggregate_summary`
- `validation_status`
- `runtime_action_performed`
- `notification_sent`
- `production_pipeline_run`
- `safety`

`ingestion_version` is currently
`daily_report_forecast_review_ingestion_v1`.

## Review Records

Each Forecast V1 stock creates three review ingestion records:

- `same_day_high_low_interval`
- `next_day_high_low_interval`
- `one_month_trend_interval`

Each record must include:

- `record_id`
- `record_type`
- `record_status`
- `stock_id`
- `stock_name`
- `forecast_version`
- `source_forecast_run_id`
- `run_date`
- `timezone`
- `forecast_horizon`
- `forecast_target`
- `target_date`
- `review_window`
- `review_due`
- `forecast_snapshot`
- `actual_outcome`
- `evaluation_metrics`
- `source_metadata`
- `safety`

`record_status` starts as `pending_actual_outcome`. Later reviewed code may
move records to `outcome_collected`, `evaluation_completed`, `inconclusive`, or
`not_reviewable`. The original forecast snapshot must not be edited to match a
later outcome.

## Review Windows

The required review windows are:

| Horizon | Forecast Target | Review Window | Target Date Policy |
| --- | --- | --- | --- |
| `same_day` | `same_day_high_low_interval` | `same_day_close` | Forecast `run_date` |
| `next_day` | `next_day_high_low_interval` | `next_trading_day_close` | Date from Forecast V1 `next_day_forecast.review_due` |
| `one_month` | `one_month_trend_interval` | `one_month_close` | Date from Forecast V1 `one_month_trend_forecast.review_due` |

If the market is closed, suspended, or actual outcome data is unavailable, the
record stays pending until a future reviewed outcome collection policy handles
the case.

## Pending Actual Outcomes

Actual outcome fields must be explicit and nullable:

- same-day and next-day records use `actual_high`, `actual_low`,
  `actual_close`, `actual_return`, and `actual_direction`.
- one-month records use `actual_return`, `actual_trend`, and
  `actual_close`.

Before actual data exists:

- `outcome_status` is `pending`
- all actual values are `null`
- `source_status` is `not_collected`
- `pending_reason` explains that the review window has not been backfilled

## Evaluation Metrics Placeholders

Metrics are placeholders until outcome collection is implemented:

- `evaluation_status`
- `interval_hit`
- `high_inside_interval`
- `low_inside_interval`
- `direction_match`
- `trend_match`
- `absolute_error`
- `high_forecast_error`
- `low_forecast_error`
- `confidence_bucket`
- `calibration_bucket`

Pending records must keep metric values `null` except for copied confidence
metadata and `evaluation_status = pending`.

## Safety Requirements

Every result and every review record must preserve:

- `fixture_only: true`
- `advisory_only: true`
- `research_only: true`
- `no_trade: true`
- `no_order: true`
- `no_trading_instruction: true`
- `no_order_execution: true`
- `requires_human_review: true`

Runtime, notification, and production pipeline flags must be false. The contract
must not contain buy/sell/order instructions, secrets, tokens, credentials,
`.env` content, private runtime payloads, production config values, or external
runtime responses.

## Dry-Run Helper

`scripts/orchestrator/daily_report_forecast_review_ingestion_dry_run.py` reads
only fixture JSON supplied through `--input` and writes a deterministic
ingestion result JSON to `--output`. It accepts the repo input template or a
direct Daily Report Forecast V1 result fixture.

The helper does not call external APIs, send notifications, read production
data, mutate production databases, run production pipelines, mutate GitHub
Issues, execute issue text, trade, or place orders.

## Validation

Use:

```bash
python3 scripts/orchestrator/validate_daily_report_forecast_review_ingestion_result.py --input templates/daily_report_forecast_review_ingestion_result.example.json --pretty
python3 scripts/orchestrator/daily_report_forecast_review_ingestion_dry_run.py --input templates/daily_report_forecast_review_ingestion_input.example.json --output /tmp/daily_report_forecast_review_ingestion_result.example.json --pretty
python3 scripts/orchestrator/validate_daily_report_forecast_review_ingestion_result.py --input /tmp/daily_report_forecast_review_ingestion_result.example.json --pretty
```

Validation is structural and safety-focused. It does not approve production
database writes, notification delivery, runtime activation, trading, or
production backtest integration.
