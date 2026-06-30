# Controlled Email Delivery Contract V1

## Purpose

Controlled Email Delivery Contract V1 defines a deterministic future email
delivery contract on top of AI-DEV-093 Delivery Payload Builder V1.

This contract is repo-only, fixture-only, preview-only, and advisory-only. It
does not send email, call SMTP, call Gmail APIs, push LINE messages, deploy a
dashboard, start an API server, call live market data, call model runtimes,
write persistent stores, modify schedules or services, perform portfolio
actions, or mutate external systems.

## Fixture Input

The input fixture is:

```text
templates/controlled_email_delivery_input.example.json
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
templates/controlled_email_delivery_result.example.json
```

The compact summary fixture is:

```text
templates/controlled_email_delivery_summary.example.json
```

Required top-level fields:

- `schema_version`
- `task_id`
- `run_id`
- `generated_at`
- `mode`
- `controlled_email_delivery`
- `email_delivery_summary`
- `validation_summary`
- `side_effects`
- `safety`
- `ok`
- `decision`
- `next_recommendation`

Allowed decisions:

- `controlled_email_delivery_contract_completed`
- `controlled_email_delivery_contract_completed_with_warnings`
- `email_delivery_blocked_pending_approval`
- `validation_failed`
- `blocked`

## Controlled Email Delivery Contract

`controlled_email_delivery` contains:

- `email_delivery_id`
- `payload_id`
- `report_date`
- `review_id`
- `review_status`
- `approval_gate`
- `delivery_allowed`
- `email_channel_enabled`
- `preview_only`
- `recipients_policy`
- `subject_preview`
- `body_preview`
- `attachments_preview`
- `delivery_blockers`
- `warning_badges`
- `human_review_required`
- `advisory_disclaimer`
- `send_intent`
- `send_status`

## Approval Gate

Email delivery requires both:

- `review_status: approved`
- `delivery_allowed: true`

`email_channel_enabled` must be false unless both conditions are true. Fixture
mode still keeps `send_status: not_sent`; this contract does not perform any
delivery action.

The current AI-DEV-093 example has `review_status: pending_review`, so this V1
fixture has:

```text
delivery_allowed: false
email_channel_enabled: false
send_status: not_sent
decision: email_delivery_blocked_pending_approval
```

## Preview Fields

`subject_preview` and `body_preview` are deterministic previews derived from
the upstream delivery payload. Recipients are not resolved, attachments are
preview-only, and no full email body is produced.

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
- `no_smtp_call: true`
- `no_gmail_api_call: true`
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
python3 scripts/orchestrator/controlled_email_delivery_dry_run.py \
  --input templates/controlled_email_delivery_input.example.json \
  --output /tmp/controlled_email_delivery_result.json \
  --summary-output /tmp/controlled_email_delivery_summary.json \
  --pretty
```

The helper reads fixture files only and writes deterministic JSON to the
requested output paths.

## Validation

Use:

```bash
python3 scripts/orchestrator/validate_controlled_email_delivery_result.py \
  --input /tmp/controlled_email_delivery_result.json \
  --pretty
```

Validation checks required fields, approval-gate semantics, email-channel
enablement policy, `send_status: not_sent`, unresolved recipients, preview-only
body and attachment policy, summary consistency, side-effect flags, safety
flags, secret-like text, live runtime terms, and prohibited transaction wording
patterns.

Validation does not approve production use, email delivery activation, SMTP
configuration, Gmail API integration, dashboard deployment, API server creation,
persistent writes, portfolio actions, or live data connections.
