# Four-Window Decision Intelligence Dashboard UI Runbook

## Scope

This runbook validates the AI-DEV-142 static preview only. It does not publish dashboard, does not send LINE / Email, does not modify scheduler, and does not run production pipeline.

## Build Preview

```bash
./venv/bin/python scripts/orchestrator/build_four_window_decision_intelligence_dashboard_preview.py --pretty
```

The builder reads deterministic repo templates and writes a JSON artifact plus static HTML preview under `templates/`.

## Validate Preview

```bash
./venv/bin/python scripts/orchestrator/validate_four_window_decision_intelligence_dashboard_ui_v1.py --pretty
```

The validator checks all four windows, required UI blocks, source policy badges, mutation policy badges, delivery safety flags, secret-like patterns, and the 13:35 close snapshot correction.

## Visual Review

Open the static preview artifact locally or through an approved repo preview viewer:

- `templates/four_window_decision_intelligence_dashboard_preview.example.html`

The preview should show card-first mobile-friendly sections for 07:00, 13:05, 13:35, and 15:00. Raw JSON should not be the primary display surface.

## Production Boundaries

Do not publish dashboard from this task. Do not call external APIs, read secrets, write DBs, change scheduler, send notifications, trade, run `python3 main.py`, execute production pipelines, or mutate rating/action/confidence/weights.
