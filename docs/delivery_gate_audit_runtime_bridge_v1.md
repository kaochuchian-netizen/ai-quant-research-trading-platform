# Delivery Gate Audit Runtime Bridge V1

## Purpose

Delivery Gate Audit Runtime Bridge V1 prepares future controlled runtime
delivery across Email, LINE, and Dashboard by producing deterministic audit and
runtime bridge artifacts from existing fixture results.

This contract is repo-only, fixture-only, preview-only, and advisory-only. It
does not send email, push LINE messages, deploy a dashboard, start an API
server, call SMTP, call Gmail APIs, call model runtimes, call market data, write
persistent stores, modify schedules or services, perform portfolio actions, or
mutate external systems.

## Fixture Input

The input fixture is:

```text
templates/delivery_gate_audit_runtime_bridge_input.example.json
```

It references only repo-local fixture outputs:

```text
templates/unified_delivery_gate_summary_result.example.json
templates/controlled_email_delivery_result.example.json
templates/line_delivery_gate_result.example.json
templates/dashboard_delivery_gate_result.example.json
```

Referenced paths must be repo-relative. Absolute paths and parent traversal are
rejected by the dry-run helper.

## Result Contract

The machine-readable result fixture is:

```text
templates/delivery_gate_audit_runtime_bridge_result.example.json
```

The compact summary fixture is:

```text
templates/delivery_gate_audit_runtime_bridge_summary.example.json
```

Required top-level fields:

- `schema_version`
- `task_id`
- `run_id`
- `generated_at`
- `mode`
- `delivery_gate_audit_log`
- `runtime_bridge_plan`
- `delivery_gate_audit_runtime_bridge_summary`
- `validation_summary`
- `side_effects`
- `safety`
- `ok`
- `decision`
- `next_recommendation`

Allowed decisions:

- `delivery_gate_audit_runtime_bridge_completed`
- `delivery_gate_audit_runtime_bridge_completed_with_warnings`
- `delivery_gate_runtime_bridge_blocked_pending_approval`
- `validation_failed`
- `blocked`

## Audit Log

`delivery_gate_audit_log` contains:

- `audit_id`
- `report_date`
- `payload_id`
- `review_id`
- `review_status`
- `approval_gate`
- `delivery_allowed`
- `final_delivery_decision`
- `channel_audit_entries`
- `blocked_channels`
- `ready_channels`
- `human_review_required`
- `audit_decision`
- `audit_notes`

`channel_audit_entries` must include `email`, `line`, and `dashboard`.
`delivery_allowed` may be true only when no channel is blocked by source schema,
source result, review status, approval gate, delivery_allowed, or channel
enabled checks.

## Runtime Bridge Plan

`runtime_bridge_plan` contains:

- `bridge_id`
- `bridge_mode`
- `allowed_channels`
- `blocked_channels`
- `runtime_preconditions`
- `channel_bridge_specs`
- `dry_run_entrypoints`
- `required_runtime_flags`
- `required_approval_fields`
- `safety_guards`
- `external_side_effects_allowed`

`bridge_mode` must be `dry_run_gated_preview_only`.
`external_side_effects_allowed` must be `false`.
All entrypoints must remain dry-run orchestrator scripts.

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
- `external_side_effects_allowed: false`
- `dashboard_deploy: false`
- `api_server_created: false`
- `trading_instruction: false`

All side-effect flags must remain false.

## Dry Run

Use:

```bash
python3 scripts/orchestrator/delivery_gate_audit_runtime_bridge_dry_run.py \
  --input templates/delivery_gate_audit_runtime_bridge_input.example.json \
  --output /tmp/delivery_gate_audit_runtime_bridge_result.json \
  --summary-output /tmp/delivery_gate_audit_runtime_bridge_summary.json \
  --pretty
```

The helper reads fixture files only and writes deterministic JSON to the
requested output paths.

## Validation

Use:

```bash
python3 scripts/orchestrator/validate_delivery_gate_audit_runtime_bridge_result.py \
  --input /tmp/delivery_gate_audit_runtime_bridge_result.json \
  --pretty
```

Validation checks required fields, channel audit semantics, dry-run runtime
bridge constraints, summary consistency, side-effect flags, safety flags,
secret-like text, live runtime terms, and prohibited transaction wording
patterns.
