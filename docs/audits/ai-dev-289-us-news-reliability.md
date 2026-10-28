# AI-DEV-289 — US News Reliability & Evidence Integrity

## Baseline and proven call graph

Base main: `6638343a0045b6539a34471fe73ccc9f4a2eb5ac`.
PR #367 was OPEN at branch creation; none of its TW changes are included here.
This audit establishes code wiring, not evidence of a particular Production run.
No Production commands, provider calls, database writes or notifications are used.

`approved_us_stock_delivery` → `build_live_runtime_artifact` serves retained
`us_pre_market_2000` and `us_post_close_review_0630` (also the existing, paused
2300 route, without changing its schedule). It calls `YFinanceUSClient.fetch_symbol`
→ `normalize_yfinance_news` → `USResearchIntelligenceBuilder.build_for_symbol`
→ `material_news` → `institutional_research.build_bundle` → v2 `normalize_news`
→ `_apply_current_news` → finalized presentation → Dashboard / LINE.
0630 preserves earlier research continuity and refreshes current news through the
same finalized selection contract; it does not regenerate frozen predictions.

## Confirmed defects and fixes

1. `material_news` sliced six inputs before downstream importance/freshness/event
   selection. Remove that slice and prefer canonical event identity over a truncated
   headline key. All admitted metadata survives; no new prediction algorithm.
2. `NEWS_SELECTION_LIMIT=2` also limited `_apply_current_news` research evidence.
   Separate `research_items` (all eligible unique events) from `selected_items`
   (two presentation highlights). Preserve per-item selected/not-selected reason,
   research use and rendered flags, plus exact downstream counters. The legacy
   SELECTION_LIMIT reason remains diagnostic compatibility metadata and is explicitly
   scoped PRESENTATION_ONLY; it does not reject research evidence.
3. Fixed elapsed 72-hour filtering missed sufficiently long US holiday closures.
   New `us_news_window_v1` uses the existing pinned NYSE calendar and America/New_York
   as_of. Start is the earlier of 72 elapsed UTC hours ago and previous completed
   session close, including early close and DST. Missing calendar/naive timestamp,
   future/stale publication or mismatched window remains fail-closed.
4. Successful Yahoo retrieval was distinct from coverage only implicitly. Coverage is
   now explicitly PARTIAL when candidates exist, UNKNOWN otherwise, with provider
   failure, candidate count, absent verified window cursor and source gaps. No path
   asserts COMPLETE. Candidate metadata is no longer silently truncated at 64.
5. Production adapters retain candidate/event identities; one old regression fixture
   discarded them when constructing material_news. Restore those fixture fields;
   do not weaken admission/identity gates. Identical duplicate records now retain
   exactly one admitted record rather than rejecting the original by shared ID.

No claim is made that Yahoo returns every article within the window. The current
`ticker.news` interface is provider-limited and offers no verified exhaustive date
cursor in this integration. This change validates all returned candidates, not a
promise of exhaustive acquisition. It adds no provider request loops or paid APIs.

## Source matrix

| Source | Existing actual wiring | News coverage claim |
|---|---|---|
| Yahoo / yfinance | `ticker.news` in fetch_symbol; normalized metadata, not full articles | PARTIAL/UNKNOWN; transport SUCCESS alone is not coverage |
| SEC EDGAR | Public ticker→CIK and submissions HTTP calls in SECClient.recent_filings; separate official research evidence | Filing metadata is not a replacement for fetched news; failure stays explicit |
| Company IR/newsroom | URL registry and empty item collections in official_sources | NOT_FETCHED / UNKNOWN, even when configured |

Minimal fallback design: retain separately verified SEC research evidence when
Yahoo fails, without converting registry URLs or filing dates into fabricated
news. No new SEC/IR crawler, credential, paid integration or title-only directional
model is introduced. Live source reachability and completeness remain unverified.

## Safety and research/presentation semantics

All returned news is locally date-filtered, entity-attributed, quality/materiality
checked, event-deduplicated and admitted before research selection. Existing
attribution and materiality rules are retained; STORY eligibility is not evidence
of a high-impact event. Importance ranking uses the existing v2 ranking over the
complete admitted input. No-admitted and directionless evidence cannot invent a
company investment direction. News research here is deterministic; no additional
LLM budget or API is introduced. Two highlights keep mobile/LINE bounded while all
metadata stays in evidence. Diagnostics are collapsed; machine enums in compact
source/direction wording are replaced with Chinese labels.

Counters: RETRIEVED = provider candidates; FRESH = local window pass before entity
filtering; ADMITTED = unique eligible events; RRE_USED = research retained;
RENDERED = at most two highlights. candidate_records retain rejection reasons,
original timestamps and canonical IDs. Presentation omission is not admission loss.

## Targeted validation and limitations

Synthetic-only tests cover: seventh high-materiality event after six low-ranked
items, >2 retained events, provider truncation/empty/failure, duplicates, wrong
entity, TSLA/SPCX/GOOGL, pre/post-close, long holiday/DST, unknown timestamps,
window/identity mismatch, configured-only IR, full research consumer and bounded
LINE size for 8 versus 80 candidates. No private payload or receipt is committed.

Targeted semantic validators and 393px collapsed/expanded browser checks precede
formal Linux CI. The local composite PDF/transport checks report legacy_pdf_truthful /
safe_pdf_export failures; these are not marked PASS. Browser sandbox failures were
separately resolved. Formal Linux CI must resolve the remaining gate result. CI is the final branch gate; no quarantine or bypass is added.

## Release boundary

Single PR, no merge or deployment authorized. Production compatibility, worker/
window, governance and rollback checks must be freshly performed on an approved
merge SHA; a BLOCKED/UNKNOWN check must stop deployment. CI/fixture success is not
natural batch acceptance. No DB, cron, trading, snapshots, notifications, secrets,
TW CNYES/Selenium pipeline or Production changes. AI-DEV-282 remains PAUSED.
