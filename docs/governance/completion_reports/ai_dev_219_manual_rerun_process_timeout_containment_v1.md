# AI-DEV-219 Manual Rerun Process-Group Timeout Containment V1

## Final status

- Status: IMPLEMENTED_DETERMINISTIC_QA_PASS_PENDING_CONTROLLED_VERIFICATION
- Controlled gate: READY_FOR_MANUAL_RERUN_TIMEOUT_CONTROLLED_VERIFICATION
- Starting main: 485d019230417b62e5560b7610ad62f3d3b2c304
- Implementation commit: c28589062de2d1c4f24cfd41cfe8e0406562cacb
- Implementation PR: #289
- CI: AI Dev Validation run 32542167547 PASS
- Merge/current main: be13632b751634f0a433135f19a67dd562c988c1

## Incident reconciliation

The preserved task manual-dc5cf70b48e5c356 was already terminal failed after infrastructure recovery, with runtime_timeout, duration 2540 seconds, and no LINE, Email, route, Dashboard, or trading side effects. Pre-reset serial evidence remains preserved in Cloud Shell at ~/dify-trading-server-pre-reset-serial-20260821.log.

Read-only reconciliation found no surviving PID, process group, descendant, or task-owned stale lock. No process signal or cleanup action was therefore required, and no unrelated process was affected.

## Root cause and runtime repair

The former bridge used direct-child subprocess.run with capture_output and timeout=1800. Descendants could inherit stdout/stderr pipes and outlive the direct child, allowing timeout handling to block before terminal task persistence.

The replacement supervisor:

- launches every governed backend with start_new_session=True;
- persists PID, PGID, sanitized command identity, task log path, heartbeat, and stage;
- streams combined stdout/stderr to a task-scoped log capped at 2 MiB;
- sends TERM to the whole process group, waits a bounded grace period, then sends KILL when required;
- performs bounded output collection and never waits indefinitely for inherited pipe EOF;
- persists failed/runtime_timeout with stage, elapsed time, timeout, and termination evidence;
- releases the task-owned active lock in success, exception, and timeout paths.

## Runtime observability

Canonical stages are:

runtime_started → market_data → news_acquisition → research_rre → prediction_projection → artifact_generation → admission → archive_publish → chromium_visual → notification → completed.

Each observed stage retains started/finished timestamps, status, and deterministic elapsed_seconds. Public status preserves the fine-grained stage and safely exposes task ID, lifecycle status, PID/PGID, heartbeat/update/finish timestamps, failure class, and stage duration without command arguments or secrets.

## Deterministic QA

Dedicated AI-DEV-219 validator: 6/6 PASS.

- successful runtime control
- descendant inherited-pipe process tree
- TERM-resistant hung child with KILL escalation
- task-lock ownership and release
- heartbeat/public status responsiveness
- process-group, bounded-output, terminal-timeout and lock-finally mutation guards

Scoped Python compile, registry JSON syntax, and git diff --check: PASS.

Targeted manual-rerun status, single-window, progress alias, revision policy, runtime activation, persistent deployment, and AI-DEV-218B regressions completed without production execution.

Full executable branch registry: ok=true, passed=true, reasons=[].
Post-merge executable registry: ok=true, errors=[].
Platform inspector: ok=true.
Workspace governance: ok=true, zero secret-pattern hits.

## Governance and cleanup

AI-DEV-219 is registered as an ACTIVE leaf with both required_in_branch_gate=true and required_in_post_merge=true. Main and origin/main were synchronized at the merge commit with ahead/behind 0/0. The merged feature branch was deleted locally and remotely. Existing runtime/generated dirty artifacts were preserved and excluded from commits.

## Decision and production safety

No change was made to strategy, scoring, prediction weights, ranking, eligibility, action, Entry, Stop, trading Target, sizing, or execution ownership.

- Second/manual/production rerun executed: false
- LINE or Email sent: false
- Trading/orders executed: false
- Scheduler/cron changed: false
- nginx/systemd changed or service restarted: false
- Secrets accessed or changed: false
- Production DB written: false
- Immutable archive rewritten: false
- Existing incident evidence deleted: false

## Remaining gate

Repository closure is complete. A new PM-authorized controlled manual rerun is required to verify real task heartbeat, stage progression, timeout terminalization, and bridge responsiveness under the deployed runtime. No controlled rerun was performed by AI-DEV-219.
