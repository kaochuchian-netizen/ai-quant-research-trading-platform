# Dashboard Delivery URL Contract Migration V1

AI-DEV-174B moves formal LINE and Email Dashboard links to a single registry.

## Canonical URLs

- Landing: `http://35.201.242.167/stock-ai-dashboard/index.html`
- TW Dashboard: `http://35.201.242.167/stock-ai-dashboard/dashboard/tw/index.html`
- US Dashboard: `http://35.201.242.167/stock-ai-dashboard/dashboard/us/index.html`

The old four-window route remains only as a backward-compatible Taiwan Dashboard route. It is not a formal delivery target.

## Contract

Delivery code must call `app.dashboard.dashboard_url_registry`:

- `get_tw_dashboard_url()` for TW runtime, Email, LINE, approved delivery, controlled previews.
- `get_us_dashboard_url()` for US runtime, Email, LINE, approved delivery, controlled previews.
- `get_dashboard_url(market)` when market is known at runtime.

Do not hard-code `decision-intelligence/four-window-preview` in formal delivery code.

## Validation

Run:

```bash
python3 scripts/orchestrator/validate_dashboard_delivery_url_contract_v1.py --pretty
```

The validator renders no-send TW and US payloads and verifies:

- TW LINE and Email use the TW Dashboard URL.
- US LINE and Email use the US Dashboard URL.
- Formal delivery contract files no longer reference the legacy route.
- No LINE or Email is sent.

## Rollback

Revert the AI-DEV-174B commit and republish the Dashboard only if the registry causes a production delivery regression. Do not repoint US delivery to the TW compatibility route.
