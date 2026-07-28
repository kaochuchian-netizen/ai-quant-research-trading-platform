# AI-DEV Task Package V2

Task ID: AI-DEV-195

## Platform Context
Institutional-grade AI Quant Research & Trading Platform with trustworthy daily research, evidence and lifecycle continuity.

## Current Phase
Phase 1 — Product Quality Consolidation.

## Phase Objective
Establish the V1 Product Baseline across all formal TW and US windows.

## Task Role
Unify Evidence → Interpretation → Decision → Action → Next Trigger → Outcome as one readable Decision Story.

## User-visible Target
Every formal report leads with current view, action, reasons, confidence explanation, change and next trigger.

## Production Target
Dashboard, LINE, Email, Archive and Operations derive semantics from one canonical projection and hash.

## Problem
Existing window projections emphasize counts while evidence, confidence limitations, lifecycle change and missing-data impact remain fragmented.

## Root Cause
The shared V4 presentation boundary classifies cards, but does not expose a complete canonical decision story; adapters can emphasize different fragments.

## Scope
Extend the existing canonical projection, integrate five channel adapters, add semantic validation, governance evidence and conservative health tracking.

## Non-goals
No strategy, factor, ranking, scoring, prediction, scheduler, delivery target, broker or production infrastructure changes.

## Implementation Contract
`daily_decision_experience_v1` contains current view/action, reason, opportunity, risk, existing confidence explanation, transition, next trigger and identity.

## Evidence Contract
Each evidence record retains market, symbol/scope, source/reference, times, freshness, class, direction, materiality, reliability and decision impact.

## Rendering Contract
Primary content is a concise Decision Story; missing data is explicit and Traditional Chinese remains the TW default.

## Engineering Gate
Compile, diff check, eight positive and five negative fixtures, governance bundle, protected regression, branch CI and post-merge gates.

## Product Quality Gate
No FAIL is permitted; deterministic evidence supports PASS or bounded CONDITIONAL_PASS for natural-production-dependent dimensions.

## Operational Gate
No-send only; no production pipeline, archive mutation, scheduler change, credentials, trading or uncontrolled publish.

## Natural Verification
Required for all seven formal windows within 2–5 trading days; deterministic fixtures do not count as natural evidence.

## Completion
After merge and deterministic post-merge validation the only permitted status is IMPLEMENTED_PENDING_NATURAL_VERIFICATION.

## Phase Contribution
Improves Decision Explainability, Evidence Traceability, Continuity, Parity, Missing-data Truthfulness and PM Daily Usability.

## Limitations
Historical immutable snapshots are not rewritten; old payloads may lack source identity fields and render safe unavailable semantics.

## Deferred Scope
Natural scenario collection, automated health telemetry and provider expansion remain tracked work.

## Completion Report
Use Completion Report V2 with repository, root cause, contracts, quality/operational gates, limitations, natural plan and phase contribution.

## Safety
No real notification, trading, secrets, scheduler, systemd, nginx, production DB writes, immutable snapshot rewrite or dirty-artifact cleanup.
