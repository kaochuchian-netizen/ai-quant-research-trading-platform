# Orchestrator Persistent Loop Plan

## Goal

Build a safe persistent operating loop that lets ChatGPT, GitHub, and the GCP VM work together continuously.

The VM should become the always-on execution host. GitHub should remain the source of truth. ChatGPT should define tasks, review results, and decide the next low-risk step with the user.

## Current status

The project already has these building blocks:

- GitHub-side code and document changes.
- VM-side validation runner.
- Stage task state generator.
- Stage notification email sender.
- Local approval parser for `continue` and `pause`.
- Approval gate and decision summary generator.
- Decision note writer.

These pieces prove the core loop can work, but the loop is still manually triggered.

## Target architecture

```text
ChatGPT / user decision
        |
        v
GitHub main branch
        |
        v
GCP VM orchestrator loop
        |
        +-- git pull --ff-only, when allowed
        +-- run allowlisted validation
        +-- render stage summary
        +-- send notification
        +-- wait for continue / pause state
        +-- prepare next low-risk task handoff
```

## Persistent loop responsibility

The persistent loop should live on the GCP VM, not inside ChatGPT.

ChatGPT is not a daemon. It should not be treated as the always-on process. The VM should run a small, controlled loop by cron or systemd timer. That loop can inspect local state files, pull approved GitHub changes, run scoped checks, and send summaries.

## Safety model

The persistent loop must start with low-risk Orchestrator work only.

Allowed in the first persistent-loop phase:

- Check Git branch and clean working tree.
- Run `git pull --ff-only` only when enabled by task state.
- Run allowlisted validation commands.
- Render stage notification.
- Send email notification when explicitly configured.
- Read local approval-state JSON.
- Write local state files under `/tmp` or a controlled orchestrator runtime directory.

Not allowed in the first persistent-loop phase:

- Formal trading pipeline execution.
- Database migration.
- Production database modification.
- LINE broadcast.
- Cron modification by the loop itself.
- Order placement.
- Unreviewed shell command execution.
- Reading or printing local private config values.

## Proposed runtime directory

Use a VM-local directory for durable loop state:

```text
~/.local/state/stock-ai-orchestrator/
```

Recommended files:

```text
current_task_state.json
latest_approval_state.json
latest_validation_result.json
latest_decision_summary.json
latest_notice.md
loop_status.json
loop.log
```

Runtime state should not be committed to GitHub.

## Phase C-9 breakdown

### Phase C-9-1: Persistent loop design document

Document the loop architecture, runtime state files, safety model, and execution boundaries.

Status: this document.

### Phase C-9-2: Runtime directory initializer

Add a script that creates the VM-local runtime directory and writes an initial `loop_status.json`.

The script should not start a loop. It should only initialize state.

### Phase C-9-3: Single-iteration loop runner

Add a script that runs exactly one loop iteration:

1. Load current task state.
2. Check Git state.
3. Run scoped validation.
4. Render or send stage notice if configured.
5. Read approval state if present.
6. Write loop status.

It must not run continuously yet.

### Phase C-9-4: Dry-run loop command

Add a dry-run mode that prints what would happen without pulling, sending, or changing runtime state.

### Phase C-9-5: systemd timer or cron plan

Document how to run the single-iteration loop periodically.

Do not install the timer automatically in this phase. The user should explicitly approve the schedule before enabling it.

### Phase C-9-6: Controlled timer installation

Only after review, add instructions or a script to install the timer.

This must remain explicit and reversible.

## Practical operating model

The final operating model should be:

1. ChatGPT creates or reviews a low-risk task.
2. Changes are committed to GitHub.
3. VM loop pulls and validates.
4. VM sends summary email.
5. User replies `continue` or `pause`.
6. Approval state is recorded locally.
7. VM prepares the next task status.
8. ChatGPT continues from the latest state.

## Key constraint

The system should become continuous, but not uncontrolled.

Every step must be observable, reversible, and limited to clearly allowlisted actions.
