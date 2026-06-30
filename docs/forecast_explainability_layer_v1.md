# Forecast Explainability Layer V1

## Purpose

Forecast Explainability Layer V1 defines a repo-only, fixture-only,
advisory-only contract on top of:

- Forecast Evidence Linking V1
- Evidence Trace Graph V1

The layer converts graph nodes and trace references into deterministic
human-readable explanations for each forecast. It answers why the forecast was
produced, what the main supporting signals were, which evidence was official or
company-linked, which evidence was industry context, which metadata was
sentiment-only, which sources have credibility concerns, and what needs human
review.

This contract does not enable live data access, external model calls, market
data calls, delivery, persistent store writes, portfolio actions, dashboard
deployment, API server creation, or schedule/service changes.

## Contract Identity

The result must include:

- `schema_version = forecast_explainability_layer_v1`
- `task_id = AI-DEV-092`
- `mode = fixture_dry_run`

Allowed decisions:

- `forecast_explainability_layer_completed`
- `forecast_explainability_layer_completed_with_warnings`
- `validation_failed`
- `blocked`

## Fixture Input

The input fixture is:

```text
templates/forecast_explainability_layer_input.example.json
```

It references a repo-local Evidence Trace Graph V1 fixture:

```text
templates/evidence_trace_graph_result.example.json
```

Referenced paths must be repo-relative. Absolute paths are rejected by the
dry-run helper.

## Result Contract

The machine-readable result fixture is:

```text
templates/forecast_explainability_layer_result.example.json
```

Required top-level fields:

- `schema_version`
- `task_id`
- `run_id`
- `generated_at`
- `mode`
- `forecast_explanations`
- `explainability_summary`
- `validation_summary`
- `side_effects`
- `safety`
- `ok`
- `decision`
- `next_recommendation`

Each `forecast_explanations` item must include:

- `explanation_id`
- `forecast_id`
- `stock_id`
- `horizon`
- `explanation_summary`
- `primary_reasoning`
- `supporting_reasoning`
- `official_evidence_summary`
- `industry_context_summary`
- `sentiment_metadata_summary`
- `credibility_risk_summary`
- `human_review_summary`
- `advisory_disclaimer`
- `source_trace_refs`

The standalone summary fixture is:

```text
templates/forecast_explainability_summary.example.json
```

## Explanation Rules

The dry-run helper reads `evidence_trace_graph.forecast_nodes`,
`evidence_nodes`, `source_nodes`, `credibility_nodes`, and `review_nodes`.

For each forecast:

- primary evidence becomes `primary_reasoning`
- supporting evidence becomes `supporting_reasoning`
- tier-1 or company-linked source evidence becomes `official_evidence_summary`
- industry and peer context evidence becomes `industry_context_summary`
- sentiment metadata evidence remains metadata-only
- low-credibility or review-required sources become `credibility_risk_summary`
- review nodes become `human_review_summary`
- all related forecast, evidence, source, credibility, and review node IDs are
  retained in `source_trace_refs`

All explanation collections and trace references are sorted deterministically.
The helper does not call a model runtime and does not read live market data.

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
- `trading_instruction: false`

All side-effect flags must remain false.

## Dry Run

Use:

```bash
python3 scripts/orchestrator/forecast_explainability_layer_dry_run.py \
  --input templates/forecast_explainability_layer_input.example.json \
  --output /tmp/forecast_explainability_layer_result.json \
  --summary-output /tmp/forecast_explainability_summary.json \
  --pretty
```

The helper reads fixture files only and writes deterministic JSON.

## Validation

Use:

```bash
python3 scripts/orchestrator/validate_forecast_explainability_layer_result.py \
  --input /tmp/forecast_explainability_layer_result.json \
  --pretty
```

Validation checks required fields, explanation shape, summary counts,
advisory-only flags, side-effect flags, safety flags, secret-like text, live
runtime terms, and prohibited transaction wording patterns.

Validation does not approve production use, dashboard deployment, API server
creation, delivery activation, portfolio actions, or live data connections.
