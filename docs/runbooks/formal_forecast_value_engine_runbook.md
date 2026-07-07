# Formal Forecast Value Engine Runbook

## Scope
This runbook covers AI-DEV-152 deterministic formal forecast and review artifact generation.

## Inputs
Allowed read-only inputs:

- data/historical/*_daily.csv
- read-only data/stock_analysis.db inspection
- existing runtime artifacts and templates
- stock universe / watchlist artifacts

Forbidden inputs and actions:

- external credentialed APIs
- secrets, tokens, credentials, .env
- production DB writes
- scheduler, cron, systemd, timer changes
- LINE / Email / notification sending
- python3 main.py
- broker/order/trading

## Build Commands
Use the project virtual environment:

```bash
./venv/bin/python scripts/orchestrator/build_formal_prediction_runtime_artifact.py --pretty
./venv/bin/python scripts/orchestrator/build_formal_prediction_review_runtime_artifact.py --pretty
./venv/bin/python scripts/orchestrator/build_four_window_dashboard_runtime_data_v1.py --pretty
./venv/bin/python scripts/orchestrator/build_four_window_dashboard_route_preview.py --pretty
```

## Validation Commands

```bash
./venv/bin/python scripts/orchestrator/validate_formal_forecast_value_engine_v1.py --pretty
./venv/bin/python scripts/orchestrator/validate_formal_prediction_runtime_artifact_v1.py --pretty
./venv/bin/python scripts/orchestrator/validate_formal_prediction_review_runtime_artifact_v1.py --pretty
./venv/bin/python scripts/orchestrator/validate_dashboard_decision_state_semantics_v1.py --pretty
```

## Missing Data Policy
If a stock lacks 20 valid OHLCV rows, price predictions remain null. If actual outcomes are missing for review_date, actual and review fields remain null or insufficient_data. The system must never create fake forecast values, fake actuals, fake hit rates, or fake factor effectiveness.

## Review Method
hit means actual_high <= same_day_high_prediction and actual_low >= same_day_low_prediction. partial_hit means only one side matched. miss means both failed. direction_result compares one_month_trend with actual close direction vs previous close.

## Dashboard Behavior
The Dashboard should show deterministic_baseline_v1 and the confidence/data-quality evidence. Nulls show 資料待接. Example artifacts stay out of the main UI.

## Rollback
Rollback is a git revert of the AI-DEV-152 PR plus regeneration of the previous formal runtime artifacts. Do not change scheduler, delivery, DB, or dashboard server configuration during rollback.
