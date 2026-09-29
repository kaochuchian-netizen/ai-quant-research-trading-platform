# AI-DEV-246 overlap owner diagnosis (2026-09-29)

Baseline: db09deb0d2f9ef4cd019c3b20076330349054856.
PR #326 merge e3bdafdaacbb6472eaca911942b24cbd571cc68b is an ancestor.

## Classification and evidence
Scheduler overlap guard FALSE POSITIVE, not a stale lock or proven active overlap.
The requested SCHEDULER_OVERLAP category describes the guard decision path only;
there were not two proven production batches. Confidence: high.

The 07:00 delivery result identifies PID 706061 (PPID 706060), started
06:59:28 Asia/Taipei, as an active owner at 07:00:01. Its command was an inline
Python read-only observer, containing an entrypoint name as source text.
Command digest: b8f98cc40e21e611eec7d6b30231014e2d5f683550a10d5a2bea632948fc0d5f.
It had no attached daily log or pipeline artifact. The previous Codex observer
unintentionally caused the guard to block the natural batch. Raw command and
production payloads are deliberately not committed.

Old process_guard substring matching of the entire command caused the false
positive. production_run_guard returned overlapping_run_blocked before pipeline
launch. This decision does not acquire a filesystem lock. Browser lock existence
is not evidence of ownership: the stable browser lease file had no kernel owner.

## Timeline (Asia/Taipei)
| Event | Evidence |
|---|---|
| Sep 28 13:05:01–13:05:41 | Intraday exit 1, 10 requested / 0 historical admitted |
| Sep 28 13:35:01–13:35:30 | Pre-close exit 1, same aggregate admission result |
| Sep 28 15:00:02–15:01:09 | Post-close exit 1, same result |
| Sep 29 06:59:28 | Observer PID 706061 started |
| Sep 29 07:00:01 | Natural pre-open guard blocked; pipeline_pid null |
| Browser worker start/exit | Not applicable to blocked pre-open run |
| Batch/browser lock acquire/release | No pipeline/browser acquisition reached |
| Observer exact exit time | UNKNOWN; process subsequently absent |
| Next natural run | Observed separately; never manually triggered |

Earlier browser-worker timing cannot be reconstructed from missing telemetry.
No timeout termination occurred in the three recorded afternoon failures.

## Separate no_valid_decision_cards diagnosis
Relationship to overlap false positive: UNRELATED (high confidence).
The three afternoon batches requested 10 stocks and admitted zero historical
records; they never produced valid decision cards. Existing read-only history
validation for the incident date required 2026-09-25. All 12 existing local CSVs
were STALE (8 latest Sep 24, 2 Sep 11, 2 Jun 2; 116–125 rows), unchanged since
before those runs. Original per-symbol admission diagnostics were not persisted,
so exact original per-card reconstruction remains UNKNOWN. No provider refresh,
history rewrite, admission weakening or calendar/evaluation semantic change is
part of this fix. Future failures now record bounded aggregate exclusion reasons.

## Fix and preserved contracts
Process ownership matches executable argv positions, canonical repository paths,
approved window/production flags, and stable Linux start ticks. Inline Python,
shell source, SSH/grep/editor arguments, foreign repositories, zombies, exited
owners and observed PID reuse cannot become owners through filename mentions.
Diagnostics retain canonical entrypoint identity rather than raw argv.
Active legitimate owners still block; long-running owners still require manual
review. No auto-kill or lock removal is added.

The existing browser worker remains isolated and bounded, with owned-process
cleanup, default concurrency one, memory admission and temporary-profile cleanup.
The OS advisory lease releases on close/process death, including crashed owners.
The stable lease pathname is never interpreted as stale merely because it exists.
Existing timeouts and all 251–254 scoring/review contracts are unchanged.

## Validation and limits
54 owner/lease/diagnostic tests and 36 existing fake-browser lifecycle tests pass.
Tests use synthetic process tables, temporary leases and disposable test children;
no production pipeline, notification or real Chrome is started.
251A/B/C/D, 252, 253 and 254 regressions, governance, source audit and branch gate
must be recorded in the PR before merge.

Process scanning remains a best-effort overlap guard, not an atomic batch mutex.
Browser concurrency is independently protected by its existing kernel lease.
A test PASS is not evidence of successful natural production browser execution.
Natural verification remains IMPLEMENTED_PENDING_NATURAL_VERIFICATION until a
real launch/cleanup cycle is observed. No extra production recovery is justified
by the diagnosed false owner, which is no longer running.
