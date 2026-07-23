# TW Intraday-to-Close Lifecycle V1

## Root cause matrix

- 13:05 observed quotes were bound, but `entry_trigger_state` and tactical formatter enums were also used as public lifecycle states. No-trade cards therefore inherited `unavailable`, and `stop_invalidated` leaked.
- 13:35 compressed invalidation and near-stop into `reduce`; the legacy V4 projection then omitted watch from its partition and recomputed notification groups.
- 15:00 used one outcome field for prediction and trade review. A triggered setup with complete OHLC but no target/stop result was forced to `pending`, while no-trade cards ran through generic target/stop rendering.

## Canonical lifecycle

Each card keeps `plan_status`, `trigger_status`, `canonical_intraday_action`,
`overnight_action`, `trade_status`, `trade_outcome`, `prediction_evaluation`,
`risk_state` and `evidence_status`. Canonical values remain machine-readable;
presentation localization is field-aware.

Plan statuses are `no_trade`, `watch`, and `active`. Trigger statuses are
`not_applicable`, `not_triggered`, `triggered`, and `invalidated`. Overnight
actions are a complete partition: `hold`, `hold_with_protection`, `watch`,
`reduce`, `exit`, and `no_trade`.

Trade outcomes are `win`, `loss`, `not_triggered`, `no_trade`,
`open_at_close`, and `pending_evidence`. `open_at_close` means complete
evidence proves the trade is still open; `pending_evidence` is reserved for
missing or insufficient evidence.

## Volume and proximity contracts

The current TW V1 volume baseline uses the existing 20-session daily mean,
prorated by elapsed trading-session fraction. It is not described as an exact
same-time cumulative median. Payloads preserve basis, lookback and as-of time.

Target- and stop-near thresholds are both 1.5% and are producer-owned constants,
persisted in every observed card and aggregate.

## Prediction, outcome, MFE and MAE

Prediction range evaluation (`hit`, `partial_hit`, `miss`, `not_applicable`)
is independent of trade outcome. For an entered long setup, MFE and MAE use
the first entry-trigger reference and post-entry extrema. The V1 TW source has
intraday high/low resolution unless a finer source is explicitly recorded.
Public output includes percent, reference price/type, and resolution.

## Cross-window identity

The producer resolves admitted same-day snapshots by market, effective date,
window and revision. Cards retain prior-window snapshot ID, revision and source
hash in `lifecycle_timeline`. The current transition is marked
`awaiting_snapshot_admission`; no self-referential snapshot identity is
fabricated before admission.

## Channel parity

Runtime, immutable snapshot, Archive, Dashboard, Email/LINE preview and
Operations consume `aggregate_cards()`. Renderers do not define outcome or
partition rules. Presentation rebuilds may normalize legacy immutable cards
without rewriting their payloads.

## Controlled verification

Use the AI-DEV-191 validators and temporary targets only. Controlled previews
must not send Email/LINE, execute the production pipeline, change the scheduler,
trade, access secrets, or modify formal runtime/archive/provenance artifacts.

## Controlled publish and rollback

After merge, CI, post-merge gates, no-send verification and rollback backup,
the governed static publisher may rebuild presentation from resolver-selected
admitted snapshots. It must not create/backfill snapshots or rewrite immutable
history. Roll back with the publisher-recorded backup directory.

## Natural verification

The next natural 13:05, 13:35 and 15:00 batches must prove lifecycle/count/
symbol/source parity across Dashboard, Archive, Email, LINE and Operations.
Until all pass, status remains `IMPLEMENTED_PENDING_NATURAL_VERIFICATION`.

## Known limitations

TW V1 production snapshots currently provide intraday high/low rather than a
complete minute sequence. When sequence is essential and unavailable, the
result must remain `pending_evidence`; no ordering is guessed.
