# Daily Report Forecast V1 Contract

## Purpose

Daily Report Forecast V1 defines a repo-only, fixture-validatable contract for
the future 07:00 Taiwan pre-open research report forecast section. It is a
schema, template, validator, and deterministic dry-run helper package only.

This contract does not enable live report delivery, external AI calls,
notifications, production database writes, trading, order placement, cron,
systemd, timers, n8n, Dify, or production pipeline behavior.

## Top-Level Result Fields

The result payload must be a JSON object with these required fields:

- `schema_version`
- `run_id`
- `run_date`
- `timezone`
- `report_window`
- `forecast_version`
- `generated_at`
- `data_cutoff`
- `stocks`
- `aggregate_summary`
- `validation_status`
- `runtime_action_performed`
- `notification_sent`
- `production_pipeline_run`
- `safety`

`report_window` must be `pre_open`. `forecast_version` must identify this
contract, currently `daily_report_forecast_v1`. Runtime, notification, and
production pipeline flags must be false.

## Per-Stock Fields

Each `stocks` entry must include:

- `stock_id`
- `stock_name`
- `reference_price`
- `same_day_forecast`
- `next_day_forecast`
- `one_month_trend_forecast`
- `signals_used`
- `prediction_review`
- `safety`

## Forecast Objects

`same_day_forecast` and `next_day_forecast` must include:

- `horizon`
- `forecast_type`
- `price_interval`
- `confidence_score`
- `confidence_bucket`
- `basis`
- `review_due`

`price_interval` must include `low`, `high`, `unit`, `interval_method`, and
`contains_reference_price`. `low` must be less than or equal to `high`.

`one_month_trend_forecast` must include:

- `horizon`
- `forecast_type`
- `trend`
- `confidence_score`
- `confidence_bucket`
- `interval`
- `basis`
- `review_due`

The one-month `interval` records the expected trend band rather than a direct
order or recommendation.

## Prediction Review

`prediction_review` keeps the forecast review lifecycle explicit:

- `review_status`
- `same_day_review_due`
- `next_day_review_due`
- `one_month_review_due`
- `actual_outcome`
- `evaluation_metrics`
- `review_notes`

Outcome and metrics fields may be null or pending in V1 examples. The original
forecast snapshot must not be edited to fit later outcomes.

## Safety Requirements

Every result and every stock entry must preserve these safety controls:

- `advisory_only: true`
- `research_only: true`
- `no_trade: true`
- `no_order: true`
- `no_trading_instruction: true`
- `no_order_execution: true`
- `requires_human_review: true`

The contract must not contain buy/sell/order instructions, secrets, tokens,
credentials, `.env` content, private runtime payloads, or production config
values.

## Dry-Run Helper

`scripts/orchestrator/daily_report_forecast_v1_dry_run.py` reads only
`templates/daily_report_forecast_v1_input.example.json` or another explicitly
provided fixture file. It writes a sanitized deterministic result JSON and does
not call external APIs, send notifications, read production data, mutate
production databases, run production pipelines, or execute issue text.

## Validation

Use:

```bash
python3 scripts/orchestrator/validate_daily_report_forecast_v1_result.py --input templates/daily_report_forecast_v1_result.example.json --pretty
python3 scripts/orchestrator/daily_report_forecast_v1_dry_run.py --input templates/daily_report_forecast_v1_input.example.json --output /tmp/daily_report_forecast_v1_result.example.json --pretty
python3 scripts/orchestrator/validate_daily_report_forecast_v1_result.py --input /tmp/daily_report_forecast_v1_result.example.json --pretty
```

Validation is structural and safety-focused. It does not approve production use
or delivery channel activation.
