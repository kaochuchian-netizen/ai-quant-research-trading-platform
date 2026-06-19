# Codex Manual Start Workflow

## Purpose

This workflow keeps the platform safe while still reducing manual work.

The current operating model is:

1. ChatGPT prepares low-risk repository changes through GitHub.
2. The VM timer automatically pulls the latest repository state.
3. The orchestrator loop checks runtime state and prepares handoff files.
4. Codex execution remains a manual operator action.

## Why Manual Start Is Required

Automatic preparation and status checking are allowed within the current safety boundary.

Automatic agent execution is intentionally not enabled. The system must stop before any autonomous code-editing agent is started.

This prevents accidental changes to:

- production workflows
- scheduler settings
- notification flows
- database files
- secret files
- trading-related execution paths

## Normal VM State

The VM timer should already be active:

```bash
systemctl --user status stock-ai-orchestrator-loop.timer --no-pager
```

The runtime directory is:

```text
~/.local/state/stock-ai-orchestrator
```

Important files:

```text
loop_status.json
loop.log
current_codex_handoff.json
current_codex_handoff.md
```

## Manual Codex Start Procedure

Only use this flow when a prepared handoff is ready and you intentionally want Codex to work on the project.

### 1. Open the VM

```bash
cd ~/stock-ai
```

### 2. Check status

```bash
cat ~/.local/state/stock-ai-orchestrator/loop_status.json
```

Confirm the state is healthy before proceeding.

### 3. Read the prepared handoff

```bash
cat ~/.local/state/stock-ai-orchestrator/current_codex_handoff.md
```

Confirm the handoff describes a low-risk task and does not ask Codex to touch blocked paths.

### 4. Start Codex manually

```bash
codex
```

Inside Codex, instruct it to read the handoff file and follow its scope exactly.

Suggested prompt:

```text
請先不要修改任何檔案。
請閱讀 ~/.local/state/stock-ai-orchestrator/current_codex_handoff.md，理解任務範圍、允許路徑、禁止路徑與驗證指令。
讀完後先回報你的執行計畫，不要先動手。
```

### 5. Let Codex work only after review

After Codex explains its plan, approve only if the plan stays within the handoff scope.

### 6. Validate changes

Run the validation commands from the handoff file.

At minimum:

```bash
git status
```

Then run the specific validation commands listed in the handoff.

### 7. Commit and push

Only commit after validation passes.

```bash
git status
git add <changed files>
git commit -m "<clear message>"
git push
git status
```

## Hard Stop Conditions

Do not proceed if any of these are true:

- Git working tree is unexpectedly dirty before starting.
- The handoff asks to modify `.env` or secrets.
- The handoff asks to modify database files.
- The handoff asks to send LINE messages.
- The handoff asks to change timer or scheduler settings.
- The handoff asks to run production workflows.
- Codex proposes changes outside the allowed paths.

## Recovery

If Codex changes unexpected files, stop and inspect:

```bash
git status
git diff --stat
git diff
```

Do not reset or clean files until the cause is understood.

## Current Automation Boundary

The system may automatically:

- pull GitHub changes with `git pull --ff-only`
- run loop health checks
- update runtime status files
- prepare handoff files

The system must not automatically:

- start Codex
- run production workflows
- send notifications
- modify scheduler settings
- modify secret files
- modify production database files
