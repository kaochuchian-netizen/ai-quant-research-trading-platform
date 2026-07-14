# Window Snapshot Archive Navigation V1

## Schema and admission

Snapshots use `window_snapshot_archive_v1` and contain market, canonical window, explicit effective trading date, generation time, revision, run kind, source metadata, and an immutable `payload`. Admission accepts only successful/complete, non-fixture, non-validator, non-incomplete artifacts. Writes are atomic and content-addressed with `snapshot_id`.

## Write integration

The approved TW runner writes after a successful pipeline for `pre_open_0700`, `intraday_1305`, `pre_close_1335`, and canonical `post_close_1500` (`prediction_review_1500` is an alias). The US runner writes production-provenance artifacts for `us_pre_market_2000`, `us_intraday_2300`, and `us_post_close_review_0630`. Failed, timed-out, late-suppressed without a render payload, dry-run, fixture, and validator executions are not admitted.

Manual completion uses `run_kind=manual_rerun`, retains the original explicit effective trading date, increments the same-day revision, and rebuilds static routes. Request/audit acceptance alone is not completion and must never create a snapshot. The current Landing bridge remains guarded: a backend must return a real admissible artifact before the completion hook is called.

## Effective batch time and revisions

The writer never derives effective trading date from write time. TW uses the scheduled batch date or an explicit manual date. US uses the batch reference converted to `America/New_York`, so the 06:30 Taipei review maps to the completed US trading session. Repeated manual runs on that date increase `revision`; they cannot become `previous`.

## Resolver and routes

Resolution is isolated by market and canonical window. It first selects the highest revision for each effective trading date, then selects the newest date as `latest` and the preceding distinct date as `previous`. Seven windows times two selections produce 14 fixed routes under `/dashboard/archive/{market}/{window}/{latest|previous}/index.html`.

The renderer receives only the resolver-selected immutable snapshot payload. It must not read global latest runtime files for an archive page. Same-window comparison uses the selected previous trading date as baseline. Missing latest or previous renders an explicit empty state.

## Backfill and retention

Backfill is opt-in and requires provable market, canonical window, effective trading date, schema, successful completion, and non-fixture provenance. Ambiguous historical artifacts remain rejected; content must never be invented to fill a page. The read-only audit is `scripts/orchestrator/audit_existing_window_snapshot_backfill_v1.py`.

Snapshots are immutable. Retention must preserve at least the latest two distinct effective trading dates per market/window; deletion requires a separately reviewed retention job and is not performed by build or publish.

## Controlled publish and rollback

Use `publish_multi_market_dashboard_v2.py --dry-run --pretty`, validate, then `--apply --pretty`. This copies static files only and reports notification and production-pipeline flags as false. It does not send LINE/Email, trade, or modify scheduler state. The publish result records the backup directory. Roll back by copying the corresponding pre-publish landing/TW/US files from that directory; archive routes are additive and may remain as explicit empty states until a corrected build is published.
