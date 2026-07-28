# Phase 1 Product Quality Consolidation & Daily Decision Experience V1

## Root-cause matrix

| Layer | Before | V1 correction |
| --- | --- | --- |
| Canonical ownership | V4 projected counts and lists, while decision story remained distributed across cards | Extend V4 with one deterministic `daily_decision_experience_v1` projection |
| Evidence | Source fields existed per feature but no shared Evidence → Interpretation → Impact contract | Normalize source, time, freshness, direction, materiality, reliability and decision impact |
| Confidence | Existing score could render without supporting, contradicting or limiting factors | Preserve the existing score and explain evidence, gaps, freshness, conflict and cap reasons |
| Missing data | Feature-specific fallbacks varied | Machine-readable state and decision/confidence impact; missing is never neutral |
| Continuity | Timelines could contain pending/admitted duplicates and adapters emphasized different states | Deduplicate one record per symbol/window and derive deterministic transition state |
| Channels | Shared projection existed, but adapters could lead with different fragments | Dashboard, LINE, Email, Archive projection and Operations share one canonical hash |

## Canonical ownership

`project_decision_intelligence_v4()` remains the existing production-facing projection boundary. It now includes `canonical_decision_summary`, produced by `build_daily_decision_experience()`. No parallel runtime or mutable global latest file is introduced.

## Canonical decision contract

Required fields include current view/action, why, opportunity, risk, existing confidence and explanation, evidence summary, missing-data impact, previous-window transition, next trigger/watch, effective date, as-of, freshness, identity and canonical summary hash.

## Evidence and source priority

Official disclosure/exchange/regulator evidence precedes financial results, company IR, material company news, official macro data, sector evidence, technical/price, flow, general media and sentiment. Social rumor is not admitted as formal evidence. Market identity is enforced and cross-market cards are rejected from the projection.

## Confidence explanation

The projection does not change model scores or weights. It uses the existing canonical card score and discloses supporting evidence, contradictory evidence, missing inputs, freshness distribution, consistency, uncertainty and cap reasons. Missing score remains unavailable.

## Missing-data truthfulness

States are AVAILABLE, STALE, MISSING, NOT_APPLICABLE, SOURCE_FAILED, PARTIAL and DEFERRED. Each record includes expected source, last success, freshness, decision impact, confidence impact, fallback and user message. Missing or stale evidence cannot be rendered as neutral/current.

## Lifecycle transitions

Allowed states are UNCHANGED, STRENGTHENED, WEAKENED, UPGRADED, DOWNGRADED, INVALIDATED, CLOSED and NO_PRIOR_STATE. Timeline entries are deduplicated by symbol/window, preferring admitted identity over awaiting placeholders. Future-dated prior evidence fails validation.

## Cross-channel parity

All adapters receive `canonical_summary_hash`. LINE may shorten the story and Email/Dashboard may expand it, but current action, confidence, transition and next trigger are derived from the same object. Operations stores the same object and hash.

## Backward compatibility

Existing payload keys, strategy decisions, rankings, source-plan ownership, lifecycle outcomes, archive revisions and delivery approvals are unchanged. Historical snapshots are read only; absent optional fields produce explicit unavailable text.

## Deterministic verification

The AI-DEV-195 bundle covers unchanged, downgraded, missing critical data, stale evidence, five-channel parity, no prior window, same-day revision and TW/US isolation. Negative cases reject missing-as-neutral, channel drift, future evidence, cross-market evidence and stale-as-latest.

## Natural verification

Observe all four TW and all three US formal windows within 2–5 trading days. Record naturally observed, deterministic-only and not-yet-observed cases separately. The task remains IMPLEMENTED_PENDING_NATURAL_VERIFICATION until accepted evidence is registered.

## Rollback

Revert the implementation commit through a normal PR. No runtime, scheduler, archive or delivery rollback is needed because this task does not mutate those surfaces.

## Known limitations

Old snapshots may not contain full lifecycle identity or evidence timestamps. They remain visible with safe unavailable semantics. Health improvements remain implemented, not naturally verified.
