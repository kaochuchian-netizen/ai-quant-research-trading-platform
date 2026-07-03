# AI-DEV-127 Production Pipeline Timeout & Stale Process Guard V1

## Purpose
AI-DEV-127 repairs the 2026-07-03 07:00 pre_open production delivery hung incident by adding bounded subprocess waits, stale process detection, overlapping run blocking, and explicit diagnostics. The repair is reliability-focused and does not change forecast weights, confidence formulas, ratings, actions, scheduler times, or delivery destinations.

## Incident summary
On 2026-07-03 cron triggered the 07:00 pre_open scheduler entry and started `approved_pre_open_delivery.py`. That wrapper started `scripts/run_pipeline.py pre_open --production-approved`, then waited indefinitely. LINE was not attempted, Email was not attempted, dashboard was not updated, `logs/daily.log` stayed zero bytes, and the latest approved delivery/dashboard artifacts remained from 2026-07-02. Old `run_stock_analysis.sh`, `run_pipeline.py`, and `main.py` processes were also alive for days.

## Scope
The release adds runtime guard modules under `app/runtime/`, a bounded production delivery wrapper path, a read-only diagnostic command, validator coverage, examples, and a manual incident runbook.

## Non-goals
- No production pipeline replay
- No LINE resend
- No Email resend
- No dashboard production publish from validation
- No cron/systemd/timer time change
- No secrets read
- No production DB write
- No trading or order placement
- No `python3 main.py`
- No n8n or Dify runtime start
- No forecast weight, confidence formula, rating rule, or action rule change

## Timeout policy
`app/runtime/timeout_policy.py` defines central defaults: production pipeline timeout 2700 seconds, warning threshold 1800 seconds, stale process threshold 5400 seconds, external HTTP source timeout 15 seconds, market data source timeout 20 seconds, source stage soft timeout 300 seconds, and terminate grace 10 seconds. Environment variables can override these without code changes.

## Process guard design
`app/runtime/process_guard.py` inspects candidate processes with best-effort `/proc`, `ps`, and `ss` reads. It captures PID, PPID, command line, elapsed time, cwd, wchan, selected file descriptors, socket summaries, daily log attachment, pipeline artifact attachment, pre_open production classification, and stale status. It does not read secrets.

## Overlapping run guard
`app/runtime/production_run_guard.py` blocks a new pre_open production run if another non-stale pre_open run is active. It reports `overlapping_run_blocked` and does not start another pipeline. Ancestor shell processes for the current scheduler invocation are ignored so the wrapper does not block itself.

## Stale process detection
Processes older than the stale threshold are reported as `stale_process_detected`. Default behavior is detect/report only; it does not kill stale processes automatically. Manual cleanup requires operator review.

## No fresh artifact policy
On timeout, blocked overlap, or stale detection, the wrapper writes an explicit guard result with `fresh_artifact_found=false`, `line_attempted=false`, `email_attempted=false`, `dashboard_attempted=false`, and `delivery_attempted=false`. A stale previous-day artifact must not be treated as a fresh delivery result.

## logs/daily.log zero-byte diagnostic
The diagnostic script reports `logs/daily.log` existence, size, timestamp, and zero-byte status. A zero-byte log is a warning because it can indicate wrapper pipe wait or a pipeline that has not emitted output.

## Delivery wrapper behavior on timeout
`approved_pre_open_delivery.py` now starts the production pipeline with `subprocess.Popen` and `communicate(timeout=...)`. If the timeout is exceeded it sends TERM, waits for the terminate grace period, optionally sends KILL, writes a `timed_out` artifact, and returns non-zero. It does not send LINE, does not send Email, and does not publish dashboard on timeout.

## Manual incident response procedure
Use the runbook at `docs/runbooks/pre_open_delivery_hung_incident_runbook.md`. Capture diagnostics first, verify no fresh delivery artifacts were produced, then terminate only clearly stale or hung production processes with TERM. Do not rerun or resend immediately.

## Validation commands
```bash
./venv/bin/python -m py_compile \
  app/runtime/process_guard.py \
  app/runtime/timeout_policy.py \
  app/runtime/production_run_guard.py \
  app/runtime/runtime_diagnostics.py \
  scripts/orchestrator/diagnose_pre_open_runtime_guard.py \
  scripts/orchestrator/validate_production_pipeline_guard_v1.py

./venv/bin/python -m py_compile \
  scripts/orchestrator/approved_pre_open_delivery.py \
  scripts/run_pipeline.py

./venv/bin/python scripts/orchestrator/validate_production_pipeline_guard_v1.py --pretty
./venv/bin/python scripts/orchestrator/diagnose_pre_open_runtime_guard.py --pretty
./venv/bin/python scripts/orchestrator/validate_ai_branch.py --base main --head HEAD --pretty
```

## Safety boundary
Validation and diagnostics are read-only. They do not run a production pipeline, send notifications, publish dashboard files, mutate scheduler settings, read secrets, trade, write production DB state, or start n8n/Dify. Timeout failure artifacts explicitly set production publish and delivery attempts to false.

## Rollback plan
Revert the PR commit if the wrapper behavior needs to be restored. Existing cron times and systemd timers are not changed by this release, so rollback is a code-only revert.

## Future follow-up
- Real Historical Artifact Ingestion & Rolling Evaluation
- Source connector live timeout hardening
- Dashboard diagnostics production publish candidate
