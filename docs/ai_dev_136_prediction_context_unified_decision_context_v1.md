# AI-DEV-136: Prediction Context Assembly & Unified Decision Context V1

## Purpose

AI-DEV-136 establishes the deterministic, offline-verifiable Prediction Context foundation for V10 Unified Decision Intelligence. The Prediction Context is the single Unified Decision Context artifact that assembles source governance, formal report integration, market regime, rolling evaluation, confidence calibration, factor effectiveness, historical context, and explainability-ready references.

This is a context artifact, not a production decision engine.

## Scope

The foundation adds:

- `app/prediction_context/` domain package.
- deterministic input and output examples under `templates/`.
- an offline builder script.
- an offline validator script.
- this governance document and an operator runbook.

The builder uses only deterministic sample input. It performs no runtime fetch, no production DB access, and no production pipeline execution.

## Unified Context Fields

The artifact includes:

- schema_version
- task_id
- generated_at
- symbol
- market
- context_window
- source_summary
- source_credibility_summary
- formal_report_integrations
- technical_context
- chip_context
- adr_context
- news_context
- finmind_context
- twse_context
- yfinance_context
- historical_context
- rolling_evaluation_context
- market_regime_context
- confidence_calibration_context
- factor_effectiveness_context
- explainability_context
- warnings
- exclusions
- safety_policy

## Formal Report Integrations

The artifact references existing formal report foundations:

- FinMind report integration artifact: `templates/finmind_report_integration_artifact.example.json`
- TWSE report integration artifact: `templates/twse_yfinance_report_integration_artifact.example.json`
- yfinance/Yahoo report integration artifact: `templates/twse_yfinance_report_integration_artifact.example.json`

FinMind is a normalized external data provider. TWSE is the official market/chip source. yfinance/Yahoo is an external reference proxy for ADR, US index, ETF, and sector proxy context.

## Source Summary Categories

The source summary explicitly separates:

- official_primary_source
- official_market_source
- normalized_external_data_provider
- external_reference_proxy
- ai_generated_analysis
- low_priority_metadata

This prevents lower-priority source types from silently replacing official source governance.

## Source Credibility Rules

Every source credibility row includes:

- source_id
- provider
- source_priority
- credibility_level
- decision_value
- report_allowed
- prediction_context_allowed
- direct_rating_action_confidence_impact

All rows must keep `direct_rating_action_confidence_impact=false`. The artifact does not directly modify rating/action/confidence and does not change production weights.

## Exclusions

The exclusions section records:

- sources that are metadata only
- sources that must not directly influence rating/action/confidence
- sources that must not replace official sources

Broker target/rating metadata and headline/news metadata stay low-priority metadata. yfinance/Yahoo and FinMind cannot replace official TWSE, MOPS/company official, or broker runtime market sources.

## Downstream Integration

Prediction Context is the V10 Unified Decision Intelligence core foundation for future tasks:

- AI-DEV-137 explainability should read this context.
- AI-DEV-138 traceability should read this context.
- AI-DEV-139 report assembly should read this context.
- AI-DEV-140 dashboard drill-down should read this context.

This foundation does not trigger report delivery and does not publish a dashboard.

## Safety Boundary

No external API calls.
No secrets.
No DB writes.
No scheduler / cron / systemd / timer changes.
No LINE / Email / notification sending.
No dashboard publish.
No broker / order / trading.
No production pipeline execution.
No `python3 main.py` execution.
No production rating/action/confidence/weight logic changes.
No formal delivery behavior changes.

## Validation

Run:

```bash
./venv/bin/python -m py_compile app/prediction_context/*.py scripts/orchestrator/build_prediction_context_artifact.py scripts/orchestrator/validate_prediction_context_v1.py
./venv/bin/python scripts/orchestrator/validate_prediction_context_v1.py --pretty
./venv/bin/python scripts/orchestrator/build_prediction_context_artifact.py --pretty
./venv/bin/python scripts/orchestrator/validate_ai_branch.py --base main --head HEAD --pretty
git diff --check
```
