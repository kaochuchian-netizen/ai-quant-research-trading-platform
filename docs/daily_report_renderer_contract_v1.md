# Daily Report Renderer Contract V1

## Purpose

Daily Report Renderer Contract V1 defines a repo-only, fixture-only,
advisory-only static renderer payload for a future 07:00 daily report. It
converts:

- AI-DEV-083 Daily Report Research Pack V1

into ordered report sections, a machine-readable render payload, and static
Markdown. This contract does not connect to live data, external model runtimes,
delivery channels, persistent stores, portfolio actions, schedule configs,
service configs, or production report sending.

## Fixture Input

The input fixture is:

```text
templates/daily_report_renderer_input.example.json
```

It references repo-local fixture output only:

```text
templates/daily_report_research_pack_result.example.json
```

Referenced paths must be repo-relative. Absolute paths are rejected by the
dry-run helper.

## Result Contract

The machine-readable result fixture is:

```text
templates/daily_report_renderer_result.example.json
```

The Markdown fixture is:

```text
templates/daily_report_markdown.example.md
```

Required top-level fields:

- `schema_version`
- `task_id`
- `run_id`
- `generated_at`
- `mode`
- `source_summary`
- `render_payload`
- `report_title`
- `report_date`
- `report_sections`
- `markdown`
- `section_order`
- `risk_and_limitations`
- `validation_summary`
- `side_effects`
- `safety`
- `ok`
- `decision`
- `next_recommendation`

Allowed decisions:

- `daily_report_renderer_completed`
- `daily_report_renderer_completed_with_warnings`
- `validation_failed`
- `blocked`

## Section Rendering

`report_sections` is assembled from the AI-DEV-083 `sections` list. The default
fixture order is:

```text
forecast_review
daily_report_intelligence
```

Each rendered section must include:

- `section_id`
- `title`
- `placement`
- `priority`
- `source_refs`
- `advisory_only`
- `requires_human_review`

The renderer preserves upstream Markdown, machine-readable payloads, badges,
source refs, source credibility metadata, advisory-only warnings, and
human-review warnings. Placement is rewritten to deterministic report-body
slots such as `body_01` and `body_02`, while `source_placement` preserves the
upstream research-pack placement.

## Render Payload

`render_payload` is the machine-readable report contract for future delivery
work. It includes report title, report date, section order, section metadata,
source credibility summary, source refs, and safety flags. It is not a delivery
request and does not authorize sending a report.

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
services, alter remotes, or send a production daily report.

## Dry Run

Use:

```bash
python3 scripts/orchestrator/daily_report_renderer_dry_run.py \
  --input templates/daily_report_renderer_input.example.json \
  --output /tmp/daily_report_renderer_result.json \
  --markdown-output /tmp/daily_report_markdown.md \
  --pretty
```

The helper reads fixture files only and writes deterministic JSON plus
deterministic Markdown.

## Validation

Use:

```bash
python3 scripts/orchestrator/validate_daily_report_renderer_result.py \
  --input /tmp/daily_report_renderer_result.json \
  --pretty
```

Validation checks required fields, decision values, source summary shape,
render payload shape, report section metadata, section ordering, source refs,
source credibility metadata preservation, advisory-only and human-review flags,
side-effect flags, safety flags, secret-like text, live runtime terms, and
trading/order instruction patterns.

Validation does not approve production use, scheduled report insertion,
delivery activation, portfolio actions, live data connections, or external
model runtime use.
