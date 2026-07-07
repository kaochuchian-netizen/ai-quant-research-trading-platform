# Forecast Calibration Proposal Runbook

## Build

```bash
python scripts/orchestrator/build_forecast_calibration_proposal_v1.py --pretty
python scripts/orchestrator/build_four_window_dashboard_route_preview.py --pretty
```

## Validate

```bash
python scripts/orchestrator/validate_forecast_calibration_proposal_v1.py --pretty
python scripts/orchestrator/validate_formal_forecast_backtest_report_v1.py --pretty
python scripts/orchestrator/validate_dashboard_decision_state_semantics_v1.py --pretty
```

## Publish Preview

Controlled static dashboard preview publish is allowed when the task scope approves it. Do not send LINE or Email, do not change scheduler, do not write DB, and do not run production pipelines.

## Human Interpretation

A low sample count means proposal visibility only. It does not justify direct formula mutation.
