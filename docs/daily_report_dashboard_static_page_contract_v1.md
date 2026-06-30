# Daily Report Dashboard Static Page Contract V1

## Purpose

Daily Report Dashboard Static Page Contract V1 converts the AI-DEV-087 Daily
Report Dashboard Preview Feed V1 fixture into a static dashboard page payload
contract.

This is repo-only, fixture-only, preview-only, and advisory-only. It does not
deploy a dashboard, start an API server, send reports, call live data, call
model runtimes, write production databases, modify schedules or services,
perform portfolio actions, or mutate external systems.

## Fixture Input

The input fixture is:

```text
templates/daily_report_dashboard_static_page_input.example.json
```

It references only:

```text
templates/daily_report_dashboard_preview_feed_result.example.json
```

Referenced paths must be repo-relative. Absolute paths and parent traversal are
rejected by the dry-run helper.

## Result Contract

The machine-readable result fixture is:

```text
templates/daily_report_dashboard_static_page_result.example.json
```

The compact summary fixture is:

```text
templates/daily_report_dashboard_static_page_summary.example.json
```

Required top-level fields:

- `schema_version`
- `task_id`
- `run_id`
- `generated_at`
- `mode`
- `dashboard_page`
- `latest_preview_card`
- `preview_cards`
- `overview_metrics`
- `filter_facets`
- `sort_options`
- `warning_badges`
- `advisory_only_badges`
- `preview_only_badges`
- `requires_human_review_badges`
- `drilldown_placeholders`
- `source_dashboard_preview_feed_summary`
- `validation_summary`
- `side_effects`
- `safety`
- `ok`
- `decision`
- `next_recommendation`

Allowed decisions:

- `daily_report_dashboard_static_page_completed`
- `daily_report_dashboard_static_page_completed_with_warnings`
- `validation_failed`
- `blocked`

## Dashboard Page Contract

`dashboard_page` contains:

- `page_id`
- `page_title`
- `generated_at`
- `latest_preview_card_ref`
- `preview_cards_ref`
- `overview_metrics_ref`
- `filter_facets_ref`
- `sort_options_ref`
- `warning_badges_ref`
- `drilldown_placeholders_ref`
- `manifest_ref`
- `markdown_ref`
- `renderer_source_ref`

The page embeds the latest card, all preview cards, overview metrics, filter
facets, sort options, warning badges, advisory-only badges, preview-only badges,
requires-human-review badges, and drill-down placeholders.

## Static Page Semantics

V1 uses the latest preview card from the source feed as
`latest_preview_card`. Cards remain sorted by the deterministic source
`sort_key` descending. `overview_metrics` counts cards, warning badges, advisory
badges, preview badges, review badges, and status totals.

`drilldown_placeholders` are intentionally disabled. They define stable IDs and
source refs for a future private dashboard, but they do not implement dashboard
deployment, routing, API creation, delivery, or live drill-down behavior.

## Safety Requirements

The result must preserve:

- `repo_only: true`
- `fixture_only: true`
- `preview_only: true`
- `advisory_only: true`
- `requires_human_review: true`
- `dashboard_deploy: false`
- `api_server_created: false`
- `no_external_model_calls: true`
- `no_market_data_calls: true`
- `no_delivery_actions: true`
- `no_persistent_store_writes: true`
- `no_portfolio_actions: true`
- `no_schedule_service_changes: true`

All side-effect flags must remain false. The fixture is not a delivery request
and does not authorize dashboard deployment, report sending, live data access,
model runtime calls, persistent writes, portfolio actions, or schedule changes.

## Dry Run

Use:

```bash
python3 scripts/orchestrator/daily_report_dashboard_static_page_dry_run.py \
  --input templates/daily_report_dashboard_static_page_input.example.json \
  --output /tmp/daily_report_dashboard_static_page_result.json \
  --summary-output /tmp/daily_report_dashboard_static_page_summary.json \
  --pretty
```

The helper reads fixture files only and writes deterministic JSON to the
requested output paths.

## Validation

Use:

```bash
python3 scripts/orchestrator/validate_daily_report_dashboard_static_page_result.py \
  --input /tmp/daily_report_dashboard_static_page_result.json \
  --pretty
```

Validation checks required fields, decision values, page/card shape, overview
metrics, filter facets, sort options, source preview feed summary, validation
summary, side-effect flags, safety flags, secret-like text, live runtime terms,
and trading/order instruction patterns.
