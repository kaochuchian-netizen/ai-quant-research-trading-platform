# AI-DEV-253 US Native Session Direction V1

US_PREOPEN_SESSION_DIRECTION_V1 is a separate prediction/evaluation producer.
The approved architecture permits reuse of governed prediction-side rules with US
features. It does not project us_daily_tactical_v1 or alter its behavior.

## Fixed prediction rule
Reuse the exact MA5/MA10 comparison extracted from
tw_ohlcv_range_direction_v2 into app/evaluation/direction_signal.py.
MA5 > MA10 * 1.002 => UP; MA5 < MA10 * 0.998 => DOWN.
Otherwise NO_FORECAST. Neutral is not a forecast of the canonical FLAT band.
No new weights, tuning, candidate selection, news features or event probability.
TW calls the same helper; its existing neutral behavior stays unchanged.
Wilder ATR14 is only the canonical outcome band, not an input threshold for the model.

## Evidence and time
The existing US client supplies OHLCV and quote; there is no new fetcher.
At capture, retain at most its last 260 daily rows that are completed and covered
by the pinned authoritative US calendar. Require at least 15 bars for Wilder ATR,
and the most recent completed trading session. Insufficient lookback abstains;
malformed/missing required inputs or stale history fail closed.
MA5/10 use last completed closes. Freeze source observation, reference source/as-of,
available_at, derived features, calculation versions, producer identity, calendar
and SHA-256 digests before the authoritative session open. US session is explicit,
not Taipei date. The NY date of freeze must match it. Holidays/special closures
are rejected; DST/early-close times come from 251D.
Replay uses recorded observation/time/calendar, never a current clock or network.

## Persistence / compatibility
Use existing window archive .frozen receipts and observations, .evidence report
bindings, .outcome final-close evidence, .assessment 252 results.
No second market-data acquisition or scoring pipeline.
Original report payloads are unchanged. Evidence links canonical snapshot identity,
revision, digest and producer identity; the pre-open source quote digest must match.
Immutable attempt receipts expose interrupted capture. First origin receipt per
symbol/session wins; later windows may only reference it. Same origin/event/horizon
is one sample. Manual rerun and nonproduction/dry-run calls do not capture.
Historical range/monthly trends never become direction samples.
Legacy capability remains unavailable absent a future receipt.

## Maturity / replay
Only canonical UP/DOWN predictions enter 252. NO_FORECAST is neither FLAT nor a
failed prediction; it has zero samples. Genuine invalid prerequisites BLOCKED_INPUT.
Outcomes come from already fetched immutable source observations after horizon close,
conservatively requiring a later dated completed bar. This can delay evaluation.
Reuse 252 market-aware freeze, outcome, assessment, 3/3 + 10/10 thresholds, 35/65
time weighting and same-stream immutable predecessor checks. No weight redistribution.
A single eligible outcome remains INSUFFICIENT_SAMPLE until cohort requirements.
No fix evidence or confidence probability is invented.

## Isolation and operational limits
Capture has a two-second best-effort budget and does not run in another thread or
over an existing caller alarm. Exceptions are logged without changing delivery.
251D/252 shadow worker limits remain unchanged. Research ranges, 1M/3M trends,
tactical labels/weights/setup/trade plans and report consumers are untouched.
No DB, scheduler, notification, watchlist, lifecycle or order mutation.
The 2026 calendar requires a separately reviewed update for later coverage.
Failure to capture means no eligible evidence, never historical reconstruction.

## Acceptance / rollback
Synthetic tests prove contracts, not production samples. Controlled production
smoke must use temporary output and label input_kind synthetic; no manual pipeline.
Production eligible accumulation starts at a natural post-deployment pre-open.
Deploy only merged CI-passing main via fast-forward, preserve runtime artifacts.
Record previous SHA and rehearse returning to it in an isolated worktree while
preserving synthetic dirty artifacts. Keep immutable production sidecars on rollback.
