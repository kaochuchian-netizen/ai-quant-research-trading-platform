# Prediction Review Storage and Backtest Integration Plan

## Purpose

This document defines a research-only plan for storing forecast outputs as
traceable prediction review records, enriching them with actual outcomes, and
preparing a future boundary with the existing backtest engine.

The goal is to make forecast results:

- traceable
- backfill-friendly
- evaluation-friendly
- archive-friendly
- future backtest-compatible

This plan does **not** connect any production pipeline, database, notification
path, cron job, or trading workflow.

## Non-goals

- No formal database writes.
- No production pipeline changes.
- No email, LINE, or other notification delivery.
- No cron, systemd, or timer changes.
- No dashboard backend implementation.
- No trading or order placement.
- No change to the existing backtest engine's production behavior.

## Current Context

AI-DEV-017 established the forecast and prediction review examples plus a
read-only evaluation prototype. The remaining gap is how those artifacts should
be stored, enriched, and later connected to historical market outcomes without
mixing them into the production trading flow.

The main missing pieces are:

- storage location
- record lifecycle
- actual outcome backfill model
- prediction review archive model
- boundary with the backtest engine

## Proposed Storage Model

The proposed model separates the workflow into three logical layers:

1. **Immutable forecast snapshot**
   - the original forecast payload
   - frozen at generation time
   - used for traceability and audit

2. **Mutable review / enrichment layer**
   - prediction review status
   - actual outcome backfill
   - evaluation metrics
   - summary notes

3. **Metadata index**
   - storage policy
   - record lifecycle status
   - data status
   - discovery / query hints

For now, these are represented as research-only sample records under
`orchestrator/templates/research_samples/prediction_review_storage/`.

## Record Lifecycle

The intended lifecycle is:

1. forecast generated
2. review record created
3. actual outcome pending
4. actual outcome backfilled
5. evaluation metrics calculated
6. report summary generated
7. archived / queryable

The lifecycle is intentionally separate from trading execution and separate
from the operational task queue.

## Forecast Output to Review Record Mapping

Recommended mapping fields:

- `forecast_id`
- `review_id`
- `run_date`
- `stock_id`
- `stock_name`
- `forecast_window`
- `predicted_direction`
- `predicted_interval_low`
- `predicted_interval_high`
- `confidence`
- `source_pipeline_metadata`
- `schema_version`
- `created_at`

This mapping preserves the original forecast snapshot while allowing later
enrichment with market outcomes.

## Actual Outcome Backfill Model

The backfill layer should store:

- `actual_close`
- `actual_high`
- `actual_low`
- `actual_return`
- `actual_direction`
- `market_data_source`
- `backfill_timestamp`
- `pending_policy`
- `missing_data_policy`
- `holiday_policy`
- `suspended_trading_policy`

Recommended policy:

- if market data is missing, keep the record pending instead of guessing
- if the trading day is a holiday or suspended day, preserve the reason in the
  record
- if the outcome is later backfilled, retain the original forecast snapshot

## Evaluation Metrics

The evaluation layer may reuse the metrics already defined in AI-DEV-017:

- `direction_match`
- `interval_hit`
- `absolute_error`
- `high_forecast_error`
- `low_forecast_error`
- `confidence_bucket`
- calibration notes

The storage model should keep these metrics as derived fields, not as
replacement fields for the original forecast payload.

## Boundary with the Existing Backtest Engine

The existing backtest engine is better suited to signal or action performance
review. Prediction review is a different layer:

- backtest engine: action / signal performance
- prediction review: forecast quality and outcome tracking

Both workflows may share a common outcome loader in the future, but they should
remain separate logical layers so that forecast evaluation does not silently
become trading evaluation.

## Proposed File and Data Flow

1. `forecast.example.json`
2. `forecast_to_review_record.example.json`
3. `actual_outcome_backfill.example.json`
4. `prediction_review_storage_index.example.json`
5. `validate_prediction_review_storage_examples.py`
6. `evaluate_prediction_review_examples.py`
7. `export_prediction_review_report_summary.py`

## Future Migration Path

- **Phase A**: docs + sample records + read-only loader
- **Phase B**: read-only sample loader summary prototype
- **Phase C**: actual outcome backfill prototype
- **Phase D**: report summary export prototype
- **Phase E**: controlled DB migration with explicit approval

## Risks and Controls

- **Lookahead bias**: retain the original forecast snapshot and generation time.
- **Forecast mutation risk**: keep immutable forecast records separate from
  mutable review/enrichment records.
- **Survivorship bias**: preserve pending and incomplete outcomes, not only
  successful examples.
- **Missing outcome data**: keep explicit pending status and missing-data
  policy.
- **Schema drift**: validate sample records with a read-only checker before
  future integration.
- **Notification / production safety**: no notification path, production
  pipeline, or scheduler should depend on these examples.

## Relationship to Other Documents

- `docs/prediction_review_forecast_evaluation.md`
- `docs/schema_examples_validation.md`
- `docs/schema_registry_governance.md`

This plan is a research-only stepping stone. It does not authorize trading,
orders, notification sends, or production database usage.
