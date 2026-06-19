# AI Development Closed Loop Runbook

## Purpose

This runbook describes the safe PR-based closed loop for AI-assisted development.

The loop is designed to accelerate stock-analysis and prediction improvements while protecting production behavior.

## Closed Loop Flow

```text
pending task
→ branch plan
→ branch launch
→ AI/Codex implementation on branch
→ validation bundle
→ PR summary
→ push branch
→ open PR
→ GitHub Actions validation
→ review gate
→ merge to main
→ VM timer pull
```

## Hard Safety Boundaries

Do not allow AI automation to:

- push directly to `main`
- merge PRs automatically
- send LINE messages
- place orders
- run trading execution
- run production pipelines
- modify `.env` or secret files
- modify `data/stock_analysis.db`
- modify `data/backups/`
- modify `analysis/output/`
- modify cron, systemd, or timer settings without an explicit reviewed task

## Step 1: Promote a Queue Task

Use the formal queue promotion layer to prepare runtime branch and PR artifacts
from `orchestrator/queue/pending_tasks.json`.

Preview the next task without writing files:

```bash
cd ~/stock-ai
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

The promotion step does not create branches, modify implementation files,
commit, push, open PRs, merge, run production workflows, send LINE messages, or
place orders. See `docs/ai_task_queue_runbook.md` for queue schema and safety
rules.

## Legacy Task Plan Helper

The original helper remains available for scaffold testing and example queues:

```bash
cd ~/stock-ai
python3 scripts/orchestrator/prepare_ai_task_branch.py --pretty
```

Outputs:

```text
~/.local/state/stock-ai-orchestrator/ai_task_branch_plan.json
~/.local/state/stock-ai-orchestrator/ai_task_pr_body.md
```

## Step 2: Launch the Task Branch

```bash
cd ~/stock-ai
bash scripts/orchestrator/launch_ai_task_branch.sh
```

The launcher requires typing:

```text
BRANCH
```

This creates or switches to the task branch. It does not modify code, commit, push, or merge.

## Step 3: Run AI/Codex Work

Use the manual Codex launcher:

```bash
cd ~/stock-ai
bash scripts/orchestrator/start_codex_manual.sh
```

Codex should stay within the task allowed paths.

The manual launcher can run from `main` or an `ai-dev/*` task branch. It still
requires a clean git working tree and the same handoff, blocked path, and safety
checks. Autostart preflight remains restricted to `main`.

### Low-Risk Dry-Run Task Guardrails

For a documentation-only or validation-only dry run, keep the change set small
and confirm it matches the generated task plan before editing.

Recommended dry-run scope:

- `docs/`
- `tests/`
- `scripts/orchestrator/`
- `orchestrator/queue/`

Avoid runtime behavior changes during dry runs. Do not run the application entry
point or any side-effecting command listed in the hard safety boundaries.

Before moving to PR preparation, run:

```bash
git status --short
python3 scripts/orchestrator/validate_ai_branch.py --base main --head HEAD --pretty
python3 scripts/orchestrator/check_forbidden_changes.py --base main --head HEAD --pretty
git diff --stat
```

## Step 4: Validate the Branch

After AI/Codex changes are complete:

```bash
cd ~/stock-ai
python3 scripts/orchestrator/run_ai_dev_validation_bundle.py --base main --head HEAD --pretty
```

Outputs:

```text
~/.local/state/stock-ai-orchestrator/ai_dev_validation_bundle.json
~/.local/state/stock-ai-orchestrator/ai_dev_validation_bundle.md
```

## Step 5: Prepare PR Summary

```bash
cd ~/stock-ai
python3 scripts/orchestrator/prepare_ai_pr_summary.py --pretty
```

Outputs:

```text
~/.local/state/stock-ai-orchestrator/ai_task_pr_summary.md
~/.local/state/stock-ai-orchestrator/ai_task_pr_commands.sh
```

## Step 6: Commit and Push Branch

Only after validation passes:

```bash
git status
git diff --stat
git add <changed files>
git commit -m "AI dev: <task-id>"
git push -u origin <branch-name>
```

## Step 7: Open Pull Request

Use the generated PR body:

```bash
gh pr create --base main --head <branch-name> --title "AI Dev: <task-id>" --body-file ~/.local/state/stock-ai-orchestrator/ai_task_pr_body.md
```

## Step 8: GitHub Actions Gate

The PR automatically runs:

```text
.github/workflows/ai_dev_validation.yml
```

It checks:

- Python compile for orchestrator scripts
- forbidden file changes
- forbidden production, LINE, and trading keywords
- allowed path scope
- changed file count limit

## Step 9: Review Gate

Only merge after:

- GitHub Actions pass
- PR diff is reviewed
- validation report is clean
- no production side effects are present

## Step 10: VM Timer Pull

After merge to `main`, the VM timer pulls the update automatically.

Manual check:

```bash
cd ~/stock-ai
systemctl --user list-timers stock-ai-orchestrator-loop.timer
git log --oneline -5
```

## Useful One-Command Sequence

```bash
cd ~/stock-ai
python3 scripts/orchestrator/prepare_ai_task_branch.py --pretty
bash scripts/orchestrator/launch_ai_task_branch.sh
# run Codex/manual implementation
python3 scripts/orchestrator/run_ai_dev_validation_bundle.py --base main --head HEAD --pretty
python3 scripts/orchestrator/prepare_ai_pr_summary.py --pretty
```

## Completion Definition

A closed-loop task is complete only when:

- branch work is complete
- validation bundle passes
- PR is opened
- GitHub Actions pass
- review gate approves
- PR is merged to `main`
- VM timer pulls `main`

## Current Status

This runbook implements a safe scaffold. It does not yet include autonomous PR creation or autonomous merge. Those should only be added after the validation gates have proven reliable.
