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

It must not:

- start code-editing agents automatically
- run production workflows
- send LINE notifications
- modify scheduler settings without an explicit operations change
- read secret files
- modify production database files

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

### Operations Documents

```text
docs/orchestrator_vm_timer_operations.md
docs/codex_manual_start_workflow.md
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

Any execution or scheduler change should remain explicit and reviewed.
