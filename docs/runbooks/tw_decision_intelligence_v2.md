# TW Decision Intelligence V2 Runbook

## Purpose

TW Decision Intelligence V2 is a read-only product projection over admitted canonical TW payloads. It improves PM usefulness without changing Trading Strategy, scoring, existing ranking, factor weights or the prediction model.

## Canonical flow

`admitted TW payload → existing canonical decision/lifecycle → tw_decision_intelligence_v2 → Dashboard / Archive / Email preview / LINE preview / Operations`

One `decision_identity` is deterministically derived from the payload projection. Channel adapters may shorten text, but do not recompute categories, confidence, coverage or ranks.

## Coverage registry

Each symbol reports Technical, Trend, Market Breadth, Gap, Volume, Event, News, Sector, ETF, ADR, Macro, Chip and Fundamental as `AVAILABLE`, `MISSING`, `STALE` or `NOT_APPLICABLE`. Missing evidence explicitly lowers research confidence and is never translated into a neutral view.

## Stock-specific intelligence

Each symbol contains market positioning, technical state, fundamental and event summary, risk factors, decision reasons, confidence components, invalidation conditions, next observation and a complete coverage matrix. Generic fallback is disclosed in `template_fallback_symbols`; it is not concealed as differentiated research.

## Decision categories and ranks

The five mutually exclusive product categories are Buy Candidate, Watch Candidate, Hold Candidate, Reduce Candidate and Avoid Candidate. Opportunity, Research and Risk ranks are deterministic presentation-only reading priorities. They do not replace or modify the repository's strategy eligibility, ranking algorithm or scores.

## Window intelligence

- 07:00: three opportunity reads, three risks, best watch, best ETF, avoid sectors and one-line market narrative.
- 13:05: breakout, breakdown, momentum, intraday strength/weakness and risk update.
- 13:35: hold view, overnight risks, truthful Gap availability, late-session flow and next-day priorities.
- 15:00: prediction/trade distributions, direction/entry/exit review, confidence calibration, error attribution, unused/missing evidence and non-automatic learning candidates.

## Confidence and conflict

Confidence explanation lists Technical, News, Macro, Coverage and Risk components plus supporting and limiting evidence. Conflicts remain visible and cap interpretation; opposite evidence is not averaged away.

## PM acceptance answers

`pm_daily_summary` answers the best single read, true no-trade reason, largest risk, largest opportunity and next observation. `market_intelligence` exposes supporting evidence, conflicts, coverage and disclosed template fallbacks. Answers are batch-specific and must not be hard-coded.

## Rendering and parity

Dashboard and Archive render the V2 hierarchy. Email/LINE previews append compact lines from the same projection. Operations stores the complete bundle and identity. Parity compares the V2 identity, symbol partition, categories, ranks and core summary.

## Validation

Run:

```bash
./venv/bin/python scripts/orchestrator/validate_ai_dev_198_tw_decision_intelligence_v2.py --pretty
```

The gate includes positive and negative fixtures for coverage truthfulness, differentiation, rank partitions, four-window inventory, 15:00 attribution, identity corruption, invalid coverage status, category overlap and TW/US isolation.

## Natural verification

Status remains `IMPLEMENTED_PENDING_NATURAL_VERIFICATION` until a complete natural TW four-window chain demonstrates useful differentiation, truthful evidence gaps, coherent window intelligence and five-channel identity within the governance SLA.

## Rollback

Revert the implementation commit. The additive V2 fields disappear and existing Decision Story/V4 behavior remains. Do not rewrite admitted snapshots or production history.

## Known limitations

No new provider is introduced. Breadth, sector, ETF, ADR, Macro, Chip or Fundamental remain missing when absent from the admitted canonical payload. Presentation ranks improve reading order only and cannot promise a trade opportunity.
