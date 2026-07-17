# AI-DEV-182 Production Multi-Window Audit

Observed at: 2026-07-17T16:00:00+08:00

## Executive scorecard

Overall: **54/100 — BLOCKED_BY_P0**

- consistency: 8/20 — P0 public latest lag; P0 US outcome contradiction; TW delivery hash evidence gap
- data_completeness: 15/20 — 88/116 applicable source fields detected in immutable snapshots
- decision_quality: 12/20 — seven-window rubric backed by expected/observed decision terms
- freshness: 6/15 — TW source_data_time absent; TW public routes one effective day behind
- ux_and_readability: 8/15 — US pre-market repetition/engineering wording; screenshot backend evidence gap
- operational_reliability: 5/10 — TW 13:05 timed out; remaining current natural batches observed

## TW 13:05 root cause

Scheduler triggered and the approved entrypoint started, but the pipeline reached `pipeline_timed_out` after 600 seconds. No runtime, snapshot, publish, Email, or LINE followed. Root cause: `pipeline_failure`.

## Seven-window result

- TW pre_open_0700: **FAIL** — snapshot 6e69ef59b3eced59e6ee6006166cdfda6fa488fbce4db660f033b458a1cc4278, public PASS
- TW intraday_1305: **FAIL** — snapshot eb29574bed8590f755db7c2358a93e628ec8eea677d9c033d47fcec2dd021cc1, public PASS
- TW pre_close_1335: **FAIL** — snapshot 96b140b63ca147f55522abb142919dd0a2b67d0a741f21cead43833f79e28d22, public PASS
- TW post_close_1500: **FAIL** — snapshot cd4e6f9f312c3fc4ebc0ed1531abf12fb17b45cabf8c6c2ef58f97ba9262e3ad, public PASS
- US us_pre_market_2000: **PARTIAL** — snapshot bf86d757cce854ad40ac37f6281b5821dc39ca6f721a6b7e4131a2b5f40d2093, public PASS
- US us_intraday_2300: **PARTIAL** — snapshot 8c74c44ef4d51ce2042fe84eac6b5972d95e92f77461844ae5905869d5d75bd7, public PASS
- US us_post_close_review_0630: **PARTIAL** — snapshot 6582b90fa5dd9cb0a5c7720651ce12e08f4facb79d8a3b28998773417bec0659, public PASS

## P0 findings

- **AI182-P0-001** TW 13:05 scheduled batch timed out before runtime persistence — No intraday decision or notification; 13:35 loses same-day baseline.
- **AI182-P0-002** US 06:30 pending cards are simultaneously presented as No Trade and Reviewed — Users receive a concluded No Trade result while actual outcomes remain pending.
- **AI182-P0-003** Public TW latest routes lag admitted 2026-07-17 snapshots — Public users see the previous trading day after successful production runs.

## P1 findings

- **AI182-P1-001** TW 07:00 snapshot has no stock cards and is dominated by health/contract summary — No prioritized opportunities, no-trade list, or chase-risk list.
- **AI182-P1-002** TW 13:35 lacks market-data time and same-day 13:05 baseline — Hold/avoid decisions cannot be traced to fresh market evidence or intraday change.
- **AI182-P1-003** TW 15:00 review remains mostly pending — The review explains little of the actual session result.
- **AI182-P1-004** US 23:00 volume/gap evidence uses repeated generic research wording — Users cannot tell which gaps or volume moves were actually confirmed.
- **AI182-P1-005** US 20:00 contains questionable financial units and Python date representation — Financial context can be materially misleading.
- **AI182-P1-006** TW notification payload identity is not persisted for post-delivery audit — Cross-channel source parity cannot be proven after delivery.

## P2 findings

- **AI182-P2-001** US 20:00 Email is long, repetitive, and exposes engineering wording — Core pre-market decisions are hard to locate on mobile.
- **AI182-P2-002** Required visual screenshots were not obtainable from the audit browser backend — Pixel-level typography and spacing could not be certified.

## Roadmap

1. AI-DEV-183 — integrated production correctness: batch timeout resilience, publish identity, outcome classification, financial normalization, and notification provenance evidence.
2. AI-DEV-184 — decision content and outcome quality: real window observations, review completion, continuity explanations, and source coverage.
3. AI-DEV-185 — information architecture and delivery UX: reduce repetition/noise and complete browser-based desktop/mobile visual QA.

## Safety

This audit did not execute pipelines, publish dashboards, attempt notifications or trading, change schedulers, or mutate runtime/archive snapshots.
