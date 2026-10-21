# AI-DEV-282 Codex full-batch rerun contract

`codex_full_batch_rerun.py` is separate from the Portal bridge. It records one
of three explicit modes: `LIVE_RERUN`, `HISTORICAL_RECOMPUTE`, or
`FROZEN_REPLAY`. Each isolated receipt records every stage and whether that
stage executed or used frozen evidence. Default operation has no notification,
publication, archive, scheduler, database, or trading write path.

A future production activation must use the existing market-specific pipeline
entrypoints and obtain explicit PM approval for market, window, date,
recipients, and duplicate-delivery risk. This task supplies only the isolated
orchestration and evidence contract.
