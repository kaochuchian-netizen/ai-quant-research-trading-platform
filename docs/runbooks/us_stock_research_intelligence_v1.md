# AI-DEV-172 US Stock Research Intelligence V1

## Purpose

AI-DEV-172 upgrades the US live runtime from quote/technical/prediction output into a research-intelligence report. It adds SEC filing metadata, fundamentals references, earnings/guidance separation, official source registry, material news classification, bilingual reading support, deterministic research factors, event-adjusted prediction, and review attribution readiness.

## Source Hierarchy

Tier 1 official/company/regulatory evidence:

- SEC EDGAR
- Company investor relations
- Company newsroom
- Company-filed 10-K / 10-Q / 8-K / 20-F / 6-K metadata

Tier 2 market/reference evidence:

- yfinance/Yahoo market and reference data
- Public benchmark proxies such as SPY, QQQ, VIX, SOXX

Tier 3 secondary evidence:

- Secondary headline metadata
- News/event classification

Market reference is never presented as official company disclosure.

## SEC EDGAR Behavior

The SEC client maps ticker to CIK through SEC company tickers, then fetches submissions metadata. It stores only structured metadata:

- form
- filing date
- reporting period
- accession
- filing URL/reference
- latest annual/quarterly filing metadata
- recent 8-K metadata

It does not store full filings, transcripts, or full copyrighted text.

## Fundamentals Methodology

V1 uses official SEC metadata plus yfinance reference fundamentals where available. Each metric carries value, currency, period, source, official-source flag, data quality, missing reason, and provenance. Missing metrics remain explicit.

Metrics include revenue, revenue growth, gross/operating margin, net income, EPS, operating cash flow, free cash flow, cash, debt, leverage, and shares outstanding where available.

## Earnings And Guidance

The runtime separates:

- company-reported or reference actuals
- company guidance
- third-party analyst consensus
- next earnings calendar reference

Verified company guidance remains unavailable unless a validated company source exists. It is not inferred from price action.

## Bilingual Reading Format

Material news items include English headline, Traditional Chinese translation/summary, headline-only flag, vocabulary, usage note, example sentence, investment reading, source tier, and provenance. Full articles are not copied.

## Research Factors

The deterministic research factor engine includes:

- earnings_quality
- growth_momentum
- margin_quality
- cash_flow_quality
- balance_sheet_strength
- guidance_direction
- official_event_signal
- news_event_signal
- market_environment
- technical_state
- volatility_risk

The version is `us_research_factor_v1`. Research factors affect US rating/action/confidence through `us_scoring_research_integrated_v1`; TW factors and chip fields are not used.

## Prediction Integration

US prediction remains deterministic. Event risk from earnings proximity or material events may widen range and lower confidence. Prediction output includes:

- event_adjusted
- event_risk_type
- research_factor_version
- deterministic rationale

No LLM-only numeric prediction is allowed.

## Review Attribution

06:30 review keeps deterministic metrics authoritative and adds readiness for attribution across technical, market, official-event, news, and data-quality causes. Missing prior snapshots or actual outcomes remain pending.

## Dashboard / Email / LINE

US Dashboard adds sections for Market Summary, Financial Quality, Earnings/Guidance, SEC/Official Events, Material News & Bilingual Reading, Prediction/Review, and per-stock research summaries.

Email full report includes research summaries and Dashboard link. LINE remains concise reminder-only and does not carry full financial/news tables.

## Copyright And Safety

- No full filings
- No full transcripts
- No full copyrighted articles
- No fabricated guidance, financials, or news
- No unscheduled Email/LINE validation sends
- No `python3 main.py`
- No trading/order execution
- No TW scheduler/formula/delivery changes

## Validation

```bash
./venv/bin/python scripts/orchestrator/validate_us_stock_research_intelligence_v1.py --pretty
./venv/bin/python scripts/orchestrator/validate_us_stock_live_data_prediction_review_runtime_v1.py --pretty
./venv/bin/python scripts/orchestrator/validate_us_stock_production_runtime_activation_v1.py --pretty
./venv/bin/python scripts/orchestrator/validate_multi_market_dashboard_v2_us_link_isolation_v1.py --pretty
```

After controlled publish:

```bash
./venv/bin/python scripts/orchestrator/validate_us_stock_research_intelligence_v1.py --pretty --require-public
```

## Rollback

Revert the AI-DEV-172 merge commit and republish the previous US Dashboard from the latest Dashboard rollback backup. Runtime artifacts are not committed to Git.
