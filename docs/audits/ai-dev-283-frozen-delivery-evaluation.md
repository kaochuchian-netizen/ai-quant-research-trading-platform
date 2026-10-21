# AI-DEV-283 — Frozen delivery/evaluation consistency

## Public scope

This audit contains methods and synthetic-test results only. No production
payload, prediction values, dates, identities, hashes, receipts, recipient data,
or runtime evidence is included. Private evidence stays outside the repository
and is not reachable from the public feature-branch history.

## Contract

A public renderer and post-close evaluator can select different forecast fields
from the same card. Shared snapshot identity alone does not prove field parity.
The versioned `frozen_delivery_prediction_v1` freezes the public forecast before
snapshot creation. Delivery and evaluation consume this projection. Tactical
trade eligibility and research scores retain their original separate ownership.

The post-close pipeline validates the natural source date, envelope digest,
revision, symbol set, projection digest and public representation. The dynamic
notification universe comes from the frozen source, never a mutable watchlist.
Missing results remain explicit unassessable rows; ambiguous source revisions
fail closed. Source-binding failures preserve official OHLC but cannot fall back
to a different forecast.

`delivery_prediction_evaluation_v1` binds the frozen public forecast and official
outcome identity. It reuses existing open/close direction tolerance and range
endpoint-overlap scoring. No thresholds, tactical strategy, research scoring or
learning-sample admission are changed. Sparse observations remain distinct from
verified complete-path evidence.

## Isolation

The correction CLI reads two explicitly identified immutable inputs and writes
only to a new isolated output directory. It has no send/publish flags and no
transport/publisher imports. It refuses existing or runtime destinations and
writes a terminal receipt last. Inputs are not changed. Original acquisition
and prediction generation are not executed: this is fixed-input reevaluation,
not a full live batch rerun.

Legacy reconstruction requires explicit correction mode, valid source hashes,
and agreement between persisted public and prediction representations. Normal
production does not silently migrate legacy predictions. Future natural runs
require a stored projection; deployment timing must respect that prerequisite.

## Synthetic validation

The fixture is authored from scratch with invented instruments, dates, prices,
and identities. It is not a masked or transformed production extract.
Coverage includes opposing public/tactical forecasts, published forecasts on
no-trade strategies, missing forecasts, dynamic universes, leading zeroes,
direction and range outcomes, provisional/invalid OHLC, identity/hash/date
mismatches, missing-symbol retention, source preservation, deterministic
correction identity, exclusive output, and Dashboard/LINE/Email parity.

CI explicitly executes this suite alongside unchanged branch governance.
No Registry/quarantine bypass is added. Mac-specific baseline validator failures
must not be represented as PASS; the Linux required CI remains a merge gate.

## Approval boundaries

Production source sync, controlled Production reevaluation, corrected Dashboard
publication, and correction notifications require their respective PM approvals.
No original notification may be resent by this change. Publication requires a
separate identity/rollback gate. Delivery requires a new correction identity and
the existing once-attempt receipt contract. AI-DEV-282 remains paused.
