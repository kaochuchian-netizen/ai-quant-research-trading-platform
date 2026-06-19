# AI Task Queue Runbook

## Purpose

The formal AI task queue promotes one reviewed pending task into runtime branch
and PR artifacts. It keeps the existing closed-loop scaffold intact: queue
promotion prepares files for review, while branch creation, implementation,
commit, push, PR creation, merge, production runs, LINE notifications, and
trading execution remain outside this script.

## Queue Files

Runtime queue:

```text
orchestrator/queue/pending_tasks.json
```

Completed-task archive:

```text
orchestrator/queue/completed_tasks.json
```

Both files must use:

```json
{
  "schema_version": 1,
  "status": "active"
}
```

## Pending Task Requirements

Each promotable task must have:

- `status` set to `pending`
- `risk_level` set to `low`
- `target_base_branch` set to `main`
- `branch_name` starting with `ai-dev/`
- `requires_pull_request` resolved to `true`
- direct main push, production commands, LINE notifications, and trading execution disabled
- blocked paths containing `.env`, `data/stock_analysis.db`, `data/backups/`, and `analysis/output/`
- allowed paths limited to `docs/`, `tests/`, `scripts/orchestrator/`, and `orchestrator/queue/`
- blocked keyword policy described by category only, without listing exact
  production, LINE, or broker helper call literals

## Promotion Command

Preview the next promotable task:

```bash
cd ~/stock-ai
python3 scripts/orchestrator/promote_next_ai_task.py --dry-run --pretty
```

Promote the highest-priority pending task:

```bash
cd ~/stock-ai
python3 scripts/orchestrator/promote_next_ai_task.py --pretty
```

Promote a specific task:

```bash
python3 scripts/orchestrator/promote_next_ai_task.py --task-id AI-DEV-001 --pretty
```

If a runtime branch plan already exists for a different task, the script refuses
to overwrite it. Use `--force` only after confirming the existing runtime plan is
stale and safe to replace.

## Runtime Artifacts

Successful non-dry-run promotion writes:

```text
~/.local/state/stock-ai-orchestrator/ai_task_branch_plan.json
~/.local/state/stock-ai-orchestrator/ai_task_pr_body.md
```

It also updates the selected task in `pending_tasks.json`:

- `status`: `promoted`
- `promoted_at`: UTC timestamp
- `runtime_plan_path`
- `runtime_pr_body_path`

The embedded task in `ai_task_branch_plan.json` uses the same promoted task
record written back to the pending queue. After a successful non-dry-run
promotion, both locations should show `status` as `promoted`.

The command output includes a status transition summary, such as `pending` to
`promoted`. This means the task was promoted into runtime artifacts only; it
does not mean a branch, pull request, or merge has been performed.

The queue write is atomic. Dry-run mode does not write queue files or runtime
artifacts.

## Task Selection

Promotion selects only tasks with `status == "pending"`.

Selection order:

1. Higher `priority` first.
2. Same priority keeps queue order.
3. `--task-id` restricts selection to one task.

## Safety Boundaries

The promotion layer does not:

- create branches
- edit implementation files
- commit
- push
- open PRs
- merge
- run `python3 main.py`
- send LINE notifications
- place orders
- run production pipelines
- modify systemd, cron, or timers
- read `.env`
- touch `data/stock_analysis.db`, `data/backups/`, or `analysis/output/`

The queue may describe blocked keyword categories such as LINE sending helpers,
broker order helpers, and production pipeline helpers. It must not list exact
callable literals because those are intentionally caught by the branch
validator when they appear in a diff.

After promotion, continue with the existing branch launcher and validation flow.
