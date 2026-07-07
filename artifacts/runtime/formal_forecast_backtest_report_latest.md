# Formal Forecast Backtest & Calibration Report V1

Task: AI-DEV-153
Method under test: `deterministic_baseline_v1`
Generated at: 2026-07-07T09:30:00+08:00
Window: 2026-03-08 to 2026-07-06

## Summary Metrics

- Stock universe count: 9
- Eligible sample count: 9
- Same-day interval hit rate: 55.5556
- Next-day interval hit rate: None
- Under-covered rate: 0.0
- Over-wide rate: 11.1111
- Direction accuracy: 66.6667

## Calibration Recommendations

- retain_formula_pending_longer_backtest: 暫不調整 deterministic_baseline_v1，持續累積正式 artifact 與 actual outcome。 Production formula changed: False.

## Safety

This report is read-only. It does not mutate deterministic_baseline_v1, production ratings, actions, confidence, weights, DB, scheduler, notifications, or trading behavior.
