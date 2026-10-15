# AI-DEV-272 TW/US End-to-End Decision Quality Gate

## 2026-10-15 US 06:30 finding

The natural `us_post_close_review_0630` artifact contains valid actual OHLC,
an immutable 20:00 source-plan identity, and `prediction_evaluation_v2`.
Direction uses `status: evaluated` plus a boolean `hit`; it does not contain a
`result` field.  The former mobile formatter expected `result`, rendered the
direction as unavailable, and combined that with a separately read range hit
or miss.  This mixed two incompatible status representations in one user
summary.

## Gate contract

`post_close_decision_quality_gate_v1` is shared by TW 15:00 and US 06:30.
For each card it retains the prediction identity and admits a public component
only when actual low/high/close are geometrically valid and the canonical
component evaluator is admitted.  Otherwise it emits a stable reason code:
`ACTUAL_OUTCOME_MISSING_OR_INVALID`, `DIRECTION_EVALUATION_NOT_ADMITTED`, or
`RANGE_EVALUATION_NOT_ADMITTED`.

A partial card may be published only with those explicit limits.  It cannot
claim hit or miss.  The LINE formatter invokes the gate before rendering, so a
summary without either a proved result or an auditable insufficient reason is
blocked.  Full detail remains in the Dashboard evidence section.

## Scope and safety

The gate is presentation admission only.  It does not alter prediction,
range, strategy, scoring, source artifacts, schedulers, or delivery
configuration.  The natural 2026-10-15 artifact is represented by a minimal
golden fixture with its immutable source identity and actual/evaluation values.
