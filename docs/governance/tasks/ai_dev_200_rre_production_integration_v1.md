# AI-DEV Task Package V2

Task ID: AI-DEV-200

## Platform Context
Institutional-grade AI Quant Research & Trading Platform with research-first daily TW content.

## Current Phase
Phase 2 Research Intelligence integration while existing Phase 1 natural-verification governance remains truthful.

## Phase Objective
Adopt AI-DEV-199 RRE as the canonical daily research generator before the Decision Intelligence presentation layer.

## Task Role
Wire admitted TW evidence into RRE notes for 07:00, 13:05, 13:35 and 15:00.

## User-visible Target
The first report section reads like an analyst brief with supporting, opposing and missing evidence, hypothesis, invalidation and counter-argument.

## Production Target
Dashboard, Archive, Email/LINE previews and Operations obtain the same RRE identity through the existing canonical TW decision-intelligence projection.

## Problem
AI-DEV-199 existed only as a library and validator; natural TW reports still used legacy coverage-first projection.

## Root Cause
`build_tw_decision_intelligence_v2()` never invoked `app.research`, so no production projection or renderer could consume RRE output.

## Scope
TW evidence adapter, per-symbol research notes, knowledge injection, research brief, four-window research updates, renderer, shared projection identity, deterministic validators and runbook.

## Non-goals
No strategy, scoring, ranking, prediction, scheduler, database, notification runtime, provider or trading change.

## Implementation Contract
`Evidence -> RRE -> Research Note -> existing Decision projection -> channel adapters`. Decision remains a read-only consumer and RRE cannot promote eligibility.

## Evidence Contract
Only evidence already present in the admitted payload is normalized. Missing data remains explicit and cannot be inferred as neutral.

## Rendering Contract
Research Brief and nine compact Institutional Research Notes precede legacy decision detail. Each note shows company context, supporting/opposing/missing evidence, hypothesis, trigger, invalidation and counter-argument.

## Engineering Gate
Compile, diff check, AI-DEV-200 positive/negative matrix, governance, AI-DEV-190–199 regressions, branch CI and post-merge validation.

## Product Quality Gate
Research generation, evidence rendering, knowledge injection, narrative, hypothesis, counter-argument, continuity, identity parity, truthfulness and research/decision separation.

## Operational Gate
No production pipeline, publish, real notification, trading, scheduler, secrets, database or immutable-history mutation.

## Natural Verification
Observe the next complete TW 07:00 -> 13:05 -> 13:35 -> 15:00 chain within 2-5 trading days.

## Completion
After merge and deterministic validation the status is IMPLEMENTED_PENDING_NATURAL_VERIFICATION.

## Phase Contribution
Turns the Phase 2 reasoning framework into the canonical daily TW research projection without changing investment-model behavior.

## Limitations
Knowledge is representative, evidence quality remains limited by admitted sources, and no new provider or automated learning is added.

## Deferred Scope
Knowledge Graph, provider expansion, US production adoption and Learning Engine.

## Completion Report
Answer whether every note is RRE-generated, knowledge/evidence/hypothesis/counter-argument render, whether the brief is non-template, and which legacy sections remain.

## Safety
Preserve all existing runtime/generated dirty artifacts; stage only task files and perform no production side effect.
