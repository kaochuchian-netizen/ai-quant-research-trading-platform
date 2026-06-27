# GitHub Issue Auto-Execution Runner V1

## Purpose

AI-DEV-058 defines a manually invoked GitHub Issue auto-execution runner for
safe repo-only tasks. It extends the AI-DEV-057 mobile Issue pickup inbox by
adding a stricter auto-run contract, request/result templates, a dry-run runner,
and result validator.

This is not a daemon, webhook, scheduler, or background service. The runner is
invoked explicitly with `--once`.

## Supported Workflow

1. The user creates a GitHub Issue from mobile.
2. The user applies the required auto-run labels:

   ```text
   ai-dev
   gcp-pickup
   auto-run
   repo-only
   ```

3. The `dry-run` label is strongly recommended and is included in the examples.
4. A GCP resident operator may run the auto-runner manually with a sanitized
   fixture or a read-only `gh issue view` lookup.
5. The runner validates the Issue, classifies the task, and emits a sanitized
   result artifact.
6. Future tasks may wire the reviewed runner into scheduled pickup. AI-DEV-058
   does not do that.

## Required Labels

The v1 auto-runner requires all of:

- `ai-dev`
- `gcp-pickup`
- `auto-run`
- `repo-only`

Missing required labels produce `needs_manual_review` unless blocked action
terms are also detected.

## Allowed V1 Task Classes

V1 only accepts safe repo-side task classes:

- `docs_only`
- `template_only`
- `validator_only`
- `repo_side_contract`
- `test_or_validation_helper`

The issue body is task description only. It is never treated as a command.

## Blocked Task Classes

The runner rejects:

- `runtime_action`
- `production_pipeline`
- `secret_handling`
- `notification_send`
- `n8n_control`
- `Dify_runtime_call`
- `OpenAI_API_call`
- `trading_or_order`
- `production_DB_mutation`
- `cron_systemd_timer_change`
- `daemon_background_service`

Blocked task classes produce `rejected`.

## Runner Modes

Default mode is plan-only dry-run:

```bash
python3 scripts/orchestrator/github_issue_auto_runner.py \
  --input templates/github_issue_auto_runner_request.example.json \
  --output /tmp/github_issue_auto_runner_result.example.json \
  --pretty \
  --once
```

`--execute-repo-only` is still constrained. It only marks that the deterministic
repo-only plan was handled inside the sanitized result artifact. It does not
create branches, PRs, comments, labels, or background services.

The optional `--issue <number>` mode may read Issue metadata through `gh issue
view`. It must not mutate the Issue.

## GitHub Issue Mutation Policy

AI-DEV-058 must not:

- create Issues
- edit Issues
- add or remove labels
- comment on Issues
- close or reopen Issues
- post status back to GitHub

Comment-back is a future task with a separate safety review.

## Branch And PR Policy

This repo-side package is itself delivered through the normal branch, PR,
validation, and merge flow. The v1 runner does not create PRs from mobile Issue
content. A future version may add allowlisted deterministic repo edits after a
separate review.

## Safety Boundaries

The runner must not:

- read or print secrets, tokens, credentials, `.env`, or production config
  values
- call Dify runtime
- call OpenAI or ChatGPT APIs
- send LINE, Email, webhook, or notification output
- trade or place orders
- modify production databases
- start, stop, or modify n8n
- run production pipelines
- modify cron, systemd, timers, or background services
- execute shell commands from Issue text
- inspect private runtime payloads

## Result Artifact

The result includes:

- issue identity and labels
- eligibility and decision
- task class
- required label status
- blocked terms
- dry-run and execute flags
- GitHub/runtime mutation flags
- branch and PR fields
- validation summaries
- sanitized summary
- next-step recommendation
- safety confirmation

## Validation

Run:

```bash
python3 -m py_compile scripts/orchestrator/github_issue_auto_runner.py scripts/orchestrator/validate_github_issue_auto_runner_result.py
python3 scripts/orchestrator/github_issue_auto_runner.py --input templates/github_issue_auto_runner_request.example.json --output /tmp/github_issue_auto_runner_result.example.json --pretty --once
python3 scripts/orchestrator/validate_github_issue_auto_runner_result.py --input templates/github_issue_auto_runner_result.example.json --pretty
python3 scripts/orchestrator/validate_github_issue_auto_runner_result.py --input templates/github_issue_auto_runner_rejected.example.json --pretty
python3 scripts/orchestrator/validate_github_issue_auto_runner_result.py --input /tmp/github_issue_auto_runner_result.example.json --pretty
python3 scripts/orchestrator/inspect_ai_platform_status.py --pretty
python3 scripts/orchestrator/validate_ai_branch.py --pretty
git diff --check main...HEAD
```
