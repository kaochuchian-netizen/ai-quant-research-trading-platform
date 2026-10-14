# AI-DEV-270A — TW Authoritative 1-Minute Intraday Data Foundation

## Scope

This is an offline foundation only. It does not collect production data, alter
the 15:00 or 17:00 evaluators, backfill historical artifacts, enable a
scheduler, or deliver notifications.

## Canonical artifact

`tw_intraday_1m_artifact_v1` holds one symbol and one authoritative TW trading
session. Its one-minute bars use Asia/Taipei `BAR_OPEN_TIMESTAMP_HALF_OPEN_1M`:
the grid starts at the calendar `open_at` and ends immediately before
`close_at`. The grid comes exclusively from the pinned 251D TWSE calendar;
there is no weekday or inferred lunch-break rule.

Each bar has market/symbol/session provenance, source and source revision,
source timestamp, OHLCV, and the artifact retains the calendar identity,
availability time, expected/minute coverage, source digest, and content hash.
Invalid timestamps, out-of-session bars, incomplete/future bars, bad geometry,
negative volume, wrong symbols, and conflicting duplicates fail closed.

## Completeness and archive

The artifact reports `COMPLETE`, `PARTIAL`, or `UNAVAILABLE`; absent bars are
recorded as missing timestamps and are never forward-filled. Immutable files
are content addressed at:

`artifacts/archive/tw_intraday/1m/YYYY-MM-DD/SYMBOL/SHA256.json`

There is no mutable latest alias. Replay validates the archive identity,
artifact digest, calendar binding, normalized ordered bars, and completeness
without provider or network access.

## Provider boundary

`fetch_shioaji_1m_rows` is a narrow adapter around the existing Shioaji
`api.kbars(contract, start, end)` interface. It performs no login and no
persistence. Production activation must separately prove that the deployed
provider returns genuine one-minute same-session bars, including timestamp and
volume semantics; `api.snapshots()` is not considered a minute-history source.

## Offline metrics

For complete artifacts only, the pure metrics function produces session
high/low, close-versus-open direction, first predicted-range touch, range
occupancy, MFE, and MAE. A partial/unavailable artifact yields
`INSUFFICIENT_EVIDENCE`, never a fabricated trend. These metrics are not wired
to production decisions or learning in this task.
