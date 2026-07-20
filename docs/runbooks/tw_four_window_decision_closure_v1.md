# TW Four-Window Decision Closure V1

## Scope and root cause matrix

AI-DEV-186 connects the four TW windows to one deterministic setup and observed-market chain. Before this change, 07:00 presentation discarded the already available daily tactical levels, afternoon builders used a historical daily close as a current price, 13:05 channel summaries were recomputed independently, 13:35 had no observed timestamp or proximity inputs, and 15:00 had review cards without same-day actual OHLC.

| Window | Root cause | Corrected owner |
|---|---|---|
| 07:00 | tactical levels were not copied into structured cards; raw objects reached presentation | `tw_daily_tactical` + `tw_pre_open_structured` |
| 13:05 | no observed Shioaji batch snapshot; channel-local aggregation | `tw_four_window_decision` |
| 13:35 | no observed timestamp/levels, so proximity was unknowable | `tw_four_window_decision` |
| 15:00 | review framework was disconnected from the admitted setup and same-day observed OHLC | `tw_four_window_decision` |

## Canonical setup identity and continuity

`setup_id` is a deterministic hash of market, effective trading date, symbol, strategy type, source window, and source revision. The 13:05, 13:35, and 15:00 cards retain that ID as `parent_setup_id`, plus the admitted 07:00 snapshot ID, revision, and payload hash. A changed setup requires a new revision and explicit change metadata; another symbol, window, or trading date is never used as a fallback.

## Four-window data flow

The 07:00 producer reuses the existing daily tactical runtime for entry, stop, targets, risk/reward and prediction corridor. The three observed windows batch-fetch Shioaji snapshots and normalize current/open/high/low/volume/as-of fields. A single structured-card list and deterministic summary are persisted in runtime and immutable snapshots and then consumed by Archive, Dashboard, Email, LINE preview, and Operations provenance.

## Freshness and observed sources

07:00 labels previous-close technical/chip data separately from news, ADR, and report time. 13:05 and 13:35 require their own observed snapshot timestamp. 15:00 uses the same-day post-close snapshot OHLC. Missing data remains on the same stock card with `partial` or `unavailable`; it is never copied across symbols, windows, or days.

## Window semantics

- 07:00 ranking uses entry readiness, completeness, risk/reward, chase/event risk and symbol tie-break. Top opportunities are a qualified subset, never the whole universe.
- 13:05 computes trigger, volume state, stop/target distance and action from observed values. `tw_window_summary` is the only count source.
- 13:35 groups `must_act`-equivalent reduce risk, hold, avoid overnight, watch tomorrow, no-trade and unavailable decisions. Priority is a deterministic subset.
- 15:00 binds the admitted prediction to actual OHLC and derives hit, fail, not-triggered, no-trade or pending. MFE/MAE are measured from trigger price; they are not applicable when entry never triggered and pending only when actual evidence is incomplete.

## Admission safety

Tracking with no cards is rejected. All 13:05 prices unavailable, all 13:35 timestamp/proximity unavailable, or all 15:00 actual OHLC unavailable cannot be admitted as a complete report. Partial symbol failures remain explicit. Immutable historical snapshots are never rewritten or backfilled.

## Presentation and news quality

Public presentation sanitizes provider errors, Python object representations, raw lists/dicts and internal enums. Diagnostics retain only sanitized category, source, attempted time and retry count. News source classes rank official disclosure, exchange/regulator and company IR above media; social/unverified content cannot independently promote a setup.

## Cross-channel parity

All channels retain snapshot ID, revision, source payload hash, symbol set, tracking/card counts, summary counts and canonical URL. Presentation hashes differ by channel by design. Any source/count mismatch fails validation.

## Controlled verification and publish

Validators build nine deterministic cards for all four windows in temporary directories. They exercise partial sources, provider timeout sanitization, observed quote failures, trigger/target/stop outcomes, duplicate/setup mismatch, admission rejection and channel parity. No production archive, runtime, public route, Email, LINE, scheduler or trading state is touched.

After merge and CI/post-merge gates, controlled static publish may rebuild only presentations selected by the admitted snapshot resolver. Create a rollback backup first and verify public snapshot identity. Old-schema snapshots show explicit unavailable fields; never synthesize observed data.

## Natural verification and rollback

Until the next natural TW trading-day sequence proves all four windows, status is `IMPLEMENTED_PENDING_NATURAL_VERIFICATION`. Verify 07:00 sanitization/ranking, 13:05 observed parity, 13:35 same-day baseline/proximity, and 15:00 prediction/OHLC/outcome/MFE/MAE. Rollback reverts source via a normal PR and restores the controlled-publish backup; do not rewrite immutable history.

## Known limitations

Shioaji snapshot volume uses the existing 20-day daily mean prorated by session elapsed time, not a minute-for-minute historical median. A full 15:00 result may remain pending when the observed post-close snapshot is unavailable; this is an explicit source failure, not a no-trade result.
