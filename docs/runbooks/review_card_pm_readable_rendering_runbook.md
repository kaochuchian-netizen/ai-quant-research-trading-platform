# Review Card PM-Readable Rendering Runbook

## Build

```bash
./venv/bin/python scripts/orchestrator/build_four_window_dashboard_route_preview.py --pretty
```

## Validate

```bash
./venv/bin/python scripts/orchestrator/validate_review_card_pm_readable_rendering_v1.py --pretty
```

After controlled static publish, also run:

```bash
./venv/bin/python scripts/orchestrator/validate_review_card_pm_readable_rendering_v1.py --pretty --published
```

## Review Rules

- Main review card must show PM-readable labels.
- Keep single-day review separate from seven-day rolling review.
- Do not generate fake high-low errors.
- Keep insufficient seven-day data explicit.
- Preserve AI-DEV-150 through AI-DEV-155 Dashboard and artifact behavior.

## Safety

This task is a display cleanup and regression guard. It does not modify forecast formulas, DB state, schedulers, notifications, production pipeline, trading logic, snapshot semantics, calibration gates, or formal artifact semantics.
