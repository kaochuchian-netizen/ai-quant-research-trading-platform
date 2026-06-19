# Orchestrator Daily Checklist

## Purpose

Use this checklist when checking whether the VM-side orchestrator is healthy.

## Quick Check

From the VM:

```bash
cd ~/stock-ai

git status

systemctl --user status stock-ai-orchestrator-loop.timer --no-pager

cat ~/.local/state/stock-ai-orchestrator/loop_status.json

tail -50 ~/.local/state/stock-ai-orchestrator/loop.log
```

## Expected Results

### Git

Expected:

```text
On branch main
Your branch is up to date with 'origin/main'.
nothing to commit, working tree clean
```

### Timer

Expected:

```text
Active: active (waiting)
```

### Loop Status

Expected fields:

```text
ok: true
git_state.ok: true
timer_state.ok: true
remote_state.ok: true
codex_running: false
```

### Loop Log

Expected:

```text
single_iteration ok=True
```

## If Something Looks Wrong

### Dirty Git Working Tree

Run:

```bash
git status
git diff --stat
git diff
```

Do not reset or clean until the cause is understood.

### Timer Not Active

Inspect first:

```bash
systemctl --user status stock-ai-orchestrator-loop.timer --no-pager
systemctl --user status stock-ai-orchestrator-loop.service --no-pager
journalctl --user -u stock-ai-orchestrator-loop.service -n 100 --no-pager
```

Restart only after inspection:

```bash
systemctl --user restart stock-ai-orchestrator-loop.timer
```

### Loop Status Not OK

Read the blocked reasons inside:

```bash
cat ~/.local/state/stock-ai-orchestrator/loop_status.json
```

Common causes:

- working tree not clean
- timer inactive
- git fetch or pull issue
- malformed runtime file
- missing expected script

## Manual Code Work Boundary

Only start manual code work after confirming:

- Git tree is clean.
- Timer is healthy.
- Loop status is readable.
- The task scope is low risk.
- No blocked files are involved.

Do not use this checklist to authorize production runs or automatic agent execution.
