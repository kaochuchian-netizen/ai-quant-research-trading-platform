# Daily Report Forecast Review Section V1

## Purpose

Daily Report Forecast Review Section V1 connects the AI-DEV-074
dashboard/report-ready prediction review export payload into a static daily
report section schema. It is repo-only, fixture-only, advisory-only, and
deterministically validatable.

This contract does not enable live report delivery, external AI calls, market
data calls, notifications, production database writes, trading, order
placement, cron, systemd, timers, n8n mutation, GitHub Issue mutation, or
forecast runtime weight updates.

## Upstream Input

The input fixture is:

```text
templates/daily_report_forecast_review_section_input.example.json
```

The required upstream payload is `source_report_export`, which must be
compatible with AI-DEV-074:

```text
schema_version = dashboard_prediction_review_report_export_v1
report_payload.sections = static report-ready review sections
```

The section generator reuses those `report_payload.sections` instead of
creating a competing prediction review schema.

## Result Schema

The result fixture is:

```text
templates/daily_report_forecast_review_section_result.example.json
```

Top-level fields:

- `schema_version`
- `task_id`
- `run_id`
- `generated_at`
- `mode`
- `source_summary`
- `daily_report_section`
- `validation_summary`
- `side_effects`
- `safety`
- `ok`
- `decision`
- `next_recommendation`

Allowed decisions:

- `forecast_review_section_completed`
- `forecast_review_section_completed_with_insufficient_data`
- `no_report_sections`
- `validation_failed`
- `blocked`

## Daily Report Section Contract

`daily_report_section` is a static renderable section with:

- `section_id`
- `section_type`
- `title`
- `placement`
- `priority`
- `render_mode`
- `markdown`
- `machine_readable`
- `badges`
- `source_refs`
- `advisory_only`
- `requires_human_review`

`section_type` must be `forecast_review`.

`render_mode` must be:

```text
static_markdown_with_machine_readable_payload
```

The Markdown example is:

```text
templates/daily_report_forecast_review_section_markdown.example.md
```

## Machine-Readable Payload

`daily_report_section.machine_readable` includes:

- `source_schema_version`
- `source_report_version`
- `source_sections`
- `quality_status`
- `insufficient_data`
- `advisory_only`
- `requires_human_review`

Each `source_sections` item preserves the upstream AI-DEV-074 section id,
title, priority, machine-readable payload, source references, and advisory-only
flag.

## Insufficient Data Handling

If the upstream export reports `source_quality_status = insufficient_data`, or
contains the insufficient-data warning text, the generated section must preserve
that warning in Markdown and machine-readable badges:

```text
資料不足，不應過度解讀命中率
```

Hit rates may remain visible for debugging and review, but the section must
not present them as strong conclusions when sample coverage is insufficient.

## Safety Requirements

The result must preserve:

- `fixture_only: true`
- `repo_only: true`
- `advisory_only: true`
- `requires_human_review: true`
- `no_trading: true`
- `no_notification: true`
- `no_production_db_write: true`
- `no_runtime_weight_change: true`
- `static_report_contract_only: true`

All side-effect flags must remain false. The fixture must not contain secrets,
tokens, credentials, private runtime payloads, production config values, live
runtime source terms, or trading/order instructions.

## Dry Run

Use:

```bash
python3 scripts/orchestrator/daily_report_forecast_review_section_dry_run.py \
  --input templates/daily_report_forecast_review_section_input.example.json \
  --output /tmp/daily_report_forecast_review_section_result.example.json \
  --pretty
```

The dry-run helper reads fixture input only and writes a deterministic static
section result. It does not call external APIs, send notifications, read
production data, mutate production databases, render a runtime report, run
production pipelines, or execute Issue text.

## Validation

Use:

```bash
python3 scripts/orchestrator/validate_daily_report_forecast_review_section_result.py \
  --input templates/daily_report_forecast_review_section_result.example.json \
  --pretty

python3 scripts/orchestrator/validate_daily_report_forecast_review_section_result.py \
  --input /tmp/daily_report_forecast_review_section_result.example.json \
  --pretty
```

Validation is structural and safety-focused. It does not approve production use
or delivery channel activation.
