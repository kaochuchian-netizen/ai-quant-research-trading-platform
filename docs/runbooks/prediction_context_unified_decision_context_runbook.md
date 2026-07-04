# Prediction Context Unified Decision Context Runbook

## Purpose

This runbook describes the offline operator flow for AI-DEV-136 Prediction Context. It is a deterministic context assembly flow and no production pipeline is executed.

## Build

Use the offline sample builder:

```bash
./venv/bin/python scripts/orchestrator/build_prediction_context_artifact.py --pretty
```

To regenerate examples:

```bash
./venv/bin/python scripts/orchestrator/build_prediction_context_artifact.py \
  --write-input-template templates/prediction_context_input.example.json \
  --output templates/prediction_context_artifact.example.json \
  --pretty
```

## Validate

```bash
./venv/bin/python scripts/orchestrator/validate_prediction_context_v1.py --pretty
./venv/bin/python scripts/orchestrator/validate_ai_branch.py --base main --head HEAD --pretty
git diff --check
```

## Operating Boundary

The flow is offline and read-only. It does not call external services, does not read secrets, does not read or write production DB, and does not execute production pipeline commands.

This context is not a production decision engine. It is not allowed to change rating/action/confidence, forecast weights, delivery behavior, notification behavior, broker behavior, or dashboard publish state.

## Future Consumers

- AI-DEV-137 explainability: attach source/evidence explanation to context fields.
- AI-DEV-138 traceability: make each downstream decision trace back to source IDs and artifact refs.
- AI-DEV-139 report assembly: assemble report text from the context without delivery side effects.
- AI-DEV-140 dashboard drill-down: render context drill-down views without publishing production dashboard changes.
