# AI-DEV-209 — 2026-08-12 Natural Research/News Root-Cause Audit

This audit is read-only. The TW 15:00 and US 20:00 snapshots are pre-fix evidence and were neither rewritten nor replayed as post-fix verification.

## US 20:00

The natural artifact persisted six symbols, zero normalized news items, zero RRE news items, and zero rendered news items. It did not persist provider raw counts, retrieval exceptions, parser rejects, or attribution rejects; those historical stages are therefore `UNKNOWN_NOT_PERSISTED`, not zero.

The production adapter had two deterministic defects:

1. `ticker.news` exceptions were converted to `[]`, making retrieval failure indistinguishable from a genuine no-result response.
2. The parser read legacy top-level `title`, `publisher`, and `providerPublishTime`. A controlled read-only provider-shape probe returned 10 items per watchlist symbol under nested `content.*`; the legacy parser accepted 0/10 for every symbol. The corrected parser admitted 2 AAPL, 5 AMD, 2 GOOGL, 4 META, 4 NVDA, and 9 TSLA items after explicit entity attribution. This probe confirms the payload mismatch; it is not natural verification of the fix.

SEC filings were available through the independent official SEC path and were correctly not presented as live news.

## TW 15:00

The immutable snapshot contained five legacy news records per symbol (45 total), while all nine Research conclusions were `insufficient_evidence`. This was not simply an overly strict directional gate:

- the RRE correctly had zero directional supporting/opposing news;
- legacy compatibility projection could treat old card evidence as admitted current evidence;
- several visible records were materially stale (for example 6873 on 2026-02-10 and 1409 on 2026-06-04);
- compatibility lower-bound telemetry populated upstream stages without rechecking the current 72-hour window.

The quality gate correctly refused to invent a bullish/bearish conclusion from directionless evidence, but the stale evidence visibility and funnel semantics were incorrect. Historical discovery, HTTP, parser and pre-card dedupe counts were not persisted and remain `UNKNOWN_NOT_PERSISTED`.

## Coverage parity

The US natural summary carried both a legacy simple ten-category average (50.0%) and effective weighted V2 coverage (57.95%). LINE used the former while Research cards used the latter. AI-DEV-209 makes effective weighted applicable-category coverage the canonical Dashboard/LINE denominator while retaining the legacy value under an explicitly legacy field.

## Remediation contract

- Exact twelve-stage provider telemetry for new US fetches.
- Separate retrieval failure, no relevant news, filtered, stale-only, admitted-not-selected, selected-not-rendered and rendered states.
- Current nested and legacy provider-shape parsing.
- Per-item entity attribution and 72-hour freshness admission.
- Directionless qualified evidence remains visible and cannot create bullish/bearish direction.
- TW legacy stale evidence remains diagnosable but cannot re-enter current RRE/rendering.
- Official, SEC, IR and company newsroom sources remain ahead of recognized financial media in source policy.
- Decision and trading ownership are unchanged.
