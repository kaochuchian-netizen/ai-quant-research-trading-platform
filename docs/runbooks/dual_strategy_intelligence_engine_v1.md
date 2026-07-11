# AI-DEV-173 Dual Strategy Intelligence Engine V1

## Purpose
AI-DEV-173 separates every market into two strategy lanes:

- Research / Position Strategy: medium and longer horizon research guidance, days to months.
- Daily Tactical Strategy: short-term daily setup guidance, current session, next session, and roughly 1-5 trading days.

Both strategies are advisory-only. They do not create orders, do not call brokerage APIs, and do not change scheduler times.

## Market Isolation

TW and US stay isolated:

- TW uses 工作表1 and Taiwan runtime artifacts.
- US uses 工作表2 and US runtime artifacts.
- US Tactical cannot use TW chip/margin/institutional factors.
- TW Tactical cannot use SEC, US pre-market, SPY/QQQ/VIX, or US earnings factors.
- Missing data in one market never falls back to the other market.

## Strategy Taxonomy

Every strategy output must include:

- `market`: `TW` or `US`
- `strategy_type`: `research_position` or `daily_tactical`
- `strategy_version`
- `generated_at`
- `horizon`
- `score`
- `action`
- `confidence`
- `risk_notes`
- `data_quality`
- `factor_version`

No untyped strategy result is authoritative.

## Research / Position Strategy

TW Research preserves existing Taiwan scoring, rating, action, prediction, and review behavior. AI-DEV-173 wraps the result as `strategy_type=research_position` and does not change TW formulas.

US Research preserves the live-data research stack:

- technical indicators
- yfinance market data
- SEC metadata
- fundamentals reference fields
- earnings/guidance separation
- official/company events
- material bilingual news
- `us_research_factor_v1`

Research remains the strategy for holding quality and 1M/3M positioning.

## Daily Tactical Strategy

Daily Tactical is independent from Research. It has its own factor versions:

- TW: `tw_daily_tactical_v1`, factor version `tw_daily_tactical_factor_v1`
- US: `us_daily_tactical_v1`, factor version `us_daily_tactical_factor_v1`

Tactical output includes:

- tactical direction
- tactical score/grade/confidence
- setup type
- entry zone
- invalidation level / stop reference
- target zone 1 and optional target zone 2
- expected move
- reward/risk ratio
- chase risk
- gap risk
- event risk
- tactical rationale

Allowed setup types:

- breakout
- pullback
- trend_continuation
- mean_reversion
- gap_follow_through
- gap_fade
- range_trade
- no_trade
- insufficient_data

## TW Tactical Factors

TW Tactical groups:

- price_momentum
- trend_strength
- breakout_quality
- volume_confirmation
- chip_confirmation
- mean_reversion_risk
- volatility_risk
- market_context
- event_risk
- data_completeness

TW-specific interpretation respects Taiwan sessions and price-limit context. Chip/flow evidence is scoped to TW only and remains optional when not available.

## US Tactical Factors

US Tactical groups:

- premarket_gap
- momentum
- trend_strength
- relative_volume
- breakout_quality
- mean_reversion_risk
- volatility_risk
- benchmark_context
- sector_context
- earnings_event_risk
- official_news_catalyst

US-specific interpretation accounts for pre-market/regular-session context, US event risk, SPY/QQQ/VIX/sector context, and DST/session metadata.

## Entry / Stop / Target Methodology

Daily Tactical levels are deterministic. Inputs may include:

- ATR-like range percentage
- daily range percentage
- return volatility
- Bollinger bands
- MA20
- current/last price
- trend and MACD/RSI state
- event risk

Rules:

- If history is insufficient, Tactical level output is suppressed.
- If event risk is high, setup can become `no_trade` and levels are suppressed.
- Entry zone must be ordered low to high.
- Stop reference must invalidate the setup.
- Target zone must be ordered low to high.
- Reward/risk is calculated from deterministic entry, stop, and target levels.
- No LLM-only price levels are allowed.

## Prediction Separation

Artifacts may contain:

```json
{
  "strategies": {
    "research_position": {},
    "daily_tactical": {}
  }
}
```

Research prediction preserves current session/next-session range and 1M/3M trend.
Daily Tactical prediction provides setup, entry, stop/invalidation, target, expected move, and tactical confidence.

Tactical never overwrites Research.

## Review Separation

Research Review preserves current direction/range/confidence/rating/action review.

Daily Tactical Review is trigger-aware:

- win
- loss
- breakeven
- not_triggered
- correctly_avoided
- invalid_data
- pending

A setup is not a loss if the entry trigger never occurred.

TW and US metrics remain separate:

- TW Research
- TW Tactical
- US Research
- US Tactical

No single cross-market hit rate is produced without an explicit cross-market summary layer.

## Backtest / Evaluation Rules

Tactical evaluation uses deterministic snapshots and actual outcomes.

Rules:

- Entry only counts when trigger occurs.
- Same-bar stop/target ambiguity must be documented by the evaluation engine before profitability claims.
- No lookahead bias.
- Transaction cost and slippage should be explicit governed assumptions before production profitability claims.
- Limited samples must not be packaged as proven performance.

## Dashboard Behavior

TW Dashboard shows:

- 中長期量化策略
- 每日短期操作策略

US Dashboard shows:

- Research / Position Strategy
- Daily Tactical Strategy

US per-stock cards display Tactical direction, setup, action, entry zone, stop reference, target zone, expected move, reward/risk, chase risk, and event risk.

Both TW and US pages retain shared navigation:

- 回到總覽
- 台股 Dashboard
- 美股 Dashboard

## Email / LINE Behavior

Email includes both strategy summaries.

LINE remains concise and may include:

- market/window label
- Research summary count
- Daily Tactical watch count
- high-risk/no-trade count
- Dashboard link

LINE does not include full entry/stop/target tables.

## Conflict Example

Research: 偏多續抱

Daily Tactical: 短線過熱，避免追高

This is valid. Research and Tactical are independent and may disagree.

## Safety

Forbidden:

- `python3 main.py`
- trading/order execution
- unscheduled LINE/Email tests
- valid manual rerun trigger
- reading or printing secrets/PIN/.env
- changing TW/US scheduler times
- TW/US cross-market fallback

## Validation

Run:

```bash
python3 -m py_compile app/strategy/dual_strategy.py scripts/orchestrator/validate_dual_strategy_intelligence_engine_v1.py
python3 scripts/orchestrator/validate_dual_strategy_intelligence_engine_v1.py --pretty
python3 scripts/orchestrator/validate_us_stock_research_intelligence_v1.py --pretty
python3 scripts/orchestrator/validate_us_stock_live_data_prediction_review_runtime_v1.py --pretty
python3 scripts/orchestrator/validate_multi_market_dashboard_v2_us_link_isolation_v1.py --pretty
python3 scripts/orchestrator/validate_dashboard_manual_single_window_rerun_v1.py --pretty
python3 scripts/orchestrator/validate_ai_branch.py --base main --head HEAD --pretty
```

## Rollback

Rollback is a normal Git revert of AI-DEV-173 plus restoring the previous Dashboard publish backup if runtime publication has occurred.

No scheduler rollback is expected because this task does not change scheduler times or services.
