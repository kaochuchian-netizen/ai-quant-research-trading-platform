# AI-DEV-155 Formal Forecast Daily Snapshot Accumulation V1

AI-DEV-155 starts file-based accumulation for formal forecast samples. It archives real formal prediction runtime artifacts, read-only actual outcomes, and null-safe review snapshots so deterministic_baseline_v1 can move from a 9-sample calibration state toward the 30/100 sample gates.

## Purpose

The goal is sample accumulation, not model tuning. The task does not change deterministic_baseline_v1, production rating/action/confidence/weight logic, scheduler, delivery behavior, DB state, or notification behavior.

## Archive Structure

- `artifacts/archive/formal_forecast_snapshots/prediction/`
- `artifacts/archive/formal_forecast_snapshots/actual_outcome/`
- `artifacts/archive/formal_forecast_snapshots/review/`
- `artifacts/archive/formal_forecast_snapshots/index/`

Daily filenames use `YYYY-MM-DD` and the latest index is written to `formal_forecast_snapshot_index_latest.json` and `.md`.

## Prediction Snapshot Policy

Prediction snapshots may only come from `artifacts/runtime/formal_prediction_runtime_latest.json` when it is a real formal runtime artifact with `is_example=false` and `method_version/model_version=deterministic_baseline_v1`. Fake historical prediction backfill is forbidden.

Existing same-date snapshots are not overwritten unless `--overwrite` is explicitly passed. This keeps the archive idempotent.

## Actual Outcome Snapshot Policy

Actual outcomes may be read from local historical OHLCV files in read-only mode. Any actual outcome sourced this way is explicitly marked with `is_backfilled_actual`. Missing actuals remain `null` with `insufficient_data` reasons.

## Review Snapshot Policy

Review snapshots connect prediction snapshots with actual outcome snapshots. Same-day interval results are computed only when prediction and actual data exist. Next-day results remain `null` when the next trading-day actual is unavailable, and the reason must be explicit.

## Sample Accumulation Thresholds

- Shadow tuning threshold: 30 eligible same-day samples
- Formula change threshold: 100 eligible same-day samples

If the eligible sample count is below 30, the gate remains `blocked_insufficient_sample`. Snapshot count is not model performance.

## Dashboard Interpretation

The Dashboard shows snapshot accumulation progress and gate distance. It must not present snapshot count as performance, hide sample count, convert missing next-day samples to 0%, or claim deterministic_baseline_v1 is fully validated.

## Safety Boundaries

AI-DEV-155 does not call external APIs, read secrets, write DB state, modify scheduler/cron/systemd/timer, send LINE/Email, run `python3 main.py`, execute the production pipeline, trade, or change production rating/action/confidence/weight logic.

## Future Scheduler Integration

A future task may propose scheduler integration after human review. This task only documents that future path and does not implement any scheduler behavior.
