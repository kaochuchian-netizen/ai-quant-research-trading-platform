# AI-DEV-148 Integrated Production Runtime Artifact Export & Dashboard Refresh V1

AI-DEV-148 adds a safe production-runtime export layer for the four-window Decision Intelligence Dashboard. It reads only existing local artifacts and read-only SQLite data, then normalizes the result into the Dashboard runtime data artifact.

## Scope

This is one integrated task covering source discovery, sanitized export, freshness normalization, Dashboard binding, static preview publish readiness, public URL validation, rollback, and closeout.

## Safe Source Policy

Allowed sources are repo templates/docs, the controlled dashboard publish manifest, orchestrator JSON state, existing structured non-secret report artifacts, and `data/stock_analysis.db` opened with `file:data/stock_analysis.db?mode=ro`.

Disallowed sources include `.env`, credentials, token values, external credentialed APIs, raw logs as Dashboard content, production pipeline execution, notification APIs, and trading/order surfaces.

## Runtime Export

`templates/four_window_dashboard_production_runtime_export.example.json` records inspected source inventory, stock universe, latest report summaries, per-stock summaries, prediction field availability, actual outcome and prediction review availability, source credibility policy, freshness checks, missing and stale data, and safety flags.

The export is honest: unavailable or stale fields are marked missing/stale instead of being fabricated.

## Dashboard Refresh

The Dashboard consumes `templates/four_window_dashboard_runtime_data.example.json`, which is normalized from the production runtime export. The page shows latest runtime timestamp, freshness, stock universe, latest reports, per-stock status, prediction availability, actual/review availability, source credibility, and a collapsed Debug section.

## Safety

AI-DEV-148 does not call external APIs, read secrets, write DB, modify scheduler/cron/systemd/timer, send LINE/Email/notifications, execute `python3 main.py`, run production pipelines, place orders, or mutate rating/action/confidence/weight logic.
