# FinMind Report Integration Runbook

## Build the offline artifact
```bash
./venv/bin/python scripts/orchestrator/build_finmind_report_integration_artifact.py --pretty
```

## Validate the artifact
```bash
./venv/bin/python scripts/orchestrator/validate_finmind_report_integration_v1.py --pretty
```

## Use an explicit input file
```bash
./venv/bin/python scripts/orchestrator/build_finmind_report_integration_artifact.py --pretty --input templates/finmind_report_integration_input.example.json
```

## Report integration steps
Map validated sections into daily report supplemental blocks only after freshness and schema checks exist. Keep FinMind sections clearly attributed and advisory.

## Prediction Context steps
Use FinMind only as supplemental normalized context. MOPS/company official sources, TWSE, and Shioaji remain authoritative for governance and conflict resolution.

## Safety checklist
Do not call external APIs, read tokens/secrets, read `.env`, write DB, send LINE/Email, publish dashboard, modify scheduler, or execute broker/order/trading flows. Do not directly change rating/action/confidence/weights based on FinMind sections.
