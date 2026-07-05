# Four-Window Dashboard Route Integration V1

## Purpose

AI-DEV-144 connects the existing four-window Decision Intelligence dashboard preview to a controlled static dashboard route artifact:

```text
/dashboard/decision-intelligence/four-window-preview
```

This is repo-side controlled route integration only. It does not publish the production dashboard.

## Four-Window Mapping

| Time | Runtime key | UI id | Label |
| --- | --- | --- | --- |
| 07:00 | `pre_open_0700` | `pre_open_0700` | 盤前預測 / Pre-open Forecast |
| 13:05 | `intraday_1305` | `intraday_1305` | 盤中追蹤 / Intraday Tracking |
| 13:35 | `pre_close_1335` | `close_snapshot_1335` | 收盤快照 / Close Snapshot |
| 15:00 | `post_close_1500` | `prediction_review_1500` | 盤後檢討 / Prediction Review |

The 13:35 runtime key remains `pre_close_1335` for compatibility. The UI concept is `close_snapshot_1335` / 收盤快照 / Close Snapshot. Full prediction review remains at 15:00 only.

## Route Artifacts

- `templates/four_window_dashboard_route_integration.example.json`
- `templates/four_window_dashboard_route_preview.example.html`
- `templates/four_window_dashboard_route_integration_input.example.json`

The route preview embeds the AI-DEV-142 static preview as a browser-inspectable controlled route page.

## Rollback

Rollback is repo-only at this stage:

1. Remove the future route mapping.
2. Restore the previous dashboard preview route configuration.
3. Keep scheduler, notification delivery, production pipeline, and DB state untouched.
4. Re-run route integration and post-merge validators.

## Safety

AI-DEV-144 does not read secrets, write DBs, change scheduler / cron / systemd / timer, send LINE / Email / notification, run `python3 main.py`, execute production pipeline, trade, mutate rating/action/confidence/weights, or change formal delivery behavior. Production dashboard publish remains false.
