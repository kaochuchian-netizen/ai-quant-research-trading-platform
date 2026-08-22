# AI-DEV-220 — US 20:00 / 23:00 Product Continuity V2

## Repository

- Starting main: `7eb0965b0943048113a654aad1cc77b927c12e8e`
- Branch: `ai-dev/220-us-premarket-intraday-product-continuity-v3`
- Implementation commit: recorded in Git history for this report
- PR / CI / merge: recorded by the governed GitHub workflow
- Final state target: main and origin/main identical, ahead/behind 0/0, feature branch removed

## Root causes

US 20:00 had no single PM-facing product projection for direction, forecast target/range and finalized-news counts. Existing renderers exposed trading-plan metadata before forecast intelligence. This was a presentation-contract gap, not a provider or market-data gap.

US 23:00 resolved the 20:00 admitted bundle when available, but the missing-source path substituted a fresh bundle and could then evolve a hypothesis as if continuity existed. The coverage denominator also included categories whose only providers were `NOT_CONFIGURED` or `NOT_LICENSED`, explaining misleadingly low PM-facing coverage despite complete market data.

## US / TW isolation

Only market-agnostic presentation ideas are shared. New canonical projections require `market=US`, consume US cards/bundles only, never read TW artifacts, and fail validation on TW lineage injection. US symbol, calendar, timezone, provider, snapshot and research identities remain US-owned.

## US 20:00 product

`us_premarket_product_projection_v1` establishes direction, reference price, forecast target and forecast interval before rendering. The target is canonical projection data, not a renderer calculation and not an execution target. Dashboard and LINE read identical projection values.

`us_news_product_projection_v1` exposes normalized retrieved, all-gates-qualified and finalized-selected counts with invariant `selected <= qualified <= retrieved`. It preserves selected headline, publisher, time, direction status, rejection distribution and retrieval status.

## US-native news reliability

No provider or fallback was removed. Yahoo/yfinance remains the existing US-native adapter. Missing underlying publisher now preserves the normalized candidate with `publisher_resolution_status=unresolved` and an explicit discovery channel; it is not treated as transport failure. A retrieval error with usable candidates is `PARTIAL`, while a true no-candidate transport error remains `FAILED`. H3/AI-DEV-216 entity attribution and directionless contribution safety remain intact.

## US 23:00 lineage and sufficiency

`us_intraday_research_continuity_v1` carries source snapshot ID/revision, origin/current research identities, continuity state, and separate market/research/news/lineage sufficiency. Missing admitted 20:00 lineage is fail-closed as `INSUFFICIENT_SOURCE_LINEAGE`; it can no longer be presented as unchanged. Complete 6/6 market data therefore remains `Market: COMPLETE` even when another sufficiency dimension is limited.

Coverage now excludes only categories whose canonical status is missing and whose complete provider set is `NOT_CONFIGURED` / `NOT_LICENSED`. Expected-but-failed evidence stays in the denominator.

## Validation

- AI-DEV-220 dedicated: PASS, 10/10 executable cases.
- AI-DEV-216 attribution/date: PASS.
- AI-DEV-214 production-shaped provenance: PASS.
- AI-DEV-212 H3 semantic integrity: PASS.
- AI-DEV-201 US Research after denominator-contract update: PASS.
- AI-DEV-209 H2 news/RRE core cases: PASS; nested AI-DEV-210 browser check was unavailable until the isolated Chromium runtime was installed.
- Python compile: PASS.
- `git diff --check`: PASS.
- Real Chromium: desktop 1440 px and mobile 390 px PNG PASS; browser PDF PASS; CJK readable; no clipping/overflow in the primary sections.
- Full local branch registry was executed once. Environment-only failures were caused by unavailable Python-3.9 future pins (`google-genai`), missing optional `gspread`, pre-install browser runtime, and live Yahoo/SEC DNS. GitHub CI is the authoritative pinned full-registry closure.

## Safety

- Production/manual rerun: false.
- LINE/Email sent: false.
- Trading/orders: false.
- Scheduler/cron/systemd/nginx/infrastructure changed: false.
- Secrets accessed or changed: false.
- Production DB written: false.
- Immutable archive rewritten: false.
- Strategy, scoring, prediction weights, ranking, eligibility, Entry/Stop/execution Target, sizing and execution ownership: no change.

## Verification status

`IMPLEMENTED_DETERMINISTIC_QA_PASS_PENDING_CONTROLLED_VERIFICATION`

The next gate is a PM-triggered controlled US 20:00 and 23:00 product verification. No production execution was performed by this task.
