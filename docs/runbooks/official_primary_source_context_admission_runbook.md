# Official Primary Source Context Admission Runbook

## Purpose

This runbook describes the offline validation flow for AI-DEV-141 official primary source context admission. It is no external API and no production connector work.

## Inputs

Use the deterministic input template:

- `templates/official_primary_source_context_admission_input.example.json`

The template describes source families and policy intent only. It does not contain secrets, runtime credentials, raw crawler output, or local-only runtime artifacts.

## Build

Build the deterministic artifact with:

```bash
./venv/bin/python scripts/orchestrator/build_official_primary_source_context_admission_artifact.py --pretty
```

The builder is offline. It does not call external APIs, does not read `.env`, does not read production DBs, and does not activate a production connector.

## Validate

Validate the package with:

```bash
./venv/bin/python scripts/orchestrator/validate_official_primary_source_context_admission_v1.py --pretty
```

The validator checks required files, source families, admission matrix, source priority policy, official-source replacement policy, integration targets, safety policy, mutation policy, deterministic rebuild consistency, and forbidden secret-like patterns.

## Source Admission Review

Review the generated artifact before any future connector task. Confirm:

- official source families are present
- official sources can be core evidence where appropriate
- metadata-only sources cannot become core evidence
- FinMind cannot replace official sources
- yfinance / Yahoo cannot replace official sources
- Google News RSS remains event/sentiment support only
- broker target price / analyst rating is metadata only
- AI-generated analysis is not original evidence

## Runtime Boundaries

Do not run MOPS, company website, financial statement, investor conference, or IR crawlers in this task. Do not modify schedulers, production pipelines, dashboards, notification delivery, order logic, rating/action/confidence, factor weights, or production connectors.

## Future Tasks

Future AI-DEV tasks may implement connector-specific dry-runs, but each must have explicit scope, source attribution, secret handling, freshness checks, and human review before production admission.
