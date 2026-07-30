# AI-DEV Task Package V2

Task ID: AI-DEV-199

## Platform Context
Institutional-grade AI Quant Research & Trading Platform with traceable research reasoning.

## Current Phase
Phase 1 remains IN_PROGRESS under the governance registry; AI-DEV-199 is a Phase 2 foundation implementation and does not advance the registry prematurely.

## Phase Objective
Establish a reusable Research Intelligence reasoning foundation before adding knowledge volume or learning behavior.

## Task Role
Add a market-agnostic, read-only Evidence-to-Reasoning-to-Hypothesis layer.

## User-visible Target
Future research conclusions can answer why, why not, supporting evidence, opposing evidence, assumptions and unknowns.

## Production Target
Provide a deterministic projection contract reusable by TW and US without changing current production decisions.

## Problem
TW and US have evidence and presentation projections but no common traceable reasoning and hypothesis contract.

## Root Cause
Existing institutional research is market-specific and existing decision intelligence focuses on product presentation. Neither owns a reusable research-only reasoning chain.

## Scope
Evidence normalization, long-lived knowledge, reasoning chains, bidirectional evidence, hypotheses, confidence explanation, counter-arguments, market narrative and post-close review hooks.

## Non-goals
No strategy, scoring, ranking, prediction, scheduler, service, database, secret, notification or production delivery change.

## Implementation Contract
`app/research` is additive and read-only. It adapts existing evidence, exports no trade action and performs no automatic learning.

## Evidence Contract
All evidence has market, class, source, timestamps, reliability, confidence, coverage, freshness and traceable identity. Duplicate clusters count once and cross-market evidence fails.

## Rendering Contract
No production renderer changes. Consumers may later present the canonical conclusion, supporting/opposing/missing evidence, counter-argument, hypothesis and narrative without recomputation.

## Engineering Gate
Compile, diff check, positive/negative semantic validator, governance validation and AI-DEV-190–198 regressions must pass.

## Product Quality Gate
Evidence integrity, traceability, conflict analysis, hypothesis completeness, research/trade separation, narrative synthesis and TW/US isolation require PASS.

## Operational Gate
No production pipeline, publish, Email/LINE, trading, scheduler, secrets, database or immutable-history mutation.

## Natural Verification
Not required for the framework-only V1. Production adoption is deferred and must receive its own governed natural-verification plan.

## Completion
The framework may close after merge, CI and post-merge deterministic validation because no production behavior changes.

## Phase Contribution
Creates the stable substrate for Phase 2 knowledge expansion and later controlled learning without rule sprawl.

## Limitations
Representative knowledge only; no new providers; no production decision integration; no model performance claim.

## Deferred Scope
Complete company knowledge, Knowledge Graph, production consumer integration, Learning Engine and natural production observation.

## Completion Report
Answer all eight PM questions and report identities, semantic tests, regressions, model-boundary evidence, limitations and safety.

## Safety
Existing runtime/generated artifacts remain untouched and unstaged. No production side effect is authorized or required.
