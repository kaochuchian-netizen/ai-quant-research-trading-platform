# Production Scheduler Gate Observability V1

## Purpose

AI-DEV-103 adds repo-side observability for the production scheduler gate runtime
introduced by AI-DEV-101 and smoke-tested by AI-DEV-102.

This change is observability-only. It does not install or mutate cron, systemd,
timers, services, secrets, delivery channels, dashboards, API servers,
production databases, market data, model runtimes, or portfolio state.

## Observability Contract

The inspection helper reads the latest gated runtime artifacts and writes a
deterministic observability result plus a compact summary.

Default latest gate runtime paths:

- `/tmp/production_scheduler_gate_runtime_result.json`
- `/tmp/production_scheduler_gate_runtime_summary.json`

Default observability output paths used by the runbook:

- `/tmp/production_scheduler_gate_observability_result.json`
- `/tmp/production_scheduler_gate_observability_summary.json`

Required result fields:

- `schema_version`
- `task_id`
- `run_id`
- `generated_at`
- `mode`
- `observed_scheduler_window`
- `latest_gate_result_path`
- `latest_gate_summary_path`
- `delivery_allowed`
- `approval_status`
- `gate_runtime_decision`
- `blocked_actions`
- `side_effects`
- `safety`
- `ok`
- `decision`
- `next_recommendation`

Allowed decisions:

- `production_scheduler_gate_observability_completed`
- `production_scheduler_gate_observability_completed_with_warnings`
- `latest_gate_result_not_found`
- `validation_failed`
- `blocked`

## Safety Boundary

The observability result must preserve:

- `repo_only: true`
- `observability_only: true`
- `gated_runtime: true`
- `dry_run_default: true`
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

## Inspection Helper

Run after a scheduled gate runtime has had time to finish:

```bash
python3 scripts/orchestrator/inspect_production_scheduler_gate_latest.py \
  --output /tmp/production_scheduler_gate_observability_result.json \
  --summary-output /tmp/production_scheduler_gate_observability_summary.json \
  --pretty
```

The helper only reads the latest gate runtime files and writes JSON artifacts to
the requested paths. If the latest gate result is missing, it writes a valid
observability artifact with `decision: latest_gate_result_not_found`.

Validate the result:

```bash
python3 scripts/orchestrator/validate_production_scheduler_gate_observability_result.py \
  --input /tmp/production_scheduler_gate_observability_result.json \
  --pretty
```

## Tomorrow Check Runbook

After the scheduled 07:00 run:

```bash
python3 scripts/orchestrator/inspect_production_scheduler_gate_latest.py \
  --output /tmp/production_scheduler_gate_observability_0700_result.json \
  --summary-output /tmp/production_scheduler_gate_observability_0700_summary.json \
  --pretty

python3 scripts/orchestrator/validate_production_scheduler_gate_observability_result.py \
  --input /tmp/production_scheduler_gate_observability_0700_result.json \
  --pretty
```

Expected key values:

- `observed_scheduler_window: pre_open_0700`
- `delivery_allowed: false`
- `approval_status: pending_approval`
- `safety.no_delivery_actions: true`
- `side_effects.sent_line_push: false`
- `side_effects.sent_email: false`
- `side_effects.deployed_dashboard: false`

After the scheduled 13:05 run:

```bash
python3 scripts/orchestrator/inspect_production_scheduler_gate_latest.py \
  --output /tmp/production_scheduler_gate_observability_1305_result.json \
  --summary-output /tmp/production_scheduler_gate_observability_1305_summary.json \
  --pretty

python3 scripts/orchestrator/validate_production_scheduler_gate_observability_result.py \
  --input /tmp/production_scheduler_gate_observability_1305_result.json \
  --pretty
```

Expected key values:

- `observed_scheduler_window: intraday_1305`
- `delivery_allowed: false`
- `approval_status: pending_approval`
- `safety.no_cron_installation: true`
- `safety.no_systemd_installation: true`
- `safety.no_timer_installation: true`
- `safety.no_service_installation: true`

After the scheduled 13:35 run:

```bash
python3 scripts/orchestrator/inspect_production_scheduler_gate_latest.py \
  --output /tmp/production_scheduler_gate_observability_1335_result.json \
  --summary-output /tmp/production_scheduler_gate_observability_1335_summary.json \
  --pretty

python3 scripts/orchestrator/validate_production_scheduler_gate_observability_result.py \
  --input /tmp/production_scheduler_gate_observability_1335_result.json \
  --pretty
```

Expected key values:

- `observed_scheduler_window: pre_close_1335`
- `delivery_allowed: false`
- `gate_runtime_decision.pipeline_execution_allowed: false`
- `gate_runtime_decision.delivery_execution_allowed: false`
- `safety.no_live_schedule_mutation: true`

## Example Validation

```bash
python3 scripts/orchestrator/validate_production_scheduler_gate_observability_result.py \
  --input templates/production_scheduler_gate_observability_result.example.json \
  --pretty
```

## Boundaries

Do not use this observability task to:

- enable the legacy production path
- send Email or LINE messages
- deploy a dashboard
- call SMTP or Gmail API
- create an API server
- mutate live data, model runtime, production databases, secrets, schedules, or services
- install or modify cron, systemd, timers, or services
