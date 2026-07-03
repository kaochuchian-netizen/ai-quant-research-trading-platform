# AI-DEV-130 Market Regime Intelligence Foundation V1

## Purpose
AI-DEV-130 adds a deterministic, offline market regime foundation for future prediction confidence, factor effectiveness, adaptive recommendation, report, and dashboard integrations.

## Scope
The release adds a market regime domain model, deterministic classifier, artifact builder, validator, example input/output artifacts, and runbook documentation.

## Supported regimes
- `trend_up`
- `trend_down`
- `range_bound`
- `high_volatility`
- `risk_on`
- `risk_off`
- `insufficient_data`

## Data sources
V1 uses deterministic sample or explicit input artifacts only. It does not call external live APIs, read secrets, write databases, or connect to production scheduler.

## Classification logic
The classifier uses input metrics such as 20-day index return, realized volatility, advance/decline ratio, drawdown, and above-MA20 ratio. It applies fixed thresholds for trend, volatility, breadth, and drawdown. Missing required metrics or sample size below the minimum returns `insufficient_data`.

## Reason codes
Reason codes include positive/negative trend strength, low trend strength, high/low volatility, positive/negative breadth, elevated drawdown, momentum direction, insufficient sample, and missing metrics. Validator enforces the reason-code enum.

## Confidence policy
Confidence is deterministic and clamped to `[0.0, 1.0]`. It is advisory only and must not mutate production prediction confidence.

## Limitations
V1 is not a live market data connector. It does not infer trading signals, alter factor weights, change rating/action rules, or publish dashboard content. Small or incomplete samples are explicitly labeled insufficient.

## Future integration
- Prediction confidence: future advisory context only.
- Factor effectiveness: future grouping dimension for rolling evaluation.
- Adaptive recommendation: future research input, no production mutation.
- Reports: future explanatory context once report contracts are updated.
- Dashboard: future display candidate with `production_publish_allowed=false` until a separate activation task.

## Safety boundary
No production scheduler connection, LINE/Email delivery, dashboard publish, secrets read, DB write, broker login, simulation order, production order, or trading execution.

## Validation commands
```bash
python -m py_compile \
  app/market_regime/schemas.py \
  app/market_regime/sample_data.py \
  app/market_regime/classifier.py \
  app/market_regime/artifact_builder.py \
  scripts/orchestrator/build_market_regime_artifact.py \
  scripts/orchestrator/validate_market_regime_intelligence_v1.py
python scripts/orchestrator/validate_market_regime_intelligence_v1.py --pretty
python scripts/orchestrator/build_market_regime_artifact.py --pretty
python scripts/orchestrator/validate_ai_branch.py --base main --head HEAD --pretty
```
