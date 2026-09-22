# AI-DEV-246 browser lifecycle / OOM incident

Status: IMPLEMENTED_PENDING_NATURAL_VERIFICATION. PR only; merge/deploy prohibited by this task.
This incident follow-up is distinct from the existing AI-DEV-246 post-merge validator-isolation contract; that validator is retained.

## Forensics and confidence

Read-only verification on 2026-09-22 (Asia/Taipei): production `dify-trading-server`, branch `main`, HEAD `137546f2635a6b269b3feeab180e45537d52c5f2`; GitHub `origin/main` matched. Production tracked runtime/dashboard dirty files were observed and preserved. Implementation starts from that freshly fetched origin/main in a separate local worktree/branch.

PR #321, AI-DEV-245, is CLOSED/MERGED at 2026-09-18 11:40:10 UTC (19:40:10 Taipei), merge commit `3203e6a3bcec898f1f2265377994f31ca7b1c204`. Its acceptance report describes no orphans after its isolated smoke test; that does not prove lifecycle safety for later interrupted production batches.

Evidence independently re-read from previous-boot journal:

- 2026-09-22 20:24:17 +08:00: global OOM, `CONSTRAINT_NONE`; victim Chrome PID `1018292`, anon RSS 234220 KiB, `task_memcg=/system.slice/cron.service`.
- Same second: cron.service failed `oom-kill`; ChromeDriver `1018125`, Chrome `1018131`, crashpad `1018152/1018154`, and further Chrome descendants remained after unit stop/restart.
- 20:24:19: cron records for US `us_pre_market_2000` and TW shell invocations appear **after** the OOM. They are not evidence that US 20:00 created the older browser tree.
- User-provided confirmed facts: Ubuntu 22.04, 3.8 GiB RAM/2 GiB swap, `python3 invoked oom-killer`, cascading resolved/snapd/Docker health/SSH/HTTP failures; preserved forensic snapshot `dify-trading-server-pre-recovery-20260922`; reboot recovered the VM with no current-boot OOM/residue. Snapshot was neither mounted nor modified. Nginx 502 was separately fixed and is out of scope.

Read-only artifact cross-check:

- `pre_open_stage_timing_latest.json`: start 2026-09-22 07:00:06, update 07:17:25, last stage `pipeline`; no browser PID linkage.
- Pre-open delivery latest: start 09-22 07:00:02, completed.
- Intraday delivery latest: start 09-21 13:05:02, timed out (stale relative to incident).
- Post-close delivery latest: start 09-22 20:25:04, timed out (after OOM).
- `logs/daily.log`, its first rotated archive and US pre-market log were searched for browser lifecycle/stage evidence. No service-PID-to-batch ownership record was found. The 07:09 historical-data readiness record is not Chrome ownership evidence.

**High confidence:** a Chrome process tree remained under cron at OOM; the code has independently reproducible lifetime/cleanup defects. **Insufficient evidence / low confidence:** exact originating TW/US batch, stock, stage and browser creation time; the fraction of total OOM pressure attributable to that tree. Do not infer ownership from PID ordering or adjacent cron timestamps. Do not claim this PR proves Chrome was the sole OOM cause.

All Python browser construction paths on main were searched. The only Selenium factory was `app/research/cnyes_selenium_browser.py`, used by TW aggregation and the explicit live diagnostic. US research uses existing HTTP paths. Code-level root causes:

1. `webdriver.Chrome()` can fail before assignment; no retained owner or cleanup on partial construction.
2. Timeout configuration can fail after Chrome exists, before a usable adapter is returned.
3. `close()` only force-cleaned on a hanging quit, not a throwing quit; cleanup exceptions propagated.
4. The old post-quit process-tree walk could miss already reparented children and used bare PIDs.
5. TW batch loops only closed after normal completion, outside `finally`; internally created aggregation sessions had no cleanup owner.
6. The concurrency constant was metadata, not a cross-process admission gate; no memory guard or hard overall browser lifetime.

## Design and state machine

`NEW -> ADMISSION -> STARTING -> READY -> CLOSING -> CLOSED`

- Admission failure: `NEW/ADMISSION -> FALLBACK`, reason `LOW_MEMORY`, `MEMORY_UNKNOWN`, `BROWSER_BUSY` or `ADMISSION_UNAVAILABLE`.
- Any constructor, navigation, parser, transport, timeout or cancellation failure converges on `CLOSING`; original exceptions survive cleanup.
- A batch session attempts creation at most once; subsequent calls reuse the browser or retain its fallback reason. Closing is idempotent.
- Nonblocking flock at `/tmp/stock-ai-browser-<uid>.lock` limits all cooperating batches/worktrees under that OS user to one browser. The lock inode is never unlinked. Worker inherits the descriptor, so parent death cannot prematurely admit another browser.
- Default admission requires at least 1 GiB `MemAvailable` (swap does not count), leaving headroom on the 3.8 GiB VM. Unknown memory fails closed. This is a conservative admission threshold, not a memory reservation or guarantee against other workloads consuming RAM later.
- Browser runs in its own Python subprocess/session. Creation 25 s, page load 12 s, script 5 s, overall lifetime 180 s, quit 5 s, descendant grace 2 s. Overall includes idle time across stocks; expiry degrades remaining work to HTTP/title-only.
- Parent IPC deadlines bound blocked browser calls. Worker-only alarm bounds lifetime even on caller death; EOF and SIGTERM also enter cleanup. No caller signal handlers are changed.
- Linux worker registers as a child subreaper. Chrome descendants that detach or outlive ChromeDriver are adopted by this worker, and remain attributable to it. PID start time plus pidfd prevents signaling a reused PID. Cleanup sends TERM then KILL only to owned descendants and reaps them. Last-resort parent kill targets its own dedicated worker session plus identity-checked descendants, never process names.
- Partially initialized Chrome object is retained via `__new__`; a quit-once override accounts for Selenium internally calling quit during constructor failure. Quit is attempted once, bounded even if it hangs/throws. Worker cleanup executes independently afterward.
- Chrome profile and TMPDIR belong to the worker's unique temporary directory. Worker removes it on parent death; parent also cleans it after shutdown. Audit events include parent/worker/service PIDs, operation, timestamp, cleanup result and exception class; never article bodies, URLs, credentials or raw exception text.

## Fallback and invariant scope

RSS collection and existing requests enrichment remain available when Selenium is denied/fails; if those cannot provide content the item stays title-only/unavailable. No browser exception fabricates FULL_CONTENT. No relevance/materiality rule, strategy weight, trading action, notification text or sender changes. The two TW pipeline diffs are `try/finally` ownership wrappers around otherwise unchanged stock loops (`git diff -w` makes this explicit).

Changed files: shared browser lifecycle module; CNYES adapter; TW aggregation; pre-open and afternoon pipeline ownership wrappers; offline fault-injection suite and fake worker fixture; new registry validator; validator registry; this report.

## Validation

Offline unit suite includes successful/idempotent quit, partial constructor and Selenium internal quit, timeout configuration failure, navigation/parser/cancellation exceptions, quit failure/hang, original-exception preservation, no repeated creation, thread/cross-process admission, low/unknown memory, PID-reuse protection, owned-tree exclusion, HTTP enrichment/title-only fallback and bounded IPC.

Linux integration uses **fake Selenium** with real detached Python child processes. It verifies success, partial construction, constructor hang, navigation failure, overall timeout, quit failure/hang, cancellation, parent EOF and idle expiry; every recorded child PID must disappear, the worker must exit, the temporary profile must disappear, the lock must be reusable and an unrelated process must survive. No real Chrome smoke test or production pipeline is run.

Local macOS: 24 unit tests PASS; ten Linux-only cases require Linux CI and are reported as skipped locally. Existing CNYES materiality validator 61/61, AI-DEV-248 24/24, AI-DEV-249 20/20, US research regression 34 checks passed. Local full branch gate was executed: existing visual validators assume Linux `/tmp` paths and fail on macOS; the existing AI-DEV-237 multiprocessing PID-lock test also observed two sequential winners under macOS spawn. No gates were weakened or unrelated validators changed. Linux CI results are recorded in the PR after execution; no claim of natural production verification is made.

## Residual risks and follow-up

- SIGKILL, kernel OOM killing the worker itself, host shutdown, or uninterruptible kernel I/O can defeat user-space finally/quit and timely cleanup. This code cannot guarantee cleanup after its cleanup owner is killed. A future per-job systemd scope/cgroup with memory limits and group termination would address stronger containment, but this PR changes no cron/systemd/VM configuration.
- Admission applies to cooperating processes under the production OS user; separately launched user Chrome or other users are intentionally untouched and can still exhaust memory.
- Worker isolation adds Python process memory and startup overhead. The 1 GiB threshold/180 s lifetime may reduce CNYES coverage during pressure or long batches; source-health fallback is explicit. Tune only using natural telemetry after a separately approved deployment.
- Linux pidfd/subreaper is required for real Selenium; unsupported platforms fail closed to HTTP/title-only. Tests on macOS do not substitute for Linux integration.
- Exact incident owner remains unresolved; forensic snapshot is preserved for separately authorized deeper analysis. No speculative US attribution.

Production mutation: NONE. No production worktree/artifact cleanup, DB writes, pipeline execution, Manual Rerun, notifications, trading, cron/systemd/Nginx/Docker/firewall/VM changes, secrets access, snapshot deletion or PR merge.
