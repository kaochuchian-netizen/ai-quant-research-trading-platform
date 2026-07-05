# Four-Window Dashboard Route Integration Runbook

## Build

```bash
./venv/bin/python scripts/orchestrator/build_four_window_dashboard_route_preview.py --pretty
```

The builder reads repo-local AI-DEV-142 preview artifacts and creates controlled route JSON and HTML preview artifacts under `templates/`.

## Validate

```bash
./venv/bin/python scripts/orchestrator/validate_four_window_dashboard_route_integration_v1.py --pretty
```

The validator checks route path, four-window mapping, 13:35 close snapshot semantics, 15:00 prediction review semantics, rollback instructions, safety flags, secret-like patterns, and production publish status.

## Preview Path

Open the repo-side static preview artifact:

```text
templates/four_window_dashboard_route_preview.example.html
```

## Boundaries

Do not publish to production dashboard from this task. Do not modify scheduler, send notifications, write DBs, run production pipelines, trade, or mutate rating/action/confidence/weights.
