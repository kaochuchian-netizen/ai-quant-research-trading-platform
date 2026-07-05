# Four-Window Dashboard Preview Publish Runbook

## Purpose

Publish the AI-DEV-144 four-window Decision Intelligence preview to the existing Dashboard static surface for PM browser inspection. This is a controlled static Dashboard preview publish.

## Preconditions

- Work in GCP `~/stock-ai` only.
- `main` is synchronized with `origin/main`.
- AI-DEV-144 route artifacts exist.
- The Dashboard public base `http://35.201.242.167/stock-ai-dashboard/index.html` is reachable.
- No secret material, credential material, DB write, scheduler change, notification, production pipeline, trading, or production mutation is required.

## Pre-Publish Validation

Run:

```bash
./venv/bin/python scripts/orchestrator/validate_four_window_dashboard_preview_publish_v1.py --pretty
```

This validates the static plan only and does not publish files.

## Controlled Publish

After merge approval and post-merge validation, run:

```bash
./venv/bin/python scripts/orchestrator/publish_four_window_dashboard_preview_v1.py --pretty
```

The helper will locate the existing Dashboard static root, create a timestamped rollback backup, publish the controlled route, write a manifest, and report the public URL.

## Post-Publish Validation

Run:

```bash
./venv/bin/python scripts/orchestrator/validate_four_window_dashboard_preview_publish_v1.py --pretty --published
```

The validator confirms the public URL is reachable and displays:

- 07:00 盤前預測 / Pre-open Forecast
- 13:05 盤中追蹤 / Intraday Tracking
- 13:35 `close_snapshot_1335` / 收盤快照 / Close Snapshot
- 15:00 `prediction_review_1500` / 盤後檢討 / Prediction Review

It also confirms rollback backup presence and safety flags.

## Rollback

Read the generated manifest at:

```text
<dashboard_static_root>/dashboard/decision-intelligence/four-window-preview/publish_manifest.json
```

Run the manifest rollback command if the preview must be removed or reverted. Do not change nginx, systemd, firewall, cron, or timers as part of rollback.

## Safety Rules

- no LINE / Email / notification
- no scheduler / cron / systemd / timer
- no DB writes
- no production pipeline
- no `python3 main.py`
- no secrets touched
- no trading / broker action
- no production rating/action/confidence/weight mutation
- no formal delivery behavior change
- no nginx/systemd/firewall change
