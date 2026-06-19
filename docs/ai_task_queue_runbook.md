# AI Task Queue Runbook

## Purpose

The AI task queue promotes one low-risk runtime task into branch and PR
artifacts, then supports a one-shot reviewed path through validation, optional
PR creation, optional conditional auto merge, and completed-task archiving.

This is not a daemon. It does not add cron, systemd, timers, or background
workers.

## Queue Files

Repository queue files are seeds, examples, and schema references only:

```text
orchestrator/queue/pending_tasks.json
orchestrator/queue/completed_tasks.json
```

Formal runtime queue files live outside git:

```text
~/.local/state/stock-ai-orchestrator/pending_tasks.json
~/.local/state/stock-ai-orchestrator/completed_tasks.json
```

Runtime queue status transitions do not dirty `main` because the runtime files
are not git-tracked.

## Initialize Runtime Queue

Initialize runtime queue files from the repository seed files:

```bash
cd ~/stock-ai
python3 scripts/orchestrator/init_ai_runtime_queue.py --pretty
```

The initializer creates the runtime directory and only writes missing runtime
queue files. It does not overwrite existing runtime state unless `--force` is
provided:

```bash
python3 scripts/orchestrator/init_ai_runtime_queue.py --force --pretty
```

## Add Runtime Tasks

Add real pending tasks to:

```text
~/.local/state/stock-ai-orchestrator/pending_tasks.json
```

Do not add real tasks to the repository seed queue. The repository queue remains
a schema/reference fixture.

Each promotable task must have:

- `status` set to `pending`
- `risk_level` set to `low`
- `target_base_branch` set to `main`
- `branch_name` starting with `ai-dev/`
- `requires_pull_request` resolved to `true`
- direct main push, production commands, LINE notifications, and trading execution disabled
- blocked paths containing `.env`, `data/stock_analysis.db`, `data/backups/`, and `analysis/output/`
- allowed paths limited to reviewed low-risk paths

## Promote Runtime Task

Preview the next promotable runtime task:

```bash
cd ~/stock-ai
python3 scripts/orchestrator/promote_next_ai_task.py --dry-run --pretty
```

Promote the highest-priority pending runtime task:

```bash
python3 scripts/orchestrator/promote_next_ai_task.py --pretty
```

Promote a specific task:

```bash
python3 scripts/orchestrator/promote_next_ai_task.py --task-id AI-DEV-001 --pretty
```

If runtime queue files are missing, initialize them first:

```bash
python3 scripts/orchestrator/init_ai_runtime_queue.py --pretty
```

Promotion writes:

```text
~/.local/state/stock-ai-orchestrator/ai_task_branch_plan.json
~/.local/state/stock-ai-orchestrator/ai_task_pr_body.md
```

It updates the selected task in the runtime pending queue:

- `status`: `promoted`
- `promoted_at`: UTC timestamp
- `runtime_plan_path`
- `runtime_pr_body_path`

The promotion script keeps the clean working tree guard. It writes runtime
queue state, not repository seed queue state. If an override points at the repo
seed queue, the output warns that the path is seed/example/reference only.

## One-Shot Runner

Run one queue iteration without opening a PR:

```bash
python3 scripts/orchestrator/run_ai_task_queue_once.py --pretty
```

The runner can promote one task, prepare the `ai-dev/*` branch, and stop at
`handoff_ready` when no implementation changes exist. It does not call Codex or
any AI CLI to modify files.

Dry-run mode does not write queue state, create branches, push, create PRs,
merge, or archive:

```bash
python3 scripts/orchestrator/run_ai_task_queue_once.py --dry-run --pretty
```

In dry-run mode, the runner only returns a preview such as
`handoff_ready_preview`; it does not write a runtime plan, create a branch,
open a PR, merge, or archive.

## PR Creation

PR creation is opt-in:

```bash
python3 scripts/orchestrator/run_ai_task_queue_once.py --create-pr --pretty
```

The runner only pushes and creates a PR after local validation passes and the
working tree is clean. Without `--create-pr`, it must not push or create a PR.

## Conditional Auto Merge

Auto merge is disabled by default. It requires both `--create-pr` and
`--auto-merge`, or an existing matching PR plus `--auto-merge`:

```bash
python3 scripts/orchestrator/run_ai_task_queue_once.py --create-pr --auto-merge --pretty
```

Auto merge is allowed only when all gates pass:

- task allows auto merge
- task risk is low
- base branch is `main`
- branch starts with `ai-dev/`
- local validation bundle passes
- forbidden-change and AI branch validators pass
- changed files stay inside task allowed paths
- PR is open and clean
- required GitHub check `validate-ai-branch` succeeds
- working tree is clean

The merge mode is fixed to merge commits. Squash and rebase auto merge are not
used by this runner.

## Completed Archive

After a successful merge, archive the task:

```bash
python3 scripts/orchestrator/archive_completed_ai_task.py \
  --task-id AI-DEV-001 \
  --pr-number 123 \
  --pr-url https://github.com/OWNER/REPO/pull/123 \
  --branch-name ai-dev/example \
  --base-branch main \
  --pretty
```

The archive script removes the task from runtime pending queue and appends a
completed record to runtime completed queue. It refuses duplicate `task_id` or
`pr_number` by default and supports `--dry-run`.

## Safety Boundaries

These tools must not:

- push directly to `main`
- modify GitHub rulesets
- relax validators or GitHub Actions
- execute arbitrary shell commands supplied by a task
- run `python3 main.py`
- send LINE notifications
- place orders
- run production pipelines
- modify `.env` or secret files
- modify `data/stock_analysis.db`
- modify `data/backups/`
- modify `analysis/output/`
- modify cron, systemd, or timer settings

Production, notification, trading, and scheduler tasks are not eligible for
auto merge.

The queue runner subprocess layer uses a fixed command allowlist for the small
set of Git, GitHub CLI, and orchestrator script commands it needs. It does not
execute arbitrary `validation_commands` strings from task definitions.
