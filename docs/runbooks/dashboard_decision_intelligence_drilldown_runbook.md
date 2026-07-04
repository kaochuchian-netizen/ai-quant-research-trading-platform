# Dashboard Decision Intelligence Drill-down Runbook

## Purpose

This runbook explains how to build and validate the offline Dashboard Decision Intelligence drill-down artifact for AI-DEV-139.

The artifact is a deterministic data contract for a future Dashboard renderer. It is not a Dashboard UI implementation and it does not publish dashboard.

## Inputs

The builder reads only repo templates:

- `templates/prediction_context_artifact.example.json`
- `templates/unified_explainability_artifact.example.json`
- `templates/context_based_report_assembly_artifact.example.json`

## Build

```bash
./venv/bin/python scripts/orchestrator/build_dashboard_decision_intelligence_artifact.py --pretty
```

To refresh deterministic examples:

```bash
./venv/bin/python scripts/orchestrator/build_dashboard_decision_intelligence_artifact.py \
  --write-input-template templates/dashboard_decision_intelligence_input.example.json \
  --output templates/dashboard_decision_intelligence_artifact.example.json \
  --pretty
```

## Validate

```bash
./venv/bin/python scripts/orchestrator/validate_dashboard_decision_intelligence_v1.py --pretty
```

The validator checks page model completeness, cards, badges, deterministic placeholder links, warning/exclusion policy, source credibility policy, publish policy, and safety policy.

## Safety

This runbook is offline and no production pipeline is executed.

It does not call external APIs, read secrets, read production DB, publish dashboard, modify Dashboard UI, modify production dashboard runtime, send LINE / Email, trade, place orders, or execute `python3 main.py`.

## Future Dashboard renderer

A future Dashboard renderer or UI task may consume the artifact after separate approval. That task must keep source credibility, metadata-only, advisory-only, and official-source replacement policy visible to users.
