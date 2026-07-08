# AI-DEV-160 Intraday Delivery Timeout, Batch-Safe Guard & Dashboard Content De-dup V1

## Purpose

AI-DEV-160 fixes the 13:05 delivery stall class and cleans the Dashboard decision surface without changing trading, scheduler, notification, forecast-weight, or production scoring behavior.

## 13:05 Incident Summary

The 13:05 intraday approved delivery did not reach Dashboard publish, Email delivery, or LINE delivery because the child production pipeline was still running after the delivery window. The formatter and sender were not the root cause.

## Root Cause

The approved delivery wrapper could wait too long for the child pipeline. When that happened, downstream delivery stages never received a completed runtime artifact, and the Dashboard showed raw missing-artifact language.

## Timeout Policy

The wrapper applies window-specific child pipeline timeouts:

- 07:00 pre-open: 30 minutes
- 13:05 intraday: 10 minutes
- 13:35 pre-close snapshot: 10 minutes
- 15:00 prediction review: 15 minutes

When the child pipeline times out, the wrapper writes a timed-out artifact, marks `pipeline_completed=false`, and keeps LINE, Email, and Dashboard publish attempts disabled.

## Late Delivery Suppression Policy

Each window has a grace period. Completed pipelines outside the grace period are marked `completed_late_delivery_suppressed`; LINE and Email are not sent because stale delivery is more harmful than missing delivery.

Grace periods:

- 07:00 pre-open: 30 minutes
- 13:05 intraday: 15 minutes
- 13:35 pre-close snapshot: 15 minutes
- 15:00 prediction review: 20 minutes

## Heartbeat Artifact Policy

The wrapper writes repo-local progress artifacts under `artifacts/runtime/` for wrapper start, pipeline launch, completion, timeout, skipped delivery, attempted delivery, and late suppression. These artifacts are operational breadcrumbs only; they are not trading signals.

## Dashboard Missing-State Wording

The main Dashboard uses human-readable state text:

- `13:05 盤中追蹤：今日資料尚未完成`
- `13:35 收盤快照：資料尚未產生`

Raw terms such as runtime artifact, report artifact, pipeline keys, and artifact inventory stay out of the main decision flow.

## Dashboard Stock Card De-dup Policy

Each stock card keeps stock-specific information only: forecast intervals, 1M / 3M trends, confidence, major news state, and data status. Shared baseline method and risk text appears once in a common section.

## Major News Rendering Policy

The Dashboard only renders news titles from existing local artifacts. If no safe title artifact is available, it shows `重大新聞資料待接`. It does not call external APIs and does not fabricate news.

## No Fake Data Policy

AI-DEV-160 does not fabricate forecasts, review metrics, historical prediction snapshots, or news titles. Missing data remains explicit and human-readable.

## Batch Regression Guard

The validator protects the four delivery contracts:

- 07:00 remains short LINE plus Dashboard URL.
- 13:05 remains intraday tracking with timeout and late-delivery guard.
- 13:35 remains `收盤快照`.
- 15:00 remains `盤後檢討` with single-day and rolling review sections.

## Safety Boundary

This release does not perform broker login, simulation order, production order, LINE send, Email send, scheduler mutation, production DB write, secrets read, forecast weight mutation, dashboard production publish, or production pipeline execution.

## Validation Commands

Use `./venv/bin/python` only:

```bash
./venv/bin/python -m py_compile   scripts/orchestrator/validate_intraday_delivery_timeout_dashboard_cleanup_v1.py   scripts/orchestrator/simulate_intraday_delivery_timeout_guard_v1.py   scripts/orchestrator/approved_pre_open_delivery.py   app/dashboard/four_window_route_integration.py

./venv/bin/python scripts/orchestrator/simulate_intraday_delivery_timeout_guard_v1.py --pretty
./venv/bin/python scripts/orchestrator/validate_intraday_delivery_timeout_dashboard_cleanup_v1.py --pretty
./venv/bin/python scripts/orchestrator/validate_ai_branch.py --base main --head HEAD --pretty
```

## Future Optional Design

A future release may add nonblocking early operator notification when an intraday pipeline is still running near the grace cutoff. AI-DEV-160 does not enable that behavior.
