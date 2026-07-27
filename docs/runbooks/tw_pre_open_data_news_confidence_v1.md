# TW 07:00 Technical History, News Evidence and Confidence V1

## Root cause matrix

- Historical fetch requested 180 days but `bounded_kbars_date_window` truncated it to 30 calendar days. Around the 2026-07-27 run this produced 19 trading rows for all nine symbols.
- The tactical limited-history branch returned `neutral`; the presentation therefore rendered `盤整` even though MA20/trend confirmation was unavailable.
- Technical coverage counted any non-empty summary text, so the fallback word `盤整` became a false 9/9 coverage claim.
- News prose was accepted without headline, publisher, timestamp or source identity. Confidence was not produced and provider-attempt diagnostics were absent.
- Chase risk defaulted to low from daily technical indicators even when Gap, pre-open price and event evidence were unavailable.

## Technical history and fallback

The primary Shioaji K-bars query retains the requested 180-day bounded window. Each card records row count, required count (20), start/end, source, eligibility and direction. Fewer than 20 rows is ineligible and direction is `unavailable`, never neutral. Existing canonical CSV remains the governed fallback; its source and row count are explicit. A future network fallback may be added only through an admitted provider adapter with source timestamp and fallback evidence. Fixtures and unlabelled mixed data are forbidden.

## Coverage and confidence

Coverage separates quote availability, sufficient history and confirmed trend. Market confidence is a producer-side weighted aggregate of technical history, overnight/ADR, chip, news, Gap and event-risk coverage. Renderers consume the score, level, components and reason codes without recomputation.

## News retrieval and source quality

The canonical contract records a 72-hour lookback, attempted sources (MOPS, TWSE, company IR and financial media), successes/failures, raw/deduped/admitted counts and timestamps. Evidence is admitted only when headline, publisher, publish time and URL/source ID are traceable. Official sources rank first, followed by professional/industry sources, general media and low-quality unverified sources. Low-quality-only results cannot change strategy ranking.

Source quality values are `high`, `medium_high`, `medium`, `low`, and `not_applicable`. No admitted news uses `not_applicable`, not an invented confidence or publisher. Available direction requires a confidence score and level with source, freshness, consistency, relevance, materiality and official-confirmation components.

## Chase risk, freshness and gaps

Missing Gap or event evidence makes chase risk `unavailable`; daily technical indicators cannot silently establish low pre-open chase risk. Every card records technical, ADR, news, chip, Gap and event timestamps plus typed data-gap reason codes. Public cards localize those codes and never render an empty freshness section.

## Channel parity and compact presentation

Dashboard, Archive, Email, LINE and Operations consume the same structured cards and aggregate. The primary card shows one consolidated decision reason, one compact news state and one collapsible freshness/gap section. Raw provider prose and internal English reason strings are diagnostics-only.

## Controlled verification and publish

Deterministic fixtures cover insufficient history, sufficient fallback, no-news diagnostics, traceable official/general-media evidence, confidence, missing Gap and cross-channel coverage. Controlled previews use temporary targets only and never send notifications. Static publish may rebuild presentation only from resolver-selected admitted immutable snapshots after merge and all gates; it must not mutate snapshot payloads.

## Natural verification and rollback

The task remains `IMPLEMENTED_PENDING_NATURAL_VERIFICATION` until a natural TW 07:00 batch proves row counts, source evidence, coverage, confidence, chase-risk semantics and five-channel identity parity. Rollback reverts the implementation commit and republishes the prior resolver-selected presentation; immutable snapshots are never rewritten.

## Known limitations

Historical snapshots without traceable news metadata are truthfully rendered as unavailable even if they contain generated prose. Official source adapters remain subject to provider availability. Date-only technical data is presented as the prior market close rather than a fabricated intraday time.
