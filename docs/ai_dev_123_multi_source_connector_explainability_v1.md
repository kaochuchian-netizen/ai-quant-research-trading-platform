# AI-DEV-123 Multi-Source Connector And Explainability Foundation V1

## Purpose

AI-DEV-123 extends AI-DEV-122 by connecting source coverage to deterministic explainability. It explains why a stock is rated bullish, neutral, or bearish; which features contributed positively or negatively; which source evidence supports those features; and whether missing primary sources capped confidence.

## Scope

This is a read-only, artifact-first capability release. It adds a source connector framework, source evidence schema, endpoint registry, TWSE/TPEx/TDCC/yfinance/FinMind readiness connectors, deterministic feature attribution, stock explanation policy, artifact builder, validator, templates, and documentation.

## Non-goals

- No production trading
- No simulation order
- No production order
- No scheduler mutation
- No LINE/Email delivery
- No production DB write
- No production forecast weight mutation
- No production dashboard publish
- No AI-generated investment advice
- No automatic change to rating/action weights
- No broker login
- No secrets read
- No large AI/Gemini batch call

## Architecture

- `app/sources/schemas.py`: source endpoint, fetch request/result, evidence batch, evidence, and connector health schemas.
- `app/sources/endpoint_registry.py`: TWSE, TPEx, TDCC, yfinance, ETF, company, management interview, and FinMind registry entries.
- `app/sources/*_connector.py`: read-only offline-safe connector fixtures.
- `app/sources/evidence_normalizer.py`: deterministic normalization into `SourceEvidence`.
- `app/explainability/schemas.py`: feature contribution, attribution, stock explanation, and artifact schemas.
- `app/explainability/feature_attribution.py`: deterministic evidence-to-feature mapping.
- `app/explainability/explanation_policy.py`: policy rules for source authority, confidence caps, and cannot-raise-rating behavior.
- `app/explainability/explanation_builder.py`: stock explanation assembly.
- `scripts/orchestrator/build_source_explainability_artifact.py`: deterministic JSON artifact builder.
- `scripts/orchestrator/validate_source_explainability_v1.py`: schema, policy, safety, template, and builder validator.

## Source connector framework

The connector framework represents:

- `SourceEndpoint`
- `SourceFetchRequest`
- `SourceFetchResult`
- `SourceEvidence`
- `SourceEvidenceBatch`
- `SourceConnectorHealth`

Connectors are read-only. Connector failure returns `SourceConnectorHealth.status=unavailable` or `skipped` and a missing-source evidence item. Failure does not fail the whole artifact.

## Source evidence schema

Each evidence item includes `schema_version`, `source_id`, `provider`, `category`, `priority`, `stock_id`, `stock_name`, `event_date`, `retrieved_at`, `title`, `summary`, `raw_fields`, `normalized_fields`, `source_url`, `evidence_type`, `quality_score`, `noise_risk`, `lineage`, and `usage_policy`.

Supported evidence types include monthly revenue, material information, financial statement, investor conference, market context, chip structure, ETF reference, news event, missing source notice, institutional flow, margin/short, and market price.

## TWSE / TPEx / TDCC / yfinance source policies

TWSE monthly revenue, TWSE material information, and TWSE financial statement readiness are official or company-linked source representations. TPEx readiness and TDCC shareholding distribution are represented even when unavailable in offline samples.

yfinance remains external market context only:

- provider: `yfinance / Yahoo Finance`
- priority: `C_market_or_industry`
- noise risk: `medium`
- usage: ADR / TSM, NASDAQ, S&P 500, SOXX / SMH, VIX proxy, US yield, USD proxy
- must not replace primary source
- must not independently raise rating

## FinMind

FinMind is included as a third-party aggregated data source, coverage accelerator, fallback / cross-check reference, and research artifact input. FinMind does not replace official primary sources.

Supported datasets in V1:

- `finmind_taiwan_stock_price`
- `finmind_monthly_revenue`
- `finmind_financial_statement`
- `finmind_balance_sheet`
- `finmind_cash_flows`
- `finmind_institutional_investors_buy_sell`
- `finmind_margin_purchase_short_sale`
- `finmind_holding_shares_per`

Priority classification is `C_market_or_aggregated_data`. Credential/token policy is optional and disabled by default. Validation does not require a token, does not read secrets, and uses offline deterministic samples.

FinMind fallback/cross-check policy:

- It can accelerate source coverage and provide normalized evidence.
- If FinMind monthly revenue is available but official TWSE/MOPS monthly revenue is missing, readiness may become partial, not ready.
- If FinMind financial statement is available but official statement source is missing, one-month and three-month readiness can be partial, not ready.
- If FinMind institutional data is available, it can contribute chip explanation but cannot override official chip/source evidence.
- If FinMind conflicts with an official source, official source wins and the artifact marks `source_conflict`.
- If FinMind is unavailable, the artifact still passes and records `finmind_unavailable`.

FinMind supports future AI-DEV-124 / 125 / 126 by providing a normalized cross-check evidence layer for confidence calibration, adaptive weight recommendation research, and dashboard explanation cards without production score mutation.

## Feature attribution schema

`FeatureContribution` records `feature_id`, `feature_name`, `feature_group`, `direction`, `magnitude`, `score_impact`, `confidence_impact`, `source_ids`, `evidence_ids`, `explanation_text`, and `risk_note`.

Supported feature groups are technical, news, ADR, chip, fundamental, disclosure, industry, macro, ETF, source coverage, missing data, and market price. Supported directions are positive, negative, neutral, and not_available.

## Explanation policy

Deterministic policy examples:

- Technical score high creates positive technical contribution.
- Weak or missing technical evidence creates negative or not_available contribution.
- ADR/yfinance can support external context, but cannot independently raise rating.
- News-only evidence is metadata only and cannot raise rating alone.
- Monthly revenue primary evidence supports a fundamental explanation.
- Missing monthly revenue or financial statements can cap one-month or three-month confidence.
- Material information unavailable creates a disclosure source coverage gap, not a runtime failure.
- TDCC unavailable creates chip structure not_available, no hard failure.
- ETF missing holdings/NAV/distribution creates ETF-specific source gap.
- Partial source coverage creates a confidence cap explanation.
- Insufficient source coverage creates `explainability_status=limited_by_missing_primary_sources`.

## Missing data impact on explanation

Missing primary source evidence is represented as `missing_source_notice` and as missing-data feature contributions. Missing data can reduce readiness, cap confidence, and explain why an output is partial or limited.

## Confidence cap explanation

Confidence cap reasons are deterministic strings derived from readiness and missing primary sources. Aggregated or fallback evidence, including FinMind, can move an explanation from unavailable to partial but cannot create full primary-source readiness by itself.

## Safety boundary

AI-DEV-123 performs no broker login, simulation order, production order, LINE send, Email send, scheduler change, production DB write, secrets read, production forecast weight change, dashboard production publish, nginx/systemd/cron mutation, or large AI/Gemini batch call.

## Validation commands

```bash
./venv/bin/python -m py_compile \
  app/sources/schemas.py \
  app/sources/source_client.py \
  app/sources/endpoint_registry.py \
  app/sources/twse_openapi_connector.py \
  app/sources/tpex_openapi_connector.py \
  app/sources/tdcc_connector.py \
  app/sources/yfinance_market_context.py \
  app/sources/finmind_connector.py \
  app/sources/evidence_normalizer.py \
  app/explainability/schemas.py \
  app/explainability/feature_attribution.py \
  app/explainability/explanation_builder.py \
  app/explainability/explanation_policy.py \
  scripts/orchestrator/build_source_explainability_artifact.py \
  scripts/orchestrator/validate_source_explainability_v1.py

./venv/bin/python scripts/orchestrator/validate_source_explainability_v1.py --pretty
./venv/bin/python scripts/orchestrator/build_source_explainability_artifact.py --pretty
./venv/bin/python scripts/orchestrator/validate_ai_branch.py --base main --head HEAD --pretty
```

## Future integration

- AI-DEV-124 Confidence Calibration
- AI-DEV-125 Adaptive Weight Recommendation
- AI-DEV-126 Dashboard Intelligence
- future backtesting.py strategy signal use
