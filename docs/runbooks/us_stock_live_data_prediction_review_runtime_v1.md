# AI-DEV-171 US Stock Live Data Prediction & Review Runtime V1

## Purpose

AI-DEV-171 repairs the US production runtime so the US Dashboard is driven by live market data instead of the AI-DEV-168 foundation/validation artifact.

The incident symptom was that the public US Dashboard showed placeholder states such as `US batch foundation ready; market data not fetched in validation`, missing USD prices, missing prediction ranges, and `insufficient_data` confidence. Root cause: the approved US delivery runner was still building its runtime artifact with the foundation builder (`build_us_stock_batch_artifact(us_stock_batch_input_example())`), and the US Dashboard renderer accepted or generated fixture/foundation artifacts when no authoritative runtime artifact was present.

## Real Data Flow

The repaired flow is:

1. Load the US watchlist from `工作表2` through the existing Google Sheet loader.
2. Fetch public market reference data through the dedicated yfinance client.
3. Fetch daily OHLCV history for technical analysis.
4. Fetch market context using SPY, QQQ, DIA, VIX proxy, and SOXX where available.
5. Fetch safe headline-only news from available yfinance news data.
6. Calculate deterministic technical state, score, rating, action, and confidence.
7. Generate deterministic session and next-session ranges when data is sufficient.
8. Persist prediction snapshots for 20:00 and 23:00 windows.
9. At 06:30, review prior prediction snapshots against actual completed-session data when available.
10. Write authoritative US runtime artifacts for the Dashboard, Email, and LINE reminder policy.

## Artifact Provenance Gate

Production US Dashboard rendering requires all of these fields:

- `artifact_kind = us_stock_runtime`
- `artifact_mode = production_runtime`
- `market = US`
- `data_source_mode = live`
- `fixture = false`
- `validation_only = false`
- `source_sheet = 工作表2`

The Dashboard rejects fixtures, foundation artifacts, dry-run validation artifacts, wrong-market artifacts, and validation-only output. Rejected or missing artifacts show `正式美股資料尚未產生`; the Dashboard does not fall back to Taiwan data and does not render fixture cards as production.

## Prediction Methodology

The V1 US deterministic baseline uses actual public market data only. It derives range width from available OHLCV fields:

- ATR-like range percentage
- median daily high-low range percentage
- log-return volatility
- 1M trend bias
- intraday adjustment for the 23:00 window

If price or sufficient history is unavailable, prediction fields remain unavailable with explicit missing-data reasons. The output does not claim guaranteed accuracy.

## Review Methodology

The 06:30 review loads prior US prediction snapshots for the same US session date. It computes range coverage and high/low error only when both prior prediction and completed-session actual data are available. It does not fabricate missing reviews.

## News Policy

Initial news integration uses available yfinance news headlines only. It stores safe headline metadata, a Traditional Chinese summary label, vocabulary placeholders, investment reading, and source quality. It does not copy full articles and does not invent headlines. If no safe news is available, the UI shows `無可驗證重大新聞`.

## Dashboard Publication

The US Dashboard lives at:

`http://35.201.242.167/stock-ai-dashboard/dashboard/us/index.html`

Use the multi-market Dashboard publisher only after authoritative live production artifacts exist. Validation-only artifacts are not accepted by the production Dashboard.

## Safe Commands

No-send live data validation:

```bash
./venv/bin/python scripts/orchestrator/approved_us_stock_delivery.py --window us_pre_market_2000 --dry-run --live-data --pretty
./venv/bin/python scripts/orchestrator/approved_us_stock_delivery.py --window us_intraday_2300 --dry-run --live-data --pretty
./venv/bin/python scripts/orchestrator/approved_us_stock_delivery.py --window us_post_close_review_0630 --dry-run --live-data --pretty
```

Production-provenance artifact without unscheduled notification:

```bash
./venv/bin/python scripts/orchestrator/approved_us_stock_delivery.py --window us_pre_market_2000 --production-artifact --publish-dashboard --pretty
```

This writes a production-provenance live artifact and refreshes Dashboard only. It does not send Email or LINE unless `--production-approved` is explicitly used by the approved scheduler.

## Validation

```bash
./venv/bin/python scripts/orchestrator/validate_us_stock_live_data_prediction_review_runtime_v1.py --pretty
./venv/bin/python scripts/orchestrator/validate_us_stock_dedicated_batch_lifecycle_v1.py --pretty
./venv/bin/python scripts/orchestrator/validate_us_stock_production_runtime_activation_v1.py --pretty
./venv/bin/python scripts/orchestrator/validate_multi_market_dashboard_v2_us_link_isolation_v1.py --pretty
```

After controlled publish, run:

```bash
./venv/bin/python scripts/orchestrator/validate_us_stock_live_data_prediction_review_runtime_v1.py --pretty --require-public
```

## Safety Boundaries

- Do not run `python3 main.py`.
- Do not send unscheduled Email or LINE test messages.
- Do not place trades or orders.
- Do not print secrets, tokens, credentials, PINs, or `.env` values.
- Do not modify TW formulas, TW scheduler times, or TW delivery behavior.
- Do not publish fixture/example/validation artifacts as production US data.

## Rollback

To rollback a Dashboard publish, restore the backup path reported by the multi-market publisher. To rollback code, revert the AI-DEV-171 merge commit and republish the last known-good Dashboard from its backup.

## Completion Criteria

- US Dashboard no longer displays foundation/validation placeholder cards as production.
- Enabled US symbols come from `工作表2` in production runs.
- Live numeric USD prices and technical indicators are present when yfinance succeeds.
- Prediction ranges are numeric and ordered when data is sufficient.
- 06:30 review uses prior snapshots and completed-session data only.
- Email/LINE remain no-send during validation; scheduled delivery remains scheduler-controlled.
