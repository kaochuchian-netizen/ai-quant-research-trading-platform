# Orchestrator Current State Summary

## Summary

The project now has a persistent VM-side orchestrator loop. The loop is intended to keep the repository synchronized and publish local runtime status for safe review.

The system is not configured to automatically start code-editing agents.

## Completed

### VM Timer Loop

A user-level systemd timer is available on the VM.

Expected components:

```text
stock-ai-orchestrator-loop.timer
stock-ai-orchestrator-loop.service
~/.local/bin/stock-ai-orchestrator-loop.sh
```

The wrapper performs:

```text
cd ~/stock-ai
git pull --ff-only
python scripts/orchestrator/run_loop_once.py --check-remote --pretty
```

### Loop Status

The loop writes status to:

```text
~/.local/state/stock-ai-orchestrator/loop_status.json
~/.local/state/stock-ai-orchestrator/loop.log
```

### Queue and Handoff Preparation

The repository includes queue and handoff support:

```text
orchestrator/templates/codex_handoff_queue.example.json
scripts/orchestrator/check_codex_queue_gate.py
scripts/orchestrator/materialize_codex_handoff.py
scripts/orchestrator/check_manual_codex_start_gate.py
```

### Documentation

The repository includes operations documentation:

```text
docs/orchestrator_vm_timer_operations.md
docs/codex_manual_start_workflow.md
docs/orchestrator_operations_index.md
```

## Current Safe Boundary

The automated system may prepare and report state.

The automated system must not:

- start Codex automatically
- run production workflows
- send LINE messages
- modify scheduler settings automatically
- modify secret files
- modify production database files

## Practical Operating Mode

Current recommended flow:

```text
ChatGPT prepares low-risk GitHub changes
→ VM timer pulls changes
→ loop writes status
→ operator reviews handoff
→ operator manually starts Codex only when needed
```

## Known Constraint

Attempts to wire a formal automatic start-request path into the loop were stopped by the safety boundary. The safe alternative is to keep manual operator control for any code-editing agent execution.

## Current Next Safe Actions

Recommended next actions that remain safe:

1. Keep documentation updated.
2. Keep loop status readable and minimal.
3. Use queue templates only for low-risk tasks.
4. Use manual Codex start workflow when actual code editing is needed.
5. Review all generated changes before commit and push.
