# AI-DEV-124 Confidence Calibration V1

## Purpose
AI-DEV-124 adds deterministic, advisory-only calibration analysis for prediction confidence, ratings, actions, source coverage readiness, and high/low forecast errors. It produces JSON artifacts and validation results without changing production behavior.

## Scope
The release builds an offline/sample-first analysis path:
Prediction / Evaluation History -> Confidence Bucket Analysis -> Rating Effectiveness -> Action Effectiveness -> High / Low Error Bias -> Source Coverage vs Accuracy -> Calibration Findings -> Recommendation Artifact -> Validator -> Documentation -> Templates / Examples.

## Non-goals
- No production trading
- No simulation order
- No production order
- No scheduler mutation
- No LINE/Email delivery
- No production DB write
- No secrets read
- No production confidence mutation
- No production forecast weight mutation
- No production rating/action mutation
- No production dashboard publish
- No automatic strategy change
- No broker login
- No large AI/Gemini batch call

## Architecture
`app/calibration/` contains schemas and pure deterministic analyzers. `scripts/orchestrator/build_confidence_calibration_artifact.py` loads optional JSON input or defaults to deterministic offline samples. `scripts/orchestrator/validate_confidence_calibration_v1.py` validates examples, direct analyzer behavior, safety flags, and builder output.

## Input model
`CalibrationInput` uses `confidence_calibration_input_v1`, an advisory-only `samples` list, and an `input_summary`. Missing real history is allowed; validation uses deterministic sample input.

## Calibration sample schema
Each `CalibrationSample` supports `schema_version`, `run_id`, `stock_id`, `stock_name`, `prediction_target`, `prediction_date`, `target_date`, `confidence`, `confidence_status`, `rating`, `score`, `action`, `source_coverage_readiness`, `source_coverage_score`, `predicted_high`, `predicted_low`, `predicted_trend`, `actual_high`, `actual_low`, `actual_close`, `actual_return_1d`, `actual_return_5d`, `actual_return_20d`, `direction_hit`, `close_direction_hit`, `high_error_pct`, `low_error_pct`, `evaluation_status`, `source_ids`, `evidence_ids`, and `advisory_only`.

Supported prediction targets are `intraday_high_low`, `next_day_high_low`, `one_month_trend`, `three_month_trend`, and `rating_action`.

## Confidence bucket analysis
Default buckets are `0.40-0.50`, `0.50-0.60`, `0.60-0.70`, `0.70-0.80`, `0.80-0.90`, and `0.90-1.00`. For each bucket the analyzer computes sample size, unavailable count, average confidence, direction hit rate, close direction hit rate, calibration gap, absolute calibration error, finding, and recommendation.

`calibration_gap = observed_direction_hit_rate - avg_confidence`. Buckets with fewer than 5 usable samples are `insufficient_sample`; 5-19 usable samples are `unstable`; 20 or more samples can be marked `over_confident`, `under_confident`, `well_calibrated`, or `unstable`.

## Overall calibration metrics
The artifact includes total sample size, usable sample size, unavailable sample size, weighted expected calibration error, mean calibration gap, and counts for over-confident, under-confident, well-calibrated, and insufficient buckets. Zero usable samples return `not_available` rather than failing.

## Rating effectiveness
Ratings `A`, `B`, `C`, `D`, `E`, and `unknown` are grouped deterministically. The analyzer reports hit rates, average and median 1d/5d/20d returns, positive return rates, and findings. It does not modify rating rules.

## Action effectiveness
Actions `偏多加碼`, `偏多續抱`, `中性觀察`, `降低追價`, `保守觀望`, and `unknown` are grouped deterministically. The analyzer reports hit rates, average returns, positive return rates, and findings. Neutral actions are not treated as bullish and no action is promoted into a trading signal.

## High / low forecast error analysis
For samples with predicted and actual high/low values, the analyzer computes absolute error, signed bias, over/underestimate rates, and range too wide/narrow rates. Missing predicted high/low is valid and returns `not_available` or excludes the sample as appropriate.

## Source coverage vs accuracy
Source coverage readiness groups are `ready`, `partial`, `insufficient`, and `unknown`. The analyzer compares direction hit rate, average confidence, calibration gap, returns, and high/low error by readiness group. Findings are advisory and may support future review of confidence cap policy.

## Recommendation policy
Recommendations are structured with `recommendation_id`, `severity`, `target_area`, `finding`, `evidence_summary`, `recommended_action`, `production_mutation_allowed`, `requires_human_review`, `related_metrics`, `sample_size`, and `limitations`.

For AI-DEV-124, `production_mutation_allowed` is always `false`. Future production logic changes always require human review.

## Safety boundary
The builder and validator are offline, deterministic, and analysis-only. They do not log in to a broker, place simulation or production orders, send LINE or Email, mutate scheduler state, write production DB state, read secrets, change production confidence, change production forecast weights, change rating/action rules, publish a production dashboard, mutate nginx/systemd/cron, or call large AI/Gemini batches.

## Validation commands
```bash
./venv/bin/python -m py_compile \
  app/calibration/schemas.py \
  app/calibration/confidence_buckets.py \
  app/calibration/calibration_metrics.py \
  app/calibration/rating_effectiveness.py \
  app/calibration/action_effectiveness.py \
  app/calibration/high_low_error.py \
  app/calibration/source_coverage_accuracy.py \
  app/calibration/recommendation_policy.py \
  app/calibration/calibration_builder.py \
  scripts/orchestrator/build_confidence_calibration_artifact.py \
  scripts/orchestrator/validate_confidence_calibration_v1.py

./venv/bin/python scripts/orchestrator/validate_confidence_calibration_v1.py --pretty
./venv/bin/python scripts/orchestrator/build_confidence_calibration_artifact.py --pretty
./venv/bin/python scripts/orchestrator/validate_ai_branch.py --base main --head HEAD --pretty
```

## AI-DEV-122 connection
AI-DEV-122 Prediction Data Foundation can provide prediction snapshots, actual outcomes, evaluations, and source coverage readiness inputs.

## AI-DEV-123 connection
AI-DEV-123 Multi-Source Explainability can provide source IDs, evidence IDs, and attribution context for calibration analysis.

## AI-DEV-125 connection
AI-DEV-125 Adaptive Weight Recommendation can consume advisory calibration findings later. AI-DEV-124 does not change production weights.

## AI-DEV-126 connection
AI-DEV-126 Dashboard Intelligence can decide whether and how to display calibration warnings later. AI-DEV-124 does not publish production dashboards.

## Future backtesting.py strategy research
The artifact can be used as offline research input for future `backtesting.py` experiments. No automatic strategy change is allowed.
