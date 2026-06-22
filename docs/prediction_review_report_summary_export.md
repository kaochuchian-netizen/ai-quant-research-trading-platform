# Prediction Review Report Summary Export

## Purpose

This document defines the research-only report summary export prototype added in
AI-DEV-020. The prototype reads the AI-DEV-018 prediction review storage
samples and produces a structured report-style summary that can later feed
dashboard preview or email preview work.

This is a read-only export. It does not write files, send notifications, touch
production data, or authorize trading.

## Input Samples

The export reads the same research-only bundle used by AI-DEV-018 and
AI-DEV-019:

```text
orchestrator/templates/research_samples/prediction_review_storage/
```

## Export Contract

The prototype emits a structured JSON summary with the following top-level
fields:

- `schema_version`
- `report_type`
- `generated_at`
- `source`
- `safety_mode`
- `record_summary`
- `forecast_quality_summary`
- `pending_outcome_summary`
- `metric_summary`
- `confidence_summary`
- `stock_summary`
- `window_summary`
- `data_quality_summary`
- `dashboard_cards`
- `email_report_sections`
- `next_actions`
- `limitations`

The `dashboard_cards` list includes cards with `card_id`, `title`, `value`,
`unit`, `status`, `description`, and `drilldown_key`. The required `card_id`
values include `total_records`, `completed_outcomes`, `pending_outcomes`,
`direction_match_rate`, `interval_hit_rate`, `average_absolute_error`,
`data_quality_status`, and `safety_mode`.

The `email_report_sections` list includes sections with `section_id`, `title`,
`priority`, `summary`, `bullets`, and `metrics`. The required `section_id`
values include `executive_summary`, `forecast_quality`, `pending_outcomes`,
`data_quality`, `methodology_notes`, and `limitations`.

The report uses `report_type = forecast_review` to stay aligned with the
existing report metadata vocabulary.

## Read-Only Validation

Run the export prototype with:

```bash
python3 scripts/orchestrator/export_prediction_review_report_summary.py --pretty
```

The prototype is read-only. It does not:

- write files
- write databases
- modify production data
- call external APIs
- send LINE or email
- modify cron, systemd, or timers
- run production pipelines
- trade or place orders
- read secrets or credentials

## Relationship to Other Documents

- `docs/prediction_review_sample_loader_summary.md`
- `docs/prediction_review_storage_backtest_integration_plan.md`
- `docs/schema_examples_validation.md`
- `docs/dashboard_email_data_requirements.md`

The export summary is a planning artifact only. It is useful for future report
preview, dashboard preview, or email preview tasks, but it does not imply
production delivery or trading approval.
