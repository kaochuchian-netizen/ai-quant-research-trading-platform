# TW Daily Tactical Factor Coverage V1

This contract records actual source availability for AI-DEV-174. Missing fields are not filled with fake neutral values.

Statuses: `available`, `partial`, `limited`, `unavailable`, `stale`, `not_applicable`.

Core groups: price/trend, volume, support/resistance, chip, market context, event/news, prediction snapshot, review outcome.

ETF governance: ETF rows use `not_applicable` for stock-specific institutional/margin fields; those fields are not treated as zero or bearish.

Limited-data governance: 10-19 local daily OHLCV rows can produce conservative range/reversal observations with low confidence and small position size. Fewer than 10 rows forces `no_trade`.

TW-only boundary: this contract does not allow SPY, QQQ, VIX, SEC, US premarket, US sector ETF, or 工作表2 data in TW Tactical.
