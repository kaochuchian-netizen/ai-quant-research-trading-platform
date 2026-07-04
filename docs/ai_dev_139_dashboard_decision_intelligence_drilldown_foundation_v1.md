# AI-DEV-139: Dashboard Decision Intelligence Drill-down Foundation V1

## Purpose

AI-DEV-139 is the V10 Unified Decision Intelligence Dashboard drill-down foundation. It reads AI-DEV-136 Prediction Context, reads AI-DEV-137 Explainability / Evidence Trace, and reads AI-DEV-138 Report Assembly to build deterministic Dashboard-ready drill-down data structures.

This is not a Dashboard UI implementation.

## Scope

The foundation creates a deterministic Dashboard Decision Intelligence artifact with:

- dashboard page model
- summary cards
- source credibility cards
- factor rationale cards
- evidence trace cards
- formal integration cards
- market regime cards
- rolling evaluation cards
- warning cards
- exclusion cards
- metadata-only badges
- advisory-only badges
- deterministic placeholder drilldown links
- UI contract notes
- safety policy
- publish policy

## Source Inputs

The builder reads offline deterministic samples:

- `templates/prediction_context_artifact.example.json`
- `templates/unified_explainability_artifact.example.json`
- `templates/context_based_report_assembly_artifact.example.json`

It does not call external APIs, read secrets, read production DB, run a production pipeline, publish dashboard, modify Dashboard UI, or send LINE / Email.

## Dashboard Page Model

The artifact supports these pages:

- overview
- source_credibility
- factor_rationale
- evidence_trace
- formal_integrations
- market_regime
- rolling_evaluation
- warnings
- advisory_policy

## Card Model

Summary cards include symbol, report window, market regime, confidence rationale, and advisory-only status.

Source credibility cards present:

- official_primary_source
- official_market_source
- normalized_external_data_provider
- external_reference_proxy
- ai_generated_analysis
- low_priority_metadata

Factor rationale cards mirror AI-DEV-137 factor explanations and preserve allowed_usage, disallowed_usage, supporting_sources, and direct_rating_action_confidence_impact=false.

Evidence trace cards expose source_id, context_section, factor_id, explanation_id, report_block_id, dashboard_block_id, trace_summary, node_count, and edge_count.

Formal integration cards include FinMind report integration, TWSE report integration, and yfinance/Yahoo report integration.

## Warning And Exclusion Policy

The warning and exclusion cards preserve AI-DEV-137 / AI-DEV-138 policy:

- broker_target_price_metadata can only be metadata.
- google_news_rss can only be event detection / sentiment support and cannot be core forecast evidence.
- yfinance_yahoo cannot replace official sources.
- finmind cannot replace MOPS / TWSE / company official information.
- gemini_google_generative_ai is not original evidence.

This is the official-source replacement policy for Dashboard drill-down display.

## Metadata-only And Advisory-only Badges

Metadata-only badges mark broker target / analyst opinion metadata only, Google News RSS support only, and Gemini generated analysis only.

Advisory-only badges mark:

- advisory_only=true
- not_trading_advice=true
- no_order_execution=true
- no_direct_rating_action_confidence_mutation=true

## Drilldown Links

Drilldown links are deterministic placeholders such as `dashboard://symbol/2330/overview`. They are not real publish URLs.

## Publish Policy

AI-DEV-139 does not publish dashboard. It does not modify production dashboard runtime. It does not modify Dashboard UI. It does not send LINE / Email. It does not modify formal delivery behavior.

The publish policy requires:

- dashboard_ui_modified=false
- dashboard_published=false
- dashboard_runtime_modified=false
- external_notification_sent=false
- delivery_executed=false

## Future Use

A future Dashboard renderer / UI task can consume this artifact to render overview cards, source credibility drill-downs, factor rationale details, evidence trace views, formal integration panels, warning panels, and advisory-only badges.

That future task must separately approve any Dashboard UI implementation, dashboard publish, runtime modification, or delivery behavior change.

## Safety Boundary

No external API calls.
No secrets or `.env` reads.
No DB writes.
No production scheduler / cron / systemd / timer changes.
No LINE / Email / notification sending.
No dashboard publish.
No Dashboard UI changes.
No production dashboard runtime changes.
No broker / order / trading.
No `python3 main.py` execution.
No production pipeline execution.
No production rating/action/confidence/weight logic changes.
No formal delivery behavior changes.

## Validation

Run:

```bash
./venv/bin/python -m py_compile app/dashboard_intelligence/*.py scripts/orchestrator/build_dashboard_decision_intelligence_artifact.py scripts/orchestrator/validate_dashboard_decision_intelligence_v1.py
./venv/bin/python scripts/orchestrator/validate_dashboard_decision_intelligence_v1.py --pretty
./venv/bin/python scripts/orchestrator/build_dashboard_decision_intelligence_artifact.py --pretty
./venv/bin/python scripts/orchestrator/validate_ai_branch.py --base main --head HEAD --pretty
git diff --check
```
