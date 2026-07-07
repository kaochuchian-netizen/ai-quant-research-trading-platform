# Formal Forecast Backtest Calibration Runbook

## Scope

This runbook covers the AI-DEV-153 read-only backtest for `deterministic_baseline_v1`.

## Steps

1. Confirm the repo is on an AI-DEV branch and clean before edits.
2. Build the latest formal prediction and review artifacts if needed.
3. Build the backtest report:

```bash
python scripts/orchestrator/build_formal_forecast_backtest_report.py --pretty
```

4. Validate the report:

```bash
python scripts/orchestrator/validate_formal_forecast_backtest_report_v1.py --pretty
```

5. Review JSON and Markdown outputs under `artifacts/runtime/`.

## Output Artifacts

- `artifacts/runtime/formal_forecast_backtest_report_latest.json`
- `artifacts/runtime/formal_forecast_backtest_report_latest.md`

## Safety Boundaries

Do not read secrets, do not write DB, do not change scheduler, do not send LINE or Email, do not run `python3 main.py`, do not trade, and do not mutate production rating/action/confidence/weight logic.

## Interpretation Guide

Use the report to decide whether a future task should propose range multiplier, trend bias, or confidence cap changes. AI-DEV-153 itself must not apply those changes.
