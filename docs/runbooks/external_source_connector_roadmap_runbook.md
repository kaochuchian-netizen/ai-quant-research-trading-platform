# External Source Connector Roadmap Runbook

## Build the roadmap
```bash
./venv/bin/python scripts/orchestrator/build_external_source_connector_roadmap.py --pretty
```

## Validate the roadmap
```bash
./venv/bin/python scripts/orchestrator/validate_external_source_connector_roadmap_v1.py --pretty
```

## Use a different audit artifact
```bash
./venv/bin/python scripts/orchestrator/build_external_source_connector_roadmap.py --pretty --audit <audit.json>
```

## How to choose the next connector task
Prioritize B official/company-linked sources with high decision value and manageable production risk. Build deterministic connector contracts and sample artifacts first, then add report/dashboard/evaluation integration in later tasks.

## What must stay out of production logic
Low-priority metadata/noise sources and manual-review sources must not affect rating, action, confidence, or forecast weights. Analyst/broker opinion requires manual review before connector work.

## Safety checklist
Do not call external APIs, read secrets or `.env`, write DB, send LINE/Email, publish dashboards, modify scheduler, or execute broker/order/trading flows while using this roadmap.

## FinMind follow-up
Because `app/sources/finmind_connector.py` exists, treat FinMind as a report integration candidate. Before using it in reports or Prediction Context, add deterministic artifacts for monthly revenue, financial statements, EPS/ROE/margin, institutional flow, dividends, share capital, market cap, and Taiwan fundamentals.

FinMind should lower integration cost, not replace source governance. Cross-check high-impact decisions against MOPS/company official filings, TWSE official market/chip data, and Shioaji broker/runtime quote data.
