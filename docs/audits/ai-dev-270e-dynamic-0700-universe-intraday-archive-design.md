# AI-DEV-270E — Dynamic 07:00 universe to 15:00 intraday archive design

## Authoritative source

The sole source for one TW session is that session's admitted immutable
`window_snapshot_archive_v1` snapshot with `market=TW` and
`window=pre_open_0700`. Its `payload.tracking_symbols` is used in its recorded
order. The 15:00 consumer must receive this snapshot explicitly; it must never
resolve a mutable current watchlist or a `latest` alias for a different date.

`tw_intraday_session_universe_v1` binds the following into a SHA-256 digest:

- trading session;
- ordered, exact numeric TW identities (4, 5 or 6 digits, preserving zeroes);
- 07:00 snapshot id, revision, payload hash and source route.

The bound object is rejected for an unadmitted/missing artifact, a different
session, duplicate symbols, invalid identities, digest mismatch or source
snapshot mismatch.

## Future 15:00 collection boundary

`build_1500_collection_plan` is an in-memory orchestration boundary. For each
and every bound symbol it invokes the injected Kbars reader and the
`tw_intraday_1m_artifact_v2` builder. Each symbol has exactly one terminal
record: `ARTIFACT_READY` or a structured failure (`KBARS_FAILURE`, canonical
artifact failure, or identity mismatch). It reports the frozen expected
universe, Kbars success count, artifact success count, failures, artifact
coverage and terminal-result coverage.

It performs no archive write. A later approved activation must persist only
successful content-addressed v2 artifacts plus the plan's immutable universe
binding and failure evidence. It must reject a plan where any expected symbol
has no terminal result.

## Sparse semantics and replay

A ready v2 artifact can be `SPARSE_UNVERIFIED`; this remains valid observed
Kbars evidence, never a claim of a complete price path. Offline replay combines
the historical 07:00 snapshot with the bound universe digest and saved per
symbol artifacts to reconstruct the expected symbols without network access.

Runtime activation, scheduler changes, 15:00/17:00 integration and production
archive writes remain out of scope.
