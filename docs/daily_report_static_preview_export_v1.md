# Daily Report Static Preview Export V1

## Purpose

Daily Report Static Preview Export V1 defines a repo-only, fixture-only,
advisory-only preview package for reviewing the AI-DEV-084 Daily Report
Renderer Contract V1 output before any future dashboard, email, or LINE
integration.

This contract exports static preview artifacts only. It does not send reports,
call live data, call model runtimes, write production databases, modify
schedules or services, perform portfolio actions, or mutate external systems.

## Fixture Input

The input fixture is:

```text
templates/daily_report_static_preview_export_input.example.json
```

It references repo-local fixture output only:

```text
templates/daily_report_renderer_result.example.json
```

Referenced paths must be repo-relative. Absolute paths are rejected by the
dry-run helper.

## Result Contract

The machine-readable result fixture is:

```text
templates/daily_report_static_preview_export_result.example.json
```

The preview manifest fixture is:

```text
templates/daily_report_static_preview_manifest.example.json
```

The Markdown preview fixture is:

```text
templates/daily_report_static_preview_markdown.example.md
```

Required top-level fields:

- `schema_version`
- `task_id`
- `run_id`
- `generated_at`
- `mode`
- `preview_package`
- `preview_manifest`
- `preview_files`
- `renderer_source_summary`
- `report_sections`
- `markdown_preview`
- `validation_summary`
- `side_effects`
- `safety`
- `ok`
- `decision`
- `next_recommendation`

Allowed decisions:

- `daily_report_static_preview_export_completed`
- `daily_report_static_preview_export_completed_with_warnings`
- `validation_failed`
- `blocked`

## Preview Package

The preview package includes:

- JSON preview manifest
- Markdown preview
- section index
- validation summary
- safety summary

The section index, validation summary, and safety summary are embedded in the
result and manifest. The manifest records artifact names, content types, paths,
and deterministic SHA-256 hashes for non-self-referential artifacts. The result
JSON and manifest JSON omit self-hashes because embedding a final file hash
inside that same file would make the artifact self-referential.

The package is intended for future dashboard, email, and LINE template review,
but it is not a delivery request and does not authorize sending a report.

## Safety Requirements

The result must preserve:

- `repo_only: true`
- `fixture_only: true`
- `advisory_only: true`
- `preview_only: true`
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
python3 scripts/orchestrator/daily_report_static_preview_export_dry_run.py \
  --input templates/daily_report_static_preview_export_input.example.json \
  --output /tmp/daily_report_static_preview_export_result.json \
  --manifest-output /tmp/daily_report_static_preview_manifest.json \
  --markdown-output /tmp/daily_report_static_preview_markdown.md \
  --pretty
```

The helper reads fixture files only and writes deterministic JSON plus
deterministic Markdown.

## Validation

Use:

```bash
python3 scripts/orchestrator/validate_daily_report_static_preview_export_result.py \
  --input /tmp/daily_report_static_preview_export_result.json \
  --pretty
```

Validation checks required fields, decision values, preview package shape,
manifest artifacts, renderer source summary, section index, validation summary,
side-effect flags, safety flags, secret-like text, live runtime terms, and
trading/order instruction patterns.

Validation does not approve production use, scheduled report insertion,
delivery activation, portfolio actions, live data connections, or external
model runtime use.
