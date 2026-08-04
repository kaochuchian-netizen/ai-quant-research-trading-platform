# RRE Production Integration V1 Runbook

## Purpose

AI-DEV-200 makes AI-DEV-199 the canonical daily TW research generator. It does not make RRE the owner of trading decisions.

## Production projection

The deterministic flow is:

`admitted TW payload -> TW evidence adapter -> RRE V1 -> research notes -> TW Decision Intelligence V2 -> existing Dashboard/Archive/preview/Operations adapters`

No adapter recomputes research.

## Evidence mapping

- Technical history and direction map to Technical evidence.
- ADR maps to overnight ADR evidence.
- Admitted news records preserve publisher, timestamp, URL, materiality and canonical direction.
- Existing sector, fundamental, macro, event, quote and volume fields map only when actually available.
- Missing and stale fields remain explicit unknowns.

Headline text is not used to invent direction.

## Research note

Every symbol provides:

- research summary;
- company context;
- supporting evidence;
- opposing evidence;
- missing and unknown evidence;
- confidence components;
- hypothesis and trigger;
- invalidation;
- counter-argument;
- current-window research update;
- source identity.

The note records `decision_modified=false`.

## Four-window continuity

- 07:00 establishes the daily research hypothesis.
- 13:05 checks the hypothesis against canonical trigger and observed-market evidence.
- 13:35 records the closing/overnight research state.
- 15:00 reviews the hypothesis, evidence conflict and missing evidence.

Review hooks never perform automatic learning.

## Rendering

The Research Brief is rendered before legacy Decision Intelligence. Detailed legacy lifecycle and coverage sections remain available for operational traceability.

Email and LINE preview content continues through the existing adapter. Its four compact TW V2 lines now consume RRE-derived brief fields; notification runtime is unchanged.

## Identity parity

`production_research_identity` and the underlying `research_reasoning_identity` are stored inside the canonical TW V2 projection. Dashboard, Archive, previews and Operations consume the same projection.

## Model boundary

RRE exports no trade action. Strategy, factor weights, scoring, ranking, prediction, scheduler, notification runtime and database are unchanged.

## Validation

Run:

`./venv/bin/python scripts/orchestrator/validate_ai_dev_200_rre_production_integration_v1.py --pretty`

The validator covers four-window generation, 2330 ADR reasoning, 4743 bullish-news/no-trade separation, knowledge rendering, supporting/opposing/missing evidence, hypothesis, counter-argument, continuity, renderer, previews, Operations identity and negative missing-data behavior.

## Rollback

Revert the AI-DEV-200 merge commit. No database or snapshot migration is required. Immutable archive history is not rewritten.

## Natural verification

Within 2-5 trading days inspect the next complete TW chain. Verify all nine notes, RRE identities, non-template brief, per-window updates and Dashboard/Archive/preview/Operations parity.

## Known limitations

RRE cannot create evidence that providers did not supply. Knowledge V1 is representative. Legacy lifecycle and operational detail remain below the research-first section for traceability.
