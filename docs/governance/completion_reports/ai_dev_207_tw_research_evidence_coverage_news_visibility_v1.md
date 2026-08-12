# AI-DEV Completion Report V2
Task ID: AI-DEV-207

## Implementation

Starting main `35be204592e22fed2962e6ab9fe6fc027be22df1`; original branch `ai-dev/207-tw-research-evidence-coverage-v1`; implementation commits `9df052c84da9bc2d949711a9e31e5d7db0670b57` and `bd9fad25a0fcb6d16cb65d36b26ca0dff1f27e2a`; PR [#252](https://github.com/kaochuchian-netizen/ai-quant-research-trading-platform/pull/252); original merge `08c73c2c733a58deaead711ffc9449fd9875e1c8`; CI run `31569399724` passed. The implementation adds a canonical per-symbol evidence funnel, separates substantive research from market/technical context, quality-gates Best Research, and derives tomorrow wording from existing Decision presentation categories.

A subsequent independent ChatGPT post-merge audit found two remaining deterministic gaps inside the same AI-DEV-207 contract. Hardening branch `ai-dev/207-research-evidence-hardening-v2` and PR #253 repair those gaps before natural verification: qualified directionless news is no longer discarded, and legacy funnel inference is explicitly marked as lower-bound rather than exact observability.

## Root-Cause Audit

- Retrieval existed: the Google News RSS path returned headline, URL, publisher and time plus retrieval metadata. It did not reliably produce trustworthy direction, materiality or relevance. The prior product collapsed discovery failure, filtering, admission and renderer selection into one `NEWS_UNAVAILABLE` message.
- `_news_items()` incorrectly treated an explicit empty `items` list as one malformed news object because truthiness fallback skipped the empty list. A real no-news result was therefore mislabeled as filtered provenance failure.
- TW daily RRE placed market price, volume, technical and ADR observations in the same directional supporting/opposing partition as official/news/fundamental evidence. Intraday price could therefore create a bullish/bearish “research evidence” headline.
- Best Research selected the highest confidence note without requiring a directional conclusion backed by substantive evidence.
- Tomorrow text used a generic fallback rather than the already-canonical Decision presentation category, weakening the distinction between `NO_TRADE` and `OBSERVE`.
- Post-merge hardening audit: `news_contract()` still rejected otherwise qualified fresh/relevant/material news when direction was absent, which preserved avoidable news under-coverage.
- Post-merge hardening audit: compatibility projection for older payloads without funnel V1 filled upstream counts from admitted count without marking that those values were lower bounds, which could make inferred counts look exact.

## Architecture and Product Outcome

`tw_research_evidence_funnel_v1` records `DISCOVERED → RETRIEVED → NORMALIZED → SYMBOL_ATTRIBUTED → RELEVANT → MATERIAL → QUALITY_QUALIFIED → FRESH → DEDUPLICATED → ADMITTED → RRE_USED → RENDERED`, together with deterministic rejection counts. Per-symbol diagnostics are aggregated under `tw_research_evidence_observability_v1`; the main Dashboard renders only a concise localized state and four key counts.

Canonical evidence carries `research_role = substantive | contextual`. Market price, volume, technical, ADR, macro/sector context remain visible and traceable as contextual evidence but cannot alone produce bullish/bearish Research headlines. News/fundamental/event evidence can remain substantive even when direction is not evaluated; a directionless substantive item is visible and traceable but does not enter bullish/bearish support or qualify Best Research by itself.

Directionless qualified news is now admitted as `direction = unavailable` with `direction_status = NOT_EVALUATED`. No card-level fallback is allowed to silently assign direction. RRE therefore preserves the evidence while keeping the directional conclusion `insufficient_evidence` unless separate directional substantive evidence exists.

Research cards expose admitted news with source and timestamp, supporting/opposing/contextual/missing partitions, hypothesis, invalidation and counterargument. Non-directional substantive news is explicitly surfaced in the research summary rather than disappearing. Best Research requires a bullish/bearish/mixed conclusion, at least one substantive evidence item and deterministic confidence >= 50. Otherwise the brief states `本批次無符合研究品質門檻的標的` and labels the top note only as a relative evidence candidate.

Tomorrow wording is presentation-only and derived from existing categories: `AVOID_CANDIDATE → 明日重新評估`, `WATCH_CANDIDATE → 明日延續觀察`, and existing buy/hold categories may be rendered as `明日優先觀察`. It does not create a new action or change Decision ownership.

Funnel observability now exposes count provenance. Current canonical funnel output is marked `count_semantics = EXACT`. Older payloads without funnel V1 are marked `COMPATIBILITY_LOWER_BOUND` and list `inferred_stages`; partially populated legacy funnels are marked `PARTIAL_COMPATIBILITY_LOWER_BOUND`. These inferred values are minimum-known counts, not claimed exact discovery/retrieval counts.

## Evidence Funnel Fixture Examples

- No discovery: 0/0/0/0 and `NO_RELEVANT_NEWS_DISCOVERED`.
- Two discovered, both quality/materiality filtered: discovered 2, admitted 0, with `LOW_RELEVANCE: 1` and `LOW_MATERIALITY: 1`.
- One official MOPS directional disclosure: discovered/retrieved/admitted/RRE-used/rendered all 1; headline, MOPS source and publication time are present in the rendered Research Note.
- One official MOPS directionless disclosure: admitted 1, `direction = unavailable`, `direction_status = NOT_EVALUATED`, RRE-used/rendered 1, but bullish/bearish Research counts remain zero and Best Research remains unqualified without other directional substantive evidence.
- Duplicate official/secondary representations sharing one canonical URL: one admitted and one `DUPLICATE` rejection.
- Stale item: one `STALE` rejection and zero admitted evidence.
- Legacy admitted evidence without funnel V1: inferred upstream counts remain monotonic but are explicitly labeled `COMPATIBILITY_LOWER_BOUND` with inferred-stage provenance.

## Source Quality

Official company, MOPS, TWSE, TPEx and IR sources retain tier 1 priority. Recognized industry research remains tier 2, credible identified media tier 3, and unidentified/weak sources are rejected. Missing direction no longer causes otherwise qualified evidence to be discarded. The platform does not infer bullish/bearish direction from headline sentiment; instead it preserves direction as `NOT_EVALUATED` and prevents that evidence from creating directional research claims.

## Validation

Original deterministic Cases A–J PASS: true no-news, filtered-news reasons, official admission, admitted-to-RRE-to-render traceability, dedup, stale rejection, market-only non-directionality, no-qualified Best Research, qualified Best Research, and NO_TRADE-versus-OBSERVE wording.

Hardening adds Cases K–O: qualified directionless-news admission, no false directional conclusion/counts, directionless-news visibility through RRE/render, truthful legacy lower-bound funnel semantics, and exact canonical funnel provenance. Mutation of Best Research to qualified without a qualified note remains rejected.

The AI-DEV-207 validator remains ACTIVE, leaf, and required by branch and post-merge gates. No validator is skipped or weakened. The hardening PR must pass the same executable registry closure before merge.

## Changed Files

Original AI-DEV-207 changed Research evidence, reasoning, TW daily projection, Decision presentation wording, Dashboard visibility, validators and governance records.

Hardening PR #253 is intentionally narrow:

- `app/reports/tw_pre_open_quality.py` — directionless qualified news admission and exact funnel marker.
- `app/research/tw_daily_generator.py` — no card-level direction fallback, non-directional substantive-news visibility, funnel count provenance and semantic validation.
- `scripts/orchestrator/validate_ai_dev_207_tw_research_evidence_coverage_news_visibility_v1.py` — Cases K–O.
- governance registry/completion report metadata for the hardened contract.

## Production Usability and Safety

Production pipeline executed: false. Controlled/public publish: false. Email attempted: false. LINE attempted: false. Trading/orders: false. Scheduler/cron/systemd changed: false. Notification runtime changed: false. Secrets accessed: false. Production DB written: false. Immutable history rewritten: false. Existing dirty runtime/generated artifacts cleaned or staged: false.

Trading strategy, scoring, trading ranking, eligibility, action, entry, stop, target, position sizing, prediction weights and execution ownership are unchanged. RRE remains advisory; the Decision Layer remains canonical.

## Known Limitations

The existing live RSS adapter still does not safely derive directional semantics from headline text. This is intentional: qualifying evidence is preserved and visible even when direction remains `NOT_EVALUATED`, rather than fabricating sentiment. Natural production must still demonstrate useful source coverage and real funnel counts after merge.

## Natural Verification

Observe the first eligible post-hardening TW lifecycle `07:00 → 13:05 → 13:35 → 15:00`. Verify real discovered/retrieved/admitted/RRE-used/rendered counts and reasons; admitted official/material evidence visibility including directionless qualified news; price-only non-directionality; Best Research quality behavior; 6873-style OBSERVE continuity; NO_TRADE re-evaluation wording; research identity parity across Dashboard, Archive, Email preview, LINE preview and Operations; and unchanged Decision actions.

The 2026-08-12 13:05 and 13:35 batches are pre-change root-cause evidence, not post-merge natural verification.

### First post-H2 natural smoke and V3 remediation

The natural 2026-08-12 15:00 batch is the first post-H2 production smoke. It confirmed directionless qualified-news visibility, but it also exposed deterministic cross-consumer defects that prevent closure: aggregate prediction counts preferred V2 and reported 9 hits while canonical per-symbol review was 8 no-trade/not-applicable plus one 6873 partial hit; stale news could be rendered as current neutral research; the missing-news label could not distinguish stale-only evidence; same-event selection did not guarantee official-source preference or newest-first ordering within a tier; and the compact NO_TRADE renderer used OBSERVE-style tomorrow wording.

AI-DEV-207 Natural Production Remediation V3 uses branch `ai-dev/207-post-close-natural-remediation-v3`, implementation commit `562082ba05ad7e8a18281b503279756b769288a6`, and PR [#255](https://github.com/kaochuchian-netizen/ai-quant-research-trading-platform/pull/255). Initial GitHub Actions run `31575649448` passed. V3 introduces one shared canonical prediction-range resolver for aggregate and Decision review consumers, requires AVAILABLE coverage for neutral current-news rendering, distinguishes stale-only news gaps, prefers official and then newest same-event representations, and routes compact NO_TRADE tomorrow text through the canonical presentation helper. The deterministic V3 fixture requires prediction counts `hit=0, partial_hit=1, miss=0, not_applicable=8` with an exact nine-symbol partition. The immutable 2026-08-12 artifact is not rewritten or republished.

V3 returns the task to deterministic-QA-pass pending natural verification after PR, CI and post-merge gates pass. Only the next eligible post-V3 TW `07:00 → 13:05 → 13:35 → 15:00` lifecycle may provide final natural evidence.

## Final Status

IMPLEMENTED_DETERMINISTIC_QA_PASS_PENDING_NATURAL_VERIFICATION
