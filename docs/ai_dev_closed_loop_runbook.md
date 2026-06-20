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

## Low-Intervention Approval Boundary

This project uses a low-intervention AI Dev closed loop. Codex should continue
ordinary low-risk AI Dev work to the final repo and runtime status without
repeatedly asking whether to continue.

User approval is required only before these action categories:

- real trading execution, order placement, position closing, or enabling trading
  automation
- sending LINE, email, or other external notifications
- modifying credentials, passwords, API keys, tokens, `.env`, or secret files

All other ordinary AI Dev steps should proceed under the existing safety gates,
including runtime queue inspection, dry-run, promotion and handoff, task branch
creation, implementation within `allowed_paths`, validation bundle, PR creation,
GitHub Actions checks, merge when required checks pass and the PR is clean,
completed-task archive, branch cleanup, syncing `main`, and final repo/runtime
status confirmation.

This boundary does not permit expanding a task's `allowed_paths`, bypassing
validators, running production commands, sending notifications, trading, changing
scheduler configuration, or pushing directly to `main`.

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

## Runtime Queue Inspector

Inspect runtime queue state without changing runtime files, repository files, or
Git state:

```bash
python3 scripts/orchestrator/inspect_ai_runtime_queue.py --pretty
```

The inspector reports pending tasks, completed tasks, the active handoff plan,
the latest validation bundle summary, current branch, and working tree status.
It is read-only and must not create branches, write runtime artifacts, commit,
push, open PRs, merge, archive, run production commands, send notifications,
trade, or modify scheduler settings.

## Platform Status Inspector

Use the read-only platform status inspector as the standard status check before
and after each closed-loop task:

```bash
python3 scripts/orchestrator/inspect_ai_platform_status.py
python3 scripts/orchestrator/inspect_ai_platform_status.py --pretty
```

Run it:

- before starting a task, before dry-run or promotion, to confirm the repo and
  runtime queue are in the expected state
- after PR merge, completed-task archive, branch cleanup, and `main` sync, to
  confirm the final platform state
- whenever runtime queue state, active handoff files, local branches, or
  `main` / `origin/main` sync status look inconsistent

The inspector is read-only. It does not modify repository files, runtime queue
files, data files, `.env`, credentials, secrets, or Git state. It does not run
`python3 main.py`, execute the production pipeline, send LINE/email/external
notifications, place trades, submit orders, or change cron, systemd, or timer
configuration.

Interpret the output as an operator status snapshot:

- `git.current_branch`, `git.clean`, and `git.status_short` show the current
  branch and whether local files are dirty.
- `git.main_origin_main_sync` compares local `main` with local `origin/main`
  refs and reports whether `main` is in sync, ahead, behind, diverged, or
  missing a ref. The inspector does not fetch or pull.
- `runtime.pending_queue.count`, `pending_count`, `promoted_count`, and
  `task_ids` show pending queue size and active task ids.
- `runtime.completed_queue.count` and `task_ids` show archived completed task
  ids.
- `runtime.active_handoff_or_branch_plan` shows whether branch plan, PR body,
  or current Codex handoff files exist.
- `runtime.handoff_diagnostics.classification` shows whether active handoff
  artifacts are absent, present, or suspected stale/example material.
- `runtime.handoff_diagnostics.example_indicators` flags active handoff JSON
  metadata that still looks like an example task or handoff.
- `runtime.handoff_diagnostics.stale_indicators` flags active handoff metadata
  that points at a task already recorded as merged in the completed queue.
- `runtime.handoff_diagnostics.stale_handoff_dir` and `archive_dir` summarize
  stale/archive artifact locations without moving or deleting files.
- `repo_files.key_orchestrator_scripts` confirms expected orchestrator helper
  scripts are present.
- `repo_files.pipeline_entrypoints` and `pipeline_entrypoint_check` confirm
  production entrypoints exist while also recording that they were not run.
- `safety_boundary_reminder` and `side_effects` should confirm the inspection
  stayed inside the read-only safety boundary.

Treat this command as the normal pre-task and post-task closed-loop checkpoint.

If `runtime.handoff_diagnostics.classification` is
`stale_or_example_suspected`, stop before promoting another task and review the
active handoff files. The inspector is intentionally read-only; it only reports
the stale/example indicators and never moves artifacts into `stale_handoff/` by
itself.

## Supervised Closed-Loop Runner

Use the supervised runner to reduce manual status checks while preserving the
existing safety gates:

```bash
python3 scripts/orchestrator/run_ai_dev_closed_loop_once.py --dry-run --pretty
```

Dry-run mode only inspects state and prints the next action. It does not run the
validation bundle because that bundle writes runtime reports. It also does not
promote, create branches, push, create PRs, merge, archive, run production
commands, send notifications, trade, or modify scheduler settings.

After branch work is committed and local validation is expected to pass, PR
creation remains explicit:

```bash
python3 scripts/orchestrator/run_ai_dev_closed_loop_once.py --create-pr --pretty
```

The supervised runner composes the read-only inspector, local validation bundle,
and existing PR-capable one-shot queue runner. It never passes `--auto-merge`
and never calls the archive helper by itself. Under the low-intervention
approval boundary, Codex may perform the remaining ordinary steps outside this
runner after confirming the PR checks pass and the PR is clean.

The preserved boundary is:

```text
branch implementation
→ local validation
→ explicit PR creation
→ GitHub Actions and review
→ clean merge when checks pass
→ completed archive
```

## Status And Failure Handling

The supervised runner is a status reporter first. Treat `state`, `next_action`,
`reasons`, and `side_effects` as the operator handoff:

- `state` tells where the loop stopped.
- `next_action` names the next human-safe action.
- `reasons` explains blockers or intentional skips.
- `side_effects` confirms whether runtime state, Git, push, PR, merge, archive,
  production, notification, trading, or scheduler actions happened.

Expected supervised states:

- `dry_run_preview`: read-only preview; no validation report, branch, push, PR,
  merge, or archive side effects.
- `handoff_ready`: branch exists but implementation is still needed.
- `branch_work_uncommitted`: source changes exist but are not committed; commit
  before PR creation.
- `validation_failed`: local validation failed; fix the branch before pushing.
- `validation_passed_dirty`: validation passed but the working tree is dirty.
- `validation_passed`: branch work is valid and can move to explicit PR
  creation.
- `auto_merge_skipped`: PR was found or created and merge remains manual.

Common recovery rules:

1. If stale handoff files point at a completed task, move them into
   `~/.local/state/stock-ai-orchestrator/stale_handoff/<task-id>/` after
   confirming the task is present in completed queue with `merged: true`.
2. If the validation bundle reports `no changed files found for PR`, check
   whether files are still untracked or uncommitted. Commit allowed-path work
   and rerun validation.
3. If PR creation is skipped, confirm `--create-pr` was intentional and the
   working tree is clean.
4. If GitHub Actions are pending or failing, wait or fix the branch. Merge only
   after required checks pass and the PR is clean.
5. Archive after a successful merge and only with the merged PR metadata.

Never resolve a failure by expanding task `allowed_paths`, disabling validators,
running production commands, sending notifications, placing orders, changing
scheduler configuration, or pushing directly to `main`.

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
