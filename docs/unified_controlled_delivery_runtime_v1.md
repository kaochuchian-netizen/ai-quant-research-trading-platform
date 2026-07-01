# Unified Controlled Delivery Runtime V1

AI-DEV-107 adds a unified controlled runtime for LINE, Email, and a private
static dashboard target.

## Scope

The runtime is repo-side and dry-run by default. It produces deterministic JSON
for:

- LINE gate/runtime readiness
- Email gate/runtime setting presence
- Dashboard private static publish readiness
- Exact manual commands for later controlled tests

It does not enable scheduler approved delivery, cron, systemd, timers, services,
LINE push, SMTP, Gmail API, dashboard publish, API server creation, portfolio
actions, or trading actions by default.

## Files

- `scripts/orchestrator/unified_controlled_delivery_runtime.py`
- `scripts/orchestrator/private_static_dashboard_publish.py`
- `scripts/orchestrator/validate_unified_controlled_delivery_runtime_result.py`
- `templates/unified_controlled_delivery_runtime_input.example.json`
- `templates/unified_controlled_delivery_runtime_result.example.json`
- `templates/unified_controlled_delivery_runtime_summary.example.json`
- `templates/private_static_dashboard_publish_result.example.json`

## Dry Run

```bash
python3 scripts/orchestrator/unified_controlled_delivery_runtime.py \
  --input templates/unified_controlled_delivery_runtime_input.example.json \
  --output /tmp/unified_controlled_delivery_runtime_result.json \
  --summary-output /tmp/unified_controlled_delivery_runtime_summary.json \
  --pretty
```

Validate:

```bash
python3 scripts/orchestrator/validate_unified_controlled_delivery_runtime_result.py \
  --input /tmp/unified_controlled_delivery_runtime_result.json \
  --pretty
```

## Controlled Commands

Do not run these commands until the user gives a separate explicit confirmation
for the specific action.

Controlled LINE test:

```bash
python3 scripts/orchestrator/unified_controlled_delivery_runtime.py \
  --input templates/unified_controlled_delivery_runtime_input.example.json \
  --output /tmp/unified_controlled_line_test_result.json \
  --summary-output /tmp/unified_controlled_delivery_runtime_summary.json \
  --pretty --send-test-line
```

Controlled Email test:

```bash
python3 scripts/orchestrator/unified_controlled_delivery_runtime.py \
  --input templates/unified_controlled_delivery_runtime_input.example.json \
  --output /tmp/unified_controlled_email_test_result.json \
  --summary-output /tmp/unified_controlled_delivery_runtime_summary.json \
  --pretty --send-test-email
```

Private static dashboard publish:

```bash
python3 scripts/orchestrator/private_static_dashboard_publish.py \
  --input templates/dashboard_delivery_gate_result.example.json \
  --publish-dir /tmp/stock_ai_private_static_dashboard \
  --output /tmp/private_static_dashboard_publish_result.json \
  --pretty --publish
```

Browser check after a confirmed publish:

```bash
python3 -m webbrowser file:///tmp/stock_ai_private_static_dashboard/index.html
```

Scheduler approved delivery activation candidate:

```bash
python3 scripts/orchestrator/production_scheduler_gate_runtime.py \
  --input templates/production_scheduler_gate_runtime_input.example.json \
  --output /tmp/production_scheduler_gate_runtime_result.json \
  --summary-output /tmp/production_scheduler_gate_runtime_summary.json \
  --window pre_open_0700 --pretty
```

This scheduler command is a candidate only. It does not install cron, systemd,
timers, services, or activate production delivery.

## Safety Contract

Required safety fields are emitted by the unified runtime:

- `controlled_delivery_runtime: true`
- `dry_run_default: true`
- `delivery_gate_required: true`
- `no_token_printing: true`
- `no_secret_logging: true`
- `no_secret_read: true`
- `no_line_push_by_default: true`
- `no_email_send_by_default: true`
- `no_dashboard_publish_by_default: true`
- `no_smtp_call_by_default: true`
- `no_gmail_api_call_by_default: true`
- `no_api_server_created: true`
- `no_persistent_store_writes: true`
- `no_portfolio_actions: true`
- `no_cron_modification: true`
- `no_systemd_modification: true`
- `no_timer_modification: true`
- `no_service_modification: true`
- `no_schedule_service_changes: true`
- `trading_instruction: false`

Email runtime inspection reports only environment variable names that are present
or missing. It does not print values.
