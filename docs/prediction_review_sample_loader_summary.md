# Prediction Review Sample Loader and Summary

## Purpose

This document describes the research-only loader summary prototype introduced by
AI-DEV-019. The goal is to read the prediction review storage samples created in
AI-DEV-018, summarize their structure, and confirm the research-only storage
boundary without touching production systems.

This is a planning and validation aid only. It does not authorize trading,
notification delivery, dashboard publishing, database writes, or scheduler
changes.

## Sample Location

The loader reads the storage samples from:

```text
orchestrator/templates/research_samples/prediction_review_storage/
```

The bundle currently contains:

- `forecast_to_review_record.example.json`
- `actual_outcome_backfill.example.json`
- `prediction_review_storage_index.example.json`

## Loader Summary Output

The prototype summarizes:

- loaded sample count
- record ids
- lifecycle status counts
- data status counts
- backfill status counts
- pending versus completed outcome examples
- forecast / review / outcome linkage
- storage policy mode
- safety boundary notes

The summary is useful for future research-only reporting because it shows
whether the sample storage bundle is internally consistent before any future
automation or backtest integration is considered.

## Read-Only Validation

Validate and summarize the bundle with:

```bash
python3 scripts/orchestrator/summarize_prediction_review_storage_examples.py --pretty
```

The prototype is read-only. It does not:

- write files
- write databases
- modify production data
- call external APIs
- send LINE or email
- modify cron, systemd, or timers
- run production pipelines
- trade or place orders
- read secrets or credentials

## Relationship to Other Documents

- `docs/prediction_review_storage_backtest_integration_plan.md`
- `docs/prediction_review_forecast_evaluation.md`
- `docs/schema_examples_validation.md`

The sample loader summary is a research-only bridge between storage samples and
future evaluation / reporting work.
