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

Generic article fetching still uses bounded HTTP for non-CNYES sources. CNYES production collection uses Selenium/Chrome browser automation because the search page is an infinite-scroll DOM experience and production correctness must not depend on undocumented internal JSON endpoints.

`analysis.news_analysis_engine` reports enrichment readiness separately from downstream admission. `result_count_admitted` remains `0` at this layer because actual `ADMITTED` counting is owned by `app.reports.tw_pre_open_quality.news_contract()`. The enrichment-side count is exposed as `result_count_evaluation_ready`.

## CNYES Freshness And Lazy Loading

CNYES is added as a bounded TW news source contract, not a parallel news system. Search results are collected incrementally through one Selenium browser session and then passed through the same article-content and deterministic relevance/materiality rules.

The freshness window is the current or most recent valid TW trading day plus the previous valid TW trading day. The implementation uses the repository TW market-day contract from `app.market.tw_history_admission.expected_completed_session()` and accepts the same explicit holiday set. It does not use `today - 1 day` or weekday-only logic. For example:

- Friday 2026-09-18 => `2026-09-18`, `2026-09-17`
- Monday 2026-09-21 => `2026-09-21`, previous Friday `2026-09-18`
- a non-trading execution day => most recent valid TW trading day plus the prior valid TW trading day
- a TW holiday supplied by the market-day contract => rolls back through the holiday

CNYES production architecture:

- `CNYES_SEARCH_METHOD = SELENIUM_BROWSER`
- `CNYES_LAZY_LOAD_METHOD = DOM_INCREMENTAL_SCROLL`
- `CNYES_ARTICLE_METHOD = SELENIUM_BROWSER`
- `CNYES_INTERNAL_JSON_ENDPOINT = NOT_PRODUCTION_DEPENDENCY`
- `CNYES_BROWSER_CONCURRENCY = 1`

Runtime dependency governance:

- Python Selenium is a formal production dependency declared in `requirements.txt`.
- Chrome or Chromium is an OS runtime dependency for the production VM.
- WebDriver compatibility should use Selenium's normal driver-management path when available; do not hand-download arbitrary driver binaries.
- Runtime enablement must verify Selenium package version, browser version, driver compatibility, headless launch, JavaScript execution, DOM access and clean process shutdown.
- If any required browser dependency is missing, CNYES remains fail-closed and must report `PRODUCTION_DEPENDENCY_INSTALL_REQUIRED`; it must not fall back to an undocumented internal CNYES JSON endpoint as a production dependency.

The browser flow opens `https://www.cnyes.com/search/news?keyword={symbol}`, waits for the result container, parses visible cards, scrolls incrementally, waits for result-card growth or bounded timeout, deduplicates and stops at the two-trading-day boundary. It does not scroll to the bottom of CNYES historical news.

The implementation intentionally does not use `selenium-stealth`, `undetected-chromedriver`, proxy rotation, CAPTCHA bypass, Cloudflare bypass or fingerprint spoofing. If CNYES presents a protection challenge, the source is marked `PROTECTION_BLOCKED` and remains fail-closed.

The collector is time-window bounded:

- parse each newly visible result batch
- deduplicate by canonical CNYES article URL or article ID
- retain only articles whose actual `published_at` falls inside the two-trading-day target window
- stop when the ordered stream reaches an article older than the previous target trading day
- avoid premature stop from a pinned/sponsored old article by requiring the older article to appear at the tail of a parsed batch after target-window evidence has been seen
- enforce `MAX_SCROLL_ROUNDS`, `MAX_SEARCH_RESULTS` and `MAX_SEARCH_DURATION`

Target-window articles are prioritized newest-first. Article body navigation is queued only for target-window records where content is `TITLE_ONLY`, `PARTIAL_CONTENT` or `EMPTY`. Records with `FULL_CONTENT` skip navigation, and records older than the target window never enter the body-fetch queue.

Article navigation reuses the bounded browser session rather than launching a new browser per article. Deduplication happens before navigation with identity order `article_id -> canonical_url -> normalized URL`, so the same CNYES article discovered through multiple symbols opens only once while preserving per-symbol attribution and relevance/materiality evaluation.

Full text is transient pipeline evidence for relevance/materiality and AI news analysis. The long-term artifact contract preserves source, article ID, title, published time, canonical URL, content state, analysis result, relevance/materiality and fetch metadata. It does not create an unbounded permanent CNYES article corpus.

Each CNYES collection result records:

- `target_trading_dates`
- `target_window_start`
- `target_window_end`
- `search_scroll_rounds`
- `search_results_seen`
- `within_window_results`
- `older_than_window_seen`
- `scroll_stop_reason`
- `article_fetch_required`
- `article_fetch_attempted`
- `article_fetch_success`
- `article_fetch_failed`
- `deduplicated_articles`
- `full_content_available`
- `article_navigation_required`
- `article_navigation_attempted`
- `article_navigation_success`
- `article_navigation_failed`
- `browser_timeout_count`
- `protection_blocked_count`
- `browser_crash_count`
- `usable_for_analysis_count`
- `oldest_result_seen`
- `newest_result_seen`

This makes the stop decision auditable. A normal boundary stop is reported as `TRADING_WINDOW_BOUNDARY_REACHED`.

Acceptance fixture for `2330`:

1. Initial CNYES results contain `2026-09-18` and `2026-09-17` articles.
2. Incremental loading adds another `2026-09-17` article and then a `2026-09-16` article.
3. The collector reports `TRADING_WINDOW_BOUNDARY_REACHED`.
4. Only `2026-09-18` and `2026-09-17` articles are retained.
5. Duplicate article IDs are collapsed.
6. Missing-content records enter the newest-first body-fetch queue.
7. `FULL_CONTENT` records do not fetch again.
8. The retained articles continue through deterministic relevance/materiality evaluation.

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
