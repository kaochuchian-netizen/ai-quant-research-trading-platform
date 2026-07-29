# TW 07:00 Missing Batch Recovery and Prevention V1

## Incident summary

On 2026-07-29 the scheduled `pre_open_0700` job started at 07:00:02 Asia/Taipei, launched pipeline run `20260729_070005_pre_open`, and failed after 190 seconds. No canonical decision, admitted immutable snapshot, Archive revision, Dashboard publication, notification content, or Operations identity was produced for that effective trading date.

Root-cause classification: **Multiple Causes**.

1. **External Source** — the Google Sheets watchlist request failed with HTTP 503 during `historical_csv_update`.
2. **Builder / Orchestrator** — the approved-delivery wrapper continued into completed-only structured-card handling after the child returned non-zero and raised `KeyError: structured_pre_open_cards`. This secondary exception prevented a complete incident artifact from being written.

The scheduler time, strategy, weights, ranking, delivery recipients, and immutable history were not changed.

## Evidence and stage audit

| Question | Evidence | Result |
| --- | --- | --- |
| Scheduler trigger | delivery progress `started_at=2026-07-29T07:00:02+08:00` | PASS |
| Pipeline start | stage timing run `20260729_070005_pre_open`, start 07:00:05 | PASS |
| Exit and duration | progress ended 07:03:12, elapsed 190 seconds, failed/non-zero | FAIL |
| Primary failure | `gspread.exceptions.APIError: [503] The service is currently unavailable` | External Source |
| Secondary failure | approved wrapper line 982 `KeyError: structured_pre_open_cards` | Builder / Orchestrator |
| Research | pipeline stopped in historical update | SKIPPED |
| Canonical decision | no 2026-07-29 07:00 runtime artifact | NOT BUILT |
| Admission | no candidate payload reached admission | NOT ATTEMPTED |
| Archive | no 2026-07-29 immutable snapshot/revision | NOT WRITTEN |
| Dashboard | no selected snapshot existed | NOT PUBLISHED |
| LINE / Email | no canonical notification content | NOT BUILT / NOT SENT |
| Operations | no admitted identity | NOT BUILT |

The old `/tmp/approved_pre_open_0700_delivery_result.json` retained a 2026-07-28 modification time, which confirms that the failed wrapper did not persist the current incident result. The later 13:05, 13:35 and 15:00 natural jobs produced nine-card runtime batches, which rules out a full-day scheduler outage. They did **not** produce current admitted Archive identities: their selected snapshots remained on 2026-07-27/28. The health gate therefore treats all four TW windows as incomplete for 2026-07-29 instead of mistaking runtime-card existence for end-to-end success.

## Recovery contract

The TW universe is loaded once per 07:00 pipeline. The primary owner remains the configured Google Sheet. If that request fails, the only permitted fallback is the tracking symbol set from the most recent **admitted immutable TW `pre_open_0700` snapshot**. The fallback records:

- primary and fallback source;
- sanitized primary failure category;
- source snapshot ID and effective trading date;
- fallback use and symbol count.

It must fail closed when no admitted TW 07:00 snapshot contains a non-empty universe. It must never infer a universe from historical CSVs, global latest runtime, another window, another market, or fixtures.

The same resolved universe is passed to historical-data update and research stages, eliminating the duplicate Google Sheets request.

If the child pipeline still fails, the wrapper now writes one complete incident artifact and exits before admission, Archive, Dashboard, Email, LINE or Operations. A failed batch cannot be presented as a successful or stale current batch.

## Safe recovery decision

A formal manual rerun would write production SQLite state and create a new immutable Archive revision. Those actions are outside AI-DEV-196 safety authorization, so the incident is not repaired by a production rerun, hand-edited snapshot, renderer-only publish, or historical backfill. Recovery is verified with deterministic no-send fixtures and awaits the next natural 07:00 batch.

## Detection and prevention

`inspect_seven_window_batch_health.py` is a read-only seven-window completeness inspector. For every formal window it compares the expected effective trading date and canonical identity across:

1. scheduler/progress evidence;
2. runtime and structured cards;
3. admission and immutable snapshot;
4. Archive/public latest sync;
5. Email and LINE content provenance;
6. Operations provenance.

At 07:05 it raises a warning if 07:00 is incomplete. At 07:10 it fails the batch as `missing_batch`. An explicit child failure fails immediately, without waiting for the deadline. The two-stage deadline avoids false alarms because successful 07:00 runs may complete shortly after 07:05.

The inspector does not send an alert by itself. An independent scheduled health invocation is recommended for production alerting, because the job being monitored cannot detect that its own scheduler never started. Activating such a timer or notification route is deferred because this task forbids scheduler and real-notification changes.

## Why previous validators missed the incident

Existing gates validated fixture content, the selected latest admitted snapshot, presentation, admission rules and channel parity. They did not assert that an artifact existed for the **expected effective trading date by a deadline**. Consequently, a valid older latest snapshot could remain visible while all content validators passed. They also did not exercise a non-zero child return through the delivery wrapper's structured-card boundary.

The new deterministic validator covers primary success, transient-source fallback, fail-closed fallback, failed-child incident output, deadline states, stale-date rejection, identity mismatch, seven-window market isolation, and mutation safety.

## Other-window exposure

All seven formal windows share the missing-batch blind spot when their scheduler does not start or the pipeline exits before a canonical artifact. TW 07:00 had additional exposure because it requested the Google Sheets universe twice and its wrapper assumed completed output after failure. TW 13:05, 13:35 and 15:00 do not perform that historical-universe update and completed on the incident day, but they are covered by the generic completeness inspector. The three US windows are also covered with market-isolated paths and their own expected trading-date semantics.

## Natural verification

The next eligible TW day must demonstrate:

- scheduler trigger and bounded duration;
- one universe resolution with provenance;
- canonical 07:00 decision artifact;
- admitted immutable snapshot and revision;
- matching Archive Latest, Dashboard, notification-content provenance and Operations identity;
- unchanged 13:05, 13:35 and 15:00 continuity;
- no real recovery notification, historical rewrite or manual fixture presented as natural evidence.

Until then AI-DEV-196 is `IMPLEMENTED_PENDING_NATURAL_VERIFICATION`, and AI-DEV-195 natural verification remains blocked.

## Rollback

Revert the implementation commit. No snapshot, production database, scheduler, service configuration, notification recipient, or immutable history migration is required. Preserve all runtime/generated artifacts during rollback.
