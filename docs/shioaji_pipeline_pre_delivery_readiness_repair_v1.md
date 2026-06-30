# Shioaji Pipeline Pre-Delivery Readiness Repair V1

Task: AI-DEV-105

## Root Cause

AI-DEV-104 identified that scheduled pre-open delivery could stop before the delivery stage when Shioaji login, maintenance, version, or historical Kbars constraints failed during historical CSV refresh.

The direct crash point was the pre-open path:

1. `app/pipelines/pre_open_pipeline.py`
2. `scripts/update_historical_csv.py`
3. `app/market/shioaji_client.py`
4. `app/market/historical_price_loader.py`

Before this repair, `scripts/update_historical_csv.py` requested roughly 180 days of Kbars and did not isolate Shioaji login or per-symbol Kbars failures from the rest of the pipeline.

## Repair

- `app/market/historical_price_loader.py` bounds Kbars requests to a 30-day window.
- `app/market/shioaji_client.py` classifies login/runtime failures without printing secrets.
- `scripts/update_historical_csv.py` returns `pipeline_pre_delivery_status_v1`.
- Historical refresh falls back to existing `data/historical/*_daily.csv` when Shioaji login or Kbars fetch fails.
- `app/pipelines/pre_open_pipeline.py` prints the pre-delivery status and continues toward report generation when a usable fallback exists.

## Fallback Behavior

Fallback source: existing historical CSV.

Fallback is used for:

- `shioaji_login_failed`
- `shioaji_maintenance`
- `shioaji_version_or_upgrade_required`
- `shioaji_kbars_range_or_history_limit`

Warnings are retained in the readiness status. Errors are not silently suppressed.

## No-Send Readiness Dry Run

The repo-only readiness helper builds deterministic JSON and does not call Shioaji, LINE, Email, Gmail, SMTP, dashboard deployment, cron, systemd, timers, services, or any production store.

```bash
python3 scripts/orchestrator/shioaji_pipeline_pre_delivery_readiness_dry_run.py \
  --input templates/shioaji_pipeline_pre_delivery_readiness_input.example.json \
  --output /tmp/shioaji_pipeline_pre_delivery_readiness_result.json \
  --summary-output /tmp/shioaji_pipeline_pre_delivery_readiness_summary.json \
  --pretty
```

## Validation

```bash
python3 -m py_compile scripts/orchestrator/shioaji_pipeline_pre_delivery_readiness_dry_run.py scripts/orchestrator/validate_shioaji_pipeline_pre_delivery_readiness_result.py
python3 scripts/orchestrator/validate_shioaji_pipeline_pre_delivery_readiness_result.py --input /tmp/shioaji_pipeline_pre_delivery_readiness_result.json --pretty
python3 scripts/orchestrator/validate_ai_branch.py
git diff --check
python3 -m py_compile scripts/run_pipeline.py main.py scripts/update_historical_csv.py app/market/shioaji_client.py app/market/historical_storage.py
```
