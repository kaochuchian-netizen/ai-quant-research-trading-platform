# GitHub Issue Scheduled Auto-Pickup Contract

## Purpose

AI-DEV-059 defines a dry-run scheduler contract for future scheduled GitHub
Issue auto-pickup. It builds on the AI-DEV-057 mobile Issue pickup inbox and the
AI-DEV-058 manual auto-runner by proving that a future scheduler can discover
eligible Issues, classify them, produce sanitized candidate reports, and avoid
duplicate execution.

This task does not enable a real schedule. It does not create a daemon, cron
job, systemd timer, GitHub Actions schedule, n8n workflow, polling worker, or
background service.

## Future Mobile Workflow

1. The user creates a GitHub Issue from GitHub mobile app or mobile web.
2. The user applies the required labels:

   ```text
   ai-dev
   gcp-pickup
   auto-run
   repo-only
   ```

3. The `dry-run` label is strongly recommended for all v1 scheduled pickup
   candidates.
4. The Issue body describes the requested repo-side task. It is never treated
   as shell commands.
5. A future scheduled runner may discover the Issue and emit a sanitized pickup
   report.
6. A later reviewed task may decide whether and how sanitized results are
   commented back to GitHub.

## Scheduler Disabled In AI-DEV-059

The scheduler is intentionally disabled in this task because scheduled pickup
changes the operational risk profile. A real schedule would need separate
approval for cadence, locking, observability, rate limits, GitHub permissions,
failure handling, and rollback.

AI-DEV-059 is contract/spec/template/validator/dry-run helper work only.

## Fixture-Only V1

The dry-run helper reads a sanitized fixture JSON file containing Issue-like
objects. It does not read live GitHub Issues, does not call GitHub APIs, and
does not mutate GitHub state.

Live read can be considered later only if it remains read-only and writes a
sanitized report without comments, labels, close/reopen operations, branch
creation, PR creation, or merges.

## Required Labels

An Issue can become a scheduled pickup candidate only when all required labels
are present:

- `ai-dev`
- `gcp-pickup`
- `auto-run`
- `repo-only`

Recommended:

- `dry-run`

## Exclusion Labels

The scheduler rejects or excludes Issues labeled with:

- `manual-review`
- `blocked`
- `runtime`
- `production`
- `secret`
- `notification`
- `trading`
- `n8n`
- `dify`

These labels prevent accidental scheduled pickup even if required labels are
also present.

## Allowed Task Classes

Scheduled candidate discovery allows only:

- `docs_only`
- `template_only`
- `validator_only`
- `repo_side_contract`
- `test_or_validation_helper`

Ambiguous Issues are marked `needs_manual_review`.

## Blocked Task Classes

The scheduler rejects task classes involving:

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

## Idempotency Strategy

Each candidate receives an idempotency key:

```text
scheduled-pickup-v1|issue_number|issue_url|task_class|normalized_required_labels
```

The key excludes Issue body text so it does not preserve sensitive or private
payload data. A future scheduler should persist terminal keys in a non-secret
state file and skip any key that already has a terminal result.

AI-DEV-059 fixtures may include `existing_idempotency_keys` to prove duplicate
handling without touching runtime state.

## Single-Active-Task Policy

A future scheduled runner should promote at most one active execution task at a
time. Candidate discovery may report multiple eligible Issues, but execution
promotion should stop when an active task already exists or when the configured
per-run promotion limit is reached.

AI-DEV-059 does not promote tasks.

## Max Issues Per Run Policy

The dry-run helper supports `max_issues_per_run` in the fixture. The report
records how many Issues were seen and evaluated. A future scheduler should keep
this limit small, deterministic, and visible in logs to avoid unbounded mobile
Issue intake.

## Failure Handling

Failures are represented as sanitized `rejected` or `needs_manual_review`
entries. The helper must continue evaluating other fixture Issues when one
Issue is rejected. Invalid fixture structure produces a safe empty report with
errors and all side-effect flags false.

## Sanitized Reporting

Reports include Issue number, URL, title, labels, decision, task class,
idempotency key, blocked term categories, and the proposed dry-run runner
command. Reports must not include secrets, private runtime payloads, raw tokens,
credentials, `.env` contents, or production config values.

## Promotion Path To AI-DEV-060

AI-DEV-060 may propose real schedule activation only after reviewing:

- cadence and concurrency controls
- lock/idempotency storage
- GitHub permission scope
- maximum Issues per run
- observability and failure alerts
- comment-back policy
- rollback and disable procedure

AI-DEV-060 must remain separate from this dry-run contract.

## Validation

Run:

```bash
python3 -m py_compile scripts/orchestrator/github_issue_scheduled_pickup_dry_run.py scripts/orchestrator/validate_github_issue_scheduled_pickup_result.py
python3 scripts/orchestrator/validate_github_issue_scheduled_pickup_result.py --input templates/github_issue_scheduled_pickup_result.example.json --pretty
python3 scripts/orchestrator/validate_github_issue_scheduled_pickup_result.py --input templates/github_issue_scheduled_pickup_empty.example.json --pretty
python3 scripts/orchestrator/validate_github_issue_scheduled_pickup_result.py --input templates/github_issue_scheduled_pickup_rejected.example.json --pretty
python3 scripts/orchestrator/github_issue_scheduled_pickup_dry_run.py --input templates/github_issue_scheduled_pickup_request.example.json --output /tmp/github_issue_scheduled_pickup_result.example.json --pretty --once
python3 scripts/orchestrator/validate_github_issue_scheduled_pickup_result.py --input /tmp/github_issue_scheduled_pickup_result.example.json --pretty
python3 scripts/orchestrator/inspect_ai_platform_status.py --pretty
python3 scripts/orchestrator/validate_ai_branch.py --pretty
git diff --check main...HEAD
```
