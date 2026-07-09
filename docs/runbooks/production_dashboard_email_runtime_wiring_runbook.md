# Production Dashboard Email Runtime Wiring Runbook

## Manual Verification

1. Confirm the four-window Dashboard URL loads.
2. Confirm the Dashboard latest data timestamp reflects the latest production export.
3. Confirm tracking cards show rating/action/score coverage instead of repeated raw missing states when production ratings exist.
4. Confirm Email preview is PM-readable and does not contain raw pipeline/debug content.
5. Confirm raw logs remain available only in artifacts/debug surfaces.

## Validation

```bash
python scripts/orchestrator/build_email_scheduled_delivery_preview_v1.py --pretty
python scripts/orchestrator/validate_production_dashboard_email_runtime_wiring_v1.py --pretty
```

## Forbidden

Do not send Email/LINE from validation. Do not change scheduler. Do not run production pipeline or `python3 main.py`. Do not write production DB.
