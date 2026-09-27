# AI-DEV-252 capability-based production evidence
The approved 251A/B direction event has one implementation:
`offline_review_evaluators.realized_prediction_direction`. Legacy TW
open-to-close review remains SESSION_OPEN_TO_CLOSE_REVIEW; it is never sampled.

## Capability and identity
TW pre_open_0700 is the only native direction candidate. Intraday 1305,
pre-close 1335 and post-close 1500 are INHERITED_REFERENCE_ONLY.
US streams are CAPABILITY_UNAVAILABLE for session direction; their range and
monthly trend evidence is retained without reinterpretation. These are capabilities,
not corrupt-input states. A native origin + event + authoritative horizon is one
sample, regardless of report reference count. Manual rerun evidence is not admitted
to the scheduled cohort. Multiple distinct predictions for a session are ambiguous.

The versioned JSON contract owns capability and dormant next-session mapping.
Next-session mapping activates only for a genuine future native producer.
Current TW native predictions freeze before the authoritative current-session open.

## Future capture and storage
The existing pre-open card creation invokes capture, retaining the original report
bytes. Sidecars live under the existing window archive owner:
.frozen for contemporaneous captures, .evidence for canonical report bindings,
.outcome for immutable source observations, .assessment for replayable evaluation.
Publication uses fsync plus exclusive same-filesystem links; conflicts fail closed.
Capture failures do not alter delivery decisions.

The existing tactical ATR is SMA and remains unchanged. A separate evaluation-only
Wilder ATR is computed from completed source bars at future capture time and frozen.
Reference price is the native producer's contemporaneous value, not horizon open.
Both have explicit source digest, version and availability. Original confidence
is not event probability. Its absence does not invalidate direction evidence.
No feature is recomputed at outcome evaluation time.

Outcome reads reuse canonical historical CSV. Daily close admission conservatively
waits for a later dated bar, calendar completion and a source write after horizon
close. Missing/immature observations stay WAITING_OUTCOME. Source revision is its
SHA-256; changed source creates a new immutable outcome. This may add a session of
latency. Source snapshots must be retained by their existing owner for upstream
audit; replay of admitted evaluation uses the frozen inputs.

## State and scoring
HISTORICAL_INELIGIBLE is never included as an eligible sample.
Missing or corrupt required native prerequisites use BLOCKED_INPUT.
A mature single input is eligible but remains INSUFFICIENT_SAMPLE until
3/3 and 10/10 distinct completed sessions satisfy READY_FOR_EVALUATION;
successful component evaluation then produces EVALUATED. Time weights are read from 251A unchanged.
A direction component result does not fabricate total prediction accuracy,
confidence, strategy or improvement scores. No weight redistribution occurs.

## Inventory reused, not rescanned
Prior read-only inventory: TW 141 reports / 1,156 rows, US 141 / 846.
These are archive counts, not sample counts.
| Required evidence | TW | US |
|---|---|---|
| canonical identity/session | AVAILABLE | AVAILABLE |
| original prediction output | AVAILABLE | AVAILABLE (range/monthly trend) |
| native session direction | AVAILABLE candidate (pre-open) | NOT_APPLICABLE |
| contemporaneous freeze/availability | MISSING historically; future capture | NOT_APPLICABLE for direction |
| native target/range | AVAILABLE where originally present | AVAILABLE ranges only |
| realized daily close | DERIVABLE from admitted completed source | NOT_APPLICABLE for direction |
| horizon | DERIVABLE from calendar for native candidate | inactive direction mapping |
| implemented fix linkage | MISSING | MISSING |
| full strategy evaluation evidence | MISSING | MISSING |
| scored predecessor | MISSING until scored artifacts exist | NOT_APPLICABLE |

Historical records without contemporaneous freeze remain ineligible, including
inherited copies. Report timestamp cannot substitute for freeze time.

## Operations and boundaries
No new scheduler, network fetch, DB, notification, strategy, weights, watchlist,
finding/fix lifecycle or trading action. The existing bounded 251D worker invokes
accumulation. Resource rejection preserves original delivery.
Calendar coverage remains 2026; a reviewed immutable calendar revision is required
before coverage ends. Never fall back to weekday heuristics.

Replay uses recorded prediction, outcome, calendar and observed_at; no live reads.
Production acceptance must separately establish deployed SHA, unchanged canonical
source hashes, persistence/idempotency, and capability semantics. Synthetic tests
cannot establish PRODUCTION_EVALUATION_ACCEPTED. Initial accumulation may have zero
eligible samples; do not estimate a calendar completion date.


## Development validation
251A 50, 251B 92, 251C 60 and 251D 49 regression tests passed.
The 252 validator exercises 74 synthetic tests, including native capture,
four-window deduplication, persistence and replay. Governance and source audit pass.
Local full gates on the branch and clean 678e4ad baseline have the same 37 failed
validator IDs and no branch-only failures. The system Python lacks dependencies
including pandas; existing PDF/transport/lock issues are not modified or waived.
CI with repository dependencies is mandatory before merge.

The original 251D artifact is published before the 252 extension runs, so an
extension timeout/resource failure cannot prevent its persistence.

An immutable attempt receipt precedes future capture. An interrupted/missing-field
capture remains BLOCKED_INPUT rather than being mislabeled historical ineligible.

The governed manual supervisor progress-marker presence and dry_run flag disable
producer capture; no environment values are read. Manual report bindings cannot
contribute direction samples, even when referencing an existing scheduled origin.
