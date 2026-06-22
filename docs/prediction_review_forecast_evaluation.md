# Prediction Review and Forecast Evaluation

This document defines the research-only forecast evaluation foundation for
future Prediction review, Dashboard, Email report, and backtest comparison work.

## Purpose

Forecast evaluation turns a forecast record and a later outcome record into a
reviewable evaluation result. It is intended to answer:

- What was predicted?
- Which horizon and target were used?
- Was the outcome pending, completed, inconclusive, or not reviewable?
- Which metric should be used for the forecast type?
- Did confidence and model or prompt versions improve over time?

This phase does not connect to production pipelines, LINE, email, cron, trading,
order placement, database writes, historical CSV, or backtest output.

## Prediction Review Lifecycle

1. `forecast_created`: a forecast is generated with `forecast_type`,
   `forecast_target`, `forecast_horizon`, `evaluation_window`,
   `model_version`, `prompt_version`, source metadata, and confidence.
2. `review_pending`: actual outcome fields remain explicit nulls or pending
   placeholders until the evaluation window closes.
3. `outcome_collected`: future reviewed code may collect actual high, low,
   close, direction, or fundamental outcome from traceable sources.
4. `evaluation_completed`: metrics are calculated and stored in a prediction
   review record.
5. `lessons_recorded`: calibration, rating drift, false positives, false
   negatives, and model/prompt comparisons inform future research changes.

The original forecast must not be edited to match the later outcome.

## Forecast Types

Supported planning targets include:

- `same_day_high_low_interval`: same-day high and low interval forecast.
- `next_day_high_low_interval`: next trading day high and low interval forecast.
- `one_month_trend`: 1M directional or categorical trend forecast.
- `confidence_probability`: probability-style forecast with confidence bucket.
- `interval_forecast`: numeric range forecast with lower and upper bounds.

Future types must define forecast target, horizon, evaluation window, required
actual outcome fields, and metrics before being used in examples.

## Evaluation Windows

Recommended windows:

- `intraday`
- `same_day`
- `T+1`
- `5D`
- `20D`
- `1M`

Each window must have a clear close condition. If the close condition is not met,
the review stays `pending`. If required actual values cannot be sourced, the
review is `inconclusive` or `not_reviewable`.

## Evaluation Metrics

Use metrics that match the forecast type:

| Metric | Purpose |
| --- | --- |
| `direction_match` | Whether forecast direction matched actual direction. |
| `interval_hit` | Whether actual high/low stayed inside the predicted interval. |
| `absolute_error` | Numeric distance from forecast interval or point estimate. |
| `high_forecast_error` | Actual high minus predicted high. |
| `low_forecast_error` | Actual low minus predicted low. |
| `confidence_bucket` | Bucketed confidence for calibration review. |
| `confidence_calibration` | Whether realized hit rate matches confidence over many samples. |
| `false_positive` | Forecast expected a positive condition that did not occur. |
| `false_negative` | Forecast missed a positive condition that did occur. |
| `rating_drift` | Change in rating or watchlist status between forecast and review. |
| `model_prompt_comparison` | Comparison across model and prompt versions. |

Single examples are not statistically meaningful. Calibration requires enough
samples per confidence bucket and forecast type.

## Missing Data And Pending Policy

- Use explicit nulls for actual values that are not yet available.
- Use `evaluation_status = pending` before the window closes.
- Use `evaluation_status = inconclusive` when outcome data conflicts or is
  incomplete.
- Use `evaluation_status = not_reviewable` when required source evidence cannot
  be obtained.
- Do not infer missing high, low, close, or direction values from unrelated data.
- Do not include pending or inconclusive records in accuracy aggregates unless a
  later reviewed policy explicitly defines how.

## Dashboard Requirements

Future Dashboard views should show:

- Forecast id, entity, horizon, target, and evaluation status.
- Predicted range, actual range, interval hit, and direction match.
- Confidence bucket and calibration status.
- Model version and prompt version.
- Source tier, data-quality flags, and missing-data policy.
- Links to original forecast and prediction review records.

Dashboard display must remain research-only and must not imply trading action.

## Email Report Requirements

Future Email report payloads may summarize:

- Number of pending, completed, inconclusive, and not-reviewable reviews.
- Top misses by absolute error.
- Interval hit rate by forecast type and horizon.
- Confidence calibration caveats.
- Model and prompt version comparison notes.

This does not authorize sending email. Any delivery mechanism must be a separate
reviewed task.

## Difference From Backtest

Forecast evaluation reviews a forecast against an explicitly defined outcome and
preserves forecast assumptions, model version, prompt version, source evidence,
and confidence. Backtests usually evaluate strategy rules across historical
signals and outcomes at scale.

Forecast evaluation may later feed backtest research, but it is not a production
backtest engine, does not write backtest output, and does not change strategy
ranking behavior in this phase.

## Read-Only Prototype

AI-DEV-017 adds:

```bash
python3 scripts/orchestrator/evaluate_prediction_review_examples.py --pretty
```

The prototype reads only:

- `orchestrator/templates/schemas/forecast.example.json`
- `orchestrator/templates/schemas/prediction_review.example.json`

It calculates example metrics and emits JSON. It does not read production data,
write databases, modify CSV files, call external APIs, run production pipelines,
send notifications, change schedulers, trade, place orders, or read secrets.

## Integration Boundary

Future integration into Dashboard, Email report, Forecast pipeline, Prediction
review storage, or backtest comparison must be separate and reviewed. Before any
integration, the task must define:

- Input source and source tier.
- Required fields and missing-data behavior.
- Whether records are preview-only or eligible for aggregate reporting.
- How model and prompt versions are compared.
- Why the change does not create trading or order execution behavior.
