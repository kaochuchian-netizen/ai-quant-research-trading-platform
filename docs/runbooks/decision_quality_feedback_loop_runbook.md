# Decision Quality Feedback Loop Runbook

## Purpose

This runbook explains how to build and validate the offline Decision Quality Feedback artifact for AI-DEV-140.

The artifact is recommendation-only and intended for a future report/dashboard feedback display after a separate human review gate.

## Inputs

The builder reads only repo templates:

- `templates/prediction_context_artifact.example.json`
- `templates/unified_explainability_artifact.example.json`
- `templates/context_based_report_assembly_artifact.example.json`
- `templates/dashboard_decision_intelligence_artifact.example.json`

## Build

```bash
./venv/bin/python scripts/orchestrator/build_decision_quality_feedback_artifact.py --pretty
```

To refresh deterministic examples:

```bash
./venv/bin/python scripts/orchestrator/build_decision_quality_feedback_artifact.py \
  --write-input-template templates/decision_quality_feedback_input.example.json \
  --output templates/decision_quality_feedback_artifact.example.json \
  --pretty
```

## Validate

```bash
./venv/bin/python scripts/orchestrator/validate_decision_quality_feedback_v1.py --pretty
```

The validator checks references to AI-DEV-136/137/138/139 artifacts, rolling evaluation, prediction review, factor effectiveness, confidence calibration, regime feedback, source attribution, recommendation blocks, mutation policy, and safety policy.

## Safety

This runbook is offline and no production pipeline is executed.

It does not call external APIs, read secrets, read production DB, publish dashboard, modify Dashboard UI, modify production dashboard runtime, send LINE / Email, trade, place orders, modify rating/action/confidence/weights, or execute `python3 main.py`.

## Human Review Gate

All recommendations require a human review gate before any future production mutation. AI-DEV-140 itself does not perform mutation.
