# Dashboard Ready Prediction Review Report Export V1

## Background And Purpose

AI-DEV-074 converts Prediction Quality Review output into dashboard-ready and
report-ready fixture payloads. It defines cards, report sections, export
metadata, a deterministic dry-run helper, validator, templates, and docs.

This task does not build or deploy a dashboard, API server, email job, LINE
notification, production runtime integration, or forecast weight update.

## Relationship To AI-DEV-065 Forecast V1

Forecast V1 creates the original forecast payload. This export never edits that
forecast. It only presents later review summaries in a UI/report-friendly
shape.

## Relationship To AI-DEV-066 Review Ingestion

Review ingestion creates review records that can later be evaluated. This
export surfaces the final review summary, not the ingestion runtime.

## Relationship To AI-DEV-072 Actual Outcome Backfill

AI-DEV-072 produces actual outcome and evaluation metrics. Those metrics flow
through AI-DEV-073 into this export.

## Relationship To AI-DEV-073 Prediction Quality Review

The input `source_prediction_quality_review` is AI-DEV-073-compatible and
contains:

- `quality_review_summary`
- `horizon_reviews`
- `confidence_calibration`
- `error_patterns`
- `daily_improvement_recommendations`
- `next_forecast_tuning_hints`
- `side_effects`

This task reuses that structure instead of creating a parallel quality schema.

## Input Schema

The input payload contains:

- `schema_version`
- `task_id`
- `run_id`
- `generated_at`
- `source_prediction_quality_review`
- `dashboard_config`
- `report_config`
- `export_policy`
- `safety`

Dashboard config declares supported cards and display options. Report config
declares supported sections and whether markdown and machine-readable sections
are included.

## Output Schema

The result payload contains:

- `schema_version`
- `task_id`
- `run_id`
- `generated_at`
- `mode`
- `input_summary`
- `dashboard_payload`
- `report_payload`
- `export_summary`
- `side_effects`
- `safety`
- `ok`
- `decision`
- `next_recommendation`

Allowed decisions:

- `dashboard_report_export_completed`
- `dashboard_report_export_completed_with_insufficient_data`
- `no_review_records`
- `validation_failed`
- `blocked`

## Dashboard Card Design

The dashboard payload contains cards for:

- overall forecast quality
- per-horizon quality
- confidence calibration
- top error patterns
- daily improvement recommendations
- pending actuals
- safety status

The overall quality card includes card id, type, title, status, grade, summary
text, metrics, warnings, and drilldown references. If the source quality status
is insufficient, the card includes:

```text
資料不足，不應過度解讀命中率
```

Horizon cards include horizon, grade, status, evaluated and pending counts,
hit rates, error rate, summary text, and risk note.

## Report Section Design

The report payload contains sections for:

- executive summary
- forecast quality summary
- horizon review summary
- confidence calibration summary
- error pattern summary
- daily improvement recommendations
- risk and limitations
- next steps

Every section includes section id, title, priority, markdown,
machine-readable payload, source refs, and `advisory_only: true`.

## Export Metadata

`export_summary` records card count, supported cards, insufficient-data cards,
section count, supported sections, markdown section count, machine-readable
section count, advisory-only status, and source quality status.

## Insufficient Data Handling

Insufficient data is preserved in dashboard cards and report sections. Hit
rates remain visible for debugging, but the warning makes clear that small
sample sizes should not be overinterpreted.

## Advisory-Only Safety Policy

All exported payloads are advisory-only and fixture-only. They must not contain
secrets, credentials, `.env` text, live runtime sources, production payloads, or
trading instructions.

## No Dashboard Deploy, Email, Or Runtime Mutation

This task does not deploy a dashboard, create an API server, send email, send
LINE messages, write production databases, call external market data, call
external AI runtimes, modify cron/systemd/n8n, mutate GitHub Issues, or change
forecast runtime weights. Those actions require separate reviewed tasks.

## Path To Daily Report Review And Dashboard MVP

The export result can feed a future Daily Report Forecast Review Section or
Dashboard MVP. The next task should decide how these cards and sections are
embedded in the daily report while keeping delivery disabled until explicitly
reviewed.

Recommended next task:

```text
AI-DEV-075: Daily Report Forecast Review Section V1
```
