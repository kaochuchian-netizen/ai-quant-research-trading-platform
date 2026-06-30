# LINE Delivery Gate Contract V1

## Purpose

LINE Delivery Gate Contract V1 defines a deterministic future LINE report
notification and preview delivery gate on top of AI-DEV-093 Delivery Payload
Builder V1.

This contract is repo-only, fixture-only, preview-only, and advisory-only. It
does not push LINE messages, call LINE APIs, send email, call SMTP, call Gmail
APIs, deploy a dashboard, start an API server, call live market data, call
model runtimes, write persistent stores, modify schedules or services, perform
portfolio actions, or mutate external systems.

## Fixture Input

The input fixture is:

```text
templates/line_delivery_gate_input.example.json
```

It references only the repo-local AI-DEV-093 fixture:

```text
templates/delivery_payload_builder_result.example.json
```

Referenced paths must be repo-relative. Absolute paths and parent traversal are
rejected by the dry-run helper.

## Result Contract

The machine-readable result fixture is:

```text
templates/line_delivery_gate_result.example.json
```

The compact summary fixture is:

```text
templates/line_delivery_gate_summary.example.json
```

Required top-level fields:

- `schema_version`
- `task_id`
- `run_id`
- `generated_at`
- `mode`
- `line_delivery_gate`
- `line_delivery_summary`
- `validation_summary`
- `side_effects`
- `safety`
- `ok`
- `decision`
- `next_recommendation`

Allowed decisions:

- `line_delivery_gate_contract_completed`
- `line_delivery_gate_contract_completed_with_warnings`
- `line_delivery_blocked_pending_approval`
- `validation_failed`
- `blocked`

## LINE Delivery Gate Contract

`line_delivery_gate` contains:

- `line_delivery_id`
- `payload_id`
- `report_date`
- `review_id`
- `review_status`
- `approval_gate`
- `delivery_allowed`
- `line_channel_enabled`
- `preview_only`
- `recipient_policy`
- `message_preview`
- `link_preview`
- `delivery_blockers`
- `warning_badges`
- `human_review_required`
- `advisory_disclaimer`
- `push_intent`
- `push_status`

## Approval Gate

LINE delivery requires both:

- `review_status: approved`
- `delivery_allowed: true`

`line_channel_enabled` must be false unless both conditions are true. Fixture
mode still keeps `push_status: not_sent`; this contract does not perform any
LINE delivery action.

The current AI-DEV-093 example has `review_status: pending_review`, so this V1
fixture has:

```text
delivery_allowed: false
line_channel_enabled: false
push_status: not_sent
decision: line_delivery_blocked_pending_approval
```

## Preview Fields

`message_preview` and `link_preview` are deterministic previews derived from
the upstream delivery payload. Recipients are not resolved, links are not
resolved, and no full LINE message is produced.

## Safety Requirements

The result must preserve:

- `repo_only: true`
- `fixture_only: true`
- `advisory_only: true`
- `preview_only: true`
- `no_external_model_calls: true`
- `no_market_data_calls: true`
- `no_delivery_actions: true`
- `no_line_push: true`
- `no_line_api_call: true`
- `no_email_send: true`
- `no_smtp_call: true`
- `no_gmail_api_call: true`
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
python3 scripts/orchestrator/line_delivery_gate_dry_run.py \
  --input templates/line_delivery_gate_input.example.json \
  --output /tmp/line_delivery_gate_result.json \
  --summary-output /tmp/line_delivery_gate_summary.json \
  --pretty
```

The helper reads fixture files only and writes deterministic JSON to the
requested output paths.

## Validation

Use:

```bash
python3 scripts/orchestrator/validate_line_delivery_gate_result.py \
  --input /tmp/line_delivery_gate_result.json \
  --pretty
```

Validation checks required fields, approval-gate semantics, LINE-channel
enablement policy, `push_status: not_sent`, unresolved recipients, unresolved
links, preview-only message policy, summary consistency, side-effect flags,
safety flags, secret-like text, live runtime terms, and prohibited transaction
wording patterns.

Validation does not approve production use, LINE delivery activation, LINE API
integration, email delivery, SMTP configuration, Gmail API integration,
dashboard deployment, API server creation, persistent writes, portfolio
actions, or live data connections.
