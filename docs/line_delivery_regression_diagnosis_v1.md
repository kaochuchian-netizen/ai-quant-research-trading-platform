# LINE Delivery Regression Diagnosis V1

Task: AI-DEV-104

This diagnostic is repo-side and read-only. It explains why daily LINE delivery appears to have stopped after 2026-06-23 13:35 without sending LINE, calling the LINE API, reading secrets, mutating cron/systemd/timers/services, writing production databases, or triggering production delivery.

## Inspection Scope

- `crontab -l`
- `run_stock_analysis.sh`
- `scripts/run_pipeline.py`
- `main.py`
- LINE sender modules under `reports/` and `app/clients/`
- `logs/daily.log` and rotated `logs/daily.log.*.gz`
- Git timeline since 2026-06-23 for scheduler, runner, app, reports, and scripts paths

## Key Findings

Cron is still installed for weekday 07:00, 13:05, and 13:35 executions, all pointing to `/home/kaochuchian/stock-ai/run_stock_analysis.sh`.

The 2026-06-23 13:35 rotated log shows a full production-style `pre_open` run: historical CSV update completed, reports were built, three LINE batches were attempted, and the backtest auto updater finished.

Starting 2026-06-24, cron entries still appear to fire, but the pipeline fails before LINE delivery. The first observed failure is a Shioaji `Kbars date range must not exceed 30 days` error during historical CSV update. Later runs repeatedly fail at Shioaji login with a maintenance/version message requiring a Shioaji package upgrade. These failures occur before report batching reaches the LINE sender.

Current `run_stock_analysis.sh` no longer directly executes the approved production pipeline unless the legacy production approval environment flag is enabled. By default it runs `scripts/orchestrator/production_scheduler_gate_runtime.py`, whose fixture input is `dry_run_no_delivery`, `approval_status=pending_approval`, and `delivery_allowed=false`.

Recent commits after 2026-06-23 are concentrated around delivery gate and production scheduler gate work, especially AI-DEV-099 through AI-DEV-103. AI-DEV-101 introduced the runtime activation gate that keeps delivery execution disabled by default.

No inspected log shows a LINE sender exception after 2026-06-23 13:35. The observed failures happen earlier in the pipeline or inside the gate runtime. No secret values were read or printed during this diagnosis.

## Likely Root Cause

The immediate delivery regression is most likely not cron absence and not a directly observed LINE token failure. The stronger evidence is:

1. Runtime pipeline failures after 2026-06-23 13:35 prevent report generation from reaching LINE send.
2. The current scheduler runner default is a no-delivery gate path unless explicit legacy production approval is present.

The Shioaji failures explain why scheduled runs after 2026-06-23 do not reach LINE. The delivery gate change explains why current default scheduler behavior can also produce successful diagnostic output while intentionally blocking LINE delivery.

## Recommended AI-DEV-105

Create a no-send production readiness diagnostic that:

- verifies the installed Shioaji version and historical request window logic without logging in or calling market APIs;
- adds a safe preflight for the 30-day Kbars constraint;
- makes scheduler logs explicitly distinguish `pipeline_failed_before_delivery` from `delivery_gate_blocked`;
- documents the manual approval path needed before restoring live LINE delivery;
- keeps LINE push and external API calls disabled until a separate explicit approval is given.
