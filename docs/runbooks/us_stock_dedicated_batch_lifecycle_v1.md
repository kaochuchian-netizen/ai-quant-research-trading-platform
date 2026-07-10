# AI-DEV-168 US Stock Dedicated Batch Lifecycle V1

AI-DEV-168 defines a dedicated US-stock batch foundation. It is intentionally separate from the Taiwan-stock workflow so US symbols from `工作表2` never enter Shioaji, TWSE, Taiwan chip, Taiwan financing, or Taiwan margin modules.

## Watchlist Source

- Same Google Sheet file is used.
- Taiwan stocks remain on `工作表1`.
- US stocks are read from `工作表2` only.
- Supported US columns and aliases: `symbol` / `ticker`, `name` / `company_name`, `market`, `exchange`, `currency`, `enabled`, `note`.
- Rows from `工作表2` default to `market=US` and `currency=USD` when omitted.
- Enabled parsing accepts `TRUE`, `true`, `yes`, `1`, `Y` and rejects `FALSE`, `false`, `no`, `0`, `N`.

## Windows

The US batch uses fixed Taiwan time, not floating ET time:

- `us_pre_market_2000`: 20:00 Asia/Taipei, US pre-market report.
- `us_intraday_2300`: 23:00 Asia/Taipei, US intraday report.
- `us_post_close_review_0630`: 06:30 Asia/Taipei next morning, post-close prediction review.

US daylight saving time may be mentioned as context in reports, but it does not move these batch times.

## Data Source Policy

V1 uses yfinance/Yahoo only as a market/external reference source contract. It is not a company official disclosure source and cannot replace SEC, company IR, earnings releases, or official filings. Validation is offline and does not call yfinance/Yahoo or Google Sheets.

## Technical Analysis

Market-agnostic indicators are contract-ready: MA5, MA20, MA60, RSI14, MACD, Bollinger, volume moving average, range position, and trend/momentum summary. Taiwan-only assumptions such as TW price limits, TWD formatting, TWSE trading days, chip score, and margin score are excluded.

## Bilingual News

English news/company information uses a copyright-safe bilingual format:

- English headline or short excerpt only.
- Traditional Chinese translation.
- Three to five vocabulary or phrase notes when available.
- Traditional Chinese investment interpretation.
- No full copyrighted article copying.

If no safe source artifact exists, the report says the news data is pending instead of inventing headlines.

## Scoring Governance

US scoring is isolated from Taiwan scoring. V1 dimensions are:

- technical: 0.40
- news/company event: 0.25
- market environment: 0.20
- volatility/risk: 0.15

Taiwan chip weights and TWSE institutional/margin modules are not used.

## Prediction Lifecycle

Each enabled US stock has a formal prediction contract with current/last price, predicted session high/low, predicted next-session high/low, one-month trend, three-month trend, confidence, rationale, generated time, `market=US`, and `currency=USD`. If market data is insufficient, prediction fields remain null with `prediction_status=insufficient_data`.

## Review Lifecycle

The 06:30 window is the main US prediction review window. Review contracts include snapshot prediction references, actual outcome status, direction hit, high/low error, confidence calibration, rating/action effectiveness, pending policy, reviewable count, reviewed count, skipped count, and `market=US`.

## Dashboard / Email / LINE

- Dashboard is the full visible output target.
- Email is a full report candidate but disabled by default.
- LINE is a short reminder candidate only and disabled by default.
- `notification_policy=controlled_pending_pm_activation`.

## Scheduler Policy

This PR defines scheduler-ready metadata only. It does not install cron, systemd timers, or notification activation. Future PM activation should separately review the 20:00 / 23:00 / 06:30 runtime plan and explicitly enable scheduler delivery.

## Validation

```bash
python3 -m py_compile app/us_stock/*.py scripts/orchestrator/build_us_stock_report_artifact.py scripts/orchestrator/run_us_stock_batch.py scripts/orchestrator/validate_us_stock_dedicated_batch_lifecycle_v1.py
python3 scripts/orchestrator/build_us_stock_report_artifact.py --window us_pre_market_2000 --pretty
python3 scripts/orchestrator/run_us_stock_batch.py --window us_pre_market_2000 --dry-run --pretty
python3 scripts/orchestrator/validate_us_stock_dedicated_batch_lifecycle_v1.py --pretty
```

## Safety Boundaries

AI-DEV-168 does not run `python3 main.py`, does not run production pipelines, does not send LINE/Email, does not activate scheduler/cron/systemd timers, does not write DB, does not trade/place orders, does not read secrets, and does not trigger valid manual rerun.
