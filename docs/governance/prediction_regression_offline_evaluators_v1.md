# AI-DEV-251B offline evaluators

The [251A canonical contract](../../config/governance/prediction_regression_data_contract_v1.json)
owns all weights, metric formulas and entity ownership. Its only amendment here is
the user-confirmed `improvement.interpretation`; formulas and weights are unchanged.
`app/evaluation/offline_review_evaluators.py` is a pure, offline derived layer under
the existing evaluation owner. It does not replace legacy evaluators, ingest sources,
store ledgers, generate immutable reports, or integrate production.

## Callable surface and input boundary

`evaluate_prediction`, `evaluate_improvement`, `evaluate_strategy` accept caller-supplied
rows and explicit market/symbol/strategy/horizon/report-date/calendar context.
`evaluate_stock` projects their results into `user_facing` and `internal_evidence`.
No CLI or scheduler starts evaluation. The validator uses only the synthetic fixture.

Rows are temporary adapter projections of prediction/feature/outcome, hypothetical
strategy and finding/fix views. They are not another canonical storage schema.
Every scalar/aggregate field has `value`, `classification`, `role`, `as_of`,
`available_at`, `source_ref`. Roles are `signal`, `outcome`, `regret`; the evaluator
requires the correct role by metric. Signals must be available before prediction;
outcome/regret evidence must be final and available by the row's `evaluation_at`,
which cannot exceed the 17:00 Asia/Taipei report cutoff. This prevents later evidence
from being retroactively admitted to an earlier evaluation.

`session_date` denotes the final session of the declared forecast horizon, not the
prediction wall date. This skeleton admits only forecasts frozen before that horizon's
first session open. Intraday adapters need separate explicit semantics before use.
Calendar rows have market, session_date, aware open_at/close_at, source reference,
coverage_through and SHA-256 of canonical session JSON. Calendar completion, including
DST and early closes, controls TW/US selection. Missing observations are not skipped
to reach farther back for replacement samples. Last 3/10 sessions overlap intentionally.

AVAILABLE requires complete admitted evidence. PARTIAL/MISSING/AMBIGUOUS and fallback
never become guessed values or redistributed weights. Eligible windows require all
3/10 samples. Other-market/stock/strategy/horizon rows cannot fill gaps; duplicate
session candidates are ambiguous. Component/window evidence and exclusion reasons
remain internal. Floating point scores are deterministic and unrounded internally.

The adapter trusts caller attestations of Wilder ATR provenance, full-path extrema,
feasible hypothetical opportunity/cost/fill assumptions and source references; it does
not fetch, hash-verify or reconstruct original market data. Returns use fractional
units (0.05 = 5%); ATR/reference is in the same fractional unit. Timing evidence maps
each frozen required event to [hypothetical execution price, hindsight feasible price].
All required events must exist. Daily-only paths cannot establish intrabar ordering.
These limitations are explicit: `production_ready` is always false.

## Improvement semantics and evidence

The score measures regression verification and improvement-loop quality. 50 means
no net evidence of loop effectiveness. It is not the magnitude of prediction uplift.
The frozen four weights remain 25/20/40/15. The canonical example 100/50/50/100 yields
70, `DIAGNOSIS_POSITIVE_EFFECT_NEUTRAL`, and `realized_prediction_effect=NEUTRAL`.
The user explanation explicitly says this cannot be called improved prediction accuracy.
`effect_summary` separates diagnosis, realized prediction effect and recurrence.
Opposing D+3/D+10 effects are MIXED, never called sustained improvement.

Each evaluation requires a confirmed finding with immutable error reference, approved
and effective fix, frozen matched baseline (market/symbol/strategy/horizon/regime),
all first 3/10 completed sessions after the effective session, identical metric version,
and a predeclared detector with 10-session recurrence evidence. A baseline's recorded
availability/freeze must precede the fix. Cohort session closes must match the calendar.
No fix or immature evidence is PENDING; zero observable opportunities is N/A, not 0.
No causal effect is asserted without a control. No automatic fix/model/strategy action.

Time windows average daily eligible assessments; repeated assessments of the same fix
are not independent interventions. Every session retains fix_id, cohort sizes and
recurrence counts. The per-stock result retains all four time-weighted components.
There must be 3/10 daily assessments; a single mature fix is not fabricated into 10 rows.

## Output and phase boundary

User-facing output has the six requested score/action keys. Each score includes a
number or null, status, and one explanation. Improvement additionally exposes its
effect summary. Actions request evidence or review; they do not change a strategy.
Internal evidence retains component scores, source coverage, missing fields, eligible
sample counts, descriptive confidence/grade and a null predecessor ID/hash placeholder
marked `PENDING_251C`. Composite uses 40/20/40 only when all scores exist; improvement
N/A/PENDING never reweights the other categories.

This result is not an A-phase `daily_scorecard` envelope: A's no-score validation
remains unchanged. 251C must bind immutable report hashes and finding/fix history
through the existing owners. Production still lacks original feature/prediction
availability, calibrated confidence, frozen ATR, authoritative calendars, complete
US paths/benchmark/cost assumptions, approved fix cohorts and report predecessor chains.

## Validation

Run `python3 scripts/orchestrator/validate_ai_dev_251b_offline_evaluators_v1.py` and
the existing 251A contract validator. Tests cover arithmetic, the 70/NEUTRAL example,
3/10 sessions, TW/US/DST/early-close cutoff, missingness/fallback, leakage, hindsight,
fix maturity, cohort/detector matching, deterministic output, no network and user/internal
separation. Repository branch/CI gates remain required. No production data is needed.
