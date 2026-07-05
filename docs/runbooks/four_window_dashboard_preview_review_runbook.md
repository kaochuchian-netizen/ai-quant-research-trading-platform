# Four-Window Dashboard Preview Review Runbook

## Build Review Artifact

```bash
./venv/bin/python scripts/orchestrator/build_four_window_dashboard_preview_review.py --pretty
```

The builder reads the AI-DEV-142 preview JSON and HTML artifacts and writes a deterministic review artifact. It does not call external APIs, read secrets, write DBs, publish dashboard, send notifications, or run production pipelines.

## Validate Review Artifact

```bash
./venv/bin/python scripts/orchestrator/validate_four_window_dashboard_preview_review_v1.py --pretty
```

The validator checks four-window coverage, 13:35 close snapshot correction, readability, mobile readability, Decision Intelligence coverage, source policy visibility, mutation policy visibility, production integration planning, and safety flags.

## Visual Review Input

The reviewed preview is:

- `templates/four_window_decision_intelligence_dashboard_preview.example.html`

The review output is:

- `templates/four_window_dashboard_preview_review_artifact.example.json`

## AI-DEV-144 Recommendation

AI-DEV-144 should implement controlled dashboard route integration only after this review artifact is accepted. It should keep no-notification, no-scheduler-change, no-production-pipeline, and human-review gates unless separately approved.
