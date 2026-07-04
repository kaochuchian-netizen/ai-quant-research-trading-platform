# AI-DEV-138: Context-Based Report Assembly Foundation V1

## Purpose

AI-DEV-138 is the V10 Unified Decision Intelligence report assembly foundation. It reads AI-DEV-136 Prediction Context and reads AI-DEV-137 Explainability / Evidence Trace to assemble deterministic report-ready sections for future daily report, email report, and dashboard report surfaces.

This is not a production renderer.

## Scope

The foundation adds a deterministic Context-Based Report Assembly artifact with:

- report sections
- report summary
- source credibility section
- factor rationale section
- formal report integration section
- market regime section
- rolling evaluation section
- warning section
- exclusion section
- evidence trace section
- dashboard-ready blocks
- email-ready blocks
- LINE summary blocks
- safety policy
- delivery policy

## Inputs

The builder reads deterministic samples:

- `templates/prediction_context_artifact.example.json`
- `templates/unified_explainability_artifact.example.json`

These are offline examples and do not call runtime services.

## Report Sections

The artifact supports:

- executive_summary
- market_regime_summary
- source_credibility_summary
- technical_context_summary
- chip_context_summary
- adr_context_summary
- finmind_summary
- twse_summary
- yfinance_summary
- rolling_evaluation_summary
- confidence_rationale_summary
- evidence_trace_summary
- metadata_only_warning
- official_source_replacement_warning
- advisory_only_disclaimer

## Formal Report Integrations

The formal report integration section includes:

- FinMind report integration
- TWSE report integration
- yfinance/Yahoo report integration

FinMind remains a normalized external data provider. TWSE remains the official market/chip source. yfinance/Yahoo remains an external reference/proxy.

## Source Credibility Policy

The source credibility section keeps AI-DEV-136 categories:

- official_primary_source
- official_market_source
- normalized_external_data_provider
- external_reference_proxy
- ai_generated_analysis
- low_priority_metadata

No source in this report assembly artifact can directly change rating/action/confidence.

## Warning And Exclusion Policy

The warning and exclusion sections preserve AI-DEV-137 policy:

- broker_target_price_metadata can only be metadata.
- google_news_rss can only be event detection / sentiment support and cannot be core forecast evidence.
- yfinance_yahoo cannot replace official sources.
- finmind cannot replace MOPS / TWSE / company official information.
- gemini_google_generative_ai is not original evidence.

## Output Surfaces

Dashboard-ready blocks support future Dashboard drill-down, but AI-DEV-138 does not publish dashboard and does not modify Dashboard UI.

Email-ready blocks support future full email report rendering, but AI-DEV-138 does not send LINE / Email.

LINE summary blocks support future short notification summaries only. AI-DEV-138 does not send notifications.

## Future Tasks

- AI-DEV-139 Dashboard Drill-down should consume this artifact for dashboard cards and trace sections.
- AI-DEV-140 Decision Quality Feedback Loop should consume this artifact alongside outcomes and review metrics.
- Future daily report renderer / email renderer / dashboard renderer may consume this artifact after separate gated tasks.

AI-DEV-138 does not modify production report delivery.

## Safety Boundary

No external API calls.
No secrets.
No DB writes.
No production scheduler / cron / systemd / timer changes.
No LINE / Email / notification sending.
No dashboard publish.
No Dashboard UI changes.
No broker / order / trading.
No `python3 main.py` execution.
No production pipeline execution.
No production rating/action/confidence/weight logic changes.
No formal delivery behavior changes.

## Validation

Run:

```bash
./venv/bin/python -m py_compile app/report_assembly/*.py scripts/orchestrator/build_context_based_report_assembly_artifact.py scripts/orchestrator/validate_context_based_report_assembly_v1.py
./venv/bin/python scripts/orchestrator/validate_context_based_report_assembly_v1.py --pretty
./venv/bin/python scripts/orchestrator/build_context_based_report_assembly_artifact.py --pretty
./venv/bin/python scripts/orchestrator/validate_ai_branch.py --base main --head HEAD --pretty
git diff --check
```
