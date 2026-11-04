# Orchestrator VM Timer Operations

## Purpose

This document records the current VM timer operating model for the AI Quant Research & Trading Platform.

The timer is responsible for running one safe orchestrator loop iteration. It must never update the checked-out Production source. Git updates belong to a separately approved deployment process.

## Current Operating Model

The VM uses a user-level systemd timer:

- Timer: `stock-ai-orchestrator-loop.timer`
- Service: `stock-ai-orchestrator-loop.service`
- Wrapper: `~/.local/bin/stock-ai-orchestrator-loop.sh`
- Runtime directory: `~/.local/state/stock-ai-orchestrator`

The wrapper runs the following high-level sequence:

1. Enter `~/stock-ai`.
2. Run `scripts/orchestrator/run_loop_once.py --check-remote --pretty` against the already deployed source.
3. Write runtime status files. The remote status probe is not authorization to fetch or pull source.

## Runtime Files

The main runtime directory is:

```text
~/.local/state/stock-ai-orchestrator
```

Important files:

```text
loop_status.json
loop.log
current_task_state.json
current_codex_handoff.json
current_codex_handoff.md
latest_approval_state.json
latest_validation_result.json
latest_decision_summary.json
latest_notice.md
```

## Expected Safe State

The normal safe state is:

- Git branch is `main`.
- Git working tree is inspected. Existing preserved runtime artifacts are not cleaned or overwritten.
- No `git pull`, source checkout, or deployment occurs as part of timer execution.
- Timer is enabled.
- Timer is active.
- Loop status is writable.
- Production commands are not run by the loop.
- Notifications are not sent by the loop.
- Scheduler settings are not modified by the loop.

## Manual Health Checks

Run from the VM when needed:

```bash
cd ~/stock-ai
systemctl --user status stock-ai-orchestrator-loop.timer --no-pager
systemctl --user status stock-ai-orchestrator-loop.service --no-pager
cat ~/.local/state/stock-ai-orchestrator/loop_status.json
tail -50 ~/.local/state/stock-ai-orchestrator/loop.log
git status
```

## Recovery Notes

If the timer is inactive:

```bash
systemctl --user restart stock-ai-orchestrator-loop.timer
```

If the service failed, inspect logs first:

```bash
systemctl --user status stock-ai-orchestrator-loop.service --no-pager
journalctl --user -u stock-ai-orchestrator-loop.service -n 100 --no-pager
```

If the remote check or Git worktree verification fails, inspect status before taking any recovery action:

```bash
cd ~/stock-ai
git status
```

Do not run reset or clean commands without confirming the cause.

## Change Control

Timer service changes should remain explicit and minimal. Any modification to the timer, service, or wrapper should be reviewed as an operations change.

## AI-DEV-300: deployment separation and already-installed wrappers

Source fix: `scripts/orchestrator/bootstrap_timer_pull_loop.sh` no longer generates
a wrapper that performs `git pull --ff-only`. The scheduled loop remains
read-only with respect to checked-out Git source (its normal runtime status
files are written separately). Repository code/CI changes **do not** alter the
existing VM-local `~/.local/bin/stock-ai-orchestrator-loop.sh` automatically.

Before any Production activation, a separately authorized operations change
must inspect the *actual* VM-installed wrapper, service, timer, runtime
permissions, active batch locks, and source SHA. Do not run the bootstrap
script as part of this GitHub change: it writes user systemd files and
restarts/starts units. Preserve the existing wrapper as rollback evidence.
Use an explicit, approved change window away from TW/US batch lifecycles;
perform a no-send/no-trade controlled validation of the proposed wrapper.
If any approval, governance, active-batch, or rollback evidence is missing,
stop and do not apply an update.

Scope boundaries: this change does not repair Portal HTTP 502, the
orchestrator-loop service failure, Docker socket permissions, Google package
drift, recipient delivery receipts or historical governance. These require
separate read-only VM diagnostics and explicitly approved fixes.
