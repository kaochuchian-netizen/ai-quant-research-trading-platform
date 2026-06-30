# Daily Report Preview Index V1

## Purpose

Daily Report Preview Index V1 defines a repo-only, fixture-only,
preview-only index for discovering Daily Report static preview artifacts
without scanning ad-hoc files.

This contract indexes the AI-DEV-085 Daily Report Static Preview Export V1
fixture only. It does not send reports, call live data, call model runtimes,
write production databases, modify schedules or services, perform portfolio
actions, or mutate external systems.

## Fixture Input

The input fixture is:

```text
templates/daily_report_preview_index_input.example.json
```

It references repo-local fixture output only:

```text
templates/daily_report_static_preview_export_result.example.json
```

Referenced paths must be repo-relative. Absolute paths and parent traversal are
rejected by the dry-run helper.

## Result Contract

The machine-readable result fixture is:

```text
templates/daily_report_preview_index_result.example.json
```

The dashboard/list-view summary fixture is:

```text
templates/daily_report_preview_index_summary.example.json
```

Required top-level fields:

- `schema_version`
- `task_id`
- `run_id`
- `generated_at`
- `mode`
- `preview_index`
- `preview_entries`
- `preview_summary`
- `source_preview_export_summary`
- `validation_summary`
- `side_effects`
- `safety`
- `ok`
- `decision`
- `next_recommendation`

Allowed decisions:

- `daily_report_preview_index_completed`
- `daily_report_preview_index_completed_with_warnings`
- `validation_failed`
- `blocked`

## Preview Entry Contract

Each preview entry contains:

- `preview_id`
- `report_date`
- `title`
- `manifest_ref`
- `markdown_ref`
- `renderer_source_ref`
- `section_count`
- `advisory_only`
- `preview_only`
- `requires_human_review`
- `warnings`
- `validation_summary`

V1 indexes exactly one static preview export fixture. Future dashboard, email,
or LINE preview integrations can use `manifest_ref`, `markdown_ref`, and
`renderer_source_ref` as deterministic discovery pointers.

## Preview Summary

`preview_summary` is intentionally compact for dashboard/list-view use. It
contains preview count, warning count, human-review count, and one summary entry
with discoverable refs.

The summary is not a delivery request and does not authorize report sending.

## Safety Requirements

The result must preserve:

- `repo_only: true`
- `fixture_only: true`
- `preview_only: true`
- `advisory_only: true`
- `requires_human_review: true`
- `no_external_model_calls: true`
- `no_market_data_calls: true`
- `no_delivery_actions: true`
- `no_persistent_store_writes: true`
- `no_portfolio_actions: true`
- `no_schedule_service_changes: true`

All side-effect flags must remain false. The dry run must not read secrets,
send notifications, place orders, write persistent stores, mutate schedules or
services, alter remotes, or send a production daily report.

## Dry Run

Use:

```bash
python3 scripts/orchestrator/daily_report_preview_index_dry_run.py \
  --input templates/daily_report_preview_index_input.example.json \
  --output /tmp/daily_report_preview_index_result.json \
  --summary-output /tmp/daily_report_preview_index_summary.json \
  --pretty
```

The helper reads fixture files only and writes deterministic JSON.

## Validation

Use:

```bash
python3 scripts/orchestrator/validate_daily_report_preview_index_result.py \
  --input /tmp/daily_report_preview_index_result.json \
  --pretty
```

Validation checks required fields, decision values, preview entry shape,
dashboard summary shape, source preview export summary, validation summary,
side-effect flags, safety flags, secret-like text, live runtime terms, and
trading/order instruction patterns.

Validation does not approve production use, scheduled report insertion,
delivery activation, portfolio actions, live data connections, or external
model runtime use.
