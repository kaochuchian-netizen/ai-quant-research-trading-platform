# Research Reasoning Engine V1 Runbook

## Purpose

RRE V1 is a market-agnostic, read-only research projection. It turns existing evidence into a traceable research conclusion and hypothesis without producing a trade action or modifying strategy, scoring, ranking or prediction.

## Architecture

`existing evidence -> evidence normalization -> long-lived knowledge -> reasoning -> research hypothesis -> market narrative -> review hooks`

The existing Decision Engine remains the sole decision owner. RRE output is context only.

## Evidence contract

Evidence preserves market, symbol/scope, class, source, reference, publication/observation times, freshness, reliability, confidence, coverage, direction and materiality. Supported classes are market, macro, technical, fundamental, news, ETF, ADR, chip, sector, corporate and event. Cross-market evidence is rejected. Duplicate event clusters retain provenance but only their strongest primary record enters reasoning.

## Knowledge context

Knowledge is versioned repository data describing business, products, customers, supply chain, industry, long-term drivers and macro sensitivity. It cannot contain current prices, daily returns or observation timestamps. Partial knowledge is disclosed rather than generated daily.

## Reasoning contract

Every directional conclusion cites evidence IDs and exposes supporting, opposing, neutral and missing evidence. Reasoning chains link evidence to interpretation, relevant knowledge and research impact. Conflict is explicit and is never hidden by arithmetic averaging. A counter-argument and unknowns are mandatory.

## Hypothesis contract

A hypothesis requires an expected trigger and invalidation condition. It is marked `research_hypothesis_only=true`, `trade_signal=false`, and has no trade action. This distinction is a hard semantic gate.

## Confidence reasoning

Confidence discloses evidence quality, coverage, knowledge completeness, conflict and freshness. Cap reasons explain why confidence cannot be higher. RRE does not modify model scores or weights.

## Market narrative

The narrative synthesizes cross-symbol reasoning states, conflicts and largest unknowns. It never concatenates headlines and does not invent a directional narrative when coverage is insufficient.

## Review hooks

Post-close hooks reserve hypothesis, evidence, conflict and missing-evidence review. V1 does not perform automatic learning or update any production weight.

## Integration boundary

V1 is additive and does not change production pipelines, renderers, notifications, scheduler, database, strategy, ranking, scoring or prediction. Existing AI-DEV-197 US research evidence can be normalized into this common contract; existing TW evidence can do the same.

## Validation

Run:

`./venv/bin/python scripts/orchestrator/validate_ai_dev_199_research_reasoning_engine_v1.py --pretty`

The deterministic matrix covers classification, traceability, deduplication, conflict, trigger/invalidation completeness, narrative synthesis, long-lived knowledge, TW/US isolation and research/trade separation.

## Rollback

Remove the additive `app/research` package, validator and documentation. No runtime data, archive snapshot or production configuration requires migration or rollback.

## Known limitations

V1 supplies the framework and representative knowledge, not complete company knowledge or new providers. It is not wired into production decision actions. Review hooks are descriptive and automatic learning is forbidden.
