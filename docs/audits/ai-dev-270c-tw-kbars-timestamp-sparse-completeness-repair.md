# AI-DEV-270C — TW Kbars timestamp and sparse completeness repair

## Scope

This repair remains an offline foundation. It changes neither production
collection nor the 15:00 and 17:00 consumers. It does not alter a historical
artifact, activate a scheduler, send a notification, or create synthetic bars.

## Versioned contract

`tw_intraday_1m_artifact_v2` replaces the incompatible v1 artifact convention.
V1 used bar-open labels (`09:00` through `13:29`); V2 uses Shioaji Kbars
bar-end labels (`09:01` through `13:30`). V1 is deliberately rejected by V2
validation rather than reinterpreted. V2 archives below `tw_intraday/1m/v2/`
so content-addressed identities cannot collide.

## Timestamp semantics

Shioaji 1.5.4 emits integer nanoseconds. Its documented Python Kbars example
casts these values directly to `Datetime(ns)` and presents TW labels such as
`09:01`. V2 therefore decodes the numeric value as a timezone-naive provider
wall-clock datetime, then explicitly attaches `Asia/Taipei`. It never treats
the numeric value as an aware UTC epoch, and it never relies on the host
system timezone.

A `09:01` label denotes `[09:00, 09:01)` and `13:30` denotes
`[13:29, 13:30)`. The expected grid is bound to the authoritative session
calendar; no weekday or inferred lunch rule exists.

## Sparse observations and completeness

Kbars is an observed-minute series. Missing labels are retained as absent
labels with a coverage ratio; they are not called zero-trade minutes and no
zero-volume bar is synthesized.

- `COMPLETE` requires every expected label and an independently supplied
  `AUTHORITATIVE_FULL_SESSION_GRID_V1` proof.
- `SPARSE_UNVERIFIED` is the default for nonempty Kbars without a proof that
  distinguishes non-trading minutes from an incomplete provider response.
- `PARTIAL` requires an independent
  `AUTHORITATIVE_ACQUISITION_INCOMPLETE_V1` proof.
- `UNAVAILABLE` means no usable bars.

Path-dependent metrics—actual path/trend, first touch, occupancy, MFE and
MAE—fail closed with `INSUFFICIENT_EVIDENCE` for every state except
`COMPLETE`. Observed-only aggregates remain outside this path-metric API and
cannot masquerade as a complete intraday path.

## Replay and activation

The artifact includes expected, observed and absent labels/counts, coverage,
proof/provenance, calendar identity, source provenance and a deterministic
content digest. Replay is offline and validates the whole artifact.

Production ingestion and evaluation remain disabled. A later task must obtain
an authoritative source or explicit provider guarantee before it can promote
sparse Kbars data to a complete path.
