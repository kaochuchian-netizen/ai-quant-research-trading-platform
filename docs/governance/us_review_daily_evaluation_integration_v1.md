# AI-DEV-254 US review and daily evaluation integration v1

Single owner: kaochuchian user crontab. Existing 20:00 / 23:00 / 06:30 entries are unchanged.
The new canonical entrypoint is scripts/orchestrator/approved_daily_evaluation.py.
Activation of a single 17:00 Asia/Taipei daily cron entry requires separate explicit approval.
This change neither installs cron nor creates a timer, transport, model, or market-data service.

## Integration matrix
| Window | Producer / input | Accumulator / review | Delivery |
|---|---|---|---|
| US 20:00 | Existing 253 native frozen prediction; NO_FORECAST excluded | Existing 252 | Existing unchanged |
| US 23:00 | Inherited origin reference only | Existing 252, no new origin sample | Existing unchanged |
| US 06:30 | Latest completed authoritative NYSE session | Existing 252 outcome maturity plus immutable direction-review sidecar | Existing unchanged |
| Daily 17:00 | Latest completed TWSE and NYSE sessions, independent dates | Existing 252 direction component, 251B components, 251C chain/effect semantics and immutable prior comparison | Artifact only; no notifications |

## Calendar and maturity
The pinned 251D calendars are the only runtime US session truth. US identity uses America/New_York,
including DST, holidays, early closes and special closures. Delivery time stays Asia/Taipei.
06:30 resolves latest completed session, never local-date equality or a weekday approximation.
The unused legacy holiday listing helper remains for compatibility, not runtime resolution.
Calendar coverage and integrity errors fail closed, with no weekday fallback. Refresh snapshots before coverage ends.

A completed session is not proof of final market data. 252 retains its conservative approved
finality rule (a later completed daily bar must exist). Thus the latest 06:30 outcome may remain
WAITING_OUTCOME. No provisional bar is promoted. Finality policy is not relaxed by this task.
Legacy range / tactical / MFE / MAE remain in the unchanged canonical report; direction review
is a separate sidecar with frozen reference, Wilder ATR14, event and source bindings.

## Daily identity and immutable persistence
The existing window archive owns .daily_evaluation/YYYY-MM-DD/<identity>.json.
Identity hashes the canonical report date, version, and exact admitted input packet.
The semantic cutoff is always 17:00 Asia/Taipei of that report date, not rerun execution time.
CLI explicit reruns use --report-date. Inputs becoming available after cutoff are not admitted.
Changed immutable inputs produce a new identity/revision, never overwrite an earlier artifact.
Exact input retries return the original artifact including its pinned predecessor.

Only scheduled, production-derived original report evidence is admitted, verified against its
canonical report revision/digest. Independent sample identity remains the 252 prediction/event/horizon identity.
Inherited windows, NO_FORECAST, historical ineligible, manual runs, synthetic inputs and immature
outcomes do not inflate the 3/3 or 10/10 windows. Duplicate origin references are deduplicated.
Conflicting close revisions fail closed rather than choosing an arbitrary revised historical value.

A prior persisted VALID daily artifact provides a bounded immutable semantic-core proof with:
report identity, version, source artifact hash, semantic core hash, inputs and component evidence.
Replay recomputes that core. No mutable latest pointer is an identity. Comparisons of scores occur
only when both direction components are EVALUATED; otherwise INSUFFICIENT_COMPARISON.
A prior daily review may support tracking without qualifying as a scored predecessor.
The prior evidence never enters current prediction features.
Missing predecessor is NO_PREDECESSOR; corrupted predecessor is REJECTED without mutating reports.

## Components and finding safety
252 computes only the governed prediction.trend component. 251B receives provenance-preserving
partial rows; absent target/range/event probability/fix/strategy assumptions remain missing.
No weight redistribution, fabricated confidence, aggregate score, fix linkage or lifecycle transitions.
251C evidence_chain and realized_effect are reused unchanged; chain completeness and effect remain separate.
3-session diagnostics and 10-session persistence evidence are retained as diagnostic evidence,
not automatic findings, fixes, resolved states or deployment permission.

## Replay / acceptance
Run approved_daily_evaluation.py --readiness --report-date YYYY-MM-DD for read-only readiness.
Run --report-date YYYY-MM-DD --shadow-output /tmp/<isolated-directory> for isolated persistence.
Run --replay <immutable-artifact-path> to verify exact deterministic semantics.
Shadow output is outside the scheduled chain and does not create production samples.
06:30 writes .review/<digest>.json in its existing report directory after 252 accumulation.
Exceptions are isolated by the existing shadow hook and bounded diagnostic logging.

## Governance / rollback
Tests are synthetic, isolated filesystem fixtures only. No production pipeline or notification is
executed by validation. Existing scheduler entries and cadence are not changed.
Code rollback uses the previous approved commit while retaining all immutable forensic artifacts;
never reset, clean, stash or overwrite production data.
Scheduler installation and rollback commands are supplied only after deployment acceptance and require approval.
