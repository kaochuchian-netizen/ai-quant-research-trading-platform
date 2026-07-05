# AI-DEV-141 Official Primary Source Connector & Context Admission Foundation V1

## Purpose

AI-DEV-141 is the V10 official source admission foundation for the Unified Decision Intelligence chain. It defines how official primary sources can enter deterministic context, evidence, report, dashboard, and feedback artifacts before any production connector or runtime crawler is implemented.

This is not a production crawler. It does not call MOPS / company websites / external APIs, does not modify production connector code, and does not change rating/action/confidence.

## Scope

This foundation defines offline source-family contracts for:

- MOPS Public Information Observatory
- company announcements
- financial statements
- monthly revenue
- investor conference materials
- company IR materials
- industry supply chain context
- peer company context

Each family is modeled with source identity, credibility, priority, freshness policy, failure mode, allowed usage, disallowed usage, replacement rules, and mutation restrictions.

## Relationship To V10 Decision Intelligence

AI-DEV-141 defines how official source families can feed the existing V10 chain:

- AI-DEV-136 `prediction_context_v1`
- AI-DEV-137 `unified_explainability_evidence_trace_v1`
- AI-DEV-138 `context_based_report_assembly_v1`
- AI-DEV-139 `dashboard_decision_intelligence_v1`
- AI-DEV-140 `decision_quality_feedback_v1`

The artifact is a policy and schema foundation only. It does not perform runtime collection, scoring, delivery, or mutation.

## Source Priority Policy

MOPS and company announcements are official primary sources. Financial statements and monthly revenue are official financial sources. Investor conferences and company IR materials are official IR sources. Industry supply chain and peer company context may provide structured context, but they require attribution and human review before production use.

FinMind can assist but cannot replace official sources. FinMind may normalize or summarize data, but official filings, company announcements, MOPS, TWSE, and company materials remain the authority.

TWSE is the official market and chip source for TWSE-published market/chip data. yfinance / Yahoo is an external reference proxy for ADR, US index, ETF, sector, and sentiment context only; it cannot replace official Taiwanese market, company, or financial sources.

Google News RSS is event and sentiment support only. It cannot be core forecast evidence. Broker target price / analyst rating is metadata only and cannot affect rating/action/confidence.

Gemini or other AI-generated analysis is not original evidence. It may only summarize or explain already-attributed evidence.

## Context Admission Policy

The admission matrix defines whether each source family may enter:

- prediction context
- explainability evidence
- report assembly
- dashboard drill-down
- decision feedback

Official primary, financial, and IR sources may be admitted as core forecast evidence when deterministic samples or later approved production connectors provide source attribution. Industry supply chain and peer context are admitted as context sources, not direct production mutation sources.

All source families have `production_decision_mutation_allowed=false` and `direct_rating_action_confidence_impact=false`.

## Official Source Replacement Policy

Official source replacement is disallowed by default. External providers and generated analysis cannot replace official sources.

- FinMind cannot replace official source records.
- yfinance / Yahoo cannot replace official source records.
- Google News RSS cannot become core forecast evidence.
- Broker target / analyst opinion cannot influence rating/action/confidence. broker target price / analyst rating is metadata only.
- AI-generated analysis cannot be treated as original evidence.

## Artifact Contract

The deterministic artifact contains:

- source families
- admission matrix
- source priority policy
- official source replacement policy
- relationship to existing sources
- integration targets
- warnings
- safety policy
- mutation policy

The builder uses deterministic sample input and produces stable JSON without external network access.

## Safety Boundaries

AI-DEV-141 does not call MOPS / company websites / external APIs. It does not read secrets or `.env`, does not write databases, does not modify production schedulers, does not send LINE / Email / notification, does not publish dashboards, does not execute orders, and does not run `python3 main.py`.

It does not modify production rating/action/confidence/weight logic, does not activate a production MOPS/company/financial statement/investor conference connector, and does not modify formal delivery behavior.

## Future Connector Path

Future connector implementation should happen in separate AI-DEV tasks with explicit runtime approval. Those tasks should connect MOPS, company announcements, financial statements, monthly revenue, investor conference, and company IR materials into deterministic ingestion outputs before production use.

Before production adoption, every connector should prove:

- source attribution
- freshness and failure mode handling
- no secret leakage
- no production mutation during validation
- no direct rating/action/confidence mutation
- human review for admission into production pipelines
