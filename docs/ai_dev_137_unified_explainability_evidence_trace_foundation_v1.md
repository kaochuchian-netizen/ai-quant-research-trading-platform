# AI-DEV-137: Unified Explainability & Evidence Trace Foundation V1

## Purpose

AI-DEV-137 is the V10 Unified Decision Intelligence explainability / traceability foundation. It reads AI-DEV-136 Prediction Context and produces deterministic source, factor, explanation, report block, and dashboard drill-down trace structures.

This is not a production decision engine.

## Scope

The foundation provides:

- Unified source explanations for each Prediction Context source category.
- Factor explanations that describe why each source/factor supports, limits, or only annotates context.
- Evidence links that connect source -> context section -> factor -> explanation -> report block -> dashboard block.
- Evidence trace graph nodes and edges for future traceability and dashboard drill-down.
- Exclusion reasons for metadata-only and non-official sources.
- Confidence rationale that explains confidence without mutating production confidence.
- Deterministic report explanation blocks and dashboard explanation blocks.

## Relationship To AI-DEV-136

AI-DEV-137 reads AI-DEV-136 Prediction Context from `templates/prediction_context_artifact.example.json`.

It preserves AI-DEV-136 policy:

- direct rating/action/confidence impact is always false.
- external proxies and metadata cannot replace official sources.
- low-priority metadata remains metadata-only.
- formal report integrations remain source-attributed context, not production decision rules.

## Source Credibility Policy

The artifact includes source explanations for:

- official_primary_source
- official_market_source
- normalized_external_data_provider
- external_reference_proxy
- ai_generated_analysis
- low_priority_metadata

Source credibility is explainable, but it does not modify rating/action/confidence.

## Metadata-Only And Exclusion Policy

The exclusion policy is explicit:

- broker_target_price_metadata can only be metadata and cannot directly affect rating/action/confidence.
- google_news_rss is event detection / sentiment support only and cannot be core forecast evidence.
- yfinance_yahoo is an external reference/proxy and cannot replace official sources.
- finmind is a normalized external data provider and cannot replace MOPS / TWSE / company official information.
- gemini_google_generative_ai is AI-generated analysis and not original evidence.

This is the official-source replacement policy for the explainability layer.

## Confidence Rationale

Confidence rationale can explain how prediction_context calibration, source credibility, factor effectiveness, and evidence trace should be read. It does not modify production confidence.

`direct_rating_action_confidence_impact` must remain false.

## Report And Dashboard Use

The artifact provides future report blocks:

- source credibility summary
- factor rationale summary
- metadata-only warning
- official-source replacement warning
- evidence trace summary

The artifact provides future dashboard drill-down blocks:

- evidence cards
- factor contribution cards
- excluded source cards
- source credibility badges
- trace graph nodes / edges

AI-DEV-137 does not trigger report delivery and does not modify Dashboard UI.

## Future Tasks

- AI-DEV-138 should use this artifact for Context-Based Report Assembly.
- AI-DEV-139 should use this artifact for Dashboard Decision Intelligence Drill-down.
- AI-DEV-140 should use this artifact for Decision Quality Feedback Loop.

## Safety Boundary

No external API calls.
No secrets.
No DB writes.
No production scheduler / cron / systemd / timer changes.
No LINE / Email / notification sending.
No dashboard publish.
No broker / order / trading.
No `python3 main.py` execution.
No production pipeline execution.
No production rating/action/confidence/weight logic changes.
No formal delivery behavior changes.
No Dashboard UI changes.

## Validation

Run:

```bash
./venv/bin/python -m py_compile app/explainability/*.py scripts/orchestrator/build_unified_explainability_artifact.py scripts/orchestrator/validate_unified_explainability_v1.py
./venv/bin/python scripts/orchestrator/validate_unified_explainability_v1.py --pretty
./venv/bin/python scripts/orchestrator/build_unified_explainability_artifact.py --pretty
./venv/bin/python scripts/orchestrator/validate_ai_branch.py --base main --head HEAD --pretty
git diff --check
```
