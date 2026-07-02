# AI-DEV-126: Dashboard Intelligence V1

## Purpose

AI-DEV-126 creates a mobile-first, repo-side Dashboard Intelligence V1 foundation. It transforms prediction, evaluation, source coverage, explainability, calibration, and factor recommendation artifacts into human-reviewable dashboard sections.

## Scope

This release adds schemas, section/card builders, diagnostics separation, a preview renderer, templates, documentation, and validation for a non-production dashboard intelligence artifact.

## Non-goals

- No production trading
- No simulation order
- No production order
- No scheduler mutation
- No LINE/Email delivery
- No production DB write
- No production confidence mutation
- No production forecast weight mutation
- No production rating/action mutation
- No production dashboard publish
- No write to /var/www/stock-ai-dashboard
- No nginx/systemd/cron change
- No automatic strategy change
- No automatic weight update
- No raw traceback in user-facing main dashboard sections

## Architecture

AI-DEV-122/123/124/125 artifacts feed a deterministic dashboard intelligence builder. Missing real artifacts are allowed and represented as diagnostics. The preview renderer creates a static mobile-first HTML preview under `templates/`, never under production dashboard paths.

## Input Model

The input model supports prediction snapshots, stock-level explanation factors, source coverage, confidence calibration, factor recommendations, and diagnostics. `templates/dashboard_intelligence_input.example.json` provides deterministic offline examples when real artifacts are unavailable.

## Dashboard Intelligence Artifact Schema

`templates/dashboard_intelligence_artifact.example.json` includes `schema_version`, `generated_at`, `source_artifact_summary`, `dashboard_status`, `sections`, `stock_cards`, `diagnostics`, `safety_summary`, `future_integration`, `advisory_only`, and `production_publish_allowed=false`.

## Dashboard Sections

Required sections are Today Overview, Prediction Performance, Stock Intelligence Cards, Source Coverage & Data Quality, Explainability, Confidence Calibration, Factor Recommendation, Diagnostics, and Safety & Governance.

## Stock Intelligence Cards

Stock cards include rating, score, action, confidence, confidence status, prediction targets, factor summaries, source coverage readiness, calibration warning, adaptive recommendation summary, dashboard priority, review status, and advisory-only status. Priority is a dashboard review label, not a trading signal.

## Prediction Performance Section

The Prediction Performance section displays confidence reliability, weighted ECE, bucket findings, rating/action effectiveness summaries, and sample-size warnings. Offline findings are labeled as sample/demo and are not production conclusions.

## Source Coverage Section

The Source Coverage section shows primary source status, aggregated market context, missing primary sources, source conflicts, and confidence cap reasons. FinMind and yfinance are supporting market-context sources, not primary authority. News-only evidence cannot act as rating authority.

## Explainability Section

Explainability is deterministic. The dashboard does not invent evidence and does not create AI-generated investment advice. It displays top positive factors, negative factors, neutral factors, missing data factors, source IDs, and evidence IDs.

## Confidence Calibration Section

Confidence Calibration displays confidence bucket, finding, calibration gap, sample size, weighted ECE, recommendation summary, and limitations. Insufficient samples are shown as warning/watch, not definitive conclusions.

## Factor Recommendation Section

Factor recommendations from AI-DEV-125 remain advisory-only. Increase, decrease, monitor, and hold recommendations all require human review. `production_mutation_allowed` remains false and no recommendation is applied.

## Diagnostics Separation Policy

Raw logs, traceback, and pipeline JSON must not appear in Today Overview or other main user-facing sections. Pipeline errors are summarized in Diagnostics with `raw_traceback_suppressed=true` and optional operator action guidance.

## Mobile-first Preview Policy

The preview is plain HTML with inline CSS and no external CDN dependency. It is designed for mobile reading and is repo-side only. It is not published to `/var/www/stock-ai-dashboard` and does not modify nginx, systemd, cron, LINE, Email, or delivery flows.

## Safety Boundary

AI-DEV-126 is artifact-first and preview-first. It does not log into brokers, place orders, mutate production database state, mutate forecast weights, mutate confidence formulas, mutate rating/action rules, publish dashboards, send notifications, or run production pipelines.

## Validation Commands

```bash
./venv/bin/python -m py_compile app/dashboard/intelligence_schema.py app/dashboard/intelligence_builder.py app/dashboard/section_builder.py app/dashboard/card_builder.py app/dashboard/diagnostics_policy.py app/dashboard/mobile_layout_policy.py app/dashboard/preview_renderer.py scripts/orchestrator/build_dashboard_intelligence_artifact.py scripts/orchestrator/render_dashboard_intelligence_preview.py scripts/orchestrator/validate_dashboard_intelligence_v1.py
./venv/bin/python scripts/orchestrator/validate_dashboard_intelligence_v1.py --pretty
./venv/bin/python scripts/orchestrator/build_dashboard_intelligence_artifact.py --pretty
./venv/bin/python scripts/orchestrator/render_dashboard_intelligence_preview.py --pretty
./venv/bin/python scripts/orchestrator/validate_ai_branch.py --base main --head HEAD --pretty
```

## Connections

- AI-DEV-122 Prediction Data Foundation provides prediction and evaluation artifacts.
- AI-DEV-123 Multi-Source Connector & Explainability provides source coverage and explanation data.
- AI-DEV-124 Confidence Calibration provides reliability and calibration warnings.
- AI-DEV-125 Factor Effectiveness & Adaptive Recommendation provides advisory-only factor recommendation summaries.
- Future production dashboard publish flow must remain a separate human-gated task.
- Future `backtesting.py` strategy research may consume dashboard diagnostics, but no automatic strategy change is introduced here.

## Future Work

AI-DEV-127 should implement Real Historical Artifact Ingestion & Rolling Evaluation V1 so real rolling artifacts can feed this dashboard intelligence contract without automatic production strategy mutation.
