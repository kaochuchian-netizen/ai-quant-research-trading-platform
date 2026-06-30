# Production Scheduler Gate Runtime Activation V1

## Purpose

AI-DEV-101 adds a repo-side gated runtime activation layer for the production
scheduler entrypoint. It builds on:

- AI-DEV-099 Production Scheduler Delivery Gate Integration V1
- AI-DEV-100 Production Scheduler Runtime Gate Wiring V1
- the existing `run_stock_analysis.sh` and `scripts/run_pipeline.py` scheduler flow

This task does not install or mutate cron, systemd, timers, services, secrets,
delivery channels, dashboards, API servers, production databases, market data,
model runtimes, or portfolio state.

## Scheduler Windows

The runtime helper supports:

- `pre_open_0700`
- `intraday_1305`
- `pre_close_1335`

Each run evaluates one scheduler window and returns a deterministic gate
decision JSON.

## Runtime Entrypoint

The repo-side entrypoint is:

```bash
python3 scripts/orchestrator/production_scheduler_gate_runtime.py \
  --input templates/production_scheduler_gate_runtime_input.example.json \
  --output /tmp/production_scheduler_gate_runtime_result.json \
  --summary-output /tmp/production_scheduler_gate_runtime_summary.json \
  --window pre_open_0700 \
  --pretty
```

It reads repo fixtures only:

- `templates/production_scheduler_delivery_gate_integration_result.example.json`
- `templates/production_scheduler_runtime_gate_wiring_result.example.json`

Referenced paths must be repo-relative and must not contain parent traversal.

## Decision Contract

Required top-level output fields:

- `schema_version`
- `task_id`
- `run_id`
- `generated_at`
- `mode`
- `scheduler_window`
- `gate_runtime_decision`
- `delivery_allowed`
- `approval_status`
- `channels`
- `blocked_actions`
- `allowed_actions`
- `side_effects`
- `safety`
- `ok`
- `decision`
- `next_recommendation`

Allowed decisions:

- `production_scheduler_gate_runtime_activation_completed`
- `production_scheduler_gate_runtime_activation_completed_with_warnings`
- `production_scheduler_gate_runtime_blocked_pending_approval`
- `service_installation_blocked_pending_confirmation`
- `validation_failed`
- `blocked`

Default fixture output is intentionally blocked:

- `mode: dry_run_no_delivery`
- `delivery_allowed: false`
- `approval_status: pending_approval`
- `decision: production_scheduler_gate_runtime_blocked_pending_approval`

## Safety Boundary

The runtime result must preserve:

- `repo_only: true`
- `gated_runtime: true`
- `dry_run_default: true`
- `manual_confirmation_required_for_service_install: true`
- `no_external_model_calls: true`
- `no_market_data_mutation: true`
- `no_delivery_actions: true`
- `no_email_send: true`
- `no_line_push: true`
- `no_dashboard_deploy: true`
- `no_smtp_call: true`
- `no_gmail_api_call: true`
- `no_api_server_created: true`
- `no_persistent_store_writes: true`
- `no_portfolio_actions: true`
- `no_cron_installation: true`
- `no_systemd_installation: true`
- `no_timer_installation: true`
- `no_service_installation: true`
- `no_live_schedule_mutation: true`
- `external_side_effects_allowed: false`
- `dashboard_deploy: false`
- `api_server_created: false`
- `trading_instruction: false`

All side-effect flags must remain false.

## `run_stock_analysis.sh` Integration

`run_stock_analysis.sh` now defaults to the gated runtime helper and writes only
decision artifacts. It does not run the production pipeline by default.

Optional environment variables:

- `STOCK_AI_SCHEDULER_WINDOW`: one of the supported scheduler windows.
- `STOCK_AI_GATE_RUNTIME_INPUT`: input fixture path.
- `STOCK_AI_GATE_RUNTIME_OUTPUT`: result output path, default `/tmp/production_scheduler_gate_runtime_result.json`.
- `STOCK_AI_GATE_RUNTIME_SUMMARY_OUTPUT`: summary output path, default `/tmp/production_scheduler_gate_runtime_summary.json`.
- `STOCK_AI_SCHEDULER_LOG_PATH`: log path, default `logs/daily.log`.

The script keeps an explicit legacy escape hatch:

```bash
STOCK_AI_LEGACY_PRODUCTION_APPROVED=1 ./run_stock_analysis.sh
```

That path preserves the previous `scripts/run_pipeline.py pre_open
--production-approved` behavior and must not be used without an explicit
operator approval because it may trigger production side effects.

## Validation

Use:

```bash
python3 -m py_compile \
  scripts/orchestrator/production_scheduler_gate_runtime.py \
  scripts/orchestrator/validate_production_scheduler_gate_runtime_result.py

python3 scripts/orchestrator/production_scheduler_gate_runtime.py \
  --input templates/production_scheduler_gate_runtime_input.example.json \
  --output /tmp/production_scheduler_gate_runtime_result.json \
  --summary-output /tmp/production_scheduler_gate_runtime_summary.json \
  --window pre_open_0700 \
  --pretty

python3 scripts/orchestrator/validate_production_scheduler_gate_runtime_result.py \
  --input /tmp/production_scheduler_gate_runtime_result.json \
  --pretty
```

Repeat the generation and validator commands with `intraday_1305` and
`pre_close_1335`.

## Activation Boundary

Actual cron, systemd, timer, or service installation remains pending a separate
explicit confirmation. This repository change only adds the safe runtime gate
and a wrapper path; it does not modify live scheduler definitions.
