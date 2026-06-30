# Forecast Evidence Linking V1

## Purpose

Forecast Evidence Linking V1 defines a repo-only, fixture-only, advisory-only
contract for linking forecast records to company intelligence, industry
intelligence, source credibility metadata, and source identifiers.

The goal is explainability: each forecast should show which evidence supports
it, which evidence is official or company-linked, which evidence is industry or
peer context, which sources are lower credibility, which metadata is sentiment
only, and whether human review is required.

This contract does not enable live data access, external model calls, market
data calls, delivery, persistent store writes, portfolio actions, dashboard
deployment, API server creation, or schedule/service changes.

## Contract Identity

The result must include:

- `schema_version = forecast_evidence_linking_v1`
- `task_id = AI-DEV-090`
- `mode = fixture_dry_run`

Allowed decisions:

- `forecast_evidence_linking_completed`
- `forecast_evidence_linking_completed_with_warnings`
- `validation_failed`
- `blocked`

## Fixture Input

The input fixture is:

```text
templates/forecast_evidence_linking_input.example.json
```

It references repo-local fixture outputs only:

- `templates/company_intelligence_result.example.json`
- `templates/industry_intelligence_peer_context_result.example.json`

Referenced paths must be repo-relative. Absolute paths are rejected by the
dry-run helper.

## Result Contract

The machine-readable result fixture is:

```text
templates/forecast_evidence_linking_result.example.json
```

Required top-level fields:

- `schema_version`
- `task_id`
- `run_id`
- `generated_at`
- `mode`
- `forecast_evidence_links`
- `evidence_summary`
- `validation_summary`
- `side_effects`
- `safety`
- `ok`
- `decision`
- `next_recommendation`

Each `forecast_evidence_links` item must include:

- `forecast_id`
- `stock_id`
- `horizon`
- `source_ids`
- `company_intelligence_refs`
- `industry_intelligence_refs`
- `credibility_summary`
- `primary_evidence`
- `supporting_evidence`
- `sentiment_metadata`
- `human_review_required`
- `advisory_only`

The standalone summary fixture is:

```text
templates/forecast_evidence_summary.example.json
```

## Linking Rules

The dry-run helper links a forecast to evidence by matching forecast
`source_ids` against:

- `company_intelligence.items[].evidence_source_ids`
- `industry_intelligence.items[].evidence_source_ids`
- `peer_context.items[].evidence_source_ids`
- `source_credibility_scores[].source_id`

Primary evidence is evidence with score or confidence greater than or equal to
the fixture policy `primary_evidence_min_credibility`. Other matched evidence is
retained as supporting evidence. Sentiment metadata is never promoted to core
forecast evidence.

Low credibility sources and review-required source metadata propagate to the
forecast-level `human_review_required` flag.

## Safety Requirements

The result must preserve:

- `repo_only: true`
- `fixture_only: true`
- `advisory_only: true`
- `preview_only: true`
- `no_external_model_calls: true`
- `no_market_data_calls: true`
- `no_delivery_actions: true`
- `no_persistent_store_writes: true`
- `no_portfolio_actions: true`
- `no_schedule_service_changes: true`
- `dashboard_deploy: false`
- `api_server_created: false`

All side-effect flags must remain false.

## Dry Run

Use:

```bash
python3 scripts/orchestrator/forecast_evidence_linking_dry_run.py \
  --input templates/forecast_evidence_linking_input.example.json \
  --output /tmp/forecast_evidence_linking_result.json \
  --summary-output /tmp/forecast_evidence_summary.json \
  --pretty
```

The helper reads fixture files only and writes deterministic JSON.

## Validation

Use:

```bash
python3 scripts/orchestrator/validate_forecast_evidence_linking_result.py \
  --input /tmp/forecast_evidence_linking_result.json \
  --pretty
```

Validation checks required fields, decisions, evidence-link shape, source
credibility summaries, advisory-only flags, side-effect flags, safety flags,
secret-like text, live runtime terms, and trading/order instruction patterns.

Validation does not approve production use, dashboard deployment, API server
creation, delivery activation, portfolio actions, or live data connections.
