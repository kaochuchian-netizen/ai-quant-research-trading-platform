# AI-DEV Completion Report V2
Task ID: AI-DEV-207

## Implementation

Starting main `35be204592e22fed2962e6ab9fe6fc027be22df1`; branch `ai-dev/207-tw-research-evidence-coverage-v1`. Implementation commits, PR, GitHub Actions run and merge/current-main identity are recorded in the final repository handoff after the normal branch gate, PR and merge workflow. The implementation adds a canonical per-symbol evidence funnel, separates substantive research from market/technical context, quality-gates Best Research, and derives tomorrow wording from existing Decision presentation categories.

## Root-Cause Audit

- Retrieval existed: the Google News RSS path returned headline, URL, publisher and time plus retrieval metadata. It did not produce trustworthy direction, materiality or relevance, so the canonical admission contract correctly refused to use most items. The prior product collapsed discovery failure, filtering, admission and renderer selection into one `NEWS_UNAVAILABLE` message.
- `_news_items()` incorrectly treated an explicit empty `items` list as one malformed news object because truthiness fallback skipped the empty list. A real no-news result was therefore mislabeled as filtered provenance failure.
- TW daily RRE placed market price, volume, technical and ADR observations in the same directional supporting/opposing partition as official/news/fundamental evidence. Intraday price could therefore create a bullish/bearish “research evidence” headline.
- Best Research selected the highest confidence note without requiring a directional conclusion backed by substantive evidence.
- Tomorrow text used a generic fallback rather than the already-canonical Decision presentation category, weakening the distinction between `NO_TRADE` and `OBSERVE`.

## Architecture and Product Outcome

`tw_research_evidence_funnel_v1` records `DISCOVERED → RETRIEVED → NORMALIZED → SYMBOL_ATTRIBUTED → RELEVANT → MATERIAL → QUALITY_QUALIFIED → FRESH → DEDUPLICATED → ADMITTED → RRE_USED → RENDERED`, together with deterministic rejection counts. Per-symbol diagnostics are aggregated under `tw_research_evidence_observability_v1`; the main Dashboard renders only a concise localized state and four key counts.

Canonical evidence now carries `research_role = substantive | contextual`. Official/news/fundamental/event evidence may form research direction when safely admitted. Market price, volume, technical, ADR, macro/sector context remain visible and traceable as contextual evidence but cannot alone produce bullish/bearish Research headlines. Existing generic RRE callers remain backward-compatible through the default substantive role; TW production assigns roles explicitly.

Research cards expose admitted news with source and timestamp, supporting/opposing/contextual/missing partitions, hypothesis, invalidation and counterargument. Best Research requires a bullish/bearish/mixed conclusion, at least one substantive evidence item and deterministic confidence >= 50. Otherwise the brief states `本批次無符合研究品質門檻的標的` and labels the top note only as a relative evidence candidate.

Tomorrow wording is presentation-only and derived from existing categories: `AVOID_CANDIDATE → 明日重新評估`, `WATCH_CANDIDATE → 明日延續觀察`, and existing buy/hold categories may be rendered as `明日優先觀察`. It does not create a new action or change Decision ownership.

## Evidence Funnel Fixture Examples

- No discovery: 0/0/0/0 and `NO_RELEVANT_NEWS_DISCOVERED`.
- Two discovered, both quality/materiality filtered: discovered 2, admitted 0, with `LOW_RELEVANCE: 1` and `LOW_MATERIALITY: 1`.
- One official MOPS disclosure: discovered/retrieved/admitted/RRE-used/rendered all 1; headline, MOPS source and publication time are present in the rendered Research Note.
- Duplicate official/secondary representations sharing one canonical URL: one admitted and one `DUPLICATE` rejection.
- Stale item: one `STALE` rejection and zero admitted evidence.

## Source Quality

Official company, MOPS, TWSE, TPEx and IR sources retain tier 1 priority. Recognized industry research remains tier 2, credible identified media tier 3, and unidentified/weak sources are rejected. Missing direction remains `UNSAFE_TO_CITE`; the task does not infer direction from headline sentiment and does not lower admission standards to increase counts.

## Validation

Dedicated deterministic Cases A–J PASS: true no-news, filtered-news reasons, official admission, admitted-to-RRE-to-render traceability, dedup, stale rejection, market-only non-directionality, no-qualified Best Research, qualified Best Research, and NO_TRADE-versus-OBSERVE wording. Mutation of Best Research to qualified without a qualified note is rejected by the canonical validator. AI-DEV-198/199/201/202/203/204/205 passed. AI-DEV-200 was legitimately strengthened to require ADR evidence in the contextual partition rather than the substantive supporting partition and then passed.

The AI-DEV-207 validator is ACTIVE, leaf, required by branch and post-merge gates. Exact registry selected/executed counts, complete regression commands and CI/post-merge results are recorded in the final repository handoff.

## Changed Files

- `app/reports/tw_pre_open_quality.py` — news parsing, funnel, reason codes and absence states.
- `app/research/evidence.py` — canonical substantive/contextual evidence role.
- `app/research/reasoning.py` — substantive-only research direction with contextual traceability.
- `app/research/tw_daily_generator.py` — evidence roles, quality gate, observability, provenance labels and semantic validation.
- `app/reports/tw_decision_intelligence_v2.py` — presentation-only tomorrow semantics.
- `app/dashboard/multi_market_dashboard.py` — concise localized evidence visibility.
- `scripts/orchestrator/validate_ai_dev_200_rre_production_integration_v1.py` — preserves ADR verification under the corrected contextual contract.
- `scripts/orchestrator/validate_ai_dev_207_tw_research_evidence_coverage_news_visibility_v1.py` — deterministic semantic gate.
- governance registry, pending natural verification and health evidence files — executable closure and source-of-truth status.
- this completion report.

## Production Usability and Safety

Production pipeline executed: false. Controlled/public publish: false. Email attempted: false. LINE attempted: false. Trading/orders: false. Scheduler/cron/systemd changed: false. Notification runtime changed: false. Secrets accessed: false. Production DB written: false. Immutable history rewritten: false. Existing dirty runtime/generated artifacts cleaned or staged: false.

Trading strategy, scoring, trading ranking, eligibility, action, entry, stop, target, position sizing, prediction weights and execution ownership are unchanged. RRE remains advisory; the Decision Layer remains canonical.

## Known Limitations

The existing live RSS adapter does not safely derive direction/materiality/relevance from headline text. Those items remain visible in funnel diagnostics but are not admitted as substantive evidence without trustworthy normalized semantics. The task intentionally does not add a paid source, fabricate live news, send notifications or rewrite historical artifacts.

## Natural Verification

Observe the first eligible post-merge TW lifecycle `07:00 → 13:05 → 13:35 → 15:00`. Verify real discovered/retrieved/admitted/RRE-used/rendered counts and reasons; admitted official/material evidence visibility; price-only non-directionality; Best Research quality behavior; 6873-style OBSERVE continuity; NO_TRADE re-evaluation wording; research identity parity across Dashboard, Archive, Email preview, LINE preview and Operations; and unchanged Decision actions.

The 2026-08-12 13:05 and 13:35 batches are pre-change root-cause evidence, not post-merge natural verification.

## Final Status

IMPLEMENTED_DETERMINISTIC_QA_PASS_PENDING_NATURAL_VERIFICATION
