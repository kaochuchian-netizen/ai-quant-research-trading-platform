# Unified Delivery Gate Summary V1

## Purpose

Unified Delivery Gate Summary V1 aggregates delivery readiness from:

- AI-DEV-094 Controlled Email Delivery Contract V1
- AI-DEV-095 LINE Delivery Gate Contract V1
- AI-DEV-096 Dashboard Delivery Gate Contract V1

The summary is repo-only, fixture-only, preview-only, and advisory-only. It does
not send email, push LINE messages, deploy a dashboard, start an API server,
call SMTP, call Gmail APIs, call model runtimes, call market data, write
persistent stores, modify schedules or services, perform portfolio actions, or
mutate external systems.

## Fixture Input

The input fixture is:

```text
templates/unified_delivery_gate_summary_input.example.json
```

It references only repo-local fixture outputs:

```text
templates/controlled_email_delivery_result.example.json
templates/line_delivery_gate_result.example.json
templates/dashboard_delivery_gate_result.example.json
```

Referenced paths must be repo-relative. Absolute paths and parent traversal are
rejected by the dry-run helper.

## Result Contract

The machine-readable result fixture is:

```text
templates/unified_delivery_gate_summary_result.example.json
```

The compact summary fixture is:

```text
templates/unified_delivery_gate_summary.example.json
```

Required top-level fields:

- `schema_version`
- `task_id`
- `run_id`
- `generated_at`
- `mode`
- `unified_delivery_gate_summary`
- `delivery_readiness_summary`
- `validation_summary`
- `side_effects`
- `safety`
- `ok`
- `decision`
- `next_recommendation`

Allowed decisions:

- `unified_delivery_gate_summary_completed`
- `unified_delivery_gate_summary_completed_with_warnings`
- `unified_delivery_blocked_pending_approval`
- `validation_failed`
- `blocked`

## Unified Summary

`unified_delivery_gate_summary` contains:

- `summary_id`
- `report_date`
- `payload_id`
- `review_id`
- `review_status`
- `approval_gate`
- `delivery_allowed`
- `channels`
- `channel_statuses`
- `blocked_channels`
- `ready_channels`
- `delivery_blockers`
- `warning_badges`
- `human_review_required`
- `advisory_disclaimer`
- `final_delivery_decision`

`channel_statuses` must include:

- `email`
- `line`
- `dashboard`

`delivery_allowed` may be true only when all source gates are approved, their
approval gates are open, their source results are valid, and their channel
enabled flags are true. If any channel is blocked,
`final_delivery_decision` must remain `blocked_pending_approval`.

## Safety Requirements

The result must preserve:

- `repo_only: true`
- `fixture_only: true`
- `advisory_only: true`
- `preview_only: true`
- `no_external_model_calls: true`
- `no_market_data_calls: true`
- `no_delivery_actions: true`
- `no_email_send: true`
- `no_line_push: true`
- `no_dashboard_deploy: true`
- `no_smtp_call: true`
- `no_gmail_api_call: true`
- `no_api_server_created: true`
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
python3 scripts/orchestrator/unified_delivery_gate_summary_dry_run.py \
  --input templates/unified_delivery_gate_summary_input.example.json \
  --output /tmp/unified_delivery_gate_summary_result.json \
  --summary-output /tmp/unified_delivery_gate_summary.json \
  --pretty
```

The helper reads fixture files only and writes deterministic JSON to the
requested output paths.

## Validation

Use:

```bash
python3 scripts/orchestrator/validate_unified_delivery_gate_summary_result.py \
  --input /tmp/unified_delivery_gate_summary_result.json \
  --pretty
```

Validation checks required fields, source fixture schemas, channel readiness
semantics, approval-gate aggregation, blocked pending-approval behavior, summary
consistency, side-effect flags, safety flags, secret-like text, live runtime
terms, and prohibited transaction wording patterns.
