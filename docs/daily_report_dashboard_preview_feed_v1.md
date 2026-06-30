# Daily Report Dashboard Preview Feed V1

## Purpose

Daily Report Dashboard Preview Feed V1 converts the AI-DEV-086 Daily Report
Preview Index V1 fixture into dashboard-ready feed and card JSON artifacts.

This is repo-only, fixture-only, preview-only, and advisory-only. It does not
deploy a dashboard, start an API server, send reports, call live data, call
model runtimes, write production databases, modify schedules or services,
perform portfolio actions, or mutate external systems.

## Fixture Input

The input fixture is:

```text
templates/daily_report_dashboard_preview_feed_input.example.json
```

It references only:

```text
templates/daily_report_preview_index_result.example.json
```

Referenced paths must be repo-relative. Absolute paths and parent traversal are
rejected by the dry-run helper.

## Result Contract

The machine-readable result fixture is:

```text
templates/daily_report_dashboard_preview_feed_result.example.json
```

The compact card fixture is:

```text
templates/daily_report_dashboard_preview_cards.example.json
```

Required top-level fields:

- `schema_version`
- `task_id`
- `run_id`
- `generated_at`
- `mode`
- `dashboard_feed`
- `preview_cards`
- `filters`
- `sort`
- `source_preview_index_summary`
- `validation_summary`
- `side_effects`
- `safety`
- `ok`
- `decision`
- `next_recommendation`

Allowed decisions:

- `daily_report_dashboard_preview_feed_completed`
- `daily_report_dashboard_preview_feed_completed_with_warnings`
- `validation_failed`
- `blocked`

## Dashboard Feed Contract

`dashboard_feed` contains:

- `feed_id`
- `generated_at`
- `title`
- `card_count`
- `cards_ref`
- `filters_ref`
- `source_preview_index_ref`

The feed embeds cards in `preview_cards` and filter facets in `filters`.

## Preview Card Contract

Each preview card contains:

- `card_id`
- `preview_id`
- `card_title`
- `report_date`
- `status`
- `warning_badges`
- `advisory_only_badge`
- `preview_only_badge`
- `requires_human_review_badge`
- `manifest_ref`
- `markdown_ref`
- `renderer_source_ref`
- `section_count`
- `sort_key`
- `filter_facets`

V1 creates one card from the AI-DEV-086 preview index fixture. `sort_key` is
stable and deterministic, using report date plus preview id.

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
python3 scripts/orchestrator/daily_report_dashboard_preview_feed_dry_run.py \
  --input templates/daily_report_dashboard_preview_feed_input.example.json \
  --output /tmp/daily_report_dashboard_preview_feed_result.json \
  --cards-output /tmp/daily_report_dashboard_preview_cards.json \
  --pretty
```

The helper reads fixture files only and writes deterministic JSON to the
requested output paths.

## Validation

Use:

```bash
python3 scripts/orchestrator/validate_daily_report_dashboard_preview_feed_result.py \
  --input /tmp/daily_report_dashboard_preview_feed_result.json \
  --pretty
```

Validation checks required fields, decision values, feed/card shape, filter
facets, sort metadata, source preview index summary, validation summary,
side-effect flags, safety flags, secret-like text, live runtime terms, and
trading/order instruction patterns.
