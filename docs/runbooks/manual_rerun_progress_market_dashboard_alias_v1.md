# Manual Rerun Progress and Market Dashboard Alias V1

## Root cause

The production Landing previously rendered a submit-only placeholder: it did not POST, poll, or restore a task. The bridge also executed the backend synchronously before responding and reduced its status artifact to a few fields, losing revision, route, stage, duration, and publish evidence. Separately, TW and US market pages read mutable global runtime files and recomposed every window, while archive pages rendered resolver-selected immutable snapshots.

## Task lifecycle and persistence

The bridge now returns a task ID immediately and persists `submitted`, `queued`, `running`, `publishing`, and terminal `completed`, `failed`, or `rejected` states. Each task has a job-specific JSON status plus an atomic latest-status pointer under `artifacts/runtime/manual_rerun/`. Terminal payloads include timestamps, duration, effective trading date, revision, Latest/market publish results, unchanged Previous/other-window flags, safe error summary, and no-send/no-trading flags. Raw stdout, stack traces, PIN values, hashes, tokens, and secrets are excluded.

The Landing polls the job-specific status endpoint every four seconds, stops at terminal state, and stops after 30 minutes with a retry message. It stores only the opaque task ID in `localStorage`; reload restores that task through the backend status endpoint. Persisted per-job files also allow completed/failed status recovery after a bridge restart.

## Active window and market Dashboard alias

For each market, the resolver examines only admitted `latest` snapshots. It selects the newest effective trading date and then the latest canonical batch order on that date: TW 07:00 → 13:05 → 13:35 → 15:00; US 20:00 → 23:00 → 06:30. Wall-clock time and mutable global runtime files do not participate. No admitted snapshot produces an explicit safe empty state.

The market page is a wrapper around the active snapshot’s immutable payload. It may retain market navigation and title, but its decision section is the same renderer fragment used by the matching archive Latest page. Both expose `data-window`, `data-snapshot-id`, `data-effective-trading-date`, `data-revision`, and `data-payload-hash`.

## Manual revision and publish behavior

A successful rerun still creates only the target market/window/date’s next revision. Latest is rebuilt; Previous and other windows are never rebuilt. If the target remains the resolved active window, its market page is synchronized. A rerun of a non-active earlier window updates its Latest route but does not switch or rewrite the market page. Failed or rejected requests do not call archive or publish functions.

Completion status records target Latest, Previous, market page, and other-route hashes before and after. Hashes are operational evidence only and do not expose payload contents.

## Engineering information placement

The production Landing no longer renders the controlled no-send engineering matrix. It shows human-readable LINE, Email, and trading state in the manual task status card. Detailed deterministic evidence remains in validator output and Operations diagnostics.

## Controlled verification

Run `python scripts/orchestrator/validate_manual_rerun_progress_market_alias_v1.py --pretty`. It creates an isolated archive/public/status tree, validates active and non-active reruns, TW/US parity, failed/rejected behavior, lifecycle persistence, reload recovery, 14 routes, seven buttons, and seven Operations rows, then removes the temporary tree. It never calls a production backend or notification sender.

## Rollback

Revert the AI-DEV-181E implementation commit, rebuild static pages, and publish through the controlled static publisher using its rollback backup. Restarting the manual bridge after source rollback restores the prior endpoint behavior. Do not delete production archive/runtime files, change scheduler configuration, or resend notifications.

## Known limitations

Polling is HTTP-based and does not stream sub-second progress. A bridge process terminated during an active backend run preserves the last persisted state; an operator may need to inspect the safe status artifact and retry after the one-batch lock clears. Existing snapshot payload completeness is preserved exactly—the alias does not invent missing cards or backfill history.
