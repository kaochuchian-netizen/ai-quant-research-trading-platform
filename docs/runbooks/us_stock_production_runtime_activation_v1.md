# AI-DEV-169 US Stock Production Runtime Activation V1

AI-DEV-169 activates the AI-DEV-168 US-stock foundation as a production scheduler-driven runtime while preserving Taiwan production behavior.

## Architecture

- Watchlist: Google Sheet `工作表2` only.
- Taiwan watchlist remains `工作表1`.
- Runner: `scripts/orchestrator/approved_us_stock_delivery.py`.
- Scheduler deploy helper: `scripts/orchestrator/deploy_us_stock_production_runtime_v1.py`.
- Runtime validator: `scripts/orchestrator/validate_us_stock_production_runtime_activation_v1.py`.
- Dashboard URL: `http://35.201.242.167/stock-ai-dashboard/dashboard/decision-intelligence/four-window-preview/index.html`.

## Schedules

All schedules are fixed Asia/Taipei time:

- `us_pre_market_2000`: 20:00 Monday-Friday.
- `us_intraday_2300`: 23:00 Monday-Friday.
- `us_post_close_review_0630`: 06:30 Tuesday-Saturday for the prior US session.

US DST is metadata only. The configured Taiwan times do not move when New York time changes.

## Delivery Policy

- Dashboard receives full visible output.
- Email receives full report at scheduled runtime.
- LINE receives one concise reminder only.
- Deployment and validation never send unscheduled test notifications.
- Duplicate same-date/window delivery is suppressed through idempotency artifacts.

## Runner Commands

Dry-run, no send:

```bash
./venv/bin/python scripts/orchestrator/approved_us_stock_delivery.py --window us_pre_market_2000 --dry-run --pretty
./venv/bin/python scripts/orchestrator/approved_us_stock_delivery.py --window us_intraday_2300 --dry-run --pretty
./venv/bin/python scripts/orchestrator/approved_us_stock_delivery.py --window us_post_close_review_0630 --dry-run --pretty
```

Production scheduler command shape:

```bash
cd /home/kaochuchian/stock-ai && /home/kaochuchian/stock-ai/venv/bin/python scripts/orchestrator/approved_us_stock_delivery.py --window us_pre_market_2000 --production-approved
```

Do not use `python3 main.py`.

## Scheduler Deployment

Dry-run:

```bash
./venv/bin/python scripts/orchestrator/deploy_us_stock_production_runtime_v1.py --dry-run --pretty
```

Apply after PR merge:

```bash
./venv/bin/python scripts/orchestrator/deploy_us_stock_production_runtime_v1.py --apply --pretty
```

Rollback:

```bash
./venv/bin/python scripts/orchestrator/deploy_us_stock_production_runtime_v1.py --rollback --pretty
```

The helper only manages the `STOCK-AI-US-BATCH` cron marker block and preserves other cron entries.

## Runtime Artifacts

- `artifacts/runtime/us_stock/us_stock_pre_market_latest.json`
- `artifacts/runtime/us_stock/us_stock_intraday_latest.json`
- `artifacts/runtime/us_stock/us_stock_post_close_review_latest.json`
- `artifacts/runtime/us_stock_delivery_status_latest.json`
- `artifacts/runtime/us_stock/idempotency/<date>_<window>.json`

Audit fields include market, window, stock counts, dashboard publish status, Email/LINE status, idempotency key, sanitized errors, and safety flags.

## Market Holiday and Missing Data

If Google Sheet, yfinance, news, official-source data, or actual outcome is unavailable, the runner produces PM-readable missing-data states. One invalid symbol does not fail the entire batch. No forecast, review, news, or official-source data is fabricated.

## Completion Criteria

A batch is complete when:

- Runtime artifact is written.
- Dashboard publication result is recorded.
- Email and LINE delivery result is recorded or duplicate-suppressed.
- `trading_or_order_executed=false`.
- Status artifact is updated.

## Failure Diagnosis

Check:

```bash
cat artifacts/runtime/us_stock_delivery_status_latest.json
ls -lt artifacts/runtime/us_stock
crontab -l | grep -A5 -B2 STOCK-AI-US-BATCH
```

Logs are under `logs/us_stock/`. Logs must not contain secrets.

## Safety Boundaries

AI-DEV-169 does not change Taiwan scoring/rating/action/confidence formulas, does not change Taiwan batch schedules, does not introduce order/trading code, does not use `main.py`, and does not perform unscheduled test notifications.
