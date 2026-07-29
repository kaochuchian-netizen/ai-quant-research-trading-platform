# AI-DEV Task Package V2

Task ID: AI-DEV-196

## Platform Context
Institutional-grade AI Quant Research & Trading Platform with trustworthy scheduled daily artifacts and visible failure evidence.

## Current Phase
Phase 1 — Product Quality Consolidation.

## Phase Objective
Establish a production-usable V1 baseline whose natural batches are complete, traceable and detected when missing.

## Task Role
Remove the TW 07:00 missing-batch root cause, preserve a fail-closed recovery path, and add seven-window completeness detection.

## User-visible Target
A transient universe-source outage no longer silently leaves an old 07:00 report looking current; users receive only admitted current content.

## Production Target
The pipeline either creates one traceable canonical batch or emits an explicit no-delivery incident artifact, while an independent inspector detects stale or missing effective dates.

## Problem
The 2026-07-29 07:00 scheduled batch failed before canonical artifact creation, and prior validators did not detect the missing effective-date batch.

## Root Cause
Google Sheets returned HTTP 503, then the delivery wrapper accessed completed-only structured-card output after the failed child and raised a secondary `KeyError`.

## Scope
Single-load bounded universe fallback, failed-child incident artifact, seven-window deadline completeness inspection, deterministic validator, runbook, pending registry and health evidence.

## Non-goals
No strategy, weights, scoring, ranking, scheduler timing, delivery policy, production database, real notification, trading, Archive rewrite or renderer-only recovery.

## Implementation Contract
The Google Sheet remains universe owner; only the latest admitted immutable TW 07:00 snapshot may provide a bounded fallback, with full provenance and fail-closed behavior.

## Evidence Contract
Incident output records trigger, child return status, elapsed time, stage outcomes, no-delivery state and sanitized diagnostics.

## Rendering Contract
No failed runtime is rendered or published; an older admitted latest remains historical rather than being relabeled as current.

## Engineering Gate
Compile, diff check, positive/negative failure fixtures, seven-window completeness semantics, protected regression, branch CI and post-merge gates.

## Product Quality Gate
Correctness, truthfulness, effective-date freshness, admission safety and identity continuity must pass deterministically; natural recovery is conditional.

## Operational Gate
No-send and read-only inspection only; no scheduler, service, production database, notification, trading or immutable-history mutation.

## Natural Verification
The next eligible natural TW 07:00 and complete four-window chain must pass. AI-DEV-195 remains blocked until that evidence exists.

## Completion
After merge and deterministic post-merge validation the permitted status is `IMPLEMENTED_PENDING_NATURAL_VERIFICATION`.

## Phase Contribution
Adds missing-batch truthfulness, failure evidence, recovery resilience and natural-verification readiness across all seven windows.

## Limitations
Independent 07:05/07:10 production alert scheduling is recommended but not activated because scheduler and real-notification changes are forbidden.

## Deferred Scope
Operational deployment of the independent health timer and production alert transport requires a separately authorized task.

## Completion Report
Use Completion Report V2 with incident evidence, recovery constraint, validation matrix, quality gate, residual limitation and natural plan.

## Safety
No real notification, trading, secrets, scheduler, systemd, nginx, production DB writes, immutable snapshot rewrite or dirty-artifact cleanup.
