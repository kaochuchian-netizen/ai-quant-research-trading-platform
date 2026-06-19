# Orchestrator Timer Plan

## Purpose

This document defines how to run the VM-side Orchestrator loop on a schedule.

This phase is a plan only. It does not install, enable, or modify any timer or cron entry.

## Current executable target

The current safe loop entrypoint is:

```bash
cd ~/stock-ai
python3 scripts/orchestrator/run_loop_once.py --pretty
```

The dry-run entrypoint is:

```bash
cd ~/stock-ai
python3 scripts/orchestrator/run_loop_once.py --dry-run --pretty
```

## Recommended scheduler

Use a user-level systemd timer on the GCP VM.

Reason:

- Easier to inspect with `systemctl --user status`.
- Better logs through `journalctl --user`.
- Easier to start, stop, enable, disable, and audit than a raw crontab line.
- Does not require root if user-level systemd is available.

Cron remains a fallback option if user-level systemd is not available.

## Recommended initial cadence

Start with a conservative cadence:

```text
Every 15 minutes
```

Reason:

- Frequent enough for development orchestration.
- Slow enough to avoid noisy logs and repeated notifications.
- Easy to observe before expanding automation.

## Proposed systemd user service

File path:

```text
~/.config/systemd/user/stock-ai-orchestrator-loop.service
```

Content:

```ini
[Unit]
Description=Stock AI Orchestrator single loop iteration

[Service]
Type=oneshot
WorkingDirectory=%h/stock-ai
ExecStart=%h/stock-ai/venv/bin/python %h/stock-ai/scripts/orchestrator/run_loop_once.py --pretty
```

If the virtual environment path differs, use the actual Python path.

## Proposed systemd user timer

File path:

```text
~/.config/systemd/user/stock-ai-orchestrator-loop.timer
```

Content:

```ini
[Unit]
Description=Run Stock AI Orchestrator loop periodically

[Timer]
OnBootSec=5min
OnUnitActiveSec=15min
Persistent=true

[Install]
WantedBy=timers.target
```

## Manual enable commands

Do not run these commands until explicitly approved.

```bash
systemctl --user daemon-reload
systemctl --user enable --now stock-ai-orchestrator-loop.timer
systemctl --user status stock-ai-orchestrator-loop.timer
```

## Manual inspection commands

```bash
systemctl --user list-timers | grep stock-ai-orchestrator
systemctl --user status stock-ai-orchestrator-loop.service
journalctl --user -u stock-ai-orchestrator-loop.service -n 100 --no-pager
cat ~/.local/state/stock-ai-orchestrator/loop_status.json
```

## Manual disable commands

```bash
systemctl --user disable --now stock-ai-orchestrator-loop.timer
systemctl --user status stock-ai-orchestrator-loop.timer
```

## Cron fallback

Use cron only if user-level systemd is not available.

Example line for manual review only:

```cron
*/15 * * * * cd ~/stock-ai && ~/stock-ai/venv/bin/python scripts/orchestrator/run_loop_once.py --pretty >> ~/.local/state/stock-ai-orchestrator/loop.log 2>&1
```

Do not install this automatically.

## Safety boundaries

The scheduled loop should initially run only `run_loop_once.py`.

It should not:

- Start Codex.
- Send notifications.
- Pull Git changes.
- Run trading workflows.
- Modify cron or timer settings by itself.
- Read or print local private config values.

## Phase C-9-7 scope

The next phase may add a controlled installer script or setup instructions.

It should remain explicit and reversible:

- Write service and timer files only after user approval.
- Show exact files before enabling.
- Support disable and status commands.
- Keep the initial cadence conservative.
