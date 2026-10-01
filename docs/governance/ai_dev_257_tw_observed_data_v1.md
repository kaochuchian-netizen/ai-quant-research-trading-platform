# AI-DEV-257 — TW observed data and LINE completeness

## Scope and delivery
PR-only, no merge/deployment, no production rerun/send/refresh/DB/scheduler mutation.
LINE and timestamp correctness plus bounded historical requests are executable changes.
Minute retention and actual-trend classification are OFFLINE_DESIGN_ONLY, not activated.
Base: 4087f0e863c9dbfd430d33890dcc31d4fe1cc935.

## Read-only incident evidence (2026-10-01)
13:35 requested ten symbols, admitted eight. The immutable archive had all eight
snapshot OHLCV fields but no actual_direction. The new 255D renderer was present;
missing actual trend was not an old-HTML mapping problem. No stored minute sequence
exists to retrospectively infer path labels. Original artifacts stay unchanged.
LINE formatter produced 580 characters; wrapper kept only the last 520. Hash of
that suffix matched delivery provenance. Header and first symbol/partial range
were lost. This is application truncation, not a platform receive-size failure.

Historical refresh at 07:00 requested a 180-day lookback in one Kbars request.
All ten provider requests failed with BadRequestError: date range must not exceed
30 days. Eight symbols had usable fallback. 009816 and 00878 .TW fallback was
STALE (122 rows, latest 09-29); .TWO was empty. Existing CSV was also 09-29.
Expected completed session was 09-30. Afternoon intentionally skips daily refresh;
existing-but-stale history is not overwritten by missing-symbol bootstrap.
Admission is correct and remains unchanged. The fix partitions the same 180-day
lookback into <=30-date calls, overlaps boundary dates, sorts and removes identical
bars; conflicting boundary revisions fail closed. No claim of production recovery
before deployment/natural provider evidence. No automatic retry or stale allowance.

## LINE contract
build_line_message returns complete canonical presentation, without the 520-char
suffix limit. Each Unicode scalar is retained; <=5000 UTF-16 units per message,
conservative for astral characters. Chunks concatenate exactly to the original.
Each chunk uses the existing sender once; no recipient/config changes. Ordered
chunk digests/counts and completed count are returned. Failure may be partial per
recipient and is never success or automatically retried. Existing transport handles
recipient errors. The caller records sanitized partial progress without token data.

The immutable report payload now includes notification_universe and
notification_exclusions from that batch's historical admission, not a fresh live
watchlist lookup. Admitted symbols retain the same canonical card; excluded symbols
receive an explicit Traditional Chinese explanation, never fabricated analysis.
Unexplained omissions and duplicate cards fail closed before transport. Accounting
covers all TW windows, not only 07:00. Older artifacts without universe evidence
cannot retrospectively prove excluded-symbol completeness.

## Timestamp contract
Source raw time remains preserved. Unix seconds/milliseconds/microseconds/nanoseconds
are decoded as UTC instants and converted to Asia/Taipei; explicit offsets are honored.
Naive exchange datetimes require declared Asia/Taipei. Unknown numeric precision,
malformed times and future times cannot be fresh. Captured-at is frozen once for
snapshot normalization, not relabeled with each stock's later analysis timestamp.
Same-session/non-future freshness includes age_seconds and a basis stating that it
is NOT a tick-recency SLA. Prior-date data is stale. The observed card cannot expose
invalid normalized time as market_data_as_of or claim complete time evidence.

The incident raw integer 1790861400000000000 decodes as 21:30 Asia/Taipei under
Unix semantics, after the 13:35 capture. Previous code simply tested nonempty.
A hypothetical exchange-wall-clock encoding would yield 13:30, but this is NOT
proven for the deployed SDK/provider; no subtract-eight-hour heuristic is permitted.
The official current snapshot reference describes integer Unix timestamps. Preserve
and flag this contradiction until version-specific provider evidence resolves it.
This PR fixes false freshness, not an unproven vendor timezone transformation.

## Minute retention contract
Canonical machine contract: config/governance/tw_observed_minute_contract_v1.json.
Reuse 251D immutable authoritative TWSE calendar and existing window archive owner.
Store OHLCV as long-term compressed columnar content-addressed partitions referenced
by reports. Do not duplicate report persistence or write a DB. Full requested
watchlist inventory includes explicit missing reasons. Sort timezone-aware bars;
dedup only identical rows; conflicting timestamp revisions fail closed. Source
revision/digest, availability, retrieval, price-adjustment and volume units are
mandatory. Changed evidence creates a new immutable revision linked to predecessor;
no overwrites, no current-price substitution, no synthetic forward fills.

Authoritative calendar defines session bounds; provider start/end bar convention,
closing auction and no-trade grid must be separately approved. Coverage denominators
must use that grid, not count returned bars as complete. Preserve original precision
and compute chronological replay using explicit as_of and bar availability. Raw
retention, legal/provider permissions and backups are activation decisions. Estimated
10 symbols x 270 bars x 250 sessions x 100–200 bytes = 67.5–135 MB/year before
metadata/backups; this is planning arithmetic, not measured provider compression.

## Actual-trend contract
Separate OBSERVED_SESSION_PATH_NOT_PREDICTION_OUTCOME. Read saved admitted bars,
prior-session close provenance and explicit versioned flat_band in price units.
No prediction, target, tactical label or evaluator outcome is an input. Rules and
priority are in JSON: open-low-rise, open-high-fall, bullish, bearish, sideways.
These are net open-to-end descriptions, not monotonic-path claims. Equality belongs
to the explicit band; missing data yields INSUFFICIENT_EVIDENCE, never sideways.
The parameter has NO production default; approval and frozen parameter version are
required before activation. The offline reference supports synthetic replay and
boundary tests only; it is not imported by production producers or Dashboard.

Use chronological splits, fixed pre-evaluation parameters, identical source/calendar
revisions, coverage and confusion matrices to evaluate repeatability/stability.
Do not optimize the band against future production outcomes. Existing session review
and 251A/B frozen-reference outcome semantics remain unchanged.

## Validation and rollback
Offline fake transport/provider tests only. Regress existing 255/255D, TW and registry
validators; no secrets/production raw payload committed. Rollback of a future approved
code deployment is the prior approved commit; existing evidence is never rewritten.
Partial LINE delivery cannot be unsent; no automatic whole-message resend is added.
Natural validation remains pending. No production activation in this task.

## Primary references
- https://sinotrade.github.io/tutor/market_data/snapshot/
- https://sinotrade.github.io/tutor/market_data/historical/
- https://developers.line.biz/en/reference/messaging-api/#text-message
- https://developers.line.biz/en/docs/messaging-api/sending-messages/
