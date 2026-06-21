# Schema Examples Validation

This document describes the research-only schema examples and their read-only
validation helper.

## Purpose

AI-DEV-014 adds maintainable JSON examples for the investment data schemas
defined in:

- `docs/investment_data_schemas.md`
- `docs/source_credibility_taxonomy.md`
- `docs/dashboard_email_data_requirements.md`

The examples are planning fixtures for future Dashboard, Email report,
Prediction review, Forecast, company intelligence, and industry intelligence
work. They do not connect any production pipeline and do not authorize trading,
order placement, LINE delivery, email delivery, dashboard publishing, database
writes, or scheduler changes.

## Example Location

Examples live under the existing orchestrator template area:

```text
orchestrator/templates/schemas/
```

The directory contains:

- `signal.example.json`
- `forecast.example.json`
- `report_metadata.example.json`
- `prediction_review.example.json`
- `company_intelligence.example.json`
- `industry_intelligence.example.json`
- `source_credibility.example.json`
- `dashboard_payload.example.json`
- `email_report_payload.example.json`

This location follows the repository's existing pattern of storing reviewable
example artifacts under `orchestrator/templates/` and stays inside the current
AI branch allowed paths.

## Validator

Run the read-only validator:

```bash
python3 scripts/orchestrator/validate_schema_examples.py --pretty
```

The validator checks:

- JSON files parse successfully.
- JSON roots are objects.
- Required common fields are present.
- `schema_version` is present and an integer.
- `source_tier` is present and one of the defined taxonomy tiers.
- `confidence` is present and between `0` and `1`.
- `data_quality` is present and contains required quality fields.
- `missing_data_policy` is present.
- Type-specific fields exist for each known example file.

The validator is read-only. It does not write files, modify runtime queue state,
write databases, modify production data, call external APIs, send notifications,
trade, place orders, run production pipelines, change cron/systemd/timers, or
read secrets.

## Future Use

Future tasks may add stricter JSON Schema files or typed validators, but those
changes should remain separate and reviewed. Any production integration must
preserve source traceability, data-quality flags, missing-data policy, and the
rule that analyst target prices and broker ratings are context metadata only,
not core decision inputs.

