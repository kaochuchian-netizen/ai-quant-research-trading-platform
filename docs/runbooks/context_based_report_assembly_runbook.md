# Context-Based Report Assembly Runbook

## Purpose

This runbook describes the offline AI-DEV-138 report assembly flow. It builds deterministic report-ready sections from AI-DEV-136 Prediction Context and AI-DEV-137 Unified Explainability / Evidence Trace. This is an offline flow and no production pipeline is executed.

## Build

```bash
./venv/bin/python scripts/orchestrator/build_context_based_report_assembly_artifact.py --pretty
```

To regenerate deterministic examples:

```bash
./venv/bin/python scripts/orchestrator/build_context_based_report_assembly_artifact.py \
  --write-input-template templates/context_based_report_assembly_input.example.json \
  --output templates/context_based_report_assembly_artifact.example.json \
  --pretty
```

## Validate

```bash
./venv/bin/python scripts/orchestrator/validate_context_based_report_assembly_v1.py --pretty
./venv/bin/python scripts/orchestrator/validate_ai_branch.py --base main --head HEAD --pretty
git diff --check
```

## Operating Boundary

This flow is offline and deterministic. It does not call external services, does not read secrets, does not read or write production DB, and does not execute production pipeline commands.

It is not a production renderer and not a production decision engine. It does not send LINE/Email, does not publish dashboard, does not modify Dashboard UI, does not modify production report delivery, and does not change rating/action/confidence.

## Future Consumers

- AI-DEV-139: Dashboard Decision Intelligence Drill-down.
- AI-DEV-140: Decision Quality Feedback Loop.
- Future daily report renderer / email renderer / dashboard renderer tasks after separate approval.
