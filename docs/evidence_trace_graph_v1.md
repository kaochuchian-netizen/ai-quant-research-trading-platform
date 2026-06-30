# Evidence Trace Graph V1

## Purpose

Evidence Trace Graph V1 defines a repo-only, fixture-only, advisory-only graph
contract on top of Forecast Evidence Linking V1.

The graph converts `forecast_evidence_links` into deterministic nodes and edges
so each forecast can be explained through:

```text
Forecast -> Evidence -> Source -> Credibility -> Human Review
```

This contract is explanatory only. It does not enable live data access, external
model calls, market data calls, delivery, persistent store writes, portfolio
actions, dashboard deployment, API server creation, or schedule/service changes.

## Contract Identity

The result must include:

- `schema_version = evidence_trace_graph_v1`
- `task_id = AI-DEV-091`
- `mode = fixture_dry_run`

Allowed decisions:

- `evidence_trace_graph_completed`
- `evidence_trace_graph_completed_with_warnings`
- `validation_failed`
- `blocked`

## Fixture Input

The input fixture is:

```text
templates/evidence_trace_graph_input.example.json
```

It references a repo-local Forecast Evidence Linking V1 fixture:

```text
templates/forecast_evidence_linking_result.example.json
```

Referenced paths must be repo-relative. Absolute paths are rejected by the
dry-run helper.

## Result Contract

The machine-readable result fixture is:

```text
templates/evidence_trace_graph_result.example.json
```

Required top-level fields:

- `schema_version`
- `task_id`
- `run_id`
- `generated_at`
- `mode`
- `evidence_trace_graph`
- `graph_summary`
- `validation_summary`
- `side_effects`
- `safety`
- `ok`
- `decision`
- `next_recommendation`

The `evidence_trace_graph` object must include:

- `graph_id`
- `forecast_nodes`
- `evidence_nodes`
- `source_nodes`
- `credibility_nodes`
- `review_nodes`
- `edges`
- `graph_summary`

Required edge types:

- `forecast_uses_evidence`
- `evidence_refs_source`
- `source_has_credibility`
- `evidence_requires_review`
- `evidence_supports_forecast`
- `evidence_is_sentiment_metadata`

The standalone summary fixture is:

```text
templates/evidence_trace_graph_summary.example.json
```

## Graph Rules

The dry-run helper reads `forecast_evidence_links` and builds:

- one forecast node per forecast link
- one evidence node per forecast evidence reference and sentiment metadata item
- one source node per source ID observed in the forecast links
- one credibility node per scored source
- one review node per forecast requiring human review
- deterministic edges across forecast, evidence, source, credibility, and review

Evidence IDs and edge IDs are derived from forecast IDs, evidence reference
types, evidence reference IDs, source IDs, and edge type. All node and edge
collections are sorted by ID before output.

Sentiment metadata is retained as graph evidence metadata only. It is not
promoted to core forecast evidence.

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
python3 scripts/orchestrator/evidence_trace_graph_dry_run.py \
  --input templates/evidence_trace_graph_input.example.json \
  --output /tmp/evidence_trace_graph_result.json \
  --summary-output /tmp/evidence_trace_graph_summary.json \
  --pretty
```

The helper reads fixture files only and writes deterministic JSON.

## Validation

Use:

```bash
python3 scripts/orchestrator/validate_evidence_trace_graph_result.py \
  --input /tmp/evidence_trace_graph_result.json \
  --pretty
```

Validation checks required fields, graph shape, required edge types, summary
counts, advisory-only flags, side-effect flags, safety flags, secret-like text,
live runtime terms, and trading/order instruction patterns.

Validation does not approve production use, dashboard deployment, API server
creation, delivery activation, portfolio actions, or live data connections.
