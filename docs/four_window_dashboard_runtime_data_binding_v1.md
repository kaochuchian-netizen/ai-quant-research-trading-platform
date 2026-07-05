# Four-Window Dashboard Runtime Data Binding V1

AI-DEV-147 performs one integrated safe path: local source discovery, sanitized runtime data export, deterministic freshness checks, PM-readable Dashboard binding, controlled publish, validation, and rollback readiness.

## Data Sources

Allowed sources are repo templates/docs-controlled artifacts, the dashboard publish manifest/result JSON, orchestrator JSON state, existing structured artifacts, and the local SQLite database opened in read-only mode. The exporter does not read secret material, does not call external APIs, and does not run the production pipeline.

## Binding Policy

The Dashboard binds stock universe, latest local report summary, four-window data status, prediction field availability, source-quality policy, freshness checks, and explicit missing-data states. It does not fabricate market predictions. Missing or stale data is shown as 資料待接 or 資料過期.

## Freshness

Freshness rules are deterministic: 07:00 uses 18 hours, 13:05 and 13:35 use 4 hours, 15:00/report/prediction fields use 36 hours, and stock universe uses 7 days. Static source-quality policy is always current when the policy artifact exists.

## Safety

- no secrets / credentials / tokens
- no DB writes
- no scheduler / cron / systemd / timer changes
- no LINE / Email / notification
- no production pipeline / `python3 main.py`
- no broker / order / trading
- no production rating/action/confidence/weight mutation
- no formal delivery behavior change
- no nginx/systemd/firewall change
- no external credentialed API calls
