# AI Development Closed Loop

## Goal

Build a high-automation development loop for improving the stock analysis and prediction platform while protecting production systems.

The target pattern is:

```text
task queue
→ branch
→ AI-assisted implementation
→ validation
→ pull request
→ review gate
→ merge to main
→ VM timer pull
→ next iteration
```

## Safety Principle

Full automation should produce reviewable branches and pull requests. It should not directly modify `main` or run production workflows.

## Current Scaffold

The repository now contains:

```text
orchestrator/queue/pending_tasks.example.json
scripts/orchestrator/check_forbidden_changes.py
scripts/orchestrator/validate_ai_branch.py
.github/workflows/ai_dev_validation.yml
```

## AI Task Queue

Use the pending task example as the schema for AI development tasks.

Each task should define:

- task ID
- objective
- base branch
- working branch
- allowed paths
- blocked paths
- validation commands
- success criteria
- risk level

## Branch Rules

AI development should use branches such as:

```text
ai-dev/<task-id>
codex/<task-id>
```

The workflow should not allow direct `main` edits for AI-generated development.

## Validation Gates

The validation workflow runs on pull requests to `main`.

It checks:

- orchestrator scripts compile
- blocked paths are not changed
- blocked production, LINE, or trading keywords are not introduced
- changed files remain within allowed AI development paths
- changed file count stays below the configured limit

## Blocked Paths

The default blocked paths are:

```text
.env
data/stock_analysis.db
data/backups/
analysis/output/
```

## Blocked Behaviors

The closed loop must not automatically:

- send LINE messages
- place orders
- trigger trading execution
- run production pipelines
- modify scheduler or timer settings
- modify production database files
- read or write secret files
- merge to `main`

## Allowed Low-Risk Work Areas

Initial AI development should focus on:

```text
docs/
tests/
scripts/orchestrator/
orchestrator/queue/
orchestrator/templates/
```

Additional paths can be allowed later after the validation gates are proven stable.

## Next Phase

After this scaffold is stable, the next development step is to add a task runner that can prepare branches and PR descriptions while still leaving merge control to a review gate.
