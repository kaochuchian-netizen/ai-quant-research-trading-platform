# AI-DEV-251C: offline report comparison and finding/fix evidence loop

This phase implements the approved PM decision: previous-report comparison, immutable
predecessor binding, and two independent dimensions of an evidence loop. It does not
change the 251A envelope or 251B evaluators, weights or effect interpretation.

## Separate, versioned contract

`config/governance/offline_report_projection_contract_v1.json` owns the C projection
shape and mapping. `offline_evaluation_report_v1` identifies an immutable derived
report; `offline_report_comparison_v1` identifies a comparison. Both bind
`ai_dev_251c_offline_report_projection_v1` and its canonical SHA-256 digest. A separate
strict rejected-result schema prevents unvalidated payloads from appearing in errors.

These are not 251A `daily_scorecard` envelopes, renamed envelopes, or an alternate path
around `phase_a_no_scores`. The existing 251A guard rejects them. C does not modify,
wrap into, or relax A's scored-record prohibition. Existing source/ledger/history and
report owners remain authoritative; C adds a pure projection under `app/evaluation`.
It has no persistence, source loader, network client, automatic clock, production
adapter or new ledger/database. `append_report` is an in-memory immutable history
projection for callers of the existing history owner, not a store writer.

## Inputs, replay and immutable identity

`build_report(report_id, inputs, ...)` accepts a SYNTHETIC or SANITIZED_AGGREGATE input
packet containing the unchanged B rows and explicit context. C calls B directly and
retains its complete user-facing and internal result. Inputs are supplied by the caller;
their digest is saved, but input rows are not embedded in the report or comparison.
The caller must retain the admitted input packet separately for replay. Dict keys are
canonicalized for hashing; array order is retained, including the calendar's own hash.
No input is silently normalized into a different prediction.

Every report binds identity (market, symbol, strategy, horizon), report date, revision,
schema/evaluator/contract version, input digest, full evaluator evidence and lifecycle
evidence records. Its content_hash is SHA-256 of canonical JSON excluding content_hash,
using the same canonical hashing primitive as A. Missing or malformed metadata fails
closed. `validate_report` recomputes B from the supplied inputs and compares the entire
report; rehashing a forged total, component or effect label cannot make it valid.

`append_report` rejects an altered existing report_id/revision, missing or skipped
revision predecessors, wrong supersedes hashes, and changes to date/stock identity
across revisions. Exact replay is idempotent; caller objects are never modified.
Revised reports require explicit history during build/validation/comparison.

## Previous-calendar-report binding

`compare_reports` requires an explicit predecessor artifact, its evaluator inputs and
an externally pinned reference containing report_id, revision, schema_version and
content_hash. The current reference is emitted alongside it. The relationship is
`PREVIOUS_CALENDAR_REPORT`: the predecessor date must be exactly one calendar date
before the current 17:00 Asia/Taipei report. It never searches a `latest` pointer or
silently selects a newer revision. Market/stock/strategy/horizon must match.

Missing predecessor produces NO_PREDECESSOR with no fabricated delta. Missing pinned
artifact is distinguished from having no pin. Bad hash, version, pin or date rejects
the comparison. Missing score evidence yields INSUFFICIENT_COMPARISON and null deltas,
not zero or weight redistribution. Report deltas are descriptive, not fix causality.
TW/US session selection remains B's; the comparison explicitly flags an unchanged
market session on holiday reports so a carried session is not called a new sample.

## Evidence-chain dimension

The report preserves caller-supplied finding_ledger, fix_ledger and fix_evaluation
records unchanged, validated against A, including immutable revisions and as-of cutoff.
`linkage_refs` selects exact content hashes, never latest IDs. COMPLETE requires:

- The three selected entity types and stock/strategy identities match.
- Finding evidence/evaluation reference IDs have digest-qualified source references.
- Fix points to the exact finding ID/schema/hash, and evaluation to the exact fix.
- Evaluation also binds the exact B semantic result digest and evaluator version.
- When eligible B samples expose fix IDs, they agree with the selected fix identity.

Any missing/mismatched edge is INCOMPLETE with stable reason codes. Invalid record
shape/hash or future lifecycle timestamps rejects the report itself. External source
digests remain caller attestations; this phase does not dereference original documents.

**COMPLETE means only required evidence-chain completeness.** It does not mean
prediction/strategy improved, fix successful, finding resolved, production safe, or
deployment permitted. A metadata fix_evaluation may remain PENDING while its chain
is complete. No finding/fix/evaluation status is promoted, closed or otherwise changed.

## Realized-effect dimension

Only B's replayed `improvement.effect_summary.realized_prediction_effect` supplies the
effect classification: IMPROVED -> POSITIVE, NEUTRAL -> NEUTRAL, REGRESSED -> NEGATIVE,
MIXED/PENDING -> INSUFFICIENT_EVIDENCE. This is an explicit presentation mapping of B's
existing taxonomy, not a scoring engine or substitute strategy-success metric.
The original label, all four improvement components and diagnosis/recurrence effects
remain visible. In particular, 100/50/50/100 remains score 70 with NEUTRAL realized
prediction effect; the aggregate never overwrites components or infers improvement.

COMPLETE can accompany any of the four effects. INCOMPLETE can accompany available
effect evidence; its attribution is explicitly EVALUATOR_SAMPLE_ONLY, not a verified
finding/fix linkage. Effect assessment remains descriptive with causal_claim=false.
Both predecessor and current full component/linkage evidence are retained separately.
Lifecycle mutation and production readiness are always false.

## Validation and boundaries

Run `scripts/orchestrator/validate_ai_dev_251c_offline_report_projection_v1.py`, plus
unchanged 251A (50) and 251B (92) regressions. The synthetic C suite covers predecessor
pins/hash/version/date, all chain/effect combinations, component and aggregate tamper,
revision immutability, original lifecycle preservation, no network and deterministic
replay. The fixture reuses B's synthetic inputs and A's record shape; no market payload
or production artifact is copied. Branch/governance/CI gates remain mandatory.

Production adapters, durable archive/report publishing, lifecycle transitions and
actual source validation remain future explicitly governed work. No scheduler,
notification, deployment, database or trading operation is added. Pre-existing
unrelated validators are neither changed nor exempted.
