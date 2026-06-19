# AI Development Closed Loop Runbook

## Purpose

This runbook describes the safe PR-based closed loop for AI-assisted
development while protecting production behavior.

## Closed Loop Flow

```text
runtime queue
→ promote
→ one-shot runner
→ Codex handoff / implementation
→ validation bundle
→ optional PR creation
→ GitHub Actions validation
→ optional conditional auto merge
→ completed archive
→ VM timer pull after merge
```

The queue runner is one-shot only. It is not a daemon and does not install cron,
systemd, or timer configuration.

## Hard Safety Boundaries

Do not allow AI automation to:

- push directly to `main`
- modify GitHub rulesets
- relax validators or GitHub Actions
- execute arbitrary shell commands supplied by a task
- send LINE messages
- place orders
- run trading execution
- run production pipelines
- modify `.env` or secret files
- modify `data/stock_analysis.db`
- modify `data/backups/`
- modify `analysis/output/`
- modify cron, systemd, or timer settings

## Step 1: Initialize Runtime Queue

Repository queue files are seed/example/reference files. Formal promotion uses
runtime queue files under `~/.local/state/stock-ai-orchestrator`.

```bash
cd ~/stock-ai
python3 scripts/orchestrator/init_ai_runtime_queue.py --pretty
```

Add real pending tasks to:

```text
~/.local/state/stock-ai-orchestrator/pending_tasks.json
```

## Step 2: Promote a Runtime Queue Task

Preview the next task without writing files:

```bash
python3 scripts/orchestrator/promote_next_ai_task.py --dry-run --pretty
```

Promote the next task:

```bash
python3 scripts/orchestrator/promote_next_ai_task.py --pretty
```

Outputs:

```text
~/.local/state/stock-ai-orchestrator/ai_task_branch_plan.json
~/.local/state/stock-ai-orchestrator/ai_task_pr_body.md
```

Promotion writes runtime queue state only. It keeps the repository clean guard
and does not create branches, modify implementation files, commit, push, open
PRs, merge, run production workflows, send LINE messages, or place orders.

## Step 3: Run One-Shot Queue Runner

Prepare a task branch and stop at handoff when no implementation exists:

```bash
python3 scripts/orchestrator/run_ai_task_queue_once.py --pretty
```

Dry-run mode performs checks without writing queue state, creating branches,
pushing, opening PRs, merging, or archiving:

```bash
python3 scripts/orchestrator/run_ai_task_queue_once.py --dry-run --pretty
```

Dry-run only returns a preview and does not write a runtime plan, create a
branch, open a PR, merge, or archive. The runner does not call Codex
automatically. At `handoff_ready`, use the runtime plan and PR body paths
printed by the runner.

## Step 4: Run AI/Codex Work

Use the manual Codex launcher:

```bash
cd ~/stock-ai
bash scripts/orchestrator/start_codex_manual.sh
```

Codex should stay within the task allowed paths.

## Step 5: Validate the Branch

After implementation is complete:

```bash
python3 scripts/orchestrator/run_ai_dev_validation_bundle.py --base main --head HEAD --pretty
```

Outputs:

```text
~/.local/state/stock-ai-orchestrator/ai_dev_validation_bundle.json
~/.local/state/stock-ai-orchestrator/ai_dev_validation_bundle.md
```

## Step 6: Commit Branch Work

Only after validation passes:

```bash
git status
git diff --stat
git add <changed files>
git commit -m "AI dev: <task-id>"
```

## Step 7: Optional PR Creation

PR creation is explicit:

```bash
python3 scripts/orchestrator/run_ai_task_queue_once.py --create-pr --pretty
```

Without `--create-pr`, the runner must not push or create a PR. With the flag,
it only proceeds after validation passes and the working tree is clean.

The runner subprocess layer uses a fixed command allowlist for required Git,
GitHub CLI, and orchestrator script commands. It does not execute arbitrary
`validation_commands` strings from task definitions.

## Step 8: GitHub Actions Gate

The PR automatically runs:

```text
.github/workflows/ai_dev_validation.yml
```

It checks Python compile, forbidden file changes, forbidden production,
notification, and trading categories, allowed path scope, and changed file count.

## Step 9: Optional Conditional Auto Merge

Auto merge is disabled by default:

```bash
python3 scripts/orchestrator/run_ai_task_queue_once.py --create-pr --auto-merge --pretty
```

Even with `--auto-merge`, the runner merges only low-risk tasks whose local
validation, GitHub check, PR state, branch, base, and allowed-path gates all
pass. Production, notification, trading, scheduler, medium-risk, and high-risk
tasks are not eligible for auto merge.

## Step 10: Completed Archive

After a successful merge, the runner archives the task automatically. The
archive can also be run manually:

```bash
python3 scripts/orchestrator/archive_completed_ai_task.py \
  --task-id AI-DEV-001 \
  --pr-number 123 \
  --pr-url https://github.com/OWNER/REPO/pull/123 \
  --branch-name ai-dev/example \
  --base-branch main \
  --pretty
```

Completed tasks are removed from runtime pending queue and appended to runtime
completed queue.

## Step 11: VM Timer Pull

After merge to `main`, the VM timer pulls the update automatically. This runbook
does not create or modify timers.

Manual check:

```bash
cd ~/stock-ai
systemctl --user list-timers stock-ai-orchestrator-loop.timer
git log --oneline -5
```

## Completion Definition

A closed-loop task is complete only when:

- branch work is complete
- validation bundle passes
- PR is opened when required
- GitHub Actions pass
- review or conditional auto-merge gate approves
- PR is merged to `main`
- runtime completed archive is written
- VM timer pulls `main`
