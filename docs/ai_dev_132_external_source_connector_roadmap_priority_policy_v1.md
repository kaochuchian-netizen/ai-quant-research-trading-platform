# AI-DEV-132 External Source Connector Roadmap & Priority Policy V1

## Purpose
AI-DEV-132 converts the AI-DEV-131 external source coverage audit into a deterministic connector roadmap and priority policy. It is an advisory planning artifact for future connector completion and Prediction Context integration.

## Inputs
The builder reads the repo-local AI-DEV-131 audit artifact at `templates/external_source_coverage_audit.example.json`. It does not call external APIs, read secrets, or inspect `.env`.

## Source status groups
The roadmap preserves the AI-DEV-131 status groups: `production_used`, `connector_exists_not_in_formal_report`, `inventory_only_not_connectorized`, `needs_connector`, and `low_priority_metadata_only`.

## Priority policy
Each source receives a policy row with source priority, decision value, freshness requirement, reliability risk, explainability value, credential requirement, implementation complexity, production risk, and recommended phase.

## Recommended phases
- `phase_0_maintain`: keep current production-used sources stable and monitored.
- `phase_1_prediction_context`: suitable for Prediction Context after deterministic artifact validation.
- `phase_2_formal_report`: connector/helper exists and should be promoted into formal reports first.
- `phase_3_connector_build`: build connector contract and deterministic sample artifacts first.
- `phase_4_defer_metadata_only`: keep as low-priority metadata/noise.
- `manual_review_required`: blocked until quality, credential, licensing, or governance review is complete.

## Prediction Context policy
Official/company-linked and primary sources are eligible for Prediction Context after sample artifacts, freshness policy, failure mode, and validation are present. Low-priority metadata must not independently affect prediction confidence.

## Formal report policy
TWSE and yfinance/Yahoo are report integration candidates because connector/helper code already exists but formal report/dashboard/evaluation integration remains incomplete.

## Low-priority metadata policy
Google News RSS, Gemini summaries, management interviews, and analyst/broker opinions are not primary evidence. They must not affect rating, action, confidence, or forecast weights without official corroboration and a separate approved task.

## Connector roadmap
Start with official/company-linked sources: MOPS, company announcements, financial statements, investor conferences, industry context, and ETF/index/sector proxies. Each future connector task should add deterministic examples and validators before any runtime activation.

## Safety boundary
No external API calls, secret reads, scheduler changes, LINE/Email, dashboard publish, DB writes, broker/order/trading, or production rating/action/confidence/weight changes.

## Validation
```bash
./venv/bin/python -m py_compile \
  app/source_roadmap/schemas.py \
  app/source_roadmap/policy.py \
  app/source_roadmap/roadmap_builder.py \
  scripts/orchestrator/build_external_source_connector_roadmap.py \
  scripts/orchestrator/validate_external_source_connector_roadmap_v1.py
./venv/bin/python scripts/orchestrator/validate_external_source_connector_roadmap_v1.py --pretty
./venv/bin/python scripts/orchestrator/build_external_source_connector_roadmap.py --pretty
./venv/bin/python scripts/orchestrator/validate_ai_branch.py --base main --head HEAD --pretty
```

## FinMind positioning
FinMind is included as a high-quality normalized external data provider. The repo already contains `app/sources/finmind_connector.py`, so AI-DEV-132 places FinMind in `report_integration_candidates` rather than `connector_build_candidates`.

FinMind can support 月營收, 財報, EPS / ROE / margin, 三大法人, 股利, 股本 / 市值, and 台股基本面資料. It reduces integration cost by normalizing multiple Taiwan market datasets, but it must not replace official-source governance.

Source positioning:
- MOPS / company official sources: primary official source.
- TWSE: official market/chip source.
- Shioaji: broker market data / runtime quote source.
- FinMind: normalized external data provider; useful for integration speed and completeness, but not a substitute for MOPS/TWSE/Shioaji authority.

FinMind may support Prediction Context and formal reports after deterministic artifact validation. It must not directly mutate rating, action, confidence, or forecast weights.
