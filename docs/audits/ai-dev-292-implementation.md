# AI-DEV-292 — dynamic batch universe and substantive news evidence

Status: IMPLEMENTED_PENDING_NATURAL_VERIFICATION. Isolated implementation only; no production replay, notification, deployment or merge.

## Root cause and immutable reference

US Google RSS previously used a six-company query map. Metadata admission was also sufficient for material news and event-range adjustment even without article content. The new acquisition gate separates discovery/ADMITTED from INVESTMENT_USABLE and prevents headline-only or unverified content entering new research and predictions.

The six missing US 20:00 trade plans on 2026-10-30 were risk-gate decisions, not a missing Entry/Stop/Target renderer:

| Symbol | Existing blocking reasons | RR |
|---|---|---|
| AAPL | RR_BELOW_THRESHOLD, DIRECTION_NOT_BULLISH, SETUP_NOT_STABILIZED | 0.35 |
| NVDA | DIRECTION_NOT_BULLISH | 1.32 |
| TSLA | RR_BELOW_THRESHOLD | 0.88 |
| GOOGL | DIRECTION_NOT_BULLISH | 1.32 |
| SPCX | RR_BELOW_THRESHOLD, DIRECTION_NOT_BULLISH, SETUP_NOT_STABILIZED | 0.35 |
| TSM | DIRECTION_NOT_BULLISH | 1.47 |

These symbols are historical evidence, never a runtime watchlist. The original observation zones remain distinct from formal trade plans. Shared Chinese explanations now expose the existing gates in Dashboard, Email and LINE. Price/ATR/gap diagnostics preserve the original calculation base and thresholds; no artificial plans or price rebasing.

Evidence: `ai-dev-292-historical-plan-evidence.json`, extracted read-only from `artifacts/archive/window_snapshots/us/us_pre_market_2000/2026-10-30/revision-0001.json`; snapshot ID `c60cf1c10aaead2e2b2633649f468d041f418b4d01ab7ffe071bbdda411baac8`; file SHA256 `40911f07a79901d8c0be472f4c2c73debd2951532ab51638454e4a12609a908f`.

## Universe contract

The existing spreadsheet readers remain authoritative: first worksheet for TW, 工作表2 for US. Existing symbol/name headers and optional activation columns remain supported. Blank/missing activation retains the existing enabled default; recognized false/disabled values disable; unknown values and explicit wrong markets fail closed. Conflicting duplicate symbols are rejected. The batch freezes enabled entries, names/English names/aliases/industry, source provenance, ordered symbols and a content hash. New prediction snapshots and runtime artifacts carry this identity. Archive and canonical presentation reject universe mismatch.

TW's admitted immutable snapshot fallback remains bounded by existing age/hash/admission governance for source unavailability. Invalid activation, explicit wrong market, invalid symbol, conflicting duplicate and deliberate empty effective universe are not reinterpreted as outages. Existing schema-unavailability fallback remains explicitly degraded. No constant stock fallback is added. US source failures remain failures. Historical universe reconstruction uses only immutable snapshot members, never the current spreadsheet. Missing historical company names do not authorize name-based acquisition.

## Content and investment usability

Dynamic search uses frozen company identities; overlapping names/aliases are excluded. US Yahoo discovery and Google RSS (including the CNYES source query) feed a shared, bounded publisher-content retriever. TW retains its existing content/relevance gate and gains the frozen company identity for query construction and ambiguity rejection.

Publisher retrieval uses existing DNS-pinned public-address transport, HTTPS allowlists, robots permission/crawl rate, request/time/size limits, explicit redirects, HTML/JSON-LD article extraction, and publication/update timestamps. It does not bypass access controls. Full bodies are ephemeral; evidence retains bounded factual excerpts, source/time, content hash and locators. At least two attributable factual event sentences are required. Title-only, insufficient, uncertain, wrong-company, access-restricted and post-as_of content cannot be investment usable. Chinese summaries and interpretation remain conservative and do not invent a price direction. Existing official-source/SEC priority is retained. New prediction news adjustment requires qualified article evidence.

The read-only public source probe in the `source_probe` section of `ai-dev-292-historical-plan-evidence.json` obtained 806 characters and publication metadata from CNYES. The Yahoo index probe exceeded the response-size bound and was rejected; it is not evidence of article coverage or an all-provider failure. No claim of exhaustive source coverage is made. All six historical cards lacked saved article evidence; their old funnel counts cannot prove the new gate and were not retroactively upgraded. Current fetches are explicitly barred from reconstructing older batch content.

## Validation and remaining boundaries

The regression suite includes new/disabled/removed symbols, TW/US market validation, boolean false and unknown activation, name collisions, immutable history, universe parity, title-only and wrong-company rejection, factual content/metadata extraction, source/robots/HTTP failure, no unsupported news prediction adjustment, and six historical gate explanations across Dashboard/Email/LINE. AI-DEV-283 through 292: 180 tests PASS in an isolated test process using CI-default umask 022; AI-DEV-292 contributes 24 tests. The existing TW cache validator also passes all 16 checks. The full AI Dev Validation workflow remains required; CI includes AI-DEV-292. A new US natural post-close review resolves and hash-checks exactly one same-session pre-market origin before any current Sheet or market-data call; missing or ambiguous origins fail closed.

No production artifact, spreadsheet data, schedule, credential, database or transport delivery was changed. LINE quota remains BLOCKED_BY_QUOTA (200/200, remaining 0, supplied constraint; no quota-bypass action). Real acquisition coverage and formal notification delivery require later authorized natural-batch verification. Mock tests are not formal delivery evidence.
