# Schema Registry Governance

This document defines governance for the research-only investment schema
registry introduced by AI-DEV-016.

## Purpose

The schema registry is the reviewable index for investment research schema
examples. It maps each schema name to its current example payload, required
fields, intended usage, owner area, allowed future consumers, and explicitly
disallowed consumers.

The registry currently covers:

- `signal`
- `forecast`
- `report_metadata`
- `prediction_review`
- `company_intelligence`
- `industry_intelligence`
- `source_credibility`
- `dashboard_payload`
- `email_report_payload`

All entries are `research_planning_only`. The registry does not connect any
production pipeline, dashboard, email sender, LINE sender, scheduler, database
writer, trading workflow, or order execution path.

## Registry Location

The registry lives at:

```text
orchestrator/templates/schema_registry.json
```

Schema examples live at:

```text
orchestrator/templates/schemas/*.example.json
```

This keeps governance artifacts inside the existing orchestrator template area
and within the current AI-DEV validation boundary.

## Schema Lifecycle

Schema lifecycle stages:

1. `draft_example`: a JSON example defines a proposed record shape.
2. `registered_example`: the example is listed in the registry with required
   fields, optional fields, owner area, intended usage, and disallowed consumers.
3. `reviewed_contract`: a later reviewed task may add stronger JSON Schema or
   typed validation.
4. `future_integration`: downstream Dashboard, Email report, Forecast pipeline,
   or Prediction review consumers may read the schema after a separate reviewed
   implementation task.

AI-DEV-016 only establishes the `registered_example` stage.

## Versioning Policy

- `schema_version` starts at `1`.
- Increment `schema_version` only when field semantics, required fields, or
  compatibility expectations change.
- Adding optional fields does not require a version bump when older consumers can
  safely ignore the field.
- Removing or renaming a required field requires a version bump and a migration
  plan in a separate task.
- Registry `schema_version` for an entry must match the example payload
  `schema_version`.

## Required Fields Governance

Every registered schema should include these governance fields unless a later
reviewed exception is documented:

- `schema_version`
- `record_id`
- `entity_id`
- `entity_type`
- `as_of_date`
- `created_at`
- `source`
- `source_tier`
- `confidence`
- `data_quality`
- `missing_data_policy`
- `notes`

Registry `required_fields` must be present in the example JSON. The validator
also requires `source_tier`, `confidence`, `data_quality`, and
`missing_data_policy` to remain required for every registry entry.

## Source Credibility Relationship

Schema records must use the source tier taxonomy defined in:

```text
docs/source_credibility_taxonomy.md
```

Source credibility drives evidence quality and review requirements. It must not
be used to bypass missing data or human review flags.

Analyst target prices, broker ratings, upgrades, downgrades, and buy/sell calls
must remain low-priority metadata. They may support market sentiment or
consensus context only. They must not become core score components, forecast
primary basis, trading triggers, order rules, or headline decision inputs.

## Future Consumer Policy

Allowed future consumers in the registry describe possible reviewed consumers,
not active production integrations.

Future Dashboard consumers may read registry-backed records for operator
preview, filtering, source-quality display, and research status tracking.

Future Email report consumers may read registry-backed records to build payloads
and previews. This does not authorize email delivery.

Future Forecast pipeline consumers may use company and industry intelligence as
research inputs only after a separate reviewed implementation.

Future Prediction review consumers may use forecast, signal, and outcome records
to evaluate forecast quality. Reviews must preserve original assumptions.

Forecast evaluation planning is documented in:

```text
docs/prediction_review_forecast_evaluation.md
```

The read-only evaluation prototype is:

```bash
python3 scripts/orchestrator/evaluate_prediction_review_examples.py --pretty
```

## Research-Only Boundary

The schema registry and examples do not:

- Run `python3 main.py`.
- Run `scripts/run_pipeline.py pre_open --production-approved`.
- Execute `run_stock_analysis.sh`.
- Send LINE, email, or any notification.
- Modify cron, systemd, or timer configuration.
- Write production database records.
- Modify historical CSV or backtest output.
- Place trades or orders.
- Read or store secrets, tokens, passwords, credentials, or `.env` content.

Any future task that connects these schemas to production code must be reviewed
separately and must preserve explicit source, confidence, data-quality, and
missing-data policies.

## Validation

Run:

```bash
python3 scripts/orchestrator/validate_schema_examples.py --pretty
```

The validator is read-only and checks:

- Example JSON parse success.
- Required common and type-specific fields.
- Source tier, confidence, data quality, and missing data policy.
- Registry JSON parse success.
- Registry example paths exist.
- Every example is registered.
- Every registered example path exists.
- Registry required fields exist in the example.
- Registry and example `schema_version` values match.
- Registry entries remain `research_planning_only`.
- Required disallowed consumers include production pipeline, notification sender,
  trading execution, and order execution.

Validation does not run production pipelines, send notifications, modify runtime
queue state, write DB data, change schedulers, trade, place orders, or read
secrets.
