# AI-DEV-174 TW Daily Tactical Intelligence Engine V1

## Purpose

TW Daily Tactical adds a deterministic short-term strategy beside the existing TW Research / Position strategy. The tactical layer focuses on the current session, next session, and roughly 1-5 trading days. It is research guidance only and never creates orders.

## Strategy Isolation

Every stock keeps two independent strategy outputs:

- `research_position`: existing TW medium-term score, rating, action, prediction, 1M/3M view, and confidence.
- `daily_tactical`: new short-term setup, entry zone, invalidation, stop reference, targets, reward/risk, confidence, playbook, and review.

Daily Tactical does not overwrite Research. Conflicting conclusions are valid, for example Research may stay neutral or constructive while Tactical says avoid chasing.

## Market Isolation

TW Tactical uses TW-only inputs:

- local historical OHLCV
- TW technical indicators
- TW volume and range context
- TW chip/flow contract, with unavailable institutional/margin data marked explicitly
- TW market breadth/volume proxy from the TW watchlist
- TW news/event status when available

TW Tactical must not use US premarket, SPY, QQQ, VIX, US sector ETFs, SEC, or US event logic. US runtime and US Tactical behavior are unchanged.

## Factor Coverage

Price and trend factors:

- MA5 / MA10 / MA20 / MA60
- MA20 slope / MA60 slope
- RSI14
- MACD / signal / histogram
- Bollinger upper / middle / lower and width
- ATR14 and ATR percentage
- 5 / 10 / 20 day high-low ranges
- current range position
- short/mid trend consistency

Volume factors:

- Volume MA5 / MA20
- Relative volume based on daily bars
- Volume expansion / contraction
- Price-volume confirmation
- Breakout volume confirmation

Chip factors:

- `chip_direction`
- `chip_score`
- `institutional_flow`
- `margin_risk`
- `short_interest_signal`
- `flow_confirmation`

When institutional or margin data is unavailable, the engine marks the source as unavailable and lowers data quality/confidence instead of inventing neutral completeness.

## Tactical Weights

`tw_daily_tactical_factor_v1` uses versioned weights:

- technical_setup: 22%
- volume_confirmation: 16%
- chip_flow: 14%
- market_context: 12%
- risk_quality: 18%
- data_quality: 18%

The Dashboard reads the output, not the weight constants. Validators protect the weight keys and strategy version.

## Setup Rules

Supported setup types:

- `breakout`: price breaks recent resistance with trend and volume support, while RSI is not extremely overheated.
- `pullback`: trend remains constructive and price pulls back into MA/support with controlled risk.
- `trend_continuation`: price remains above key moving averages with constructive momentum.
- `mean_reversion`: price is stretched toward lower band or oversold while structure is not broken.
- `range_trade`: price remains in a defined range with acceptable reward/risk.
- `reversal_watch`: early turn signal with incomplete confirmation.
- `no_trade`: reward/risk, data quality, volatility, chase risk, liquidity, chip conflict, or event uncertainty is not acceptable.

## Entry / Stop / Target Methodology

All numeric levels are deterministic.

Entry zone depends on setup:

- Breakout: resistance area plus a small ATR-based confirmation buffer.
- Pullback: support and short moving-average area with ATR allowance.
- Mean reversion: lower band/support area.
- Range trade: lower to middle range area.

Stop / invalidation uses structural support and ATR, not a fixed percent.

Targets use nearby resistance, recent highs, Bollinger bands, and ATR-derived move expectations.

Reward/risk formula:

```text
reward_risk = (target_1_mid - entry_mid) / max(entry_mid - stop_invalidation, small_positive_value)
```

If reward/risk is too poor or risk is excessive, the engine downgrades position size or emits `no_trade`.

## Data Quality Downgrade

Sources are marked as:

- available
- partial
- unavailable
- stale

Limited data lowers confidence. Critical gaps can force `no_trade`. Missing fields remain explicit; the engine does not fabricate values.

## Prediction Lifecycle

Each stock gets a TW Daily Tactical prediction snapshot with:

- market = TW
- strategy_type = daily_tactical
- stock_id
- prediction_date
- direction
- setup_type
- entry zone
- stop / invalidation
- target 1 / target 2
- expected move
- reward/risk
- confidence
- position size
- data quality

Research predictions remain unchanged.

## Review Lifecycle

The review contract is trigger-aware and supports:

- win
- loss
- breakeven
- not_triggered
- no_trade
- expired
- insufficient_data

A setup is not counted as a loss if the entry zone was never triggered. Same-day stop/target ambiguity uses conservative handling. Review fields include entry touched, stop breached, target reached, MFE, MAE, realized reward/risk, false breakout, and pending reason.

## Dashboard Contract

TW Dashboard shows:

- 中長期量化策略
- 每日短期操作策略

Each TW tactical card includes direction, setup, action, score, rating, confidence, entry zone, stop/invalidation, target 1, target 2, expected move, reward/risk, chase risk, event risk, position size, data quality, reasons, risks, playbook, and prediction review.

US Dashboard is not changed by this task.

## Email / LINE Contract

TW Email includes Research / Position Strategy, Daily Tactical Strategy, and risk/data-quality context. The tactical section can include setup, entry, stop, target, reward/risk, confidence, and no-trade reasons.

TW LINE remains concise and contains only counts, risk summary, and Dashboard URL. It does not include full entry/stop/target tables.

No validation run sends LINE or Email.

## Controlled Runtime

Allowed:

- dry-run build
- runtime artifact build without approved delivery
- Dashboard controlled publish

Forbidden:

- `python3 main.py`
- orders/trades
- scheduler time changes
- secrets or PIN reads
- unscheduled LINE/Email
- US Tactical rule changes

## Rollback

1. Revert the AI-DEV-174 commit from main if needed.
2. Rebuild/publish the previous Dashboard backup.
3. Remove `artifacts/runtime/tw_daily_tactical` runtime artifacts if they are no longer desired.
4. Leave scheduler unchanged.

## Validation Commands

```bash
python3 -m py_compile app/strategy/tw_daily_tactical.py scripts/orchestrator/build_tw_daily_tactical_runtime_v1.py scripts/orchestrator/validate_tw_daily_tactical_intelligence_engine_v1.py
python3 scripts/orchestrator/build_tw_daily_tactical_runtime_v1.py --pretty
python3 scripts/orchestrator/validate_tw_daily_tactical_intelligence_engine_v1.py --pretty
python3 scripts/orchestrator/validate_dual_strategy_intelligence_engine_v1.py --pretty
python3 scripts/orchestrator/validate_multi_market_dashboard_v2_us_link_isolation_v1.py --pretty
python3 scripts/orchestrator/validate_ai_branch.py --base main --head HEAD --pretty
```

## Known Limitations

- Institutional flow and margin/short data are marked unavailable unless the current runtime provides safe source artifacts.
- Broad TW market breadth is approximated from the tracked universe until official breadth data is connected.
- V1 does not claim profitability; it creates a backtest-ready deterministic tactical contract.
