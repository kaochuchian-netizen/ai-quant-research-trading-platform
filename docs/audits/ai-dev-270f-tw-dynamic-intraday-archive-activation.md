# AI-DEV-270F — TW Dynamic Intraday Archive Activation

## Scope

The existing scheduled TW 15:00 `post_close` pipeline collects immutable
intraday evidence as an isolated sidecar. It does not change the current 15:00
prediction evaluation, LINE content, or the 17:00 learning loop.

## Authoritative universe

For a session `D`, the collector selects only the admitted, scheduled
`TW/pre_open_0700` snapshot whose `effective_trading_date` is `D`. It binds the
snapshot identity, revision, payload hash, source route, ordered
`payload.tracking_symbols`, and a SHA-256 universe digest. It never reads the
current mutable watchlist and never substitutes another session.

## Archive and manifest

Each expected symbol produces exactly one terminal record:

- `ARTIFACT_READY`: immutable v2 artifact at
  `artifacts/archive/tw_intraday/1m/v2/D/SYMBOL/SHA256.json`.
- `FAILED`: structured Kbars, canonicalization, or archive-write failure.

The append-only content-addressed collection manifest is stored at
`artifacts/archive/tw_intraday/1m/v2/D/_manifests/SHA256.json`. It records
universe binding, every expected symbol, coverage, artifact digest/path, and
safe failure evidence. A partial provider failure never removes other saved
artifacts and cannot be represented as full coverage.

## Replay

Offline replay validates the manifest hash, resolves the exact natural 07:00
snapshot for the session, verifies the universe digest and identity, and
replays every saved v2 artifact without Shioaji/network access.

## Completeness and safety

Shioaji Kbars data is decoded as provider local-wall-clock nanoseconds in
`Asia/Taipei`, using BAR_END labels from 09:01 to 13:30. Sparse Kbars remains
`SPARSE_UNVERIFIED`; no zero-volume bars are synthesized and no full-path
metric is inferred. No historical backfill is part of this activation.

## Runtime isolation

Collection errors are a sidecar diagnostic and do not alter or block existing
15:00 report evaluation/delivery. The collection introduces no cron, no
notification, no 17:00 consumer, and no modification to the known reversed
2337 prediction interval.
