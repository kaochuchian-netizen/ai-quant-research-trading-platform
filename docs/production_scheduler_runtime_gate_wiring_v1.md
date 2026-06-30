# Production Scheduler Runtime Gate Wiring V1

## Purpose

Production Scheduler Runtime Gate Wiring V1 documents the current production
scheduler shape and prepares gated dry-run-first runtime wiring for the three
known scheduler windows:

- `pre_open_0700` at `07:00`
- `intraday_1305` at `13:05`
- `pre_close_1335` at `13:35`

This contract builds on AI-DEV-099 Production Scheduler Delivery Gate
Integration V1 and AI-DEV-098 Delivery Gate Audit + Runtime Bridge V1.

The artifact is repo-only and advisory-only. It does not modify cron, systemd,
timers, services, secrets, production databases, delivery channels, dashboards,
API servers, model runtimes, market data, or portfolio state.

## Read-Only Scheduler Inspection

Allowed read-only inspection found the following user crontab entries:

```text
0 7 * * 1-5 /home/kaochuchian/stock-ai/run_stock_analysis.sh
5 13 * * 1-5 /home/kaochuchian/stock-ai/run_stock_analysis.sh
35 13 * * 1-5 /home/kaochuchian/stock-ai/run_stock_analysis.sh
```

The current shared entrypoint is:

```text
/home/kaochuchian/stock-ai/run_stock_analysis.sh
```

The script currently changes directory to the repo and invokes:

```text
/home/kaochuchian/stock-ai/venv/bin/python scripts/run_pipeline.py pre_open --production-approved >> logs/daily.log 2>&1
```

Read-only `systemctl list-timers --all` and
`systemctl list-units --type=service --all` were attempted, but the sandbox
could not connect to DBus:

```text
Failed to connect to bus: Operation not permitted
```

No cron, systemd, timer, or service definitions were modified.

## Fixture Input

The input fixture is:

```text
templates/production_scheduler_runtime_gate_wiring_input.example.json
```

It references:

```text
templates/production_scheduler_delivery_gate_integration_result.example.json
```

Referenced paths must be repo-relative. Absolute paths and parent traversal are
rejected by the dry-run helper.

## Result Contract

The machine-readable result fixture is:

```text
templates/production_scheduler_runtime_gate_wiring_result.example.json
```

The compact summary fixture is:

```text
templates/production_scheduler_runtime_gate_wiring_summary.example.json
```

Required top-level fields:

- `schema_version`
- `task_id`
- `run_id`
- `generated_at`
- `mode`
- `scheduler_inspection_summary`
- `production_scheduler_runtime_gate_wiring`
- `runtime_gate_wiring_summary`
- `validation_summary`
- `side_effects`
- `safety`
- `ok`
- `decision`
- `next_recommendation`

Allowed decisions:

- `production_scheduler_runtime_gate_wiring_completed`
- `production_scheduler_runtime_gate_wiring_completed_with_warnings`
- `runtime_wiring_blocked_pending_service_change_confirmation`
- `validation_failed`
- `blocked`

## Wiring Object

`production_scheduler_runtime_gate_wiring` contains:

- `wiring_id`
- `report_date`
- `runtime_mode`
- `source_integration_refs`
- `scheduler_windows`
- `contract_requirements`
- `activation_boundary`
- `rollback_plan`

Each scheduler window contains:

- `scheduler_window_id`
- `current_entrypoint`
- `proposed_gate_entrypoint`
- `dry_run_command`
- `future_runtime_command`
- `delivery_gate_required`
- `approval_required`
- `manual_confirmation_required`
- `allowed_side_effects`
- `blocked_side_effects`
- `rollback_plan`

## Scheduler Window Wiring

All three windows preserve the current live entrypoint as:

```text
/home/kaochuchian/stock-ai/run_stock_analysis.sh
```

The proposed repo-side gated dry-run entrypoint is:

```text
scripts/orchestrator/production_scheduler_runtime_gate_wiring_dry_run.py
```

The deterministic dry-run command is:

```bash
python3 scripts/orchestrator/production_scheduler_runtime_gate_wiring_dry_run.py \
  --input templates/production_scheduler_runtime_gate_wiring_input.example.json \
  --output /tmp/production_scheduler_runtime_gate_wiring_result.json \
  --summary-output /tmp/production_scheduler_runtime_gate_wiring_summary.json \
  --pretty
```

Future runtime commands are modeled as contract strings only. They are not
installed into cron, systemd, timers, or services by this task, and they all
include `--require-manual-confirmation`.

## Safety Requirements

The result must preserve:

- `repo_only: true`
- `gated_dry_run_first: true`
- `advisory_only: true`
- `manual_confirmation_required: true`
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
- `no_cron_modification: true`
- `no_systemd_modification: true`
- `no_timer_modification: true`
- `no_service_modification: true`
- `no_schedule_service_changes: true`
- `external_side_effects_allowed: false`
- `dashboard_deploy: false`
- `api_server_created: false`
- `trading_instruction: false`

All side-effect flags must remain false.

## Validation

Use:

```bash
python3 scripts/orchestrator/validate_production_scheduler_runtime_gate_wiring_result.py \
  --input /tmp/production_scheduler_runtime_gate_wiring_result.json \
  --pretty
```

Validation checks required fields, read-only inspection summary, scheduler
window modeling, current entrypoints, proposed gated dry-run entrypoints, source
AI-DEV-099 refs, manual confirmation requirements, activation boundary, summary
consistency, side-effect flags, safety flags, secret-like text, forbidden live
mutation commands, and prohibited transaction wording patterns.

## Runtime Activation Boundary

AI-DEV-100 stops before actual scheduler mutation. Any future change to cron,
systemd, timers, services, delivery channels, dashboard deployment, API servers,
databases, market data, model runtime, or portfolio actions requires a separate
reviewed task and explicit manual confirmation.
