# Production Scheduler Dashboard URL Contract V1

AI-DEV-174C closes the gap between controlled formatter payloads and the actual production scheduler path.

## Root Cause

`run_stock_analysis.sh` is the cron entrypoint for Taiwan windows. Before AI-DEV-174C it passed this fallback into `approved_pre_open_delivery.py`:

`/dashboard/decision-intelligence/four-window-preview/index.html`

That CLI argument overrode the registry default fixed in AI-DEV-174B. Controlled formatter checks used the registry, but the cron-equivalent wrapper injected the legacy URL at runtime.

## Production Delivery Path Inventory

| Market | Window | Scheduler entrypoint | Approved delivery path | URL source |
| --- | --- | --- | --- | --- |
| TW | pre_open_0700 | `run_stock_analysis.sh` | `approved_pre_open_delivery.py` | `dashboard_url_registry.get_tw_dashboard_url()` |
| TW | intraday_1305 | `run_stock_analysis.sh` | `approved_pre_open_delivery.py` | `dashboard_url_registry.get_tw_dashboard_url()` |
| TW | pre_close_1335 | `run_stock_analysis.sh` | `approved_pre_open_delivery.py` | `dashboard_url_registry.get_tw_dashboard_url()` |
| TW | post_close_1500 | `run_stock_analysis.sh` | `approved_pre_open_delivery.py` | `dashboard_url_registry.get_tw_dashboard_url()` |
| TW | prediction_review_1500 | `run_stock_analysis.sh` dry-run/alias path | `approved_pre_open_delivery.py` | `dashboard_url_registry.get_tw_dashboard_url()` |
| US | us_pre_market_2000 | cron -> `approved_us_stock_delivery.py` | `approved_us_stock_delivery.py` | `dashboard_url_registry.get_us_dashboard_url()` |
| US | us_intraday_2300 | cron -> `approved_us_stock_delivery.py` | `approved_us_stock_delivery.py` | `dashboard_url_registry.get_us_dashboard_url()` |
| US | us_post_close_review_0630 | cron -> `approved_us_stock_delivery.py` | `approved_us_stock_delivery.py` | `dashboard_url_registry.get_us_dashboard_url()` |

## Runtime Rules

- Formal delivery code must not use the legacy four-window route as a default, fallback, compatibility URL, or environment fallback.
- If an environment variable or stale artifact supplies a legacy URL, delivery builders normalize it back to the market URL.
- Legacy route publication may remain for old bookmarks, but it is not a notification target.

## Validator

Run:

```bash
./venv/bin/python scripts/orchestrator/validate_production_scheduler_dashboard_url_contract_v1.py --pretty
```

The validator executes cron-equivalent no-send payload generation:

- TW uses `run_stock_analysis.sh` with `STOCK_AI_APPROVED_DELIVERY=1` and `STOCK_AI_APPROVED_DELIVERY_DRY_RUN=1`.
- US uses `approved_us_stock_delivery.py --dry-run`.
- It intentionally injects the legacy URL for TW to prove normalization prevents stale URL regression.

Expected safety:

- `email_attempted=false`
- `line_attempted=false`
- `trading_or_order_executed=false`
- no scheduler time changes

## Evidence

Latest no-send evidence is written to:

- `artifacts/runtime/production_scheduler_dashboard_url_contract/production_scheduler_dashboard_url_contract_latest.json`
- `artifacts/runtime/production_scheduler_dashboard_url_contract/production_scheduler_dashboard_url_contract_latest.md`

Do not commit production runtime evidence unless a future task explicitly asks for fixture promotion.
