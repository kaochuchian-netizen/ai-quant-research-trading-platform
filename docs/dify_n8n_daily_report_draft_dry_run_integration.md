# Dify n8n Daily Report Draft Dry-Run Integration

## Purpose

AI-DEV-046 defines a repo-only integration package that connects the AI-DEV-045
daily report forecast dry-run JSON contract to future Dify and n8n draft report
workflows. The package is a contract, template, validator, and runbook layer only.
It does not start n8n, call Dify runtime, send notifications, write databases, or
change the production pipeline.

## Scope

This package covers:

- Dify input contract based on `templates/daily_report_forecast_dry_run_output.example.json`
- Dify output contract for research-only daily report drafts
- sanitized n8n manual-trigger workflow template
- ChatGPT review package template
- validator for required keys, safety flags, channel split, and secret-pattern checks
- runbook commands for local repo validation only

## Non-Goals

AI-DEV-046 does not authorize:

- n8n startup, publish, activation, or workflow import
- Dify runtime login or API calls
- use of Dify API keys, GitHub credentials, LINE tokens, SMTP credentials, or `.env`
- production database reads or writes
- cron, systemd, or timer changes
- LINE, Email, or notification sending
- trading, order placement, order routing, or personalized financial advice
- `python3 main.py`
- AI-DEV-047 runtime dry-run execution

## Input Contract

The Dify input contract must preserve the AI-DEV-045 dry-run payload shape:

- `dry_run: true`
- `research_only: true`
- `no_trading_instruction: true`
- `no_order_execution: true`
- `review_required: true`
- `report_window: pre_open_0700`
- required horizons: `same_day_high_low`, `next_day_high_low`, `one_month_trend`, `three_month_trend`
- `evidence_sources`, `confidence`, `interval_bounds`, and `risk_flags`
- `output_channels.dashboard`, `output_channels.email`, and `output_channels.line_reminder`

Dify must treat analyst target price or broker rating context as low-priority
sentiment metadata only. It must not convert analyst metadata into a core
forecast basis, ranking basis, or action basis.

## Dify Prompt Contract

A future Dify workflow should use the input payload to produce a research-only
draft report. The prompt must require:

- explicit uncertainty and confidence language
- evidence summaries tied to source tiers
- review status and review-required reminders
- Dashboard detail text for full review
- Email detail text for draft report review
- LINE reminder text as short reminder only
- no trading recommendation, no order instruction, no execution shortcut

The prompt must not ask for secrets and must not call tools or external services
from this repo package.

## Output Contract

The Dify output contract contains:

- `report_summary`
- `per_stock_summary`
- `forecast_explanation`
- `risk_summary`
- `evidence_summary`
- `confidence_disclaimer`
- `dashboard_detail_text`
- `email_detail_text`
- `line_reminder_text`
- `safety_flags`

`line_reminder_text` must be short and must not carry the full report. Dashboard
and Email are the detail-bearing channels. LINE remains reminder-only until a
separate approved notification task exists.

## n8n Manual Trigger Template

The n8n template is a sanitized example. It is not an imported runtime workflow.
The intended dry-run flow is:

1. Manual Trigger
2. Generate or load AI-DEV-045 dry-run JSON
3. Call Dify Workflow placeholder node
4. Format ChatGPT review package
5. End with review-ready JSON output

The template intentionally excludes notification nodes, production DB write
nodes, cron activation, webhook exposure, and auto-merge behavior. Credential
fields are placeholders only and must be configured later by a human operator in
n8n credential storage if AI-DEV-047 is approved.

## ChatGPT Review Package

The ChatGPT review package should include:

- input contract summary
- Dify draft summary
- safety checklist
- validation checklist
- open questions
- next step recommendation

The package is for human review. It is not a Codex execution command and not a
merge authorization.

## Safety Boundaries

AI-DEV-046 is repo-only and dry-run-only. It does not:

- start n8n
- call Dify runtime
- use API keys or tokens
- read or write secrets, credentials, or `.env`
- write production DB records
- No production database writes are allowed
- modify cron, systemd, or timers
- send LINE or Email
- No LINE or Email notification sending is allowed
- execute `python3 main.py`
- trade, place orders, route orders, or generate execution instructions
- mutate runtime queue

## AI-DEV-047 Boundary

AI-DEV-047 may only perform controlled runtime dry-run if separately approved.
That future task must re-check human approval, n8n status, Dify endpoint policy,
credential containment, no-notification policy, no-production-write policy, and
post-run cleanup. AI-DEV-046 does not grant runtime access.

## Validation

Run from the repo root:

```bash
python3 scripts/orchestrator/generate_daily_report_forecast_dry_run.py --pretty
python3 scripts/orchestrator/validate_daily_report_forecast_dry_run.py --pretty
python3 scripts/orchestrator/validate_dify_n8n_daily_report_draft_dry_run.py --pretty
python3 scripts/orchestrator/validate_n8n_dify_export_recovery.py --pretty
python3 scripts/orchestrator/inspect_ai_platform_status.py --pretty
```

All validation is read-only except normal stdout output. The generator may write
to `/tmp` only when explicitly invoked with `--output` for local dry-run testing.


## AI-DEV-047 Runtime Readiness Result

AI-DEV-047 performed the approved controlled runtime dry-run check for the daily
report draft path. n8n was started and then stopped, but a daily-report specific
n8n runtime workflow was not found or not safely listable. Because the workflow
and Dify daily-report input contract were not present at runtime, Dify runtime
was not called.

This fallback was a safe stop, not a production failure. It prevented accidental
use of an unrelated workflow, avoided credential exposure, and kept LINE, Email,
production DB writes, cron/timer changes, trading, order execution, and runtime
queue mutation out of scope.

The packaged readiness result is documented in
`docs/ai_dev_047_runtime_readiness_result.md` with the sanitized example
`templates/ai_dev_047_runtime_readiness_result.example.json`. AI-DEV-048 is the
next task that may explicitly create or safely import a daily-report n8n
manual-trigger workflow, map the Dify daily-report app/input contract, and
request credential use through a separate approval gate.
