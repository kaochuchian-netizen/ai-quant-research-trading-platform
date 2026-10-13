# AI-DEV-256B — Legacy Frozen-Evidence Replay Compatibility

## Scope and result

This repair preserves immutable frozen evidence while allowing the 17:00 unified
learning loop to replay the known pre-`learning_used` representation. It makes no
production write, does not rerun a production batch, and does not mutate a learning
state.

**Result: PASS in isolated replay.**

## Root cause

`learning_used` was added to the current frozen-prediction representation on
2026-10-02. `freeze()` always emits that key, including when its value is `null`.
The older records legitimately omit the key. Before this repair,
`validate_frozen()` read an omitted key as `None`, re-froze the object with an
explicit `learning_used: null`, and compared that new canonical object with the
stored one. The content hash and strict replay equality therefore differed and
the daily evaluator surfaced `FROZEN_REPLAY` as `BLOCKED_INPUT`.

The affected natural 17:00 runs from 2026-10-06 through 2026-10-11 failed at
the frozen-evidence admission step for both markets. The paused 13:05, 13:35,
and 23:00 windows were not part of this failure.

## Compatibility contract

`legacy_missing_learning_used_v1` is a narrow compatibility representation:

- only `FROZEN_PREDICTION` records at
  `production_evidence_accumulation_v1` qualify;
- the sole omitted field must be `learning_used`;
- every pre-existing required field must remain present;
- `prediction_frozen_at` must precede the fixed contract-introduction cutoff
  `2026-10-02T13:38:22+00:00`;
- the stored digest is verified before compatibility handling;
- expected content is re-created in the historical shape (the field is removed
  before re-stamping) and must equal the stored object byte-for-semantic-field.

The validator never adds a field to the stored value. Current-schema records
without `learning_used` fail closed with `FROZEN_LEARNING_USED_MISSING`.
Changing prediction content, outcome content, hashes, market, date, or any
other evidence field remains rejected. A current explicit `learning_used: null`
representation remains valid.

## Read-only historical replay

An isolated, in-memory replay used only immutable origin evidence envelopes and
mature outcome sidecars on Production; it did not call a batch entrypoint,
persist an artifact, or write learning state. Frozen-record validation covered
the historical origin range needed by the 2026-10-06–2026-10-11 reports:

| Market | validated frozen records | validation failures |
| --- | ---: | ---: |
| TW | 65 | 0 |
| US | 26 | 0 |

For each of 2026-10-06, 10-07, 10-08, 10-09, 10-10, and 10-11, the unified
daily evaluation replay was `VALID` for both markets. TW admitted ten stocks and
US admitted six stocks on every replay. The resulting learning artifacts were
not merely evidence diagnostics: each market produced
`DIRECTION_ERROR_OBSERVED` with an active
`AVOID_REPEATING_MATURE_DIRECTION_ERROR` candidate control. These are replay
outputs only; they were not persisted or applied to Production learning state.

## Integrity and readiness

The compatibility path is versioned and bounded to the legacy representation;
it does not suppress a hash mismatch globally and does not relax current-schema
integrity. No frozen artifact, stored hash, outcome, report, or daily artifact
was rewritten.

After this code is reviewed and deployed, the next natural 17:00 run can replay
the existing immutable evidence without restoring paused windows, rewriting
frozen artifacts, or rerunning historical TW/US batches. User-facing delivery is
intentionally outside this task.

## Validation

- 11 focused legacy compatibility tests passed.
- 163 focused production-evidence, daily-evaluation, and unified-learning tests
  passed with an isolated non-symlink temporary root.
- No secret, credential, raw prediction payload, or per-symbol price was copied
  into this document.
