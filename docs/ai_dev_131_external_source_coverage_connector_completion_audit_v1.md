# AI-DEV-131 External Source Coverage & Connector Completion Audit V1

## Purpose
AI-DEV-131 provides a deterministic, offline audit of external source coverage, connectors, artifacts, reports, dashboards, prediction, and evaluation usage.

## Current source completion
Production-used sources are Google Sheet stock universe, Shioaji/Sinopac market data, and SQLite/historical CSV local storage. TWSE and yfinance/Yahoo have connector or helper coverage but still need formal report/dashboard/evaluation integration. MOPS/company official filings and industry/ETF context are inventory or roadmap items. News, LLM summaries, interviews, and analyst opinions are low-priority metadata/noise unless confirmed by official sources.

## Incomplete items
Missing or incomplete areas include connectorization for official filings, company announcements, financial statements, investor conference material, industry/supply-chain context, ETF/index/sector proxy artifacts, and analyst/broker opinion governance. Several existing connector-like sources also need shadow artifacts and evaluation linkage before being promoted.

## Source priority policy
- `A_primary`: local universe, broker market data, and local historical data already used in production-like flows.
- `B_official_or_company_linked`: TWSE, MOPS, company filings, financial statements, and investor conference material.
- `C_market_or_industry`: Yahoo/yfinance context, industry chain data, ETF/index/sector proxies.
- `D_low_priority_metadata_noise`: Google News RSS, Gemini summaries, management interviews, and analyst target/broker opinion.

## Prediction context policy
A/B sources may enter prediction context after deterministic artifacts and freshness checks exist. C sources may be confirmation/context only. D sources must not independently raise confidence, rating, or action.

## Low-priority metadata policy
News, LLM summaries, interviews, and analyst/broker opinions should remain low-priority metadata/noise until corroborated by official filings, exchange data, or company materials.

## Connector roadmap
1. Add deterministic connector contracts for MOPS/company official filings.
2. Add shadow artifacts for TWSE and yfinance context.
3. Add report/dashboard/evaluation integration only after artifact validation.
4. Keep D-priority sources out of primary scoring and confidence mutation.
5. Re-run this audit after each connector completion task.

## Safety boundary
This audit reads repo-local files only. It does not call external APIs, read secrets or `.env`, modify DB, send LINE/Email, publish dashboard, change scheduler, access broker/order/trading, or mutate production rating/action/confidence/weight logic.

## Validation
```bash
python -m py_compile \
  app/source_audit/schemas.py \
  app/source_audit/repo_scanner.py \
  app/source_audit/source_catalog.py \
  app/source_audit/audit_builder.py \
  scripts/orchestrator/build_external_source_coverage_audit.py \
  scripts/orchestrator/validate_external_source_coverage_audit_v1.py
python scripts/orchestrator/validate_external_source_coverage_audit_v1.py --pretty
python scripts/orchestrator/build_external_source_coverage_audit.py --pretty
python scripts/orchestrator/validate_ai_branch.py --base main --head HEAD --pretty
```
