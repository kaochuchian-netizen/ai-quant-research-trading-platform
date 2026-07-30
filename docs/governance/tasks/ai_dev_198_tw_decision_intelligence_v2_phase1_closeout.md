# AI-DEV Task Package V2

Task ID: AI-DEV-198

## Platform Context
Institutional-grade AI Quant Research & Trading Platform with truthful, explainable and daily-usable TW decisions.

## Current Phase
Phase 1 remains IN_PROGRESS. This task is the deterministic product-quality closeout implementation; natural verification remains required.

## Phase Objective
Establish the TW Decision Intelligence V2 product baseline without changing investment-model behavior.

## Task Role
Project existing TW evidence and canonical decisions into differentiated research, PM reading priorities, window intelligence and review attribution.

## User-visible Target
Every TW formal window explains the strongest opportunity, largest risk, per-symbol differences, evidence coverage, confidence limits and next observation.

## Production Target
Dashboard, Archive, Email preview, LINE preview and Operations consume one deterministic TW Decision Intelligence identity from the admitted payload.

## Problem
Existing lifecycle correctness does not provide per-symbol coverage, differentiated research, presentation-only PM ranks, window-specific intelligence or complete 15:00 attribution.

## Root Cause
The canonical Decision Story and V4 presentation focus on lifecycle and aggregate counts. Specialized notification formatters bypass a common richer TW projection, while missing evidence is not exposed as a per-symbol research registry.

## Scope
Coverage registry, stock-specific intelligence, presentation-only opportunity/research/risk ranks, five candidate categories, four-window intelligence, prediction review, confidence explanation, breadth/sector narrative, PM summary and five-channel identity.

## Non-goals
No strategy, strategy ranking, scoring, factor weights, prediction model, scheduler, delivery runtime, credentials, database, backfill or window topology changes.

## Implementation Contract
`tw_decision_intelligence_v2` is an additive read-only projection built after the existing canonical strategy output. Ranks prioritize PM reading and never write back to eligibility or actions.

## Evidence Contract
Each symbol exposes Technical, Trend, Breadth, Gap, Volume, Event, News, Sector, ETF, ADR, Macro, Chip and Fundamental as AVAILABLE, MISSING, STALE or NOT_APPLICABLE with source and decision impact.

## Rendering Contract
The primary hierarchy is PM summary, opportunity/risk/read order, per-symbol category and confidence, coverage gaps, window intelligence and supporting details. Missing is never rendered as neutral.

## Engineering Gate
Compile, diff check, deterministic positive/negative semantic matrix, governance, TW/US regressions, branch CI and post-merge validation must pass.

## Product Quality Gate
Research Coverage, Decision Diversity, Stock Differentiation, Decision Ranking, Prediction Review, Explainability, Continuity, Parity, Truthfulness, Readability and Localization must pass or disclose a bounded limitation.

## Operational Gate
No production pipeline, real Email/LINE, trading, scheduler, secrets, database, immutable-history rewrite or existing-artifact mutation.

## Natural Verification
Observe the next complete TW 07:00 → 13:05 → 13:35 → 15:00 natural chain within 2–5 trading days for differentiation, truthful coverage, useful PM priorities, review attribution and five-channel identity.

## Completion
After merge and deterministic post-merge validation the status is IMPLEMENTED_PENDING_NATURAL_VERIFICATION, not CLOSED.

## Phase Contribution
Supplies the final TW product-quality baseline for decision usefulness, explainability, evidence transparency, continuity and daily PM review.

## Limitations
The task does not add providers or improve model performance. A missing source remains missing; presentation ranks are not investment recommendations or strategy ranks.

## Deferred Scope
Natural Phase 1 exit, provider expansion, strategy/ranking changes, model learning and Phase 2 research intelligence remain separate governed work.

## Completion Report
Report PM acceptance answers, coverage and conflicts, remaining templates, model-boundary evidence, five-channel identity, quality gates, limitations and natural verification plan.

## Safety
No production notifications, trading, secrets, scheduler, infrastructure, database, immutable snapshots, backfill or unrelated dirty-artifact changes.
