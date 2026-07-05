# AI-DEV-140: Decision Quality Feedback Loop Foundation V1

## Purpose

AI-DEV-140 is the V10 Unified Decision Intelligence feedback loop foundation. It reads AI-DEV-136 Prediction Context, reads AI-DEV-137 Explainability / Evidence Trace, reads AI-DEV-138 Context-Based Report Assembly, and reads AI-DEV-139 Dashboard Decision Intelligence to produce deterministic feedback, review, attribution, and recommendation artifacts.

It only produces recommendation / review / attribution.

## Non-Goals

AI-DEV-140 is not an adaptive strategy engine.
AI-DEV-140 is not a production mutation engine.
It does not change factor weights.
It does not change confidence.
It does not change rating/action.
It does not connect to production pipeline.
It does not send LINE / Email.
It does not publish dashboard.
It does not modify production dashboard runtime.
It does not modify production delivery behavior.

## Feedback Questions

The artifact is designed to answer:

1. Which factors recently appear effective?
2. Which sources may contribute to error or uncertainty?
3. Whether confidence appears too high or too low.
4. Which signals deserve caution under the current market regime.
5. Which report or dashboard improvement hints should be surfaced for human review.

## Artifact Sections

The artifact includes:

- rolling_evaluation_summary
- prediction_review_summary
- factor_effectiveness_summary
- confidence_calibration_summary
- market_regime_quality_summary
- source_error_attribution
- factor_feedback_blocks
- confidence_feedback_blocks
- regime_feedback_blocks
- source_reliability_feedback_blocks
- report_feedback_blocks
- dashboard_feedback_blocks
- recommendation_blocks
- warning_blocks
- mutation_policy
- safety_policy

## Mutation Policy

The mutation policy requires:

- recommendation_only=true
- production_weight_changed=false
- production_confidence_changed=false
- production_rating_action_changed=false
- production_pipeline_modified=false
- dashboard_runtime_modified=false
- delivery_behavior_modified=false
- direct_rating_action_confidence_impact=false

Every recommendation block requires human review and has production_mutation_allowed=false and production_mutation_executed=false.

## Source Policy

Warning blocks preserve the existing source policy:

- broker_target_price_metadata can only be metadata.
- google_news_rss can only be event detection / sentiment support and cannot be core forecast evidence.
- yfinance_yahoo cannot replace official sources.
- finmind cannot replace MOPS / TWSE / company official information.
- gemini_google_generative_ai is not original evidence.
- recommendation cannot automatically change production rating/action/confidence/weight.

## Future Use

Future dashboard/report feedback display tasks can consume this artifact to show factor quality, confidence bias, source attribution, regime cautions, and human-gated recommendations.

Any future production mutation must pass a separate human review gate and a separate approved AI-DEV task.

## Safety Boundary

No external API calls.
No secrets or `.env` reads.
No DB writes.
No production scheduler / cron / systemd / timer changes.
No LINE / Email / notification sending.
No dashboard publish.
No Dashboard UI changes.
No production dashboard runtime changes.
No broker / order / trading.
No `python3 main.py` execution.
No production pipeline execution.
No production rating/action/confidence/weight logic changes.
No formal delivery behavior changes.
No actual factor weight adjustment.
No actual confidence adjustment.
No actual rating/action adjustment.

## Validation

Run:

```bash
./venv/bin/python -m py_compile app/decision_feedback/*.py scripts/orchestrator/build_decision_quality_feedback_artifact.py scripts/orchestrator/validate_decision_quality_feedback_v1.py
./venv/bin/python scripts/orchestrator/validate_decision_quality_feedback_v1.py --pretty
./venv/bin/python scripts/orchestrator/build_decision_quality_feedback_artifact.py --pretty
./venv/bin/python scripts/orchestrator/validate_ai_branch.py --base main --head HEAD --pretty
git diff --check
```
