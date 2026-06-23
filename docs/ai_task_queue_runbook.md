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

## Low-Intervention Approval Boundary

The AI Dev queue is operated as a low-intervention closed loop for low-risk
tasks. Codex should not repeatedly ask whether to continue ordinary queue work
when the task remains inside its safety envelope.

Ask the user before only these three action categories:

- real trading execution, order placement, position closing, or enabling trading
  automation
- sending LINE, email, or any other external notification
- modifying credentials, passwords, API keys, tokens, `.env`, or secret files

Outside those categories, continue the normal AI Dev flow to completion:

- inspect runtime queue and repository state
- run dry-run previews
- promote the task and prepare handoff artifacts
- create or switch to the `ai-dev/*` task branch
- implement only within task `allowed_paths`
- run the validation bundle
- commit branch work and create the PR
- check GitHub Actions
- merge when required checks pass and `mergeStateStatus` is clean or an
  equivalent clean state
- archive the completed task with merged PR metadata
- clean up local and remote task branches
- sync local `main`
- confirm final repository and runtime queue status

This boundary does not override hard safety gates. Do not expand
`allowed_paths`, bypass validators, run `python3 main.py`, run production
pipelines, send notifications, trade, modify scheduler configuration, change
secrets, or push directly to `main`.

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

## Runner Status Report

Read the top-level JSON fields before taking the next action:

- `ok`: whether the current runner step completed its own checks.
- `state`: the current workflow state; this is the primary operator signal.
- `reasons`: blocking reasons or explicit skip reasons for this step.
- `side_effects`: the action ledger. Confirm unwanted actions remain `false`.
- `current_branch`: the branch observed before or during the runner step.
- `git_status_short`: must be empty before promotion and PR creation.
- `validation`: local validation bundle result when branch work exists.
- `pr`: GitHub PR metadata when an existing or newly created PR is found.
- `preview`: dry-run intent, including whether promotion or branch preparation
  would happen.

Common `state` values:

- `handoff_ready_preview`: dry-run found a promotable task and would prepare a
  branch, but stopped before writing runtime state or touching Git.
- `handoff_ready`: a task branch is ready and implementation is still manual.
- `validation_passed`: branch work passed local validation; PR creation may
  still require `--create-pr`.
- `validation_failed`: local validation failed; inspect `blocked_reasons`.
- `pr_ready_blocked_dirty`: validation passed but the working tree is not clean.
- `pr_created`: the runner pushed the task branch and opened the PR.
- `auto_merge_skipped`: PR exists or was created, but merge was intentionally
  skipped because `--auto-merge` was not provided.
- `auto_merge_blocked`: auto-merge was requested but safety gates failed.
- `archived`: the runner merged and archived after all auto-merge gates passed.

For low-risk supervised work, `auto_merge_skipped` is normally the expected
terminal runner state after PR creation. Human review, GitHub Actions, merge,
archive, and branch cleanup remain separate steps unless an explicit policy
enables conditional auto-merge.

## Failure Cases

Use this table to interpret blocked states without weakening safety gates.

| Symptom | Meaning | Safe next action |
| --- | --- | --- |
| `blocked_preflight` with missing queue files | Runtime queue has not been initialized. | Run `python3 scripts/orchestrator/init_ai_runtime_queue.py --pretty`. |
| `blocked_preflight` with dirty Git status | Promotion started with local source changes. | Review or commit/stash the unrelated work before retrying. |
| `runtime plan already exists for different task_id` | A previous handoff plan remains active. | Confirm the old task is completed, then move `ai_task_branch_plan.json` and `ai_task_pr_body.md` into `stale_handoff/<task-id>/`. |
| `no pending task found` | There is no pending runtime task matching the request. | Add a valid low-risk task to runtime `pending_tasks.json`. |
| `validation_failed` | Local validators found forbidden paths, forbidden keywords, wrong branch, or invalid scope. | Fix the branch changes; do not push or create a PR until validation passes. |
| `no changed files found for PR` | The branch has no committed diff against `main`; untracked files do not count. | Commit allowed-path work, then rerun the validation bundle. |
| `pr_ready_blocked_dirty` | Validation passed but there are uncommitted files. | Commit or remove the worktree changes, then rerun with `--create-pr`. |
| `failed to push branch or create PR` | GitHub CLI push or PR creation failed. | Check auth/network/duplicate PR state; do not retry with broader permissions. |
| `auto_merge_blocked` | One or more merge safety gates failed. | Inspect `reasons`, wait for checks or request manual review; do not bypass gates. |

After any failure, rerun the read-only inspector:

```bash
python3 scripts/orchestrator/inspect_ai_runtime_queue.py --pretty
```

The inspector should show the expected pending/completed queue state, active
handoff task, current branch, and clean/dirty worktree state before continuing.

## Platform Status Inspector

Use the platform status inspector for the standard queue and repository status
checkpoint around closed-loop work:

```bash
python3 scripts/orchestrator/inspect_ai_platform_status.py
python3 scripts/orchestrator/inspect_ai_platform_status.py --pretty
```

Run it:

- before starting a queue task, before dry-run or promotion, to confirm branch,
  working tree, runtime queue, and active handoff state
- after PR merge, completed-task archive, branch cleanup, and `main` sync, to
  confirm the queue and repository returned to the expected state
- whenever pending/promoted queue entries, completed archive records, active
  handoff files, local branches, or `main` / `origin/main` sync state appear
  inconsistent

This tool is read-only. It does not modify the repository, runtime queue, data,
`.env`, credentials, API keys, tokens, secrets, or Git state. It does not run
`python3 main.py`, execute production pipelines, send LINE/email/external
notifications, trade, place orders, or modify cron, systemd, or timer settings.

Read the output as a platform-level status snapshot:

- `git.current_branch`, `git.clean`, and `git.status_short` identify the active
  branch and whether local repo files are dirty.
- `git.main_origin_main_sync` compares local `main` with local `origin/main`
  refs and reports `in_sync`, `local_ahead`, `local_behind`, `diverged`, or
  `missing_ref`. The inspector does not fetch or pull.
- `runtime.pending_queue.count`, `pending_count`, `promoted_count`, and
  `task_ids` show queue size, pending/promoted split, and task ids.
- `runtime.completed_queue.count` and `task_ids` show completed archive size
  and completed task ids.
- `runtime.active_handoff_or_branch_plan` reports whether active branch plan,
  PR body, or current Codex handoff files exist.
- `runtime.handoff_diagnostics.classification` reports whether active handoff
  artifacts are absent, present, or suspected stale/example material.
- `runtime.handoff_diagnostics.example_indicators` flags active handoff JSON
  metadata that still looks like an example task or handoff.
- `runtime.handoff_diagnostics.stale_indicators` flags active handoff metadata
  that points at a task already recorded as merged in the completed queue.
- `runtime.handoff_diagnostics.stale_handoff_dir` and `archive_dir` summarize
  existing stale/archive artifact locations without moving or deleting files.
- `repo_files.key_orchestrator_scripts` confirms the expected queue and
  validation helpers are present.
- `repo_files.pipeline_entrypoints` and `pipeline_entrypoint_check` confirm
  production entrypoints exist and were not executed by inspection.
- `safety_boundary_reminder` and `side_effects` should confirm no repo,
  runtime queue, data, secret, notification, trading, scheduler, branch, commit,
  push, PR, merge, or production side effect occurred.

Use this command as the normal closed-loop pre-task and post-task status check.

If `runtime.handoff_diagnostics.classification` is
`stale_or_example_suspected`, treat it as an operator review signal only. The
inspector does not repair state. Confirm the task id against
`runtime.completed_queue.merged_task_ids`, inspect the active handoff files, and
only then move confirmed stale artifacts into
`~/.local/state/stock-ai-orchestrator/stale_handoff/<task-id>/`.

## First Real Runtime Queue Task Flow

Use this sequence for the first real low-risk runtime queue task after the
runtime queue is available:

1. Initialize the runtime queue from repository seed files:

   ```bash
   cd ~/stock-ai
   python3 scripts/orchestrator/init_ai_runtime_queue.py --pretty
   ```

2. Add one low-risk task to the runtime pending queue:

   ```text
   ~/.local/state/stock-ai-orchestrator/pending_tasks.json
   ```

   Keep the task constrained to reviewed low-risk paths, require a PR, use an
   `ai-dev/*` branch, and keep production commands, LINE notifications, trading
   execution, direct main push, and auto merge disabled unless explicitly
   reviewed.

3. Preview the task with the dry-run runner:

   ```bash
   python3 scripts/orchestrator/run_ai_task_queue_once.py --dry-run --pretty
   ```

   The expected dry-run result is `handoff_ready_preview`. It must not write
   runtime queue state, create a branch, push, open a PR, merge, or archive.

4. Run the non-dry-run runner without PR creation:

   ```bash
   python3 scripts/orchestrator/run_ai_task_queue_once.py --pretty
   ```

   The runner promotes the task, writes the runtime plan and PR body artifacts,
   prepares the `ai-dev/*` branch, and stops at `handoff_ready` for manual
   implementation. It must not push or open a PR without `--create-pr`.

5. Implement the task manually with Codex or another reviewed manual workflow,
   using the runtime plan and PR body:

   ```text
   ~/.local/state/stock-ai-orchestrator/ai_task_branch_plan.json
   ~/.local/state/stock-ai-orchestrator/ai_task_pr_body.md
   ```

   Keep all changes inside the task `allowed_paths`.

6. Run the validation bundle on the branch:

   ```bash
   python3 scripts/orchestrator/run_ai_dev_validation_bundle.py --base main --head HEAD --pretty
   ```

   Commit only after the validation bundle passes and the diff matches the task
   scope.

7. Create the PR only after local validation passes and the branch work is
   committed:

   ```bash
   python3 scripts/orchestrator/run_ai_task_queue_once.py --create-pr --pretty
   ```

8. Let GitHub Actions run the required gate, including `validate-ai-branch`.
   Do not merge while required checks are pending or failing.

9. Merge after required checks pass and the PR is clean. Conditional auto merge
   is optional and remains gated by the task policy, local validation, PR state,
   GitHub check status, allowed paths, and a clean working tree.

10. After a successful merge, archive the task into the runtime completed queue.
    The runner can archive automatically after merge, or the archive command can
    be run manually with the merged PR metadata.

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

## Post-Merge Closeout

After the PR merges and before treating the task as fully closed, run the
standard post-merge status check:

```bash
cd ~/stock-ai
git checkout main
git pull --ff-only
python3 scripts/orchestrator/inspect_ai_platform_status.py --pretty
python3 scripts/orchestrator/validate_post_merge_status.py --pretty
```

Use the simulation flag only for feature-branch format checks:

```bash
python3 scripts/orchestrator/validate_post_merge_status.py --pretty --simulate-post-merge-success
```

Record these closeout fields in the completion report or checklist when the
task is archived:

- `post_merge_validator` pass/fail
- `inspector_ok` true/false
- `main_in_sync` true/false
- `git_status_clean` true/false

The validator is read-only and is part of the standard operator closeout
workflow. It does not replace PR branch validation, and it does not authorize
production commands, notifications, trading, or scheduler changes.

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
