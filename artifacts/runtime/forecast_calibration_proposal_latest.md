# Forecast Calibration Proposal V1

Task: AI-DEV-154
Method: `deterministic_baseline_v1`
Source: `artifacts/runtime/formal_forecast_backtest_report_latest.json`

## Dashboard Summary

- Stock universe count: 9
- Eligible sample count: 9
- Same-day interval hit rate: 55.5556
- Next-day interval hit rate: 資料不足
- Tuning gate status: blocked_insufficient_sample

## Sample Limitations

- 目前 eligible sample count 低於 30，只能作初步 proposal visibility，不能進入 shadow tuning。
- 隔日高低價區間命中率為 null，因 selected window 沒有 usable next-day actual outcome。

## Blocked Actions

- direct_deterministic_baseline_v1_formula_mutation
- production_rating_action_confidence_weight_mutation
- treat_55_5556_percent_as_validated_model_performance
- display_next_day_null_as_zero_or_failure

## Safety

This proposal does not change deterministic_baseline_v1, production scores, delivery behavior, scheduler, DB, notifications, or trading behavior.
