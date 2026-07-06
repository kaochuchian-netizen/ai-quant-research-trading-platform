# Formal Prediction And Review Runtime Artifact Runbook

## Artifact Purpose
AI-DEV-151 adds formal prediction and review runtime artifacts so the dashboard can bind contract-backed fields without pretending missing data is complete.

## Safe Producer Usage
Use the formal prediction producer to create `artifacts/runtime/formal_prediction_runtime_latest.json`. Use the review producer to create `artifacts/runtime/formal_prediction_review_runtime_latest.json`. Both are safe local JSON writers only.

## Allowed Operations
Read existing local artifacts, read local SQLite in read-only mode, inspect local CSV/JSON files, write deterministic JSON artifacts, rebuild static dashboard artifacts, and publish the controlled static preview.

## Forbidden Operations
Do not read secrets or `.env`, write the database, change scheduler/cron/systemd/timers, send LINE/Email/notifications, run `python3 main.py`, run a production pipeline, trade, call credentialed external APIs, or mutate production rating/action/confidence/weight logic.

## Dashboard Binding Behavior
A non-example formal prediction artifact may appear in the 07:00 prediction section. A non-example formal review artifact may appear in the 15:00 review section. Null fields are shown as `資料待接`, never as complete data.

## Missing Data Policy
If supporting data is insufficient, fields remain null and must include `missing_fields` plus `insufficient_data_reasons`. No placeholder numbers, example numbers, fake hit rates, or fake actual prices are allowed.

## Example Artifact Policy
Templates under `templates/` with `is_example=true` are non-production references. They are never shown as formal main dashboard data.

## Validation Commands
Run the prediction and review validators, rebuild runtime/dashboard artifacts, run dashboard semantics validators, run branch validation, and run post-merge validation after merge.

## Rollback Guidance
Revert the AI-DEV-151 PR, delete the generated formal runtime artifact files if needed, rebuild the dashboard route preview, and republish the previous controlled static preview. Do not touch scheduler, notification, DB, broker, or production scoring settings.

## Inspection Without Notifications
Inspect generated JSON and the public preview URL only. Do not send LINE/Email or trigger delivery systems.

## Future Scheduler Integration Notes
A future task may connect the producers to scheduler windows after a separate human-approved scheduler gate. AI-DEV-151 does not implement scheduler wiring.
