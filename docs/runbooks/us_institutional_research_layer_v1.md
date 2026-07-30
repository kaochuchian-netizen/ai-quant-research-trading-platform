# US Institutional Research Layer V1

## Purpose

AI-DEV-197 adds a governed research projection without modifying the existing Decision Engine. The current roadmap remains Phase 1 IN_PROGRESS and Phase 2 PLANNED until governance explicitly advances it.

## Architecture

Existing SEC/yfinance/IR collectors feed a canonical provider snapshot and evidence engine. Evidence is clustered, deduplicated, joined with machine-readable company knowledge, measured for coverage, checked for directional conflict and synthesized into a research-only score. The export contains no trade action.

## Provider truthfulness

`CONNECTED` means an adapter exists. Per-bundle `AVAILABLE` additionally requires observed data. `CONFIGURED` means repository metadata exists but no retrieval is claimed. `NOT_CONFIGURED`, `NOT_LICENSED`, `SOURCE_FAILED` and `STALE` remain visible and do not fabricate coverage.

Currently implemented collectors are SEC EDGAR and Yahoo Finance/yfinance. Company IR URLs are configured and become available as source references; they are not represented as a licensed news feed. Reuters, AP, Bloomberg, FMP, Finnhub, Polygon and other commercial sources remain registry-only.

## Evidence and deduplication

Each record retains `evidence_id`, `event_cluster_id`, provider, tier, quality, headline/summary, publish/observe time, freshness, event type, direction, materiality, relevance, confidence, official confirmation and source reference. Within a cluster, the highest-quality official record is counted and secondary copies keep `duplicate_of` for audit.

## Knowledge and coverage

Company knowledge is structured across business, products, revenue drivers, competition, supply chain, sector, macro exposure, risks and catalysts. Coverage separately reports official, fundamental, macro, sector, news, knowledge, ETF, options, analyst and insider states. Missing licenses are transparent gaps, not pipeline failures.

## Conflict and synthesis

Conflict is LOW, MEDIUM or HIGH based on opposing material evidence; it is not an arithmetic average. `research_score` is explicitly not a trade score. Confidence is capped for source concentration, coverage gaps, stale evidence and conflict.

## Three-window continuity

20:00 originates the bundle. 23:00 and 06:30 resolve the exact admitted 20:00 effective date/revision and inherit its `research_identity`; later windows do not rebuild a competing research truth. If the source bundle is missing, status is explicit and validation fails continuity.

## 06:30 diagnosis

Review cards add prediction-failure attribution, unused evidence, coverage gaps, research diagnosis and a learning-candidate flag. Auto-learning and weight changes are always false.

## Channel parity

Dashboard and Archive render the canonical bundle; Email and LINE previews show the same research identity/summary; Operations persists the same identity bindings. Channel adapters do not recompute stance or coverage.

## Validation and rollback

Run `scripts/orchestrator/validate_ai_dev_197_institutional_research_layer_v1.py --pretty`, governance validation and protected US/TW regression gates. Rollback is a normal revert of task source files; no runtime, archive, credential or scheduler rollback is required.

## Natural verification

The next complete natural US 20:00, 23:00 and 06:30 chain must prove bundle completeness, identity continuity, coverage truthfulness, conflict behavior, evidence traceability and five-channel parity before closure.
