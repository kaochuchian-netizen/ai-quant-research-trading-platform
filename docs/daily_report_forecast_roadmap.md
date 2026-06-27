# Daily Report Forecast Roadmap

## Purpose

This document defines the research-only roadmap for future daily report,
forecast, prediction review, Dashboard, Email, and LINE reminder integration.
It extends the existing V6 roadmap, prediction review lifecycle, schema
examples, source credibility taxonomy, and dashboard/email data requirements.

This stage is documentation, template, and validator work only. It makes no
production pipeline changes and does not enable report generation, notification
sending, database writes, scheduler changes, trading, order placement, or
personalized financial advice.

## 07:00 Pre-Open Report Scope

The future 07:00 pre-open report should summarize research state before the
Taiwan market opens. It may include:

- stock universe and report window metadata
- prior-day market and company event context
- technical, chip, ADR, news, company, and industry evidence summaries
- same-day high/low interval forecast with confidence and uncertainty
- next-day high/low interval forecast where evidence is sufficient
- one-month and three-month trend scenarios for research review
- risk flags, missing-data flags, and human-review requirements
- links to source records, forecast records, and prediction review due dates

The 07:00 report is not an order instruction, order recommendation, or
personalized financial advice. It must not place orders, route orders, or expose
an execution path.

## 15:00 And Post-Close Review Scope

The future 15:00 and post-close review should compare prior forecasts with
actual market outcomes and newly available evidence. It may include:

- same-day actual high, low, close, and direction
- interval coverage for same-day high/low forecasts
- next-day review status when the evaluation window has closed
- direction hit/miss and range error metrics
- confidence calibration by horizon and confidence bucket
- evidence-quality changes since the forecast was created
- lessons for prompt, model, source, and schema improvement

Prediction reviews must preserve the original forecast snapshot. The original
forecast must not be edited to match later outcomes.

## Forecast Horizons

The daily report contract must support these required horizons:

| Horizon | Purpose | Review Window |
| --- | --- | --- |
| `same_day_high_low` | Same trading day high/low interval forecast. | 15:00 or post-close when market data is complete. |
| `next_day_high_low` | Next trading day high/low interval forecast. | Next post-close or later if market data is missing. |
| `one_month_trend` | One-month directional or categorical trend forecast. | After the 1M review window closes. |
| `three_month_trend` | Three-month directional or categorical trend forecast. | After the 3M review window closes. |

Each horizon must include a forecast target, confidence, interval bounds or
categorical trend state, evidence sources, review due date, and missing-data
policy before it can be displayed in Dashboard, Email, or LINE reminder output.

## Output Channels

Future output channels are:

- `dashboard`: reviewable operator UI payloads and forecast status views
- `email`: draft report payloads only until a separate approved sender exists
- `LINE reminder`: reminder-only summary that points the operator to the report

LINE reminder only means LINE must not carry order instructions, execution
commands, personalized financial advice, or an approval shortcut. This roadmap
does not authorize LINE, Email, or other notification sending.

## Evidence Policy

Forecasts and daily reports must be source-grounded and auditable. Source
priority is:

1. company official material information
2. financial reports
3. earnings calls
4. annual and monthly revenue reports
5. official press releases
6. management interviews
7. company guidance
8. upstream/downstream industry information
9. peer financial reports and primary industry supply/demand evidence
10. reputable market data and news context

Analyst target price, broker ratings, upgrades, downgrades, and consensus
metadata are low-priority sentiment metadata only. Analyst target price is low-priority sentiment metadata
and never a core decision basis, forecast basis, ranking basis, order basis, or
recommendation basis.

Evidence records must include source tier, publisher, published/retrieved time
where available, excerpt policy, data-quality flags, and missing-data policy.
Conflicting sources require explicit review flags.

## Uncertainty, Confidence, And Interval Policy

Uncertainty/confidence is required for every forecast horizon. Forecasts must
avoid single-point certainty and should prefer:

- interval bounds for high/low forecasts
- base, bull, and bear scenario notes where useful
- confidence values or buckets tied to source quality
- explicit missing-data and stale-data caveats
- invalidation conditions that would require a forecast update

Interval forecasts must include lower bound, upper bound, unit, confidence, and
evidence basis. If the interval cannot be supported by traceable evidence, the
forecast should be omitted or marked `review_required` instead of guessed.

## Prediction Review Lifecycle

The lifecycle follows the existing prediction review documents:

1. `forecast_created`: a forecast snapshot is created with horizon, interval or
   trend value, confidence, model/prompt metadata, evidence, and review due
   date.
2. `review_pending`: actual outcome fields remain explicit nulls or pending
   placeholders until the evaluation window closes.
3. `outcome_collected`: actual high, low, close, direction, trend state, or
   source evidence is collected from traceable sources.
4. `evaluation_completed`: hit metrics, interval coverage, error metrics, and
   evidence-quality metrics are calculated.
5. `lessons_recorded`: calibration, evidence drift, false positives, false
   negatives, model/prompt changes, and schema notes are recorded.
6. `archived_for_research`: the forecast and review remain queryable for
   dashboard, email draft, and backtest comparison research.

Review lifecycle records must stay separate from trading execution and from the
runtime task queue.

## Data Source Priority

Data source priority should match the source credibility taxonomy:

- Tier 1 official filing and company official communication are primary.
- Tier 2 peer, industry, and attributed management sources support context.
- Tier 3 market data and reputable news provide quantitative or contextual
  confirmation.
- Tier 4 consensus and analyst material is sentiment metadata only.
- Tier 5 unverified or social material is excluded from core report logic.

When a lower-priority source cites an official filing, the official filing
should be used directly where possible.

## Non-Goals And Safety Boundaries

This roadmap explicitly does not authorize:

- no orders
- no order instructions
- no trading execution
- no production pipeline changes
- no production database writes
- no cron, systemd, or timer changes
- no LINE, Email, or notification sending
- no runtime queue mutation
- no Dify or n8n runtime activation
- no secrets, tokens, API keys, credentials, or `.env` handling
- no personalized financial advice
- no automatic PR merge or production approval

The work is research-only. Future output must preserve `research_only`,
`no_trading_instruction`, and `no_order_execution` controls.

## Phased Implementation Plan

1. **Stage 1: roadmap and contract**
   - add this roadmap
   - add daily report forecast and review result examples
   - add a read-only validator
2. **Stage 2: schema alignment**
   - align examples with the schema registry and prediction review storage
   - define archive and report metadata linkage
3. **Stage 3: read-only preview generator**
   - generate local preview payloads from sample data only
   - do not send dashboard, email, or LINE output
4. **Stage 4: evaluation and monitoring prototype**
   - compute hit metrics, interval coverage, error metrics, and calibration
   - keep outputs read-only and separate from production pipelines
5. **Stage 5: reviewed channel adapters**
   - separately review dashboard, email draft, and LINE reminder adapters
   - keep notification sending disabled until explicitly approved
6. **Stage 6: production gate design**
   - define human approval, monitoring, rollback, and audit requirements before
     any production use


## AI-DEV-045 Dry-Run Generator Stage

AI-DEV-045 adds a deterministic daily report forecast dry-run generator as a
contract verification layer between the roadmap contract and any future channel
or production integration. The generator reads
`templates/daily_report_forecast_contract.example.json` and emits a synthetic
`pre_open_0700` payload that can be validated before any Dashboard, Email, LINE
reminder, Dify, n8n, or production pipeline work is considered.

The generator is dry-run only. It does not read production databases, does not
call external APIs, does not require secrets or credentials, does not send LINE
or Email, does not mutate the runtime queue, and does not change cron, systemd,
timers, trading, order, or production pipeline behavior.

Operator commands:

```bash
python3 scripts/orchestrator/generate_daily_report_forecast_dry_run.py --pretty
python3 scripts/orchestrator/generate_daily_report_forecast_dry_run.py --pretty --output /tmp/daily_report_forecast_dry_run_output.json
python3 scripts/orchestrator/validate_daily_report_forecast_dry_run.py --pretty
```

The generated payload may be used in future AI-DEV tasks as draft input for
Dashboard, Email, LINE reminder shape checks, or Dify/n8n draft workflows.
AI-DEV-045 itself does not call Dify or n8n and does not activate any delivery
channel. Future production pipeline integration requires a separate reviewed
task, explicit validation, and human approval.


## AI-DEV-046 Dify n8n Draft Integration Package

AI-DEV-046 connects the AI-DEV-045 dry-run JSON contract to repo-only Dify and
n8n draft integration templates. It adds Dify input/output contracts, a
sanitized n8n manual-trigger workflow template, a ChatGPT review package
example, and a validator. This is still a contract verification and draft
handoff layer only.

AI-DEV-046 does not start n8n, does not call Dify runtime, does not use API keys
or tokens, does not send LINE or Email, does not write production databases,
does not mutate runtime queue, and does not change cron, systemd, timers,
trading, order, or production pipeline behavior.

AI-DEV-047 is the earliest task that may request a separately approved
controlled runtime dry-run. Until then, the n8n template remains a sanitized repo
artifact, the Dify contracts remain examples, and all channel output remains
review-only.

## AI-DEV-047 Runtime Readiness Finding

AI-DEV-047 attempted the first controlled runtime dry-run for the Dify/n8n daily
report draft path. The result confirmed that the repo contracts and local
readiness outputs are valid, but the runtime does not yet expose a
daily-report-specific n8n workflow or Dify daily-report app/input mapping.

The safe fallback result is now part of the roadmap evidence. AI-DEV-048 should
focus on the missing runtime setup: create or safely import the manual-trigger
daily-report workflow, map AI-DEV-045 input into the Dify contract, keep
notification nodes disabled, and require explicit approval before any credential
use.

## Validation, Backtest, And Monitoring Plan

Validation should check:

- docs and templates exist
- JSON examples parse
- required keys and horizons exist
- `research_only`, `no_trading_instruction`, and `no_order_execution` exist
- review lifecycle and evaluation metrics are documented
- secret-like values are absent
- docs state no orders, no production pipeline changes, LINE reminder only,
  uncertainty/confidence required, and analyst metadata restrictions

Backtest and monitoring work must remain separate from trading execution.
Future research may compare forecast records with historical outcomes, but that
must not silently become an order strategy, live signal executor, or production
ranking mutation.

Monitoring should track schema drift, missing data, stale evidence, confidence
calibration, interval coverage, error distributions, review backlog age, and
records blocked by evidence policy.

## Related Documents

- `docs/roadmap_v6_reconciliation.md`
- `docs/prediction_review_forecast_evaluation.md`
- `docs/prediction_review_storage_backtest_integration_plan.md`
- `docs/dashboard_email_data_requirements.md`
- `docs/investment_data_schemas.md`
- `docs/source_credibility_taxonomy.md`
- `docs/schema_examples_validation.md`
