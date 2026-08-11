# TW Production Intelligence Data Foundation V1

## Purpose

AI-DEV-202 separates five ownership layers: source facts, canonical evidence, RRE interpretation, prediction/evaluation, and Decision Layer action. Research and prediction never authorize a trade.

## Root cause audit

The 2026-08-11 admitted TW lifecycle showed current quotes for all nine symbols, but every local historical CSV contained only 19 daily rows and ended on 2026-07-24. The pre-open updater requested Shioaji bars, then fell directly back to those files when login/fetch failed. The technical engine already supported MA, RSI, MACD, ATR, volume, and price-structure features, but its 20-bar eligibility gate therefore correctly rejected every symbol. RRE received an unavailable technical contract. Intraday quotes reached presentation cards, but RRE encoded a lone price as neutral rather than deriving session behavior from open/current/high/low. Prediction used Entry/Target geometry and was changed to `no_trade` when Decision abstained, so post-close returned `not_applicable` and accumulated no forecast sample.

Google News RSS did return metadata. The upstream analysis path did not produce a safe direction, while many results were stale or secondary. Public aggregation treated “metadata exists but no usable directional evidence” as indistinguishable from “no source”. V2 keeps raw/partial coverage separate from usable evidence and never invents sentiment.

## Canonical lineage

`Shioaji -> yfinance .TW/.TWO -> existing CSV` is the historical fallback order. A fallback must normalize date/open/high/low/close/volume and contain at least 20 bars before it replaces the canonical CSV. Per-source failure details remain in the stage status.

Existing technical calculations are reused. `tw_daily_ohlcv_features_v2` attaches period, bars, source, method version, sufficiency, freshness, and reason codes. A semantic validator rejects the unexplained state “sufficient OHLCV but empty technical evidence”.

Coverage V2 is category-aware. `not_applicable` is removed from the denominator; partial or stale evidence receives reduced usefulness; duplicate news does not add coverage. ETF cards do not require company fundamentals or issuer events. ADR evidence applies only to mapped symbols.

## Prediction versus decision

`tw_prediction_snapshot_v2` is generated whenever at least ten valid bars, latest close, and deterministic volatility evidence exist. Direction uses deterministic MA5/MA10 alignment; the range uses latest close ± ATR14. This is an evaluable research forecast, not a trade plan. It stores method, evidence, research, hypothesis, decision linkage, and pre-outcome timestamp.

A `NO_TRADE` card retains this snapshot. Post-close independently evaluates range overlap, interval width, high/low/midpoint error, direction, confidence bucket, and a conservative no-trade classification. Trade outcome remains owned by the existing lifecycle and can remain `no_trade` for all symbols.

## Verification maturity

The append-safe record links immutable prediction identity to a later review identity. Maturity is reported as `NO_SAMPLE`, `EARLY_SAMPLE`, `DEVELOPING_SAMPLE`, `MINIMUM_REVIEWABLE_SAMPLE`, or `MEANINGFUL_FORWARD_SAMPLE`. Fixture/replay success proves architecture only. Live predictive usefulness requires natural forward samples and no-lookahead review.

## Source limitations

MOPS/TWSE/TPEx official-event collectors are not proven production-connected. Google News RSS provides metadata but not guaranteed reliable direction. No paid source was added. These remain explicit coverage gaps rather than neutral evidence.

## Natural verification

Observe a full admitted 07:00→13:05→13:35→15:00 lifecycle. Confirm refreshed history, technical provenance, differentiated RRE notes, independent predictions on no-trade cards, post-close evaluation counts, source reason codes, channel identities, and append-safe maturity growth. Do not call deterministic replay evidence of predictive accuracy.
