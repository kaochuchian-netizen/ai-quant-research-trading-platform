# AI-DEV-133 FinMind Formal Report Integration Foundation V1

## Purpose
AI-DEV-133 makes the existing FinMind connector usable by a deterministic formal report integration foundation without calling external APIs, reading secrets, or changing production runtime.

## Scope
The release adds a FinMind report integration model, offline sample input/output artifacts, an artifact builder, validator, and runbook. Supported report sections are monthly revenue, financial statement summary, EPS, ROE, margin, institutional trading, dividend, share capital, and market cap.

## FinMind positioning
FinMind is a normalized external data provider. It can reduce integration cost for Taiwan market and fundamental datasets, but it does not replace MOPS / company official filings, TWSE official market/chip data, or Shioaji broker/runtime quote governance.

## Formal report usage
FinMind can supplement daily reports with 月營收, 財報摘要, EPS, ROE, margin, 三大法人, 股利, 股本, and 市值 context. Every section must include source attribution, freshness policy, explainability notes, and limitations.

## Prediction Context usage
Future Prediction Context integration may use FinMind as attributed supplemental context after freshness and schema validation. It must not directly mutate rating, action, confidence, forecast weights, or trading behavior.

## Freshness policy
V1 uses deterministic offline samples. A future runtime task must validate dataset period, staleness, schema compatibility, and source attribution before using FinMind in live reports.

## Safety boundary
No external API calls, no API token requirement, no secrets or `.env` reads, no scheduler changes, no LINE/Email delivery, no dashboard publish, no DB writes, no broker/order/trading, and no production rating/action/confidence/weight mutation.

## Validation
```bash
./venv/bin/python -m py_compile \
  app/finmind_report/schemas.py \
  app/finmind_report/sample_data.py \
  app/finmind_report/artifact_builder.py \
  scripts/orchestrator/build_finmind_report_integration_artifact.py \
  scripts/orchestrator/validate_finmind_report_integration_v1.py
./venv/bin/python scripts/orchestrator/validate_finmind_report_integration_v1.py --pretty
./venv/bin/python scripts/orchestrator/build_finmind_report_integration_artifact.py --pretty
./venv/bin/python scripts/orchestrator/validate_ai_branch.py --base main --head HEAD --pretty
```
