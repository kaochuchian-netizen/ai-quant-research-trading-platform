# AI-DEV-282 Codex full-batch rerun contract

`codex_full_batch_rerun.py` is separate from the Portal bridge. It records one
of three explicit modes: `LIVE_RERUN`, `HISTORICAL_RECOMPUTE`, or
`FROZEN_REPLAY`. Each isolated receipt records every stage and whether that
stage executed, used immutable evidence, or was blocked. The command cannot
claim `SUCCESS` from a fixture or synthetic-success runner.

The established TW and US delivery entrypoints are recorded as official
bindings. They currently lack a verified isolated-output/no-write contract, so
the Codex CLI returns `BLOCKED` with
`OFFICIAL_PIPELINE_ISOLATION_UNSUPPORTED` instead of calling them. This makes
the no-send/no-latest/no-archive/no-DB/no-trading boundary fail closed.

A future isolation-aware adapter must execute each real market-data, analysis,
evaluation, Dashboard, LINE-renderer, Email-renderer, and receipt stage and
write its declared output under the isolated output directory before a
full-pipeline acceptance can be claimed. A future production activation must
also obtain explicit PM approval for market, window, date, recipients, and
duplicate-delivery risk. This task does not authorize a Production deployment
or notification.
