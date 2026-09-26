# AI-DEV-251D session-based production shadow integration

This task implements the PM-approved session prerequisite decision. Legacy A/B/C v1
APIs and fixtures retain their historical 17:00 behavior for replay; production D
uses explicit market session and aware evaluation_at, never a generic 17:00 cutoff.
Weights, feature meaning, lifecycle and original report payload remain unchanged.

## Calendar authority and immutable snapshots

TWSE's 2026 published market opening/holiday schedule is the TW authority:
https://www.twse.com.tw/holidaySchedule/holidaySchedule?response=json&queryYear=2026
Regular cash sessions are 09:00–13:30 Asia/Taipei, confirmed by https://www.twse.com.tw/en/products/system/trading.html. NYSE's official published
holiday/early-close schedule and cash equity hours are the US authority:
https://www.nyse.com/trade/hours-calendars
Normal sessions are 09:30–16:00 America/New_York; November 27 and December 24
2026 close at 13:00. ZoneInfo records DST offsets per session.

The checked-in snapshots enumerate every date, including non-trading days, for
2026-01-01 through 2026-12-31. Their source document digest, acquisition date,
annual schedule version, revision and content digest are retained. The manifest
pins content hashes; runtime does not generate dates, consult the network, or
fall back to a weekday/legacy holiday heuristic. Snapshot materialization uses
the exchanges' regular week and published exceptions, not runtime inference.
A special closure notice takes precedence over the annual schedule and requires
a reviewed new immutable snapshot revision and manifest pin. No unobserved
special closure is claimed to have been verified. Future exceptional closures
require maintenance; outside coverage is blocked, never extrapolated.
The synthetic SPECIAL_CLOSURE test is explicitly not a real exchange notice.

## Review mapping and eligibility

The admitted archive's market/window/effective_trading_date is the review identity.
All four TW streams retain session D; all three US streams retain the US session
already explicitly assigned by the source archive, not a converted Taipei date.
generated_at is the frozen evaluation availability bound for this immediate hook;
it is not relabeled as prediction_at. Pre-open/intraday remain PENDING until D
is completed. Calendar missing/malformed/corrupt/outside coverage/non-session
produces BLOCKED_INPUT. That is not evaluation/comparison success and cannot
enter a scored predecessor chain.

Once D has closed, unchanged B component formulas can evaluate eligible inputs.
The initial production adapter admits stock identity and source references only.
It does NOT reinterpret strategy confidence, monthly trend, report scores or
archive time as forecast probability/direction/generated_at. Missing point-in-time
mapping and outcome/fix cohorts are explicit admission gaps. Thus current
production reports are expected to produce contract-valid INSUFFICIENT_SAMPLE
evaluations, not numeric scores. Synthetic fixtures exercise fully scored paths.
No readiness claim should imply production scored coverage.

## Ownership, isolation and retention

window_snapshot_archive remains the only report authority. Shadow artifacts are
derived .evaluation sidecars under each immutable date directory; archive
navigation excludes them. They retain source identity/revision/schema/digest,
sanitized input packet, complete calendar, B component results, C chain/effect
semantics, comparison and generation/version metadata. Raw report/positions/
delivery content is not duplicated. Existing source archives remain referenced.

A worker is invoked only for the canonical archive root after its report file
is persisted. It has a three-second timeout and no delivery/action imports.
Failure produces bounded diagnostics without changing return data or delivery
decision; the original pipeline continues. This introduces at most the worker
timeout latency. No extra scheduler, background daemon, database or dependency
is added. Tests use temporary archives and explicit worker mocks/direct calls.

Publication uses same-filesystem temporary staging, fsync and exclusive hardlink:
an existing artifact cannot be overwritten. Identity is source digest + D
contract version. Exact replay is idempotent; canonical report revisions have
new identities. No source artifact is cleaned or moved. Retention is append-only;
raw sources remain under their existing owner; derived evidence is retained
alongside it. Large historic payload retention/compaction is not changed here.

## Predecessor and evidence semantics

Only successfully scored, contract-valid scheduled EVALUATED artifacts are
eligible. Manual reruns neither select nor become scored predecessors. Selection
uses prior session date in the same market/window; revisions break ties
deterministically, then digest. Existing artifact retries retain their original
binding even if a later predecessor revision arrives. BLOCKED_INPUT/PENDING/
INSUFFICIENT_SAMPLE never masquerade as scored history. Missing predecessor
stays NO_PREDECESSOR. Corrupt prior evidence rejects comparison while preserving
the current report and shadow evidence.

Pins carry report identity/schema/hash. Component-level predecessor evidence is
retained for replay. C's unchanged evidence_chain and realized_effect functions
are reused; no finding/fix status is changed. Empty finding/fix inputs yield an
INCOMPLETE chain and no causal claim. Aggregate results cannot rewrite component
evidence. Current and retained predecessor component results are replay-checked.

## Replay, acceptance and rollback

Use app.evaluation.production_shadow.validate_shadow on a retained sidecar. It
recomputes from its retained packet/calendar without network, DB or clock.
A controlled acceptance may call the archive owner's persist on an existing
admitted report file. This only creates a shadow sidecar; it does not invoke the
report pipeline, change the original archive or send notifications. Record both
source file hash before/after and returned artifact hash. Repeat persist must
return IDEMPOTENT; reload/replay must pass. A temporary synthetic missing-calendar
artifact checks BLOCKED_INPUT without touching canonical report history.

Before deployment record previous production SHA and preservation classification.
Only merge-approved main is fast-forwarded. Never reset/clean/stash production.
Rollback removes integration code by returning to the recorded previous approved
commit using a clean source checkout transition after checking dirty paths do not
overlap. Preserve all sidecars and diagnostic evidence; no production hotfix.
If that checkout transition cannot be guaranteed, stop before deployment.

Validation: D fixture gate plus A 50/B 92/C 60 regressions, relevant archive/TW/US
validators, governance, source audit and complete GitHub branch gate. Old unrelated
PDF/transport/lock validators remain unchanged and are not exempted.

## Differential attribution

The local TW post-close payload consistency validator fails in both this branch
and a clean cb997f689879b04ee560713a8497584b05d4e50b worktree with
AttributeError: list has no attribute get at app/reports/tw_human_summary.py:145.
That renderer and the failing validator are unchanged. This fixture/renderer
mismatch is PRE_EXISTING_UNRELATED and is not fixed or waived here.
