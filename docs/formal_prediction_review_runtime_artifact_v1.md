# Formal Prediction Review Runtime Artifact V1

AI-DEV-151 defines the first null-safe formal 15:00 prediction review runtime artifact for the TW dashboard.

## Purpose
The artifact gives the dashboard a formal contract for actual high/low/close, direction result, high-low forecast error, hit/miss status, seven-day hit rate, confidence calibration, factor effectiveness, error reasons, and improvement notes.

## Missing Data Policy
A review is only valid when a formal prediction artifact and actual outcome data can be compared safely. If those inputs are missing, review values remain `null`, `missing_fields` lists the blocked fields, and `insufficient_data_reasons` explains the gap. The producer must not create fake hit rates, fake actual prices, or fake review metrics.

## Source Policy
The review producer may read existing local artifacts and safe actual outcome sources in read-only mode. The current V1 safe stub records insufficient data rather than inventing a review.

## Dashboard Binding
The dashboard may show a non-example `formal_prediction_review_runtime` artifact in the 15:00 review section. Null fields remain `資料待接`. Example artifacts are debug/reference only.

## Safety
The producer is read-only except for writing the JSON artifact. It does not call external APIs, read secrets, write the database, send notifications, run `python3 main.py`, execute a production pipeline, trade, or mutate rating/action/confidence/weight logic.
