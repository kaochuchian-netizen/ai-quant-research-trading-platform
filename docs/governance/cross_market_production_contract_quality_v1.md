# Cross-Market Production Contract Quality V1

## Canonical provider boundary

Provider responses are raw facts, not consumer contracts. Each provider shape is normalized once, versioned, and rejected with `SCHEMA_MISMATCH` when its shape changes. Validators must label evidence as `SYNTHETIC_UNIT`, `PRODUCTION_SHAPE_FIXTURE`, `IMMUTABLE_HISTORICAL_REPLAY`, or `NATURAL_PRODUCTION`; fixture success never proves natural verification.

The US yfinance context contract is `items[SPY|QQQ|SOXX|...]`. `us_market_context_v2` exposes broad market, growth/technology, semiconductor sector, volatility, and provenance independently. Research consumers may not read raw provider keys.

## Taiwan history admission

Shioaji, yfinance `.TW`, yfinance `.TWO`, and existing CSV all pass `validate_history_candidate`. Fetch success, normalization, integrity, freshness, admission, feature generation, and research consumption are separate states. Admission requires canonical OHLCV columns, parseable/unique dates, valid OHLC geometry, nonnegative volume, no future bars, minimum lookback, and freshness relative to the target session.

An existing 19-row or stale file is not usable merely because it exists. Its explicit status is retained in Operations. No rejected candidate is persisted over a previously admitted history file.

## Instrument master

`config/governance/instrument_master_v1.json` is the canonical versioned source for the formal TW watchlist. Task-local mappings may consume this master but cannot override it. ETF company-only categories and unmapped ADR relationships are `NOT_APPLICABLE`, not missing. Metadata includes source and effective date.

## No-lookahead V2

All timestamps are parsed as timezone-aware values. The enforced order is:

1. `last_input_market_timestamp <= prediction_data_cutoff`
2. `prediction_data_cutoff < first_outcome_observation_timestamp`
3. `first_outcome_observation_timestamp <= outcome_data_cutoff`
4. `outcome_data_cutoff <= review_generated_at`
5. `prediction_data_cutoff <= prediction_generated_at`

Naive timestamps, malformed offsets, future daily bars, and outcome data inside prediction inputs fail closed.

## Completeness and semantic health

`intelligence_completeness_v2` separates market data, technical evidence, research evidence, Decision input, and prediction input. A complete quote is never universal “data complete.” Runtime success is separate from data-quality, research, prediction, Decision, and intelligence health.

Semantic degradation includes provider values lost by consumers, valid history with empty technical features, price evidence disconnected from research, predictions without evidence identity, and market-complete/research-partial states. Known root causes use explicit failure codes; `insufficient_evidence` remains a research conclusion rather than an operational diagnosis.

## Cache and compatibility policy

Canonical schema and method versions participate in identities/provenance. A provider-shape change must change its raw schema adapter or fail parity validation; legacy consumer-shaped caches are not silently admitted. Normalized results may be cached only with source identity, path/size/mtime where applicable, schema version, and method version.

## Natural verification

After merge, observe one complete US 20:00→23:00→06:30 chain and one TW 07:00→13:05→13:35→15:00 chain. Confirm real provider context survives normalization, stale/short history is degraded, adequate history reaches technical evidence, completeness labels remain scoped, timing stays no-lookahead-safe, and Operations separates runtime from intelligence health.
