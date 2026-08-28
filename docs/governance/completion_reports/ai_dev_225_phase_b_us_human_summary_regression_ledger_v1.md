# AI-DEV-225 Phase B — US Human Summary and Evidence Regression Ledger

## Repository

- Starting main: `ac5ec9cf4750fd225e07b12bc8fc86b97495c565`
- Branch: `ai-dev/225-us-human-summary-regression-ledger-v1`
- Implementation commit, PR, CI and merge: recorded by the governed Git/GitHub history.
- Final repository target: `HEAD = main = origin/main`, ahead/behind `0/0`, no task-branch residue.

## Human summary

The presentation-only `us_human_decision_summary_v1` is derived from admitted US artifacts and has no Decision authority. It does not write back to scoring, prediction, ranking, eligibility or trading.

- 20:00 presents direction, confidence, forecast target/range, Research / Position stance, Daily Tactical stance, bounded reasons, main risk and at most four important news items before execution details.
- 23:00 preserves the 20:00 forecast and snapshot lineage, then reports current range position, target progress, confidence change, trigger state, new evidence and deterministic hypothesis continuity. Missing lineage fails closed.
- 06:30 keeps prediction and trade evaluation separate, presenting direction/range results, error fields, MFE/MAE, hypothesis outcome, evidence lesson and next-session carry-forward. `NO_TRADE` and `NOT_TRIGGERED` are not prediction failures.

## News integrity

The existing US-native provider path and H3 entity rules remain authoritative. A publisher-independent canonical event identity groups syndicated copies while retaining every publisher/source reference; distinct updates remain distinct. Contextual macro/sector roles remain non-directional and cannot be promoted into company-primary evidence. Important-news impact text is derived only from finalized metadata and attribution, without article bodies or unsupported facts.

## Regression ledger and offline evaluation

The versioned `us_evidence_regression_record_v1` ledger is bounded to 64 candidate metadata records per symbol/window and uses immutable-by-record files under the governed runtime artifact tree. It retains admitted and rejected candidate metadata, rejection reason, event identity, provenance, evidence/hypothesis/prediction linkage and later evaluation linkage when available. It stores no full article body and performs no production DB write.

Replay is idempotent; an existing identity with different content fails closed. Offline leave-one-out recomputes Research synthesis only when replay inputs are sufficient, never changes production prediction or weights, and otherwise returns `INSUFFICIENT_REPLAY_INPUTS`. Technical-only comparison remains explicitly deferred offline while required linkage fields are retained.

## Validation

- AI-DEV-225 dedicated executable cases: PASS (7/7).
- AI-DEV-216, AI-DEV-214, AI-DEV-212 H3, AI-DEV-201, cross-market/governance and window-renderer targeted regressions: PASS.
- Python compile, scoped undefined-name check and `git diff --check`: PASS.
- Full registry: executed once locally; browser/PDF leaves require the governed CI Chromium runtime. GitHub CI is the authoritative full-registry and visual closure.
- Post-merge registry and platform inspector are required before cleanup.

## Safety

- Strategy/scoring/prediction weights/ranking/eligibility: unchanged.
- Entry/Stop/execution Target/sizing/trading/orders: unchanged.
- TW behavior: unchanged.
- Scheduler/cron/systemd/nginx/infrastructure: unchanged.
- Production DB: unchanged.
- OAuth/Drive/secrets: untouched.
- Production rerun and LINE/Email sends: not executed.
- Immutable historical archives: not rewritten.

## Natural verification

Repository closure remains `IMPLEMENTED_PENDING_NATURAL_VERIFICATION`. Required natural lifecycle: `20:00 → 23:00 → 06:30`.
