# Actual Outcome Backfill Plan

## Purpose

This document defines a research-only plan and read-only prototype boundary for
actual outcome backfill. The goal is to make prediction review records
evaluable after the forecast window has elapsed while preserving the original
forecast snapshot and avoiding production side effects.

The companion prototype is:

```bash
python3 scripts/orchestrator/backfill_actual_outcome_examples.py --pretty
```

It reads only the AI-DEV-018 research samples, emits JSON to stdout, and does
not write files, write databases, call external services, send notifications,
run production pipelines, or generate investment advice.

## Relationship to AI-DEV-018/019/020

AI-DEV-018 introduced the research-only prediction review storage samples and
the future boundary between forecast review, actual outcome enrichment, and
backtest integration.

AI-DEV-019 added a read-only loader summary for the same sample bundle. That
loader verifies linkage, lifecycle, and status counts before any reporting or
backfill work is considered.

AI-DEV-020 added a read-only report summary export. It turns the same sample
bundle into a dashboard/email-shaped preview without delivery side effects.

AI-DEV-021 builds on those artifacts by describing the actual outcome backfill
lifecycle and adding a read-only prototype that classifies completed and
pending sample outcomes. It remains a planning artifact only.

## Non-goals

- No production pipeline changes.
- No formal database writes.
- No historical CSV or SQLite mutation.
- No cron, systemd, or timer changes.
- No LINE, email, dashboard, or notification delivery.
- No external market-data service calls.
- No secrets, credentials, tokens, or `.env` access.
- No trading, order placement, or investment advice.
- No change to the existing backtest engine behavior.

## Input Records

The prototype reads this research-only bundle:

```text
orchestrator/templates/research_samples/prediction_review_storage/
```

Expected inputs:

- `forecast_to_review_record.example.json`
- `actual_outcome_backfill.example.json`
- `prediction_review_storage_index.example.json`

The forecast record provides the immutable forecast snapshot, forecast window,
run date, stock identity, and pending policy. The outcome record provides a
completed actual outcome example plus a pending example. The storage index
provides metadata linkage and safety boundaries.

## Actual Outcome Fields

Completed outcome examples should carry:

- `actual_close`
- `actual_high`
- `actual_low`
- `actual_return`
- `actual_direction`
- `unit`
- `market_data_source`
- `captured_at`

The backfill record should also preserve:

- `backfill_status`
- `backfill_timestamp`
- `missing_data_policy`
- `holiday_policy`
- `suspended_trading_policy`

Allowed `backfill_status` values for this prototype are:

- `pending`
- `completed`
- `missing_market_data`
- `non_trading_day`
- `suspended`
- `invalid_window`
- `not_due`

## Backfill Lifecycle

The intended lifecycle is:

1. Forecast snapshot is created.
2. Prediction review record is created.
3. Actual outcome remains pending until the forecast window is due.
4. Outcome is classified as completed, pending, missing market data,
   non-trading day, suspended, invalid window, or not due.
5. Completed outcomes become evaluable.
6. Non-evaluable outcomes remain explicit and are not counted as failures.
7. Derived metrics may be calculated by separate research-only evaluation tools.

Pending records are preserved so that incomplete data does not disappear from
later summaries or calibration checks.

## Forecast Window Alignment

The forecast window and outcome window must align before an outcome can be
treated as evaluable. The prototype reports:

- start date match
- end date match
- window type match
- horizon match
- overall window alignment
- forecast start date relative to run date

If alignment fails, future production-grade logic should classify the record as
`invalid_window` and require manual review instead of scoring it.

## Trading Day, Holiday, and Suspended Policy

This prototype does not call a trading calendar or market-data service. It only
documents the intended policy:

- If the forecast target date is not a trading day, preserve a
  `non_trading_day` status or keep the record pending until a reviewed calendar
  rule is approved.
- If trading is suspended, classify the record as `suspended` and preserve the
  reason for manual review.
- If the window has not elapsed, use `not_due` or `pending`.
- Do not infer prices for holidays, suspended sessions, or missing sessions.

Future calendar integration must be approved separately because it may require
external data access or production data boundaries.

## Missing Data Policy

Missing outcome data must remain explicit. The allowed data quality flags are:

- `sample_data_only`
- `research_only`
- `missing_actual_close`
- `missing_actual_high`
- `missing_actual_low`
- `missing_actual_return`
- `window_not_elapsed`
- `manual_review_required`

Pending records do not fail validation. They are counted as non-evaluable and
kept available for later backfill.

## Lookahead Bias Control

Backfill must not change the original forecast snapshot. Controls:

- Preserve `created_at` from the forecast record.
- Preserve `captured_at` and `backfill_timestamp` from outcome data.
- Verify forecast creation occurred before actual outcome capture.
- Keep actual outcomes in a mutable enrichment layer, separate from the
  immutable forecast snapshot.
- Do not score records whose windows are not elapsed or not aligned.
- Do not fabricate missing outcomes.

## Data Quality Flags

The read-only prototype emits aggregate and per-candidate data quality flags.
Flags are intended for research triage only. They do not authorize production
alerts, trading decisions, dashboard publishing, or notification delivery.

## Backtest Engine Boundary

Actual outcome backfill is not the backtest engine. Prediction review evaluates
forecast quality, while the backtest engine evaluates strategy or signal
performance. They may share an approved outcome loader in the future, but the
boundary should remain explicit:

- Prediction review: forecast accuracy and calibration.
- Backtest engine: strategy, signal, and action performance.

No current backtest engine behavior changes as part of AI-DEV-021.

## Future DB Migration

A future controlled migration may add formal tables for forecast snapshots,
review records, outcome enrichment, evaluation metrics, and archive indexes.
That migration must be a separate approved task with explicit safeguards for:

- schema migration review
- dry-run validation
- backup strategy
- production write approval
- rollback plan
- notification and scheduler isolation

AI-DEV-021 does not create or modify any database.

## Safety Boundaries

AI-DEV-021 is limited to docs and read-only scripts. It must not:

- run `python3 main.py`
- run `./run_stock_analysis.sh`
- run any production-approved runner
- modify `.env` or secrets
- write production DB or formal DB records
- change cron, systemd, or timers
- send LINE, email, or other notifications
- call external services
- trade or place orders

## Validation Commands

Use these local read-only checks:

```bash
python3 -m py_compile scripts/orchestrator/backfill_actual_outcome_examples.py
python3 scripts/orchestrator/backfill_actual_outcome_examples.py --pretty
python3 scripts/orchestrator/validate_prediction_review_storage_examples.py --pretty
python3 scripts/orchestrator/summarize_prediction_review_storage_examples.py --pretty
python3 scripts/orchestrator/export_prediction_review_report_summary.py --pretty
python3 scripts/orchestrator/validate_schema_examples.py --pretty
python3 scripts/orchestrator/evaluate_prediction_review_examples.py --pretty
python3 scripts/orchestrator/validate_scheduled_runner.py --pretty
python3 scripts/orchestrator/inspect_ai_platform_status.py --pretty
python3 scripts/orchestrator/check_forbidden_changes.py --base main --head HEAD --pretty
python3 scripts/orchestrator/validate_ai_branch.py --base main --head HEAD --pretty
```
