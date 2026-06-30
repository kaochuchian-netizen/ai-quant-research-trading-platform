# Production Scheduler Gate Runtime Smoke Test V1

## Purpose

AI-DEV-102 documents a safe runtime smoke test for the production scheduler gate
entrypoint added by AI-DEV-101. The smoke test confirms that the scheduler path
stays in gated dry-run/no-delivery mode and that all external delivery and live
scheduler mutation paths remain blocked by default.

This smoke test must not send Email, push LINE, deploy dashboards, write
production databases, mutate secrets, modify cron/systemd/timers/services, or
enable the legacy production path.

## Scope

The smoke test covers:

- `run_stock_analysis.sh`
- `production_scheduler_gate_runtime.py --window pre_open_0700`
- `production_scheduler_gate_runtime.py --window intraday_1305`
- `production_scheduler_gate_runtime.py --window pre_close_1335`

All runs use `templates/production_scheduler_gate_runtime_input.example.json`
and write temporary artifacts under `/tmp`.

## Required Safety Assertions

Every smoke result must preserve:

- `delivery_allowed: false`
- `safety.no_email_send: true`
- `safety.no_line_push: true`
- `safety.no_dashboard_deploy: true`
- `safety.no_persistent_store_writes: true`
- `safety.no_live_schedule_mutation: true`
- `side_effects.sent_email: false`
- `side_effects.sent_line_push: false`
- `side_effects.deployed_dashboard: false`
- `side_effects.wrote_persistent_store: false`
- `side_effects.modified_cron: false`
- `side_effects.modified_systemd: false`
- `side_effects.modified_timer: false`
- `side_effects.modified_service: false`

## Commands

Syntax check:

```bash
bash -n run_stock_analysis.sh
```

Shell entrypoint smoke test:

```bash
./run_stock_analysis.sh
```

Runtime window smoke tests:

```bash
python3 scripts/orchestrator/production_scheduler_gate_runtime.py \
  --input templates/production_scheduler_gate_runtime_input.example.json \
  --output /tmp/production_scheduler_gate_runtime_smoke_pre_open.json \
  --summary-output /tmp/production_scheduler_gate_runtime_smoke_pre_open_summary.json \
  --window pre_open_0700 \
  --pretty

python3 scripts/orchestrator/production_scheduler_gate_runtime.py \
  --input templates/production_scheduler_gate_runtime_input.example.json \
  --output /tmp/production_scheduler_gate_runtime_smoke_intraday.json \
  --summary-output /tmp/production_scheduler_gate_runtime_smoke_intraday_summary.json \
  --window intraday_1305 \
  --pretty

python3 scripts/orchestrator/production_scheduler_gate_runtime.py \
  --input templates/production_scheduler_gate_runtime_input.example.json \
  --output /tmp/production_scheduler_gate_runtime_smoke_pre_close.json \
  --summary-output /tmp/production_scheduler_gate_runtime_smoke_pre_close_summary.json \
  --window pre_close_1335 \
  --pretty
```

Runtime result validation:

```bash
python3 scripts/orchestrator/validate_production_scheduler_gate_runtime_result.py \
  --input /tmp/production_scheduler_gate_runtime_smoke_pre_open.json \
  --pretty

python3 scripts/orchestrator/validate_production_scheduler_gate_runtime_result.py \
  --input /tmp/production_scheduler_gate_runtime_smoke_intraday.json \
  --pretty

python3 scripts/orchestrator/validate_production_scheduler_gate_runtime_result.py \
  --input /tmp/production_scheduler_gate_runtime_smoke_pre_close.json \
  --pretty
```

Smoke result fixture validation:

```bash
python3 scripts/orchestrator/validate_production_scheduler_gate_runtime_smoke_test_result.py \
  --input templates/production_scheduler_gate_runtime_smoke_test_result.example.json \
  --pretty
```

Branch and formatting validation:

```bash
python3 scripts/orchestrator/validate_ai_branch.py
git diff --check
```

## Forbidden Paths

Do not run:

- `STOCK_AI_LEGACY_PRODUCTION_APPROVED=1 ./run_stock_analysis.sh`
- `python3 main.py --production-approved`
- `scripts/run_pipeline.py pre_open --production-approved`
- commands that send Email or LINE messages
- commands that deploy dashboards
- commands that modify cron, systemd, timers, or services
- commands that read or mutate secrets
- commands that write production databases

## Expected Result

The deterministic fixture is:

- `templates/production_scheduler_gate_runtime_smoke_test_result.example.json`

It records successful dry-run/no-delivery smoke coverage for all three scheduler
windows and confirms that no delivery, persistent store write, or live scheduler
mutation occurred.
