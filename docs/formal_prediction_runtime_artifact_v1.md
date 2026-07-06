# Formal Prediction Runtime Artifact V1

AI-DEV-151 defines the first null-safe formal 07:00 prediction runtime artifact for the TW dashboard.

## Purpose
The artifact gives the dashboard a formal contract for same-day high/low, next-day high/low, one-month trend, three-month trend, confidence, evidence, risk notes, source evidence, and data quality.

## Missing Data Policy
The producer must not fabricate forecast values. If a safe model output is unavailable, prediction fields remain `null`, `missing_fields` lists the blocked fields, and `insufficient_data_reasons` explains why. Values such as `0`, `-1`, `N/A`, or example numbers are not allowed as fake predictions.

## Source Policy
Existing local summaries may be used as context evidence only. They cannot be recast as formal high/low predictions. Source evidence must identify source types such as `local_summary`, `historical_price`, `technical_snapshot`, `chip_summary`, and `news_summary`.

## Dashboard Binding
The dashboard may show a non-example `formal_prediction_runtime` artifact in the main view. Null fields remain `資料待接`. Example artifacts are debug/reference only.

## Safety
The producer is read-only except for writing the JSON artifact. It does not call external APIs, read secrets, write the database, send notifications, run `python3 main.py`, execute a production pipeline, trade, or mutate rating/action/confidence/weight logic.
