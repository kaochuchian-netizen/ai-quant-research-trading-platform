# Schema Examples Validation

This document describes the research-only schema examples and their read-only
validation helper.

## Purpose

AI-DEV-014 adds maintainable JSON examples for the investment data schemas
defined in:

- `docs/investment_data_schemas.md`
- `docs/source_credibility_taxonomy.md`
- `docs/dashboard_email_data_requirements.md`

The examples are planning fixtures for future Dashboard, Email report,
Prediction review, Forecast, company intelligence, and industry intelligence
work. They do not connect any production pipeline and do not authorize trading,
order placement, LINE delivery, email delivery, dashboard publishing, database
writes, or scheduler changes.

## Example Location

Examples live under the existing orchestrator template area:

```text
orchestrator/templates/schemas/
```

The directory contains:

- `signal.example.json`
- `forecast.example.json`
- `report_metadata.example.json`
- `prediction_review.example.json`
- `company_intelligence.example.json`
- `industry_intelligence.example.json`
- `source_credibility.example.json`
- `dashboard_payload.example.json`
- `email_report_payload.example.json`

This location follows the repository's existing pattern of storing reviewable
example artifacts under `orchestrator/templates/` and stays inside the current
AI branch allowed paths.

## Validator

Run the read-only validator:

```bash
python3 scripts/orchestrator/validate_schema_examples.py --pretty
```

The validator checks:

- JSON files parse successfully.
- JSON roots are objects.
- Required common fields are present.
- `schema_version` is present and an integer.
- `source_tier` is present and one of the defined taxonomy tiers.
- `confidence` is present and between `0` and `1`.
- `data_quality` is present and contains required quality fields.
- `missing_data_policy` is present.
- Type-specific fields exist for each known example file.
- `orchestrator/templates/schema_registry.json` parses successfully.
- Registry entries point to existing example files.
- Every example file is covered by the registry.
- Registry `required_fields` are present in the example payload.
- Registry and example `schema_version` values match.
- Registry entries remain `research_planning_only`.
- Registry governance keeps production pipeline, notification sender, trading
  execution, and order execution as disallowed consumers.
- Forecast and prediction review examples include evaluation status, evaluation
  window, model version, prompt version, and calibration fields.

The validator is read-only. It does not write files, modify runtime queue state,
write databases, modify production data, call external APIs, send notifications,
trade, place orders, run production pipelines, change cron/systemd/timers, or
read secrets.

## Registry

AI-DEV-016 adds the schema registry at:

```text
orchestrator/templates/schema_registry.json
```

The registry is the reviewable index for schema names, schema versions, example
paths, owner areas, intended usage, required fields, optional fields, validation
level, allowed future consumers, disallowed consumers, and research-only notes.

All current registry entries use `production_status = research_planning_only`.
The registry does not enable Dashboard, Email, Forecast, Prediction review,
LINE, cron, production pipeline, trading, or order execution behavior.

Governance details are documented in:

```text
docs/schema_registry_governance.md
```

## Forecast Evaluation Prototype

AI-DEV-017 adds a read-only evaluator prototype:

```bash
python3 scripts/orchestrator/evaluate_prediction_review_examples.py --pretty
```

It reads only the forecast and prediction review examples, calculates sample
direction, interval, error, and confidence-bucket metrics, and prints JSON. It
does not read production data, write DB data, update historical CSV, send LINE or
email, run production pipelines, change schedulers, trade, place orders, or read
secrets.

## Future Use

Future tasks may add stricter JSON Schema files or typed validators, but those
changes should remain separate and reviewed. Any production integration must
preserve source traceability, data-quality flags, missing-data policy, and the
rule that analyst target prices and broker ratings are context metadata only,
not core decision inputs.

## AI-DEV-018 Storage Samples

AI-DEV-018 adds a separate research-only storage bundle under:

```text
orchestrator/templates/research_samples/prediction_review_storage/
```

This bundle is **not** part of the formal schema registry. It is a planning
fixture for prediction review storage, actual outcome backfill, and future
backtest boundary design.

Validate the storage bundle with:

```bash
python3 scripts/orchestrator/validate_prediction_review_storage_examples.py --pretty
```

The storage validator checks:

- JSON parse success for the sample records.
- Required fields for the forecast-to-review mapping sample.
- Required fields for the actual outcome backfill sample.
- Required fields for the storage index sample.
- Allowed lifecycle status values.
- Allowed data status values.
- Linkage between the forecast, review, and outcome example record ids.

The validator remains read-only. It does not write files, modify databases,
change production data, call external services, send LINE or email, modify
cron/systemd/timers, or run any production pipeline.

## AI-DEV-019 Sample Loader Summary

AI-DEV-019 adds a read-only sample loader summary prototype for the research
bundle created in AI-DEV-018.

Use:

```bash
python3 scripts/orchestrator/summarize_prediction_review_storage_examples.py --pretty
```

The loader summary reads the same research-only storage samples and reports
linkage, lifecycle, and status counts. It is still a read-only check. It does
not write files, modify databases, call external services, send notifications,
change cron/systemd/timers, or run production pipelines.

## AI-DEV-020 Report Summary Export

AI-DEV-020 adds a read-only report summary export prototype for the same
research-only bundle.

Use:

```bash
python3 scripts/orchestrator/export_prediction_review_report_summary.py --pretty
```

The export summary converts the research-only storage samples into a
report-shaped JSON preview. It remains read-only and does not write files,
modify databases, call external services, send notifications, change
cron/systemd/timers, or run production pipelines.

The export contract now requires top-level `schema_version`, `report_type`,
`generated_at`, `source`, `safety_mode`, `record_summary`,
`forecast_quality_summary`, `pending_outcome_summary`, `metric_summary`,
`confidence_summary`, `stock_summary`, `window_summary`,
`data_quality_summary`, `dashboard_cards`, `email_report_sections`,
`next_actions`, and `limitations` fields. This keeps the preview contract
stable while still remaining research-only.

The `dashboard_cards` and `email_report_sections` fields are lists, not mapping
objects. Cards must carry `card_id`, `title`, `value`, `unit`, `status`,
`description`, and `drilldown_key`. Sections must carry `section_id`, `title`,
`priority`, `summary`, `bullets`, and `metrics`.

## AI-DEV-021 Actual Outcome Backfill Prototype

AI-DEV-021 adds a research-only actual outcome backfill plan and read-only
prototype for the same prediction review storage samples.

Use:

```bash
python3 scripts/orchestrator/backfill_actual_outcome_examples.py --pretty
```

The prototype reads only:

```text
orchestrator/templates/research_samples/prediction_review_storage/
```

It emits a JSON summary with `schema_version`, `operation`, `generated_at`,
`safety_mode`, `input_records`, `backfill_candidates`,
`backfill_status_counts`, `window_alignment_summary`,
`actual_outcome_summary`, `missing_data_summary`, `data_quality_flags`,
`lookahead_bias_controls`, `evaluable_records`, `non_evaluable_records`,
`next_actions`, and `limitations`.

Allowed `backfill_status` values are `pending`, `completed`,
`missing_market_data`, `non_trading_day`, `suspended`, `invalid_window`, and
`not_due`. Allowed data quality flags are `sample_data_only`, `research_only`,
`missing_actual_close`, `missing_actual_high`, `missing_actual_low`,
`missing_actual_return`, `window_not_elapsed`, and
`manual_review_required`.

Pending records are non-evaluable and do not fail validation. The prototype is
read-only: it does not write files or databases, call external services, send
notifications, change schedulers, run production pipelines, trade, place
orders, read secrets, or generate investment advice.
