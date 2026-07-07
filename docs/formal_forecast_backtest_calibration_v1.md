# AI-DEV-153 Forecast Backtest & Calibration Report V1

AI-DEV-153 adds a read-only backtest and calibration report for `deterministic_baseline_v1`, the formal forecast value engine introduced in AI-DEV-152.

## Purpose

The report answers whether the baseline high/low interval is useful, where it misses, and whether artifact-level `confidence_score` is directionally calibrated. It does not introduce a new forecast method and does not modify the AI-DEV-152 formula.

## Data Source Policy

Allowed inputs are read-only local artifacts and historical data:

- `data/historical/*_daily.csv`
- formal prediction runtime artifact for stock universe discovery
- formal review runtime artifact for compatibility checks
- read-only SQLite inspection when a future report needs contextual metadata

The builder does not call external APIs, does not read secrets, does not write DB, does not run `python3 main.py`, and does not execute production pipelines.

## Metric Definitions

- `interval_hit`: actual high is less than or equal to predicted high and actual low is greater than or equal to predicted low.
- `partial_hit`: only the high side or only the low side is covered.
- `miss`: neither side is covered.
- `under_covered_rate`: percentage of eligible cases with a miss.
- `over_wide_rate`: percentage of eligible cases where interval width is above the V1 wide-interval threshold.
- `direction_accuracy`: percentage of bullish/bearish trend signals that match same-day close direction versus previous close.
- `confidence_bucket_hit_rate`: hit rate grouped into low, medium, and medium_high buckets.
- `confidence_calibration_gap`: bucket hit rate minus the bucket midpoint.

## Insufficient Data Policy

When history is missing, fewer than 20 rows exist, or actual outcome is unavailable, the report marks the case as `insufficient_data`. It never fabricates hit rates, actual prices, or calibration findings.

## Calibration Interpretation

Recommendations are proposals only. They can suggest reviewing range multiplier, confidence cap, or trend bias, but `production_formula_changed` must remain false. Any actual formula change requires a future AI-DEV task with separate validation.

## Known Limitations

The report is a deterministic historical replay. It is not a production model training job, not an adaptive strategy engine, and not a trading signal. Confidence calibration is meaningful only when each bucket has enough eligible samples.

## Validation

Run:

```bash
python scripts/orchestrator/build_formal_forecast_backtest_report.py --pretty
python scripts/orchestrator/validate_formal_forecast_backtest_report_v1.py --pretty
python scripts/orchestrator/validate_ai_branch.py --base main --head HEAD --pretty
```

## Future Roadmap

Future tasks may add longer-window comparisons, volatility-regime-specific calibration, human approval gates for formula proposals, and dashboard display of a concise backtest summary.
