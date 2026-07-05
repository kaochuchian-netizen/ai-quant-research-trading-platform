# Four-Window Dashboard Production Runtime Export Runbook

## Purpose

Refresh the controlled static four-window Dashboard preview from existing production-generated local artifacts without running the production pipeline.

## Procedure

1. Confirm the repo is on `main` and clean.
2. Build the production runtime export with `build_four_window_dashboard_production_runtime_export_v1.py`.
3. Validate the export with `validate_four_window_dashboard_production_runtime_export_v1.py`.
4. Build normalized Dashboard runtime data with `build_four_window_dashboard_runtime_data_v1.py`.
5. Rebuild the route preview HTML.
6. Run Dashboard validators.
7. Publish with the controlled static preview publisher.
8. Validate the public URL and keep the rollback backup path.

## Freshness Policy

Freshness is deterministic and uses Asia/Taipei time. Missing timestamps are marked missing. Existing safe data older than its window threshold is marked stale.

## Rollback

Use the rollback command emitted by the controlled publisher. Rollback must not touch scheduler, notification delivery, production pipelines, DB, credentials, or trading surfaces.

## Non-actions

Do not run `python3 main.py`, do not call external credentialed APIs, do not write DB, do not send LINE/Email, and do not modify formal delivery behavior.
