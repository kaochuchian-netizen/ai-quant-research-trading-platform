# Dashboard Decision State Semantics Runbook

## Validation
Run `validate_dashboard_decision_state_semantics_v1.py --pretty` before PR and `--published` after controlled static publish.

## PM review checklist
- Top summary must not imply complete data.
- Prediction and review gaps must be visible as `資料待接`.
- Stock cards must mean watchlist validity only.
- Example artifacts must not appear as official latest reports in the main UI.
- Debug may contain raw keys; the main UI must remain readable.

## Rollback
Use the controlled Dashboard preview publish manifest rollback command. Do not change scheduler, production pipeline, notification delivery, or DB state.
