# Orchestrator Codex Role

## Purpose

This document defines how Codex fits into the continuous Orchestrator model.

The intended model has four parts:

```text
ChatGPT
Codex
GitHub
GCP VM
```

## Role summary

### ChatGPT

ChatGPT is the planning and review layer.

It defines the next task, explains the scope, reviews the result, and helps the user decide whether to continue or pause.

### Codex

Codex is the coding agent used from the project checkout on the GCP VM.

Its role is to work on scoped engineering tasks after a task has been clearly described.

Codex should receive a task handoff that includes:

- Task ID.
- Task name.
- Scope.
- Files or directories involved.
- Validation commands.
- Expected summary format.

### GitHub

GitHub is the source of truth for committed project changes.

It keeps history, reviewable diffs, and the main branch state shared by ChatGPT, Codex, and the VM.

### GCP VM

The GCP VM is the always-on host.

It stores the working checkout, local runtime state, validation outputs, notification outputs, and Codex task handoff files.

## Runtime state

Codex handoff state should live on the VM, not in ChatGPT memory.

Recommended local path:

```text
~/.local/state/stock-ai-orchestrator/current_codex_handoff.md
```

This file should be generated from the current task state and decision summary.

## Operating rule

The continuous loop should coordinate the work, but Codex should receive one scoped handoff at a time.

The loop should record:

- Current task ID.
- Current task name.
- Handoff path.
- Validation result path.
- Notification result path.
- Continue or pause decision.

## Next implementation direction

The next practical step is to add a VM-local runtime initializer, then add a Codex handoff file format.

This keeps the architecture ready for continuous operation while keeping each task observable and reviewable.
