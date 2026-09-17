# TW News Content Relevance / Materiality V1

## Purpose

This release closes the gap that caused 2026-09-17 TW 07:00 news candidates to remain at `RELEVANCE_NOT_EVALUATED`.

The existing pipeline already fetched Google News RSS candidates and AI-DEV-241 fixed deterministic symbol attribution for targets such as `2330` and `3293`. The remaining blocker was upstream evidence completeness: candidate records carried title, source URL, publisher and published time, but not readable article content or deterministic relevance/materiality fields.

## Root Cause

`app.reports.tw_pre_open_quality.news_contract()` is intentionally fail-closed:

- missing `relevance` becomes `RELEVANCE_NOT_EVALUATED`
- missing `materiality` becomes `MATERIALITY_NOT_EVALUATED`
- failed symbol attribution remains rejected
- ETF targets must not consume company-specific news

The 2026-09-17 07:00 production artifacts showed `DISCOVERED=5` and `SYMBOL_ATTRIBUTED>0` for company symbols, but `RELEVANT=0`, `MATERIAL=0`, `ADMITTED=0`. That is correct behavior because the upstream `analysis.news_analysis_engine` did not provide deterministic relevance/materiality evidence.

## Implementation

`app.research.tw_news_content_relevance` adds a read-only enrichment layer:

- fetches openly accessible article pages with bounded timeout
- extracts readable article text from HTML
- refuses invalid/non-HTTP URLs
- validates the initial URL before sending a request
- follows redirects manually and validates each redirect destination before the next request
- rejects loopback, private, link-local, metadata and otherwise non-public network targets
- binds the transport to the verified public IP instead of letting the HTTP client resolve a different address
- fails closed if connection-time DNS evidence changes to an internal or unverified address
- caps redirect depth
- caps response size
- records fetch status and failure reason
- evaluates relevance and materiality with deterministic keyword rules
- preserves per-item admission or rejection evidence
- leaves fields unset when content is unavailable, so downstream remains fail-closed

No Selenium is introduced. Existing `requests` is sufficient for the V1 interface and fixture validation.

`analysis.news_analysis_engine` reports enrichment readiness separately from downstream admission. `result_count_admitted` remains `0` at this layer because actual `ADMITTED` counting is owned by `app.reports.tw_pre_open_quality.news_contract()`. The enrichment-side count is exposed as `result_count_evaluation_ready`.

## Admission Rules

An item can provide downstream `relevance/materiality` only when:

- article content is successfully extracted
- target company identity appears in title/content using canonical aliases
- content contains material business, financial, operational or market event evidence
- the target is a company, not an ETF

Otherwise it remains rejected or unevaluated:

- `ARTICLE_CONTENT_UNAVAILABLE`
- `CONTENT_SYMBOL_EVIDENCE_MISSING`
- `ETF_COMPANY_NEWS_NOT_APPLICABLE`
- `LOW_VALUE_METADATA_OR_FORUM_CONTENT`
- `NO_MATERIAL_EVENT_KEYWORD`

## ETF Policy

ETF symbols such as `00878` and `009816` are not allowed to admit company-specific news through this path. ETF-specific news must come from ETF-specific evidence such as NAV, holdings, distribution, issuer notices or ETF-specific article content.

## 2026-09-17 Diagnostic Sample

Read-only production inspection showed:

- `2330`: fetched 5, symbol-attributed 5, admitted 0, rejection `RELEVANCE_NOT_EVALUATED`
- `3293`: fetched 5, symbol-attributed 4, admitted 0, rejection `RELEVANCE_NOT_EVALUATED` and one `SYMBOL_ATTRIBUTION_FAILED`
- ETFs `009816` and `00878`: no company news admitted

After this change, candidates with accessible article content and material event evidence can become `RELEVANT`, `MATERIAL` and `ADMITTED`. Candidates without content remain fail-closed.

## Safety

This release does not:

- rerun production batches
- send LINE or Email
- write DB or Google Sheets
- modify scheduler, cron or systemd
- read or modify credentials
- change trading, rating, action or weight policy

## Validation

Run:

```bash
./venv/bin/python -m py_compile \
  app/research/tw_news_content_relevance.py \
  analysis/news_analysis_engine.py \
  scripts/orchestrator/validate_tw_news_content_relevance_materiality_v1.py

./venv/bin/python scripts/orchestrator/validate_tw_news_content_relevance_materiality_v1.py --pretty
./venv/bin/python scripts/orchestrator/validate_ai_dev_241_tw_news_attribution_line_completeness_v1.py --pretty
```
