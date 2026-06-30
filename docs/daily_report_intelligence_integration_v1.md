# Daily Report Intelligence Integration V1

## Purpose

Daily Report Intelligence Integration V1 defines a repo-only, fixture-only,
advisory-only static section contract for future insertion into the 07:00 daily
report. It combines:

- AI-DEV-076 Company Intelligence + Source Credibility V1
- AI-DEV-077 Industry Intelligence + Peer Context V1

This contract does not connect to live data, external model calls, delivery
channels, persistent stores, portfolio actions, or schedule/service changes.

## Contract Identity

The result must include:

- `contract_name = daily_report_intelligence_integration`
- `contract_version = v1`
- `schema_version = daily_report_intelligence_integration_v1`
- `mode = fixture_dry_run`

Allowed decisions:

- `daily_report_intelligence_integration_completed`
- `daily_report_intelligence_integration_completed_with_warnings`
- `validation_failed`
- `blocked`

## Fixture Input

The input fixture is:

```text
templates/daily_report_intelligence_integration_input.example.json
```

It references repo-local fixture outputs only:

- `templates/company_intelligence_result.example.json`
- `templates/industry_intelligence_peer_context_result.example.json`

Referenced paths must be repo-relative. Absolute paths are rejected by the
dry-run helper.

## Result Contract

The machine-readable result fixture is:

```text
templates/daily_report_intelligence_integration_result.example.json
```

Required top-level fields:

- `schema_version`
- `task_id`
- `run_id`
- `generated_at`
- `mode`
- `source_summary`
- `daily_report_intelligence_section`
- `company_intelligence_summary`
- `industry_peer_context_summary`
- `source_credibility_summary`
- `risk_and_limitations`
- `validation_summary`
- `side_effects`
- `safety`
- `ok`
- `decision`
- `next_recommendation`

The markdown section fixture is:

```text
templates/daily_report_intelligence_section_markdown.example.md
```

`daily_report_intelligence_section` preserves both markdown and
machine-readable payloads so a future report renderer can insert the static
section without re-reading the original fixtures.

## Source Credibility Preservation

`source_credibility_summary` preserves source metadata from AI-DEV-076 and
AI-DEV-077, including:

- source identifiers
- source tiers
- publisher metadata
- base scores
- adjustments
- final credibility scores
- core scoring eligibility
- conflict flags
- human-review flags
- usage policy

The integration layer does not recalculate source scores. It summarizes and
preserves the fixture metadata.

## Safety Requirements

The result must preserve:

- `repo_only: true`
- `fixture_only: true`
- `advisory_only: true`
- `requires_human_review: true`
- `no_external_model_calls: true`
- `no_market_data_calls: true`
- `no_delivery_actions: true`
- `no_persistent_store_writes: true`
- `no_portfolio_actions: true`
- `no_schedule_service_changes: true`

All side-effect flags must remain false. The dry run must not read secrets,
send notifications, place orders, write persistent stores, mutate schedules or
services, alter remotes, or render a runtime report.

## Dry Run

Use:

```bash
python3 scripts/orchestrator/daily_report_intelligence_integration_dry_run.py \
  --input templates/daily_report_intelligence_integration_input.example.json \
  --output /tmp/daily_report_intelligence_integration_result.json \
  --markdown-output /tmp/daily_report_intelligence_section_markdown.md \
  --pretty
```

The helper reads fixture files only and writes deterministic JSON plus
deterministic markdown.

## Validation

Use:

```bash
python3 scripts/orchestrator/validate_daily_report_intelligence_integration_result.py \
  --input /tmp/daily_report_intelligence_integration_result.json \
  --pretty
```

Validation checks required fields, decisions, source summary shape, section
shape, source credibility metadata preservation, advisory-only and human-review
flags, side-effect flags, safety flags, secret-like text, live runtime terms,
and trading/order instruction patterns.

Validation does not approve production use, scheduled report insertion, delivery
activation, portfolio actions, or live data connections.
