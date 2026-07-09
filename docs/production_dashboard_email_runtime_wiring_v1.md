# AI-DEV-161 Production Dashboard Runtime Binding, Daily Artifact Wiring & Email Sanitization V1

AI-DEV-161 connects the approved delivery wrapper to the formal artifact builders, snapshot index, controlled Dashboard publish path, and PM-readable Email summary contract.

## Root Cause

The 2026-07-09 production Email came from the approved delivery wrapper legacy Email body, which embedded raw pipeline tail content and debug identifiers. The public four-window Dashboard was not refreshed by that wrapper, while the legacy root page was refreshed. Formal prediction/review artifacts used fixed sample timestamps, so the Dashboard could appear stuck on older data. Snapshot accumulation existed but was not invoked by the daily wrapper.

## Policy

- LINE remains short notification plus Dashboard link.
- Email is a PM-readable scheduled summary plus Dashboard link.
- Dashboard is the official decision surface.
- Raw logs, pipeline details, backtest tables, and artifact paths stay in Debug / artifacts only.
- No fake forecasts, review metrics, historical prediction snapshots, or news titles.

## Safety

This task does not change scheduler, cron, systemd, timers, DB writes, trading, production rating/action/confidence/weight logic, or deterministic baseline formula.
