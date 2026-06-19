# Orchestrator VM Timer Operations

## Purpose

This document records the current VM timer operating model for the AI Quant Research & Trading Platform.

The timer is responsible for periodically refreshing the repository and running one safe orchestrator loop iteration.

## Current Operating Model

The VM uses a user-level systemd timer:

- Timer: `stock-ai-orchestrator-loop.timer`
- Service: `stock-ai-orchestrator-loop.service`
- Wrapper: `~/.local/bin/stock-ai-orchestrator-loop.sh`
- Runtime directory: `~/.local/state/stock-ai-orchestrator`

The wrapper runs the following high-level sequence:

1. Enter `~/stock-ai`.
2. Run `git pull --ff-only`.
3. Run `scripts/orchestrator/run_loop_once.py --check-remote --pretty`.
4. Write runtime status files.

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
- Git working tree is clean.
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

If `git pull --ff-only` fails, check whether the working tree is dirty before taking any recovery action:

```bash
cd ~/stock-ai
git status
```

Do not run reset or clean commands without confirming the cause.

## Change Control

Timer service changes should remain explicit and minimal. Any modification to the timer, service, or wrapper should be reviewed as an operations change.
