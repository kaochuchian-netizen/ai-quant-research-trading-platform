# Unified Explainability & Evidence Trace Runbook

## Purpose

This runbook describes the offline AI-DEV-137 flow. It builds deterministic explainability and evidence trace artifacts from AI-DEV-136 Prediction Context. The flow is offline and no production pipeline is executed.

## Build

```bash
./venv/bin/python scripts/orchestrator/build_unified_explainability_artifact.py --pretty
```

To regenerate deterministic examples:

```bash
./venv/bin/python scripts/orchestrator/build_unified_explainability_artifact.py \
  --write-input-template templates/unified_explainability_input.example.json \
  --output templates/unified_explainability_artifact.example.json \
  --pretty
```

## Validate

```bash
./venv/bin/python scripts/orchestrator/validate_unified_explainability_v1.py --pretty
./venv/bin/python scripts/orchestrator/validate_ai_branch.py --base main --head HEAD --pretty
git diff --check
```

## Operating Boundary

This is an offline deterministic artifact flow. It does not call external services, does not read secrets, does not read or write production DB, and does not execute production pipeline commands.

It is not a production decision engine. It does not modify rating/action/confidence, delivery behavior, notification behavior, Dashboard UI, broker behavior, order behavior, or trading behavior.

## Future Consumers

- AI-DEV-138: Context-Based Report Assembly.
- AI-DEV-139: Dashboard Decision Intelligence Drill-down.
- AI-DEV-140: Decision Quality Feedback Loop.
