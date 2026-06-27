# GitHub Issue Scheduled Auto-Pickup Activation Proposal

## Purpose

AI-DEV-060 prepares the real schedule activation proposal and preflight package
for GitHub Issue scheduled auto-pickup. It is the review package for AI-DEV-061,
which may enable the actual schedule only after explicit operator approval.

AI-DEV-060 does not enable a real schedule. It does not create or modify cron,
systemd timers, GitHub Actions schedules, daemons, polling workers, n8n
workflows, or background services.

## Proposed Activation Design

The first scheduled version should run a single `--once` command on a fixed
cadence. Each run should:

1. acquire a single-active-task lock
2. discover open GitHub Issues in read-only mode
3. filter by required labels
4. reject blocked labels and blocked task classes
5. produce a sanitized scheduled pickup report
6. write idempotency state for terminal outcomes
7. stop without mutating Issues

The first scheduled version should not comment on Issues, add or remove labels,
close/reopen Issues, create branches from Issue content, create PRs from Issue
content, merge PRs from Issue content, run runtime actions, or execute shell
commands from Issue body text.

## Cadence Proposal

Supported cadence options for AI-DEV-061 review:

- every 30 minutes
- every 15 minutes

Recommended first production cadence: every 30 minutes.

The 30-minute cadence is conservative enough for initial observation while still
supporting mobile task submission. A 15-minute cadence can be considered after
the scheduler has stable logs, lock behavior, and idempotency state.

## Expected Command For AI-DEV-061

AI-DEV-061 may wire a command equivalent to:

```bash
python3 scripts/orchestrator/github_issue_scheduled_pickup_dry_run.py \
  --input /home/kaochuchian/.local/state/stock-ai-orchestrator/github_issue_scheduled_pickup_request.json \
  --output /home/kaochuchian/.local/state/stock-ai-orchestrator/github_issue_scheduled_pickup_latest.json \
  --pretty \
  --once
```

If AI-DEV-061 adds live read, it must remain read-only and should use a
separately reviewed command and validator. AI-DEV-060 does not implement live
scheduling or live Issue discovery.

## Lock Policy

Use a single-active-task lock:

- proposed lock path:
  `/home/kaochuchian/.local/state/stock-ai-orchestrator/github_issue_scheduled_pickup.lock`
- acquire lock before discovery
- release lock after writing the sanitized report
- if lock exists and is fresh, skip the run
- if lock is stale, report `needs_manual_review` before replacement

No scheduled run should promote a new task while another AI-DEV task is active.

## Idempotency Storage

Use terminal idempotency keys that do not include Issue body text:

```text
scheduled-pickup-v1|issue_number|issue_url|task_class|normalized_required_labels
```

Proposed state path:

```text
/home/kaochuchian/.local/state/stock-ai-orchestrator/github_issue_scheduled_pickup_idempotency.json
```

The state file should store only non-secret metadata:

- idempotency key
- issue number
- issue URL
- decision
- task class
- observed labels
- timestamp
- report file path

## Max Issues Per Run

Recommended starting value: `1`.

The scheduler may discover more Issues, but first activation should only prepare
one candidate per run. This keeps review, logs, retries, and rollback simple.

## Labels

Required labels:

- `ai-dev`
- `gcp-pickup`
- `auto-run`
- `repo-only`

Recommended label:

- `dry-run`

Blocked labels:

- `manual-review`
- `blocked`
- `runtime`
- `production`
- `secret`
- `notification`
- `trading`
- `n8n`
- `dify`

## Task Classes

Allowed task classes:

- `docs_only`
- `template_only`
- `validator_only`
- `repo_side_contract`
- `test_or_validation_helper`

Blocked task classes:

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

## Read-Only Discovery Permission Model

The scheduled process should require only read access for Issues and repository
metadata. It must not need permission to write Issues, comments, labels,
branches, PRs, releases, Actions schedules, secrets, environments, packages, or
deployments.

The first scheduled version should not comment back to GitHub. Comment-back
requires a separate approval and a sanitizer that prevents echoing unsafe
instructions or sensitive values.

## Observability And Logs

Proposed log path:

```text
/home/kaochuchian/.local/state/stock-ai-orchestrator/logs/github_issue_scheduled_pickup.log
```

Proposed latest result path:

```text
/home/kaochuchian/.local/state/stock-ai-orchestrator/github_issue_scheduled_pickup_latest.json
```

Proposed archive directory:

```text
/home/kaochuchian/.local/state/stock-ai-orchestrator/archive/github_issue_scheduled_pickup/
```

Logs and result artifacts must be sanitized. They may include Issue number,
Issue URL, labels, task class, decision, idempotency key, and safety flags. They
must not include secrets, tokens, credentials, `.env`, private runtime payloads,
production config values, or raw unsafe command text.

## Dry-Run First Rollout

AI-DEV-061 should activate dry-run scheduled reporting first. It should not
execute repo edits or create PRs from Issue content. After several successful
dry-run cycles, a later task may propose controlled repo-only execution.

## Rollback And Disable Procedure

The disable procedure must be simple and reversible:

1. disable the scheduler entry
2. verify the scheduler is inactive
3. run the preflight helper with `scheduler_activation_requested=false`
4. preserve sanitized logs and state files for audit
5. report final status and `git status --short`

If a scheduled run behaves unexpectedly, the emergency stop is to disable the
scheduler entry and leave idempotency state untouched until reviewed.

## Operator Approval Checklist For AI-DEV-061

AI-DEV-061 must not proceed unless the operator explicitly approves:

- first cadence: `30m`
- max issues per run: `1`
- single-active-task lock path
- idempotency state path
- log path and archive path
- read-only Issue discovery permission
- no Issue mutation
- no comment-back
- no runtime action
- no production pipeline
- no cron/systemd/timer/GitHub Actions schedule mutation beyond the reviewed
  scheduler entry
- rollback and emergency stop procedure

## Risks And Mitigations

- duplicate pickup: use idempotency keys and terminal state
- overlapping runs: use a single-active-task lock
- unsafe Issue content: classify by labels and blocked text categories; never
  execute Issue body
- excessive intake: start with `max_issues_per_run=1`
- permission creep: use read-only discovery only
- noisy logs: write structured sanitized summaries
- accidental production action: keep runtime, notification, DB, n8n, trading,
  and production pipeline surfaces out of scope

## Preflight Validation

Run:

```bash
python3 -m py_compile scripts/orchestrator/github_issue_scheduled_activation_preflight.py scripts/orchestrator/validate_github_issue_scheduled_activation_preflight_result.py
python3 scripts/orchestrator/validate_github_issue_scheduled_activation_preflight_result.py --input templates/github_issue_scheduled_activation_preflight_result.example.json --pretty
python3 scripts/orchestrator/validate_github_issue_scheduled_activation_preflight_result.py --input templates/github_issue_scheduled_activation_preflight_rejected.example.json --pretty
python3 scripts/orchestrator/github_issue_scheduled_activation_preflight.py --input templates/github_issue_scheduled_activation_preflight_request.example.json --output /tmp/github_issue_scheduled_activation_preflight_result.example.json --pretty --once
python3 scripts/orchestrator/validate_github_issue_scheduled_activation_preflight_result.py --input /tmp/github_issue_scheduled_activation_preflight_result.example.json --pretty
python3 scripts/orchestrator/inspect_ai_platform_status.py --pretty
python3 scripts/orchestrator/validate_ai_branch.py --pretty
git diff --check main...HEAD
```
