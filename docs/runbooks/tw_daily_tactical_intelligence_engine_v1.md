# AI-DEV-174 TW Daily Tactical Intelligence Engine V1

## Purpose

TW Daily Tactical adds a deterministic short-term strategy beside the existing TW Research / Position strategy. It answers whether a stock has tactical value today through roughly 1-5 trading days. It is research guidance only and never creates orders.

## Strategy Isolation

Every TW card contains `strategies.research_position` and `strategies.daily_tactical`. Research keeps existing score/rating/action/prediction behavior. Tactical has its own factor version, score components, action, entry, invalidation, targets, reward/risk, prediction snapshot, and trigger-aware review. Tactical never overwrites Research.

## Market Isolation

TW Tactical uses only Taiwan market inputs: local TW historical OHLCV, TW technical indicators, volume, support/resistance, TW chip/flow contract, TW market context proxy, and TW news/event status when available. It does not use US premarket, SEC, SPY, QQQ, VIX, US sector ETFs, or 工作表2 data.

## Actual Data Source Inventory

Current production-safe V1 sources are local historical OHLCV and existing TW formal runtime artifacts. TWSE institutional flow, margin/short, broad market breadth, and news/event details are explicit `unavailable` or `not_applicable` where not connected. Missing data lowers confidence and position size instead of being fabricated.

## Factor Definitions

Price/trend: MA5, MA10, MA20, MA60, MA20/MA60 slope, RSI14, MACD/signal/histogram, Bollinger bands/width, ATR14, 5/10/20 day high-low, range position, MA deviation, volatility state.

Volume: latest daily volume, volume MA5, volume MA20, daily relative volume, expansion/contraction, price-volume confirmation, breakout volume confirmation. Daily relative volume is based on daily bars and is not described as real-time intraday RVOL.

Support/resistance: recent swing high/low, 5/10/20 day high-low, MA5/MA10/MA20/MA60, Bollinger band, ATR buffer, and Taiwan tick-size rounding.

Chip: chip direction, chip score, institutional flow shell, margin risk shell, short signal, flow confirmation, chip data quality. ETF-specific fields are `not_applicable`.

Market context: watchlist breadth proxy, market volume status, market risk, market regime. Broad TWSE/OTC breadth remains unavailable until connected.

## Setup Rules

Supported setups: `breakout`, `pullback`, `trend_continuation`, `mean_reversion`, `range_trade`, `reversal_watch`, `no_trade`. Each setup has deterministic trigger logic, reasons, risk reasons, invalidation, and a fixed playbook template. Limited 10-19 bar history can only produce conservative range/reversal observations with low confidence.

## Entry / Stop / Target

Entry depends on setup: breakout uses resistance plus ATR buffer; pullback uses support/MA/ATR; mean reversion uses lower band/support; range trade uses lower-to-mid range. Stop/invalidation uses structure plus ATR and tick-size rounding. Targets use resistance, ATR extension, range projection, and reward/risk. No LLM-generated price levels are allowed.

Reward/risk uses representative entry, stop, and target: `(target_1_mid - entry_mid) / max(entry_mid - stop, small_positive_value)` for long/neutral tactical observations, with absolute distance handling in runtime. Low reward/risk downgrades rating or emits no_trade.

## Score and Confidence

`tw_daily_tactical_factor_v1` weights: technical_setup 22%, volume_confirmation 16%, chip_flow 14%, market_context 12%, risk_quality 18%, data_quality 18%. Runtime stores score components, score_before_penalty, risk_penalty, data_quality_penalty, and final_score. Confidence is separate from score and reflects coverage, setup confirmation, reward/risk, chase risk, market risk, and missing data.

## Chase Risk and Position Size

Chase risk considers MA5/MA20 deviation, RSI, Bollinger upper proximity, ATR expansion, resistance/target proximity, and weak volume confirmation. High chase risk can output avoid/wait-for-pullback even when Research is constructive. Position size is `normal`, `half`, `small`, or `avoid`.

## Prediction Lifecycle

Each stock has an independent TW Tactical prediction snapshot with market, strategy_id, strategy_type, stock_id, prediction_date, valid_from, valid_until, 1D/3D/5D windows, direction, setup, entry, stop, targets, expected move, reward/risk, confidence, position size, data quality, score components, and prediction_status. Research predictions remain unchanged.

## Review Lifecycle

The review is trigger-aware and supports win, loss, breakeven, not_triggered, no_trade, expired, insufficient_data, and pending. It records entry trigger, stop/target trigger indices, conservative same-bar policy, MFE, MAE, realized reward/risk, false breakout, and whether the outcome counts as win/loss. No Trade is reviewed separately and is not counted as a normal win/loss.

## Dashboard / Email / LINE

TW Dashboard shows Research and Daily Tactical separately. Daily Tactical displays direction, setup, action, score/rating/confidence, entry, stop/invalidation, targets, expected move, reward/risk, chase risk, event risk, position size, data quality, factor coverage, score components, reasons, risk reasons, playbook, and review.

TW Email preview includes Research + Tactical and tactical entry/stop/target/RR. TW LINE stays concise with counts only; no full price table. Validation sends no Email or LINE.

## Runtime Health and Delivery Readiness

Runtime artifacts include `runtime_health` and `delivery_readiness`: stock counts, tactical coverage, prediction coverage, insufficient-data counts, dashboard/email/line readiness, and blocking reasons. Secrets, sessions, raw network logs, and credentials are never displayed.

## Controlled Runtime

Allowed: fixture/unit validation, dry-run, production artifact build without delivery approval, controlled TW artifact refresh, controlled Dashboard publish. Forbidden: `python3 main.py`, production-approved delivery, orders, scheduler changes, secrets, unscheduled notifications, US tactical changes.

## Rollback

Revert the AI-DEV-174 commit, rebuild/publish the prior Dashboard backup, and leave scheduler unchanged. Runtime artifacts can be regenerated from the previous main if needed.

## Known Limitations

Current V1 marks detailed TWSE institutional flow, margin/short, official broad market breadth, and event/news details unavailable unless already present in safe runtime artifacts. Limited local history produces conservative observation only and does not claim performance.
