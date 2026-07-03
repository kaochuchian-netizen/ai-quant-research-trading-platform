# Pre-open Delivery Hung Incident Runbook

## Diagnose
Run the read-only diagnostic command:
```bash
./venv/bin/python scripts/orchestrator/diagnose_pre_open_runtime_guard.py --pretty
```
Do not run `scripts/run_pipeline.py`, do not run `python3 main.py`, and do not resend LINE or Email while diagnosing.

## Identify hung pre_open processes
Look for `run_stock_analysis.sh`, `approved_pre_open_delivery.py --window pre_open_0700`, `scripts/run_pipeline.py pre_open --production-approved`, and orphaned `main.py` processes associated with old pre_open runs. Check PID, PPID, elapsed time, cwd, wchan, file descriptors, and network sockets.

## Capture evidence

Use this section to capture evidence before process cleanup.
Save ps, pstree, lsof, ss, `/proc/<pid>/cmdline`, `/proc/<pid>/cwd`, wchan, log file metadata, `/tmp/approved_pre_open_0700_delivery_result.json` metadata, dashboard manifest metadata, and cron evidence before changing process state.

## When to terminate with TERM
Use TERM only after evidence is captured and the process is clearly a hung or stale pre_open production process. Prefer TERM on the wrapper and child pipeline, then verify that no matching process remains.

## when not to KILL
Do not KILL before TERM has had time to work. Do not KILL a process that is not clearly associated with the hung pre_open run. Escalate if a process owns unknown state, appears newly started, or is not under the stock-ai repo path.

## why not to rerun or resend
A rerun or resend can duplicate advisory reports, mask the original failure, and publish stale content. First verify whether LINE, Email, or dashboard delivery already happened.

## verify no delivery was sent
Check that `logs/daily.log` did not contain current-day delivery success, `/tmp/approved_pre_open_0700_delivery_result.json` was not updated for the incident time, and `/var/www/stock-ai-dashboard/publish_manifest.json` was not updated. Confirm timeout artifacts have `line_attempted=false`, `email_attempted=false`, and `dashboard_attempted=false`.

## verify post-merge status
After a fix is merged, ensure `main` and `origin/main` are synchronized, repo status is clean, validator passes, and the diagnostic command returns valid JSON without side effects.

## escalation notes
Escalate to an operator before KILL, before any manual resend, before scheduler changes, before reading secrets, and before any production dashboard publish. If the source connector remains hung, create a follow-up for source connector live timeout hardening.
