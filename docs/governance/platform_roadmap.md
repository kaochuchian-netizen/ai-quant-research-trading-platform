# Platform Roadmap V1

## Vision

Build an institutional-grade AI Quant Research & Trading Platform that produces trustworthy, readable and actionable research every day, with explainable decisions, traceable evidence, continuous verification and maintainable operations.

Feature count is not the success metric. Daily production usefulness is.

## Phase 1 — Product Quality Consolidation

Status: current.

Objective: establish the V1 Product Baseline across all TW and US production windows.

Exit outcomes:

- public content is correct, complete enough for its stated decision and honest about missing data;
- decision and confidence explanations are user-readable;
- evidence and source identity are traceable;
- cross-window lifecycle continuity and cross-channel parity pass;
- natural verification can close within a bounded SLA;
- recurring defect classes are blocked by regression gates.

Phase 1 closes only through `phase_completion_standard.md` and the machine-readable phase registry. A merged PR or passing CI alone cannot close it.

## Phase 2 — Research Intelligence

Objective: deepen source coverage, research synthesis, event interpretation and source-quality ranking after the V1 Product Baseline is stable.

Entry requirement: Phase 1 must-fix items closed; accepted limitations explicitly bounded.

## Phase 3 — Decision Intelligence

Objective: improve scenario reasoning, decision confidence, portfolio context and decision explainability without weakening truthfulness.

Entry requirement: research evidence contracts and quality measurements stable.

## Phase 4 — Evaluation & Learning

Objective: connect predictions and decisions to canonical outcomes, calibration, error analysis and controlled improvement loops.

Entry requirement: source-plan identity and outcome semantics remain stable across natural batches.

## Phase 5 — Institutional-grade Platform

Objective: mature reliability, governance, auditability, operational resilience and institutional workflows.

Entry requirement: phase health, technical debt, incident rate and production usability meet approved targets.

## Roadmap governance

- Every AI-DEV declares current phase and phase contribution.
- Enhancements cannot bypass an unresolved must-fix item in the same contract area.
- Phase exit requires evidence across engineering, product, operations and user value.
- Deferred work has an owner, rationale and target phase; it is never hidden inside “known limitations.”
