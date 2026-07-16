# TW 13:35 Snapshot Notification V1

## Incident and root cause

The scheduler correctly selected `pre_close_1335`, but the approved delivery wrapper built Email and LINE from mutable global `tw_daily_tactical_latest` and four-window export artifacts. The latter supplied the displayed `05:42:23` value through `latest_runtime_timestamp`; it was neither the 13:35 batch time nor a 13:35 market-data timestamp. All non-15:00 TW delivery URLs were normalized to the generic market Dashboard. The archive payload also omitted structured window cards, so its V4 projection contained no real 13:35 decision counts.

## Scheduler and window binding

`run_stock_analysis.sh` maps 13:3x to `pre_close_1335` and invokes `approved_pre_open_delivery.py --window pre_close_1335`. The afternoon pipeline now persists a window-scoped structured runtime. The wrapper accepts that runtime only when its window and pipeline run ID match the just-completed child output, embeds its cards and provenance in the immutable archive snapshot, then resolves Email, LINE and the archive page from that snapshot. It never falls back to another window or the global latest runtime.

## Time semantics

- `effective_batch_time`: scheduled Asia/Taipei batch reference, 13:35 for this window.
- `source_data_time`: exact timestamp supplied by the window runtime. Missing intraday time remains `尚未取得`; a daily source date is retained separately.
- `generated_at`: report/snapshot projection creation time after pipeline completion.

Artifact mtime is never a data timestamp. Snapshot schema accepts an explicit effective batch time while preserving manual rerun original-batch semantics.

## 13:35 projection and comparison

The projection exposes hold, avoid-hold, no-trade, near-target, near-stop, late-session-risk, setup and tomorrow-watch values only when explicit source fields exist. Missing fields are `null`/`尚未取得`, never invented zeroes. Ranking priority is late-session risk, near stop, near target, hold, avoid, then tomorrow watch; rating is not the primary ordering.

The comparison resolver selects the highest admitted revision of TW `intraday_1305` on the same effective trading date. It never uses a prior date. Missing baseline renders `本次無同日 13:05 可比較基準`.

## Email, LINE and canonical URL

Both notifications use `/dashboard/archive/tw/pre_close_1335/latest/index.html`, generated centrally from market/window/position. Email contains the three times, decision categories, action ranking, same-day comparison and partial-prediction explanation. LINE contains only actual counts or explicit unavailable states, the comparison summary and canonical route. Runtime health, calibration gates, snapshot counts and generic rating Top Signals are not the 13:35 main body.

All seven report contracts use their own canonical archive Latest URL. Generic TW/US market Dashboard URLs remain navigation surfaces, not notification targets.

## Validation and controlled verification

Run `python scripts/orchestrator/validate_tw_1335_snapshot_notification_v1.py --pretty`. It builds isolated 13:05/13:35 snapshots, full/partial/no-baseline/no-source-time cases and invokes the formal approved-delivery entrypoint with `--dry-run`. Temporary archive, output and mail paths are outside production and removed automatically. Email, LINE, trading, scheduler mutation and production-approved delivery remain false.

## Rollback

Revert the AI-DEV-181F implementation commit, rebuild static pages and use the controlled publisher rollback backup. Do not delete production archive/runtime evidence or resend notifications. A rollback restores the prior generic notification URLs and therefore should be used only during an incident.

## Known limitations

Historical immutable snapshots are not rewritten. Existing snapshots without structured cards display unavailable decision fields rather than fabricated counts. A future successful 13:35 scheduled or manual revision begins using the corrected binding automatically. Exact intraday data time remains unavailable until the upstream market source provides a timestamp rather than only a daily bar date.
