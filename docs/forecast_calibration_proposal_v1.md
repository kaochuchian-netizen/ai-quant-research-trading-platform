# Forecast Calibration Proposal V1

AI-DEV-154 turns the AI-DEV-153 backtest into a dashboard-visible calibration proposal and method tuning gate.

## Purpose

The proposal makes calibration status visible without overstating the result. It shows sample count, same-day hit rate, next-day insufficiency, recommendation summary, and blocked actions.

## Source Backtest Artifact

Input: `artifacts/runtime/formal_forecast_backtest_report_latest.json`

Outputs:

- `artifacts/runtime/forecast_calibration_proposal_latest.json`
- `artifacts/runtime/forecast_calibration_proposal_latest.md`

## Tuning Gate Rules

- `< 30` eligible samples: block shadow tuning and formula change.
- `< 100` eligible samples: formula change remains blocked.
- next-day null requires an explicit limitation reason.
- PM approval is required before any formula change task.

## Dashboard Interpretation

Dashboard must show the result as a baseline V1 early calibration state. It must not claim model validation, hide sample size, or render null next-day hit rate as 0%.

## Safety

The proposal does not modify `deterministic_baseline_v1`, production ratings, actions, confidence, weights, DB, scheduler, notifications, delivery behavior, or trading behavior.
