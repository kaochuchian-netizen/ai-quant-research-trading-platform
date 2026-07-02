# AI-DEV-125: Factor Effectiveness and Adaptive Recommendation V1

## Purpose

AI-DEV-125 establishes a read-only Factor Effectiveness and Adaptive Recommendation V1 package. It evaluates historical-style offline sample records across factor groups, source priorities, forecast horizons, prediction targets, and contribution attribution, then emits advisory recommendations for future human review.

This task does not change any production forecast weight, confidence formula, rating rule, action rule, trading behavior, notification path, scheduler, runtime queue, or database record.

## Scope

The package covers:

- factor effectiveness by feature group
- source effectiveness by source priority and source category
- horizon effectiveness for 1D, 5D, and 20D windows
- prediction target effectiveness for same-day, next-day, one-month, and three-month targets
- contribution attribution with explicit missing-data handling
- adaptive recommendations that are advisory only

## Offline Sample Contract

The input template is `templates/factor_recommendation_input.example.json`. It contains deterministic offline samples with no external service calls. Samples include positive, weak, noisy, inverted, and insufficient-sample cases so that validators can exercise all policy branches.

Source priorities are represented as:

- `A_primary`
- `B_verified_secondary`
- `C_market_aggregated`
- `D_sentiment_or_noise`

FinMind and yfinance style inputs are modeled as market context metadata, not primary decision evidence.

## Artifact Contract

The artifact template is `templates/factor_recommendation_artifact.example.json`. It includes:

- `factor_effectiveness`
- `source_effectiveness`
- `horizon_effectiveness`
- `target_effectiveness`
- `contribution_analysis`
- `adaptive_recommendations`
- `safety_summary`
- `future_integration`

All adaptive recommendations set `production_mutation_allowed=false` and `human_review_required=true`.

## Recommendation Policy

Recommendations may produce `increase`, `decrease`, `hold`, `monitor`, or `exclude_from_increase` directions. These are not production instructions. They are dry-run suggestions for future review only.

Increase and decrease recommendations require sufficient evidence and remain blocked from direct production mutation. Insufficient samples are kept in monitoring state. Sentiment/noise sources cannot receive an increase recommendation.

## Safety Boundaries

AI-DEV-125 is read-only and dry-run only:

- no production forecast weight mutation
- no confidence formula mutation
- no rating or action rule mutation
- no database writes
- no external service calls
- no LINE or Email notification
- no scheduler, cron, systemd, or timer mutation
- no broker login
- no order execution
- no trading instruction

## Validation

Run:

```bash
./venv/bin/python -m py_compile app/recommendation/schemas.py app/recommendation/factor_effectiveness.py app/recommendation/source_effectiveness.py app/recommendation/horizon_effectiveness.py app/recommendation/target_effectiveness.py app/recommendation/contribution_analysis.py app/recommendation/recommendation_policy.py app/recommendation/recommendation_builder.py scripts/orchestrator/build_factor_recommendation_artifact.py scripts/orchestrator/validate_factor_recommendation_v1.py
./venv/bin/python scripts/orchestrator/validate_factor_recommendation_v1.py --pretty
./venv/bin/python scripts/orchestrator/build_factor_recommendation_artifact.py --pretty
./venv/bin/python scripts/orchestrator/validate_ai_branch.py --base main --head HEAD --pretty
```

## Follow-Up

AI-DEV-126 may use this read-only artifact as an input for a separate human-gated review workflow. AI-DEV-126 must remain separate and must not be executed by this task.
