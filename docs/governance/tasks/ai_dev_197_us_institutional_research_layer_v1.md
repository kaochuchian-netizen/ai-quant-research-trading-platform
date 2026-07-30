# AI-DEV Task Package V2

Task ID: AI-DEV-197

## Platform Context
Institutional-grade AI Quant Research & Trading Platform with governed, traceable research evidence.

## Current Phase
Phase 1 remains IN_PROGRESS. Phase 2 remains PLANNED; this is Phase 2 design and implementation preparation.

## Phase Objective
Prepare the canonical Research Intelligence foundation without prematurely changing the roadmap phase status.

## Task Role
Build an Institutional Research Layer that is a read-only context provider to the existing Decision Engine.

## User-visible Target
US research cards disclose sources, quality, time, coverage, conflict, synthesis, limitations and research identity.

## Production Target
The 20:00 admitted research bundle is reused by 23:00 and 06:30, with one identity across Dashboard, Archive, Email preview, LINE preview and Operations.

## Problem
The existing layer collects SEC, yfinance fundamentals, earnings and headline metadata, but lacks a governed provider registry, canonical evidence clustering, knowledge, transparent coverage and conflict-aware synthesis.

## Root Cause
AI-DEV-172 research factors were designed for initial decision integration. They directly feed existing scoring and prediction, so replacing them would violate the Decision read-only boundary; an additive canonical projection is required.

## Scope
Provider registry, canonical evidence, company knowledge, coverage, conflict, deduplication, synthesis, decision-context export, three-window identity, 06:30 diagnosis, five-channel rendering and validators.

## Non-goals
No strategy, ranking, scoring, prediction, weights, scheduler, notification runtime, credentials, production database, backfill, trading or TW changes.

## Implementation Contract
`us_institutional_research_bundle_v1` is attached after existing score, prediction and strategy construction. The exported trade action is always null.

## Evidence Contract
Every evidence item has an ID, cluster, provider, tier, quality, source reference, time, freshness, type, direction, materiality, relevance, confidence and official-confirmation state.

## Rendering Contract
US Dashboard, Archive, Email preview, LINE preview and Operations expose the same research identity and aggregate; unavailable or unlicensed providers remain explicit.

## Engineering Gate
Compile, diff check, deterministic positive/negative bundle matrix, AST boundary comparison, governance, US/TW regression, branch CI and post-merge validation.

## Product Quality Gate
Research Explainability, Evidence Integrity, Coverage Transparency, Source Truthfulness, Duplicate Detection, Knowledge Consistency, Conflict Analysis, Cross-source Verification, Research Identity and Cross-channel Parity must pass.

## Operational Gate
No production pipeline, real Email/LINE, trading, scheduler change, secrets, backfill, immutable-history rewrite or TW runtime mutation.

## Natural Verification
Observe the next complete US 20:00 → 23:00 → 06:30 chain within 2–5 trading days for bundle completeness, identity continuity, coverage truthfulness, conflict logic and channel parity.

## Completion
After merge and deterministic post-merge validation, status is IMPLEMENTED_PENDING_NATURAL_VERIFICATION.

## Phase Contribution
Creates the only governed research foundation intended for later Phase 3 Decision Intelligence and Phase 4 Controlled Learning.

## Limitations
Reuters, Bloomberg, AP and other commercial providers are registry-only until licensed; no provider is represented as connected without repository evidence.

## Deferred Scope
Provider licensing/connectors, production macro/options/analyst/insider feeds, Decision Engine adoption and controlled learning remain future work.

## Completion Report
Report actual connected versus registry-only providers, coverage, deduplicated events, single-source stance, Decision Engine boundary evidence, validation, limitations and natural plan.

## Safety
No production notifications, trading, secrets, scheduler, infrastructure, database, immutable snapshots, backfill or TW pipeline changes.
