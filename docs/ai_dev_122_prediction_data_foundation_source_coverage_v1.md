# AI-DEV-122 Prediction Data Foundation And Source Coverage V1

## Purpose

AI-DEV-122 establishes a repo-local prediction data foundation so each advisory prediction can leave a structured snapshot, later match to actual outcomes, produce deterministic evaluation metrics, and explain whether source coverage is sufficient for the prediction target.

## Scope

This release adds additive modules for prediction snapshots, actual outcomes, evaluation V1, source inventory, source coverage, missing-data policy, deterministic artifact building, validation, and example templates.

## Non-goals

- No trading execution
- No production order
- No simulation order
- No scheduler mutation
- No LINE/Email delivery
- No production dashboard publish
- No production DB write
- No production weight mutation
- No backtesting.py runtime integration yet
- No broker login
- No secrets read
- No external AI/Gemini batch call

## Architecture

- `app/prediction/schemas.py`: advisory-only prediction snapshot schema.
- `app/prediction/snapshot_builder.py`: snapshot builder that applies coverage confidence caps.
- `app/prediction/source_inventory.py`: formal source inventory including current, candidate, yfinance, primary, official, market, and noisy sources.
- `app/prediction/source_coverage.py`: target-level source coverage matrix and readiness model.
- `app/prediction/missing_data_policy.py`: explicit policy rules for missing data.
- `app/evaluation/actual_outcome.py`: repo-local historical CSV outcome loader with pending handling.
- `app/evaluation/evaluator.py`: deterministic evaluation V1 metrics.
- `scripts/orchestrator/build_prediction_data_foundation_artifact.py`: prints the full artifact JSON.
- `scripts/orchestrator/validate_prediction_data_foundation_v1.py`: validates schemas, templates, policies, safety, and missing-data behavior.

## Prediction Snapshot schema

`PredictionSnapshot` V1 records `schema_version`, `run_id`, `run_date`, `run_time`, `scheduler_window`, `pipeline_type`, `stock_id`, `stock_name`, `prediction_target`, `predicted_high`, `predicted_low`, `predicted_trend`, `confidence`, `confidence_status`, `rating`, `score`, `action`, `advisory_only`, `source_ids`, `evidence_summary`, `data_coverage_score`, `source_quality_summary`, and `review_status`.

Supported targets are `intraday_high_low`, `next_day_high_low`, `one_month_trend`, `three_month_trend`, and `rating_action`. Missing or unavailable high/low values use explicit objects such as `{"status": "unavailable"}` or `{"status": "not_applicable"}`. Snapshot creation must not fail when high/low are unavailable. All snapshots are advisory-only.

## Actual Outcome schema

`ActualOutcome` V1 records `stock_id`, `target_date`, `actual_open`, `actual_high`, `actual_low`, `actual_close`, `actual_volume`, `actual_return_1d`, `actual_return_5d`, `actual_return_20d`, and `outcome_status`.

Supported statuses are `completed`, `pending`, `missing`, and `insufficient_data`. Future outcomes return `pending`, not failure. V1 reads repo-local historical CSV files only and does not introduce a new external dependency.

## Evaluation V1 metrics

The deterministic evaluator produces `direction_hit`, `high_error_pct`, `low_error_pct`, `close_direction_hit`, `rating_return_1d`, `action_return_1d`, `evaluation_status`, and `pending_reason`.

When actual outcome is unavailable, `evaluation_status` is `pending_actual_outcome`. When predicted high or low is unavailable, the related metric is `not_available`.

## Source Inventory

The inventory fields are `source_id`, `category`, `provider`, `priority`, `status`, `refresh_frequency`, `credential_required`, `current_integration`, `prediction_targets`, `quality_score`, `noise_risk`, `recommended_usage`, and `notes`.

Supported categories are `market_price`, `technical`, `chip`, `news`, `adr`, `fundamental`, `disclosure`, `industry`, `macro`, `etf`, and `trading_runtime`. Supported priorities are `A_primary`, `B_official_or_company_linked`, `C_market_or_industry`, and `D_sentiment_or_noise`.

Current known sources include `google_sheet_stock_universe`, `shioaji_ohlcv`, `historical_csv_fallback`, `twse_openapi`, `google_news_rss`, `gemini_news_summary`, `chip_analysis_existing`, `adr_yfinance`, `yfinance_external_market`, and `sqlite_historical_or_analysis`.

Candidate or missing sources include MOPS revenue, financial statements, material information, investor conference records, TDCC shareholding distribution, ETF NAV/holdings/distribution, industry chain sources, macro context, branch flow, securities lending, company guidance, management interviews, and earnings call or investor deck material.

## Source Coverage Matrix

For each target, the coverage matrix records required sources, optional sources, available sources, missing sources, coverage score, readiness, confidence cap, and missing-data policy. Readiness values are `ready`, `partial`, and `insufficient`.

- `intraday_high_low`: requires OHLCV, technical, and recent price context. ADR and external market are optional confirmation signals.
- `next_day_high_low`: requires OHLCV, technical, and recent price. ADR, US market, semiconductor proxy, and chip data are optional but important.
- `one_month_trend`: requires stronger fundamental and disclosure coverage. Missing monthly revenue, financial statements, or material information lowers readiness.
- `three_month_trend`: requires fundamental, industry, company guidance, macro, and disclosure coverage. Missing those sources should produce insufficient readiness.
- `rating_action`: can run with existing technical, news, chip, and ADR scoring, but confidence must reflect source quality and coverage gaps.

Confidence caps are policy-based: ready uses a maximum near `0.90`, partial uses about `0.60` to `0.70`, and insufficient uses about `0.40` or marks the prediction insufficient.

## Missing Data Policy

Explicit policy ids:

- `missing_historical_ohlcv`: technical prediction cannot be completed.
- `missing_actual_outcome`: evaluation_status=pending_actual_outcome.
- `missing_fundamental`: one-month and three-month confidence caps are lowered.
- `news_only_without_primary_source`: must not raise rating; event/risk metadata only.
- `adr_not_applicable`: only applies when ADR mapping exists, otherwise not_applicable.
- `etf_specific_source_gap`: ETF predictions mark NAV, holdings, and distribution gaps.
- `yfinance_unavailable`: pipeline must not fail; external market context becomes unavailable only.

## yfinance formal source policy

`yfinance_external_market` and `adr_yfinance` are formal sources with provider `yfinance / Yahoo Finance`, priority `C_market_or_industry`, and `noise_risk=medium`. yfinance is external market context and confirmation only. It must not replace primary sources and must not independently raise rating.

## Backtest Integration Readiness

AI-DEV-122 does not integrate backtesting.py runtime. It prepares data that future backtesting.py work can consume: prediction snapshot, actual outcome, evaluation artifact, rating, score, action, confidence, source coverage, and source quality.

Future strategy use cases include rating threshold strategy, score threshold strategy, action-based strategy, holding period strategy, stop-loss / take-profit, transaction cost, position sizing, and parameter comparison.

## Safety boundary

AI-DEV-122 is repo-local and fixture/local-file based. It does not perform broker login, simulation orders, production orders, LINE sends, Email sends, scheduler changes, production DB writes, secret reads, production forecast weight changes, large AI/Gemini batch calls, dashboard production publishing, or nginx/systemd/cron mutation.

## Validation commands

```bash
./venv/bin/python -m py_compile \
  app/prediction/schemas.py \
  app/prediction/snapshot_builder.py \
  app/prediction/source_inventory.py \
  app/prediction/source_coverage.py \
  app/prediction/missing_data_policy.py \
  app/evaluation/schemas.py \
  app/evaluation/actual_outcome.py \
  app/evaluation/evaluator.py \
  scripts/orchestrator/build_prediction_data_foundation_artifact.py \
  scripts/orchestrator/validate_prediction_data_foundation_v1.py

./venv/bin/python scripts/orchestrator/validate_prediction_data_foundation_v1.py --pretty
./venv/bin/python scripts/orchestrator/build_prediction_data_foundation_artifact.py --pretty
./venv/bin/python scripts/orchestrator/validate_ai_branch.py --base main --head HEAD --pretty
```

## Future roadmap linkage

- AI-DEV-123 Explainability
- AI-DEV-124 Confidence Calibration
- AI-DEV-125 Adaptive Weight Recommendation
- AI-DEV-126 Dashboard Intelligence
