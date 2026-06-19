# Codex Manual Launcher Plan

## Purpose

Create a safe script-assisted workflow for starting Codex from the VM.

The launcher is not an autonomous agent runner. It is a manual convenience tool that performs preflight checks, prepares a branch, shows the current handoff, and then asks the operator to confirm before opening Codex.

## Target Script

```text
scripts/orchestrator/start_codex_manual.sh
```

## Intended Flow

```text
operator runs script
→ script checks repository state
→ script checks runtime handoff files
→ script shows handoff summary
→ script creates or switches to a task branch
→ script prints safety boundaries
→ operator confirms
→ script opens Codex interactively
```

## Required Checks

The launcher should check:

- current directory is inside the project repository
- current branch is `main` before branch creation
- Git working tree is clean
- `~/.local/state/stock-ai-orchestrator/current_codex_handoff.md` exists
- `~/.local/state/stock-ai-orchestrator/current_codex_handoff.json` exists
- handoff task ID is readable
- branch name can be derived safely from task ID or handoff ID

## Required Safety Boundaries

The launcher must remind the operator that Codex may not touch:

- `.env`
- secret files
- `data/stock_analysis.db`
- `data/backups/`
- `analysis/output/`
- scheduler or timer settings
- production workflows
- LINE notification sending
- trading or order execution

## Branch Policy

The launcher should create a branch like:

```text
codex/<task-id-or-handoff-id>
```

It must not commit, push, merge, or delete branches automatically.

## Confirmation Policy

The launcher should stop before opening Codex and require an explicit confirmation.

Example:

```text
Type START to open Codex for this handoff:
```

Any other input exits safely.

## First Prompt for Codex

After Codex opens, use this instruction:

```text
請先不要修改任何檔案。
請閱讀 ~/.local/state/stock-ai-orchestrator/current_codex_handoff.md，理解任務範圍、允許路徑、禁止路徑與驗證指令。
讀完後先回報你的執行計畫，不要先動手。
```

## Non-goals

The launcher must not:

- run production commands
- send notifications
- edit runtime files
- edit queue files
- read secret files
- auto-commit
- auto-push
- auto-merge
- bypass operator review
