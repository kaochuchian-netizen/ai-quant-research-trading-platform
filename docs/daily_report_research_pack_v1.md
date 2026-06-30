# Daily Report Research Pack V1

## Purpose

Daily Report Research Pack V1 defines a repo-only, fixture-only, advisory-only
static research payload for a future 07:00 daily report. It combines:

- AI-DEV-075 Daily Report Forecast Review Section V1
- AI-DEV-082 Daily Report Intelligence Integration V1

This contract does not connect to live data, external model runtimes, delivery
channels, persistent stores, portfolio actions, schedule configs, service
configs, or runtime report sending.

## Fixture Input

The input fixture is:

```text
templates/daily_report_research_pack_input.example.json
```

It references repo-local fixture outputs only:

- `templates/daily_report_forecast_review_section_result.example.json`
- `templates/daily_report_intelligence_integration_result.example.json`

Referenced paths must be repo-relative. Absolute paths are rejected by the
dry-run helper.

## Result Contract

The machine-readable result fixture is:

```text
templates/daily_report_research_pack_result.example.json
```

The markdown fixture is:

```text
templates/daily_report_research_pack_markdown.example.md
```

Required top-level fields:

- `schema_version`
- `task_id`
- `run_id`
- `generated_at`
- `mode`
- `source_summary`
- `research_pack`
- `sections`
- `section_order`
- `forecast_review_summary`
- `intelligence_summary`
- `source_credibility_summary`
- `risk_and_limitations`
- `validation_summary`
- `side_effects`
- `safety`
- `ok`
- `decision`
- `next_recommendation`

Allowed decisions:

- `daily_report_research_pack_completed`
- `daily_report_research_pack_completed_with_warnings`
- `validation_failed`
- `blocked`

## Section Assembly

`sections` preserves the upstream renderable section objects from AI-DEV-075
and AI-DEV-082. `section_order` must match the assembled section ids and the
default fixture order is:

```text
forecast_review
daily_report_intelligence
```

Placement metadata, priority, render mode, markdown, machine-readable payloads,
badges, source refs, advisory-only flags, and human-review flags are preserved
from the source sections.

## Source Credibility Preservation

`source_credibility_summary` is copied from the AI-DEV-082 intelligence
integration fixture and remains a preserved metadata summary. The research pack
does not recalculate credibility scores, override source tiers, resolve
conflicts, or promote low-credibility sources into core scoring inputs.

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
python3 scripts/orchestrator/daily_report_research_pack_dry_run.py \
  --input templates/daily_report_research_pack_input.example.json \
  --output /tmp/daily_report_research_pack_result.json \
  --markdown-output /tmp/daily_report_research_pack_markdown.md \
  --pretty
```

The helper reads fixture files only and writes deterministic JSON plus
deterministic markdown.

## Validation

Use:

```bash
python3 scripts/orchestrator/validate_daily_report_research_pack_result.py \
  --input /tmp/daily_report_research_pack_result.json \
  --pretty
```

Validation checks required fields, decisions, source summary shape, section
ordering, placement metadata preservation, source refs preservation, source
credibility metadata preservation, advisory-only and human-review flags,
side-effect flags, safety flags, secret-like text, live runtime terms, and
trading/order instruction patterns.

Validation does not approve production use, scheduled report insertion,
delivery activation, portfolio actions, live data connections, or external
model runtime use.
