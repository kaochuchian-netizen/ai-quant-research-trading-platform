# Forecast Method Tuning Gate V1

AI-DEV-154 defines the decision gate for tuning `deterministic_baseline_v1`. It is deliberately conservative: AI-DEV-153 produced useful early evidence, but 9 eligible samples are not enough to change the formula.

## Current State

- Method under test: `deterministic_baseline_v1`
- Eligible sample count: 9
- Same-day interval hit rate: 55.5556%
- Next-day interval hit rate: null because next-day actual outcomes are unavailable in the selected window
- Current action: proposal visibility only / insufficient sample warning

## Why 9 Samples Cannot Change the Formula

A 9-case backtest is useful for wiring and sanity checks, but it cannot establish stable model performance. It does not cover enough trading days, volatility regimes, stock-specific behavior, or confidence buckets. Treating 55.5556% as validated performance would overstate the result.

## Ready For Shadow Tuning

A future task may enter shadow tuning only when all minimum gates are met:

- eligible sample count >= 30
- at least 5 trading days of comparable formal prediction / actual outcome artifacts
- same-day hit rate and under-covered rate can be computed without fake metrics
- confidence buckets have basic sample coverage
- no fake metrics and no missing actuals disguised as failures

## Ready For Formula Change

A future task may propose formula changes only when all stricter gates are met:

- eligible sample count >= 100
- at least 20 trading days of formal artifacts
- multiple stocks have comparable forecast / actual outcomes
- calibration proposal has a clear improvement direction
- shadow tuning beats deterministic_baseline_v1
- PM explicit approval is recorded

## Forbidden Direct Changes

Do not directly mutate:

- `deterministic_baseline_v1` range formula
- next-day multiplier
- confidence cap
- trend bias
- production rating/action/confidence/weight logic
- delivery behavior

## Tunable Parameters For Future Proposals

Potential future tuning targets are range multiplier, volatility-regime stratification, trend-bias multipliers, confidence cap, confidence bucket thresholds, and minimum-data rules. AI-DEV-154 documents these only; it does not apply them.
