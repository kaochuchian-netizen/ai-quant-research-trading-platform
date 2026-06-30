# Dashboard Delivery Gate Contract V1

## Purpose

Dashboard Delivery Gate Contract V1 defines a deterministic controlled gate for
future dashboard publication. It sits on top of:

- AI-DEV-093 Delivery Payload Builder V1
- AI-DEV-088 Daily Report Dashboard Static Page Contract V1

The contract is repo-only, fixture-only, preview-only, and advisory-only. It
does not deploy a dashboard, start an API server, send email, push LINE
messages, call SMTP, call Gmail APIs, call live market data, call model
runtimes, write persistent stores, modify schedules or services, perform
portfolio actions, or mutate external systems.

## Fixture Input

The input fixture is:

```text
templates/dashboard_delivery_gate_input.example.json
```

It references only repo-local fixture outputs:

```text
templates/delivery_payload_builder_result.example.json
templates/daily_report_dashboard_static_page_result.example.json
```

Referenced paths must be repo-relative. Absolute paths and parent traversal are
rejected by the dry-run helper.

## Result Contract

The machine-readable result fixture is:

```text
templates/dashboard_delivery_gate_result.example.json
```

The compact summary fixture is:

```text
templates/dashboard_delivery_gate_summary.example.json
```

Required top-level fields:

- `schema_version`
- `task_id`
- `run_id`
- `generated_at`
- `mode`
- `dashboard_delivery_gate`
- `dashboard_delivery_summary`
- `validation_summary`
- `side_effects`
- `safety`
- `ok`
- `decision`
- `next_recommendation`

Allowed decisions:

- `dashboard_delivery_gate_contract_completed`
- `dashboard_delivery_gate_contract_completed_with_warnings`
- `dashboard_delivery_blocked_pending_approval`
- `validation_failed`
- `blocked`

## Dashboard Delivery Gate

`dashboard_delivery_gate` contains:

- `dashboard_delivery_id`
- `payload_id`
- `preview_id`
- `report_date`
- `review_id`
- `review_status`
- `approval_gate`
- `delivery_allowed`
- `dashboard_channel_enabled`
- `preview_only`
- `dashboard_page_ref`
- `static_page_summary`
- `publish_target_policy`
- `publish_preview`
- `delivery_blockers`
- `warning_badges`
- `human_review_required`
- `advisory_disclaimer`
- `publish_intent`
- `publish_status`

`delivery_allowed` may be true only when `review_status` is `approved`.
`dashboard_channel_enabled` must remain false unless `delivery_allowed` is true
and `review_status` is `approved`. In fixture mode, `publish_status` must remain
`not_published` and `publish_preview.publish_action_performed` must remain
false.

## Safety Requirements

The result must preserve:

- `repo_only: true`
- `fixture_only: true`
- `advisory_only: true`
- `preview_only: true`
- `no_external_model_calls: true`
- `no_market_data_calls: true`
- `no_delivery_actions: true`
- `no_dashboard_deploy: true`
- `no_api_server_created: true`
- `no_email_send: true`
- `no_line_push: true`
- `no_smtp_call: true`
- `no_gmail_api_call: true`
- `no_persistent_store_writes: true`
- `no_portfolio_actions: true`
- `no_schedule_service_changes: true`
- `dashboard_deploy: false`
- `api_server_created: false`
- `trading_instruction: false`

All side-effect flags must remain false.

## Dry Run

Use:

```bash
python3 scripts/orchestrator/dashboard_delivery_gate_dry_run.py \
  --input templates/dashboard_delivery_gate_input.example.json \
  --output /tmp/dashboard_delivery_gate_result.json \
  --summary-output /tmp/dashboard_delivery_gate_summary.json \
  --pretty
```

The helper reads fixture files only and writes deterministic JSON to the
requested output paths.

## Validation

Use:

```bash
python3 scripts/orchestrator/validate_dashboard_delivery_gate_result.py \
  --input /tmp/dashboard_delivery_gate_result.json \
  --pretty
```

Validation checks required fields, source fixture schemas, approval-gate
semantics, dashboard channel policy, publish status, summary consistency,
side-effect flags, safety flags, secret-like text, live runtime terms, and
prohibited transaction wording patterns.
