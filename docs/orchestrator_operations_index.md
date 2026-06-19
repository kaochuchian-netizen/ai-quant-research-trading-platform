# Orchestrator Operations Index

## Current Automation Boundary

The orchestrator is currently designed for safe preparation and monitoring only.

It may:

- pull repository updates through the VM timer wrapper
- run one safe loop iteration
- write runtime status files
- read queue templates
- prepare handoff files for review
- report health and readiness state
- run local preflight checks before a manual Codex launch

It must not:

- start code-editing agents automatically
- run production workflows
- send LINE notifications
- modify scheduler settings without an explicit operations change
- read secret files
- modify production database files
- commit, push, or merge generated changes without review

## Key Runtime Location

```text
~/.local/state/stock-ai-orchestrator
```

Important runtime files:

```text
loop_status.json
loop.log
current_task_state.json
current_codex_handoff.json
current_codex_handoff.md
codex_manual_launcher_preflight.json
latest_approval_state.json
latest_validation_result.json
latest_decision_summary.json
latest_notice.md
```

## Key Repository Files

### Timer and Loop

```text
scripts/orchestrator/bootstrap_timer_pull_loop.sh
scripts/orchestrator/run_loop_once.py
```

### Queue and Handoff

```text
orchestrator/templates/codex_handoff_queue.example.json
scripts/orchestrator/check_codex_queue_gate.py
scripts/orchestrator/materialize_codex_handoff.py
scripts/orchestrator/check_manual_codex_start_gate.py
```

### Codex Launcher

```text
scripts/orchestrator/codex_autostart_preflight.py
scripts/orchestrator/start_codex_manual.sh
```

The manual launcher now runs the preflight checker first. It only continues when the local state is safe, then asks for an explicit `START` confirmation before opening Codex.

### Operations Documents

```text
docs/orchestrator_vm_timer_operations.md
docs/codex_manual_start_workflow.md
docs/codex_manual_launcher_plan.md
docs/orchestrator_operations_index.md
docs/orchestrator_current_state_summary.md
docs/orchestrator_daily_checklist.md
```

## Normal Operating Chain

```text
GitHub main
→ VM timer
→ git pull --ff-only
→ run_loop_once.py
→ loop_status.json / loop.log
→ handoff files for manual review
```

## Manual Launch Chain

```text
operator runs start_codex_manual.sh
→ preflight checks local state
→ handoff preview is displayed
→ safety boundaries are displayed
→ operator types START
→ task branch codex/<task-id> is created or selected
→ Codex opens interactively
```

## Manual Checks

From the VM:

```bash
cd ~/stock-ai
git status
systemctl --user status stock-ai-orchestrator-loop.timer --no-pager
systemctl --user status stock-ai-orchestrator-loop.service --no-pager
cat ~/.local/state/stock-ai-orchestrator/loop_status.json
tail -50 ~/.local/state/stock-ai-orchestrator/loop.log
```

## Manual Codex Launcher

From the VM:

```bash
cd ~/stock-ai
bash scripts/orchestrator/start_codex_manual.sh
```

The launcher writes its preflight report to:

```text
~/.local/state/stock-ai-orchestrator/codex_manual_launcher_preflight.json
```

## Manual Review Before Code Work

Before opening Codex manually, review:

```bash
cat ~/.local/state/stock-ai-orchestrator/current_codex_handoff.md
```

Only continue when the handoff is low-risk and stays within allowed paths.

## Stop Conditions

Stop and inspect before continuing if:

- Git working tree is dirty unexpectedly.
- Timer is not active.
- Loop status is not ok.
- Launcher preflight is blocked.
- Handoff asks for blocked files or paths.
- Handoff asks for production commands.
- Handoff asks for notifications.
- Handoff asks for scheduler changes.

## Recommended Next Safe Work

Safe work can continue in these areas:

- documentation consolidation
- status reporting
- validation command lists
- non-production dry-run checks
- queue template refinement
- handoff wording refinement
- branch-only development workflows

Any production execution or scheduler change should remain explicit and reviewed.
