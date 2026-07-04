# AI-DEV-134: TWSE & yfinance Formal Report Integration Foundation V1

## Purpose

AI-DEV-134 creates a deterministic, read-only formal report integration foundation for TWSE OpenAPI and yfinance/Yahoo context. It does not call external APIs and does not require tokens or secrets.

## Scope

This task adds a report integration model, deterministic sample input/output artifacts, a builder, a validator, and this runbook. It checks existing TWSE/yfinance/Yahoo connector coverage by repository inspection only; it does not execute runtime fetchers.

## Source Roles

TWSE is the official market/chip source for formal report sections such as chip / institutional summary, margin trading summary, and official market/chip attribution.

yfinance is an external reference/proxy. It can support ADR reference, US index / ETF / sector proxy, and external market sentiment proxy, but it is not an official source and cannot replace TWSE, MOPS, company filings, or broker/runtime market data governance.

## Report Sections

The artifact supports:

- TWSE chip / institutional summary
- TWSE margin trading summary
- TWSE official market/chip attribution
- yfinance ADR reference
- yfinance US index / ETF / sector proxy
- yfinance external market sentiment proxy
- freshness and failure modes
- safety and governance

## Freshness Policy

TWSE and yfinance sections are market-day context. Stale or unavailable data must be shown as diagnostics and must not fail the full report. yfinance unavailable states must not block official source reporting.

## Explainability Notes

TWSE attribution can explain official market/chip context. yfinance can explain external cross-market context only. Both must not directly change rating/action/confidence or production weights.

## Daily Report and Prediction Context

Future daily report and prediction context builders may consume this artifact as formal context. The artifact is advisory and context-only; downstream production mutation requires a separate human-gated task.

## Safety

No external API calls are made. No secrets are read. No `.env` is read. No production DB writes occur. No scheduler, cron, systemd, LINE, Email, dashboard publish, broker, order, or trading action occurs. This task must not directly change rating/action/confidence or forecast weight logic.

## Validation

Run:

```bash
./venv/bin/python -m py_compile app/reports/twse_yfinance_report_schema.py app/reports/twse_yfinance_report_builder.py scripts/orchestrator/build_twse_yfinance_report_integration_artifact.py scripts/orchestrator/validate_twse_yfinance_report_integration_v1.py
./venv/bin/python scripts/orchestrator/validate_twse_yfinance_report_integration_v1.py --pretty
./venv/bin/python scripts/orchestrator/build_twse_yfinance_report_integration_artifact.py --pretty
./venv/bin/python scripts/orchestrator/validate_ai_branch.py --base main --head HEAD --pretty
```

## Follow-Up

A later AI-DEV can wire real runtime TWSE/yfinance fetch results into daily report or prediction context, still without allowing yfinance to replace official sources or directly mutate rating/action/confidence.
