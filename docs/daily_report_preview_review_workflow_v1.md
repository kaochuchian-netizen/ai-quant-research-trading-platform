# Daily Report Preview Review Workflow V1

## Purpose

Daily Report Preview Review Workflow V1 adds a deterministic review and
approval contract on top of AI-DEV-088 Daily Report Dashboard Static Page
Contract V1.

This is repo-only, fixture-only, preview-only, and advisory-only. It does not
send reports, deploy a dashboard, start an API server, call live data, call
model runtimes, write production databases, modify schedules or services,
perform portfolio actions, or mutate external systems.

## Fixture Input

The input fixture is:

```text
templates/daily_report_preview_review_workflow_input.example.json
```

It references only:

```text
templates/daily_report_dashboard_static_page_result.example.json
```

Referenced paths must be repo-relative. Absolute paths and parent traversal are
rejected by the dry-run helper.

## Result Contract

The machine-readable result fixture is:

```text
templates/daily_report_preview_review_workflow_result.example.json
```

The compact summary fixture is:

```text
templates/daily_report_preview_review_summary.example.json
```

Required top-level fields:

- `schema_version`
- `task_id`
- `run_id`
- `generated_at`
- `mode`
- `preview_review_workflow`
- `review_status`
- `approval_gate`
- `delivery_allowed`
- `reviewer_notes`
- `source_dashboard_static_page_summary`
- `validation_summary`
- `side_effects`
- `safety`
- `ok`
- `decision`
- `next_recommendation`

Allowed decisions:

- `daily_report_preview_review_workflow_completed`
- `daily_report_preview_review_workflow_completed_with_warnings`
- `validation_failed`
- `blocked`

## Preview Review Workflow Contract

`preview_review_workflow` contains:

- `review_id`
- `preview_id`
- `report_date`
- `review_status`
- `reviewer`
- `reviewer_notes`
- `approval_gate`
- `approved_at`
- `rejected_at`
- `revision_requested_at`
- `revision_notes`
- `source_dashboard_page_ref`
- `manifest_ref`
- `markdown_ref`
- `warning_badges`
- `requires_human_review`
- `delivery_allowed`

Supported review statuses:

- `pending_review`
- `approved`
- `rejected`
- `needs_revision`

`delivery_allowed` may be true only when `review_status` is `approved`. The V1
example fixture uses `pending_review`, so delivery remains blocked.

## Approval Gate

`approval_gate` records the required status, current status, human-review
requirement, and whether the gate is open. It is a contract artifact only. It
does not send email, send LINE messages, deploy dashboard assets, start an API,
write state to a persistent store, or schedule future work.

## Safety Requirements

The result must preserve:

- `repo_only: true`
- `fixture_only: true`
- `preview_only: true`
- `advisory_only: true`
- `delivery_allowed: false` unless `review_status` is `approved`
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
python3 scripts/orchestrator/daily_report_preview_review_workflow_dry_run.py \
  --input templates/daily_report_preview_review_workflow_input.example.json \
  --output /tmp/daily_report_preview_review_workflow_result.json \
  --summary-output /tmp/daily_report_preview_review_summary.json \
  --pretty
```

The helper reads fixture files only and writes deterministic JSON to the
requested output paths.

## Validation

Use:

```bash
python3 scripts/orchestrator/validate_daily_report_preview_review_workflow_result.py \
  --input /tmp/daily_report_preview_review_workflow_result.json \
  --pretty
```

Validation checks required fields, supported review statuses, approval gate
semantics, delivery gate policy, source dashboard static page summary,
side-effect flags, safety flags, secret-like text, live runtime terms, and
trading/order instruction patterns.
