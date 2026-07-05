# Four-Window Dashboard Preview Publish V1

AI-DEV-145 defines a controlled static Dashboard preview publish for the AI-DEV-144 route `/dashboard/decision-intelligence/four-window-preview`.

This is a controlled static Dashboard preview publish, not a production scheduler, not a production pipeline, and not formal delivery behavior. It publishes the deterministic four-window preview HTML under the existing Dashboard static root so the PM can inspect it in a browser.

## Route

- Public base: `http://35.201.242.167/stock-ai-dashboard`
- Controlled route: `/dashboard/decision-intelligence/four-window-preview`
- Expected public URL: `http://35.201.242.167/stock-ai-dashboard/dashboard/decision-intelligence/four-window-preview/index.html`
- Source preview: `templates/four_window_dashboard_route_preview.example.html`
- Route artifact: `templates/four_window_dashboard_route_integration.example.json`

## Four-Window Mapping

| Time | Runtime key | UI display |
| --- | --- | --- |
| 07:00 | `pre_open_0700` | 盤前預測 / Pre-open Forecast |
| 13:05 | `intraday_1305` | 盤中追蹤 / Intraday Tracking |
| 13:35 | `pre_close_1335` | `close_snapshot_1335` / 收盤快照 / Close Snapshot |
| 15:00 | `post_close_1500` | `prediction_review_1500` / 盤後檢討 / Prediction Review |

The 13:35 runtime key remains `pre_close_1335` for compatibility, but the UI concept must be `close_snapshot_1335` / 收盤快照 / Close Snapshot. The primary UI must not describe 13:35 as pre-close or 收盤前. Full Prediction Review remains at 15:00.

## Controlled Publish Behavior

The publish helper locates the existing Dashboard static root by comparing the public Dashboard index with writable local candidates. It refuses to publish when the root cannot be found safely.

Before writing, it creates a timestamped rollback backup under the Dashboard static root. It then writes only the controlled route preview and a publish manifest. It may add a small discoverability link to the existing Dashboard index, using a marker so the link is not duplicated.

## Rollback

Every publish writes a manifest with source file, target path, public URL, backup path, rollback command, publish timestamp, and safety flags.

Rollback restores the previous `index.html` and removes the controlled preview route, restoring a prior route copy if one existed.

## Safety

- no LINE / Email / notification
- no scheduler / cron / systemd / timer
- no DB writes
- no production pipeline
- no `python3 main.py`
- no secrets touched
- no broker / order / trading
- no production rating/action/confidence/weight mutation
- no formal delivery behavior change
- no nginx/systemd/firewall change

## Validation

Pre-publish validation checks the publish plan and artifacts without mutating Dashboard static files. Post-publish validation checks the public URL, window markers, 13:35 Close Snapshot semantics, rollback backup, and safety flags.
