# Delivery Payload Builder V1

## Purpose

Delivery Payload Builder V1 creates deterministic delivery-ready payload
fixtures on top of:

- AI-DEV-089 Daily Report Preview Review Workflow V1
- AI-DEV-092 Forecast Explainability Layer V1

The contract is repo-only, fixture-only, preview-only, and advisory-only. It
does not send email, push LINE messages, deploy a dashboard, start an API
server, call live market data, call model runtimes, write persistent stores,
modify schedules or services, perform portfolio actions, or mutate external
systems.

## Fixture Input

The input fixture is:

```text
templates/delivery_payload_builder_input.example.json
```

It references only repo-local fixture outputs:

```text
templates/daily_report_preview_review_workflow_result.example.json
templates/forecast_explainability_layer_result.example.json
```

Referenced paths must be repo-relative. Absolute paths and parent traversal are
rejected by the dry-run helper.

## Result Contract

The machine-readable result fixture is:

```text
templates/delivery_payload_builder_result.example.json
```

The compact summary fixture is:

```text
templates/delivery_payload_summary.example.json
```

Required top-level fields:

- `schema_version`
- `task_id`
- `run_id`
- `generated_at`
- `mode`
- `delivery_payload`
- `delivery_summary`
- `validation_summary`
- `side_effects`
- `safety`
- `ok`
- `decision`
- `next_recommendation`

Allowed decisions:

- `delivery_payload_builder_completed`
- `delivery_payload_builder_completed_with_warnings`
- `delivery_blocked_pending_approval`
- `validation_failed`
- `blocked`

## Delivery Payload Contract

`delivery_payload` contains:

- `payload_id`
- `report_date`
- `preview_id`
- `review_id`
- `review_status`
- `approval_gate`
- `delivery_allowed`
- `channels`
- `email_payload`
- `line_payload`
- `dashboard_payload`
- `explainability_refs`
- `warning_badges`
- `human_review_required`
- `delivery_blockers`
- `advisory_disclaimer`

Channels are always present and disabled by default:

- `email`
- `line`
- `dashboard`

Each channel and channel payload remains `enabled: false`, `preview_only: true`,
and `delivery_action_performed: false`.

## Approval Gate

`delivery_allowed` may be true only when `review_status` is `approved`.

The example fixture reads the current AI-DEV-089 review result, whose
`review_status` is `pending_review`, so the generated V1 example has:

```text
delivery_allowed: false
decision: delivery_blocked_pending_approval
```

When `delivery_allowed` is false, all channel payloads must remain disabled and
preview-only.

## Explainability References

The builder converts forecast explanations into compact
`explainability_refs`. These refs retain only fixture identifiers, review
requirements, source trace counts, and advisory flags. Forecast explanations
remain advisory context and never become a delivery instruction or trading
instruction.

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
python3 scripts/orchestrator/delivery_payload_builder_dry_run.py \
  --input templates/delivery_payload_builder_input.example.json \
  --output /tmp/delivery_payload_builder_result.json \
  --summary-output /tmp/delivery_payload_summary.json \
  --pretty
```

The helper reads fixture files only and writes deterministic JSON to the
requested output paths.

## Validation

Use:

```bash
python3 scripts/orchestrator/validate_delivery_payload_builder_result.py \
  --input /tmp/delivery_payload_builder_result.json \
  --pretty
```

Validation checks required fields, approval-gate semantics, disabled
preview-only channels, channel payload safety, summary consistency,
side-effect flags, safety flags, secret-like text, live runtime terms, and
prohibited transaction wording patterns.

Validation does not approve production use, delivery activation, dashboard
deployment, API server creation, persistent writes, portfolio actions, or live
data connections.
