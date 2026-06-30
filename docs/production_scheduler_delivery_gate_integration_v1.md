# Production Scheduler Delivery Gate Integration V1

## Purpose

Production Scheduler Delivery Gate Integration V1 defines how future production
scheduler windows can connect to the Delivery Gate Audit + Runtime Bridge before
any real scheduler activation.

This contract is repo-only, fixture-only, dry-run-only, preview-only, and
advisory-only. It does not modify cron, systemd, timers, services, production
pipelines, external delivery, secrets, databases, runtime notifications, market
data, model runtimes, API servers, SMTP, Gmail APIs, LINE, dashboards, or
portfolio state.

## Fixture Input

The input fixture is:

```text
templates/production_scheduler_delivery_gate_integration_input.example.json
```

It references only:

```text
templates/delivery_gate_audit_runtime_bridge_result.example.json
```

Referenced paths must be repo-relative. Absolute paths and parent traversal are
rejected by the dry-run helper.

## Scheduler Windows

The integration models the current scheduler concepts:

- `pre_open_0700` at `07:00` for `daily_pre_open_analysis`
- `intraday_1305` at `13:05` for `intraday_analysis_refresh`
- `pre_close_1335` at `13:35` for `pre_close_analysis_refresh`

Each window requires the Delivery Gate and explicit approval. In fixture mode,
`delivery_allowed` must remain `false`, `channels_enabled` must remain empty,
and the blocked reason must preserve manual confirmation requirements.

## Result Contract

The machine-readable result fixture is:

```text
templates/production_scheduler_delivery_gate_integration_result.example.json
```

The compact summary fixture is:

```text
templates/production_scheduler_delivery_gate_integration_summary.example.json
```

Required top-level fields:

- `schema_version`
- `task_id`
- `run_id`
- `generated_at`
- `mode`
- `scheduler_delivery_gate_integration`
- `scheduler_delivery_gate_summary`
- `validation_summary`
- `side_effects`
- `safety`
- `ok`
- `decision`
- `next_recommendation`

Allowed decisions:

- `production_scheduler_delivery_gate_integration_completed`
- `production_scheduler_delivery_gate_integration_completed_with_warnings`
- `production_scheduler_delivery_gate_blocked_pending_runtime_confirmation`
- `validation_failed`
- `blocked`

## Integration Object

`scheduler_delivery_gate_integration` contains:

- `scheduler_integration_id`
- `report_date`
- `runtime_mode`
- `scheduler_windows`
- `gate_preconditions`
- `approval_preconditions`
- `delivery_gate_refs`
- `allowed_actions`
- `blocked_actions`
- `dry_run_entrypoints`
- `future_runtime_entrypoints`
- `rollback_plan`
- `manual_confirmation_required`

Each scheduler window contains:

- `window_id`
- `local_time`
- `pipeline_context`
- `gate_required`
- `approval_required`
- `delivery_allowed`
- `channels_considered`
- `channels_enabled`
- `blocked_reason`
- `dry_run_command`
- `future_runtime_command`

## Safety Requirements

The result must preserve:

- `repo_only: true`
- `fixture_only: true`
- `dry_run_only: true`
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
- `no_cron_modification: true`
- `no_systemd_modification: true`
- `no_timer_modification: true`
- `no_service_modification: true`
- `no_schedule_service_changes: true`
- `external_side_effects_allowed: false`
- `dashboard_deploy: false`
- `api_server_created: false`
- `trading_instruction: false`
- `manual_confirmation_required: true`

All side-effect flags must remain false.

## Dry Run

Use:

```bash
python3 scripts/orchestrator/production_scheduler_delivery_gate_integration_dry_run.py \
  --input templates/production_scheduler_delivery_gate_integration_input.example.json \
  --output /tmp/production_scheduler_delivery_gate_integration_result.json \
  --summary-output /tmp/production_scheduler_delivery_gate_integration_summary.json \
  --pretty
```

The helper reads fixture files only and writes deterministic JSON to the
requested output paths.

## Validation

Use:

```bash
python3 scripts/orchestrator/validate_production_scheduler_delivery_gate_integration_result.py \
  --input /tmp/production_scheduler_delivery_gate_integration_result.json \
  --pretty
```

Validation checks required fields, scheduler window semantics, fixture-mode
`delivery_allowed: false`, manual confirmation requirements, dry-run
entrypoints, summary consistency, side-effect flags, safety flags, secret-like
text, and prohibited transaction wording patterns.

## Runtime Activation Boundary

This V1 contract prepares future integration only. Any future cron, systemd,
timer, service, delivery channel, dashboard, API server, database, or runtime
pipeline change requires a separate reviewed task, explicit manual
confirmation, and a rollback plan before activation.
