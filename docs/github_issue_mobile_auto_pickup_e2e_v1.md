# Mobile GitHub Issue Auto-Pickup End-To-End V1

## Purpose

AI-DEV-063 upgrades the mobile GitHub Issue workflow from fixture-only dry-run
to a live-read, repo-only, scheduled path.

The v1 path is intentionally narrow. It can read eligible open Issues, classify
them, select at most one candidate per run, and, only when explicitly approved
with `approved-auto-run`, create a sanitized repo artifact through controlled
runner code. The Issue body is never executed as a command.

## Mobile Workflow

1. Open GitHub mobile app or mobile web.
2. Create an Issue with a concise AI-DEV task title.
3. Add all required labels:

   ```text
   ai-dev
   gcp-pickup
   auto-run
   repo-only
   ```

4. Add exactly one approval mode label:

   ```text
   dry-run
   ```

   or:

   ```text
   approved-auto-run
   ```

Use `dry-run` for discovery and planning. Use `approved-auto-run` only after
reviewing that the task is repo-only and safe for controlled automation.

Never paste secrets, tokens, `.env` values, private runtime payloads, production
config, account credentials, or API keys into an Issue.

## Required Labels

All auto-pickup candidates require:

- `ai-dev`
- `gcp-pickup`
- `auto-run`
- `repo-only`

One of these is also required:

- `dry-run`
- `approved-auto-run`

## Blocked Labels And Text Classes

Any of these labels or matching task classes reject the candidate:

- `runtime`
- `production`
- `secret`
- `notification`
- `trading`
- `n8n`
- `dify`
- `db`
- `cron`
- `systemd`
- `timer`
- `pipeline`
- `credential`
- `env`

The runner also rejects text that asks for runtime actions, production
pipelines, secret handling, notification sending, n8n/Dify/OpenAI calls,
trading/orders, production database mutation, cron/systemd/timer changes,
daemon/background services, or arbitrary shell execution.

## Allowed Task Classes

V1 accepts only:

- `docs_only`
- `template_only`
- `validator_only`
- `repo_side_contract`
- `test_or_validation_helper`
- `runbook_only`
- `inspector_only`

Ambiguous Issues are marked `needs_manual_review`.

## Live Discovery

The scheduled runner may call:

```bash
gh issue list --state open --label ai-dev --label gcp-pickup --label auto-run --label repo-only
```

This is read-only discovery. It does not comment, label, close, reopen, or edit
Issues.

## Repo-Only Execution

When the selected Issue has `approved-auto-run`, the runner may perform a
controlled repo-only execution:

1. require current branch `main`
2. require clean git status
3. create a deterministic branch
4. write one sanitized execution artifact under `docs/mobile_issue_auto_runs/`
5. run local validation
6. open a PR
7. wait for GitHub checks
8. merge only when checks are successful and `mergeStateStatus` is `CLEAN`
9. delete the remote branch through the merge command
10. return to `main` and fast-forward pull

The Issue body is task description only. It is never shell, never a patch, and
never free-form execution instructions.

## Comment-Back And Label Mutation

Comment-back and label mutation are disabled by default. The scheduled command
does not pass `--comment-back` or `--label-closeout`.

V1 does not close Issues automatically. Future comment or label closeout needs
separate review and explicit enablement.

## State Files

Default state directory:

```text
/home/kaochuchian/.local/state/stock-ai-orchestrator/
```

State files:

- `github_issue_scheduled_pickup_latest.json`
- `github_issue_mobile_auto_pickup_latest.json`
- `github_issue_mobile_auto_pickup_latest_candidate.json`
- `github_issue_mobile_auto_pickup_idempotency.json`
- `github_issue_scheduled_pickup.lock`
- `github_issue_scheduled_pickup.log`

The scheduled service keeps using the AI-DEV-061 lock file so there is a single
active scheduled pickup run.

## Scheduled Command

The reviewed 30-minute timer should call:

```bash
/usr/bin/flock -n /home/kaochuchian/.local/state/stock-ai-orchestrator/github_issue_scheduled_pickup.lock \
  /usr/bin/python3 scripts/orchestrator/github_issue_mobile_auto_pickup.py \
  --once \
  --live-read-open-issues \
  --max-issues 1 \
  --execute-repo-only \
  --output /home/kaochuchian/.local/state/stock-ai-orchestrator/github_issue_scheduled_pickup_latest.json \
  --state-dir /home/kaochuchian/.local/state/stock-ai-orchestrator \
  --repo kaochuchian-netizen/ai-quant-research-trading-platform \
  --pretty
```

The timer cadence remains 30 minutes.

## Idempotency

Each candidate receives:

```text
mobile-auto-pickup-v1|issue_number|issue_url|task_class|required_labels|approval_label
```

Processed keys are stored in:

```text
/home/kaochuchian/.local/state/stock-ai-orchestrator/github_issue_mobile_auto_pickup_idempotency.json
```

Already processed keys are skipped without Issue mutation.

## Health Inspection

Run:

```bash
python3 scripts/orchestrator/inspect_github_issue_scheduled_pickup_health.py --pretty --output /tmp/github_issue_scheduled_pickup_health.json
python3 scripts/orchestrator/validate_github_issue_mobile_auto_pickup_result.py --input /home/kaochuchian/.local/state/stock-ai-orchestrator/github_issue_scheduled_pickup_latest.json --pretty
```

All side-effect flags must remain false for runtime, production, Issue
mutation, notification, n8n, Dify, production database, and trading actions.

## Rollback

Disable the scheduled path:

```bash
systemctl --user disable --now stock-ai-github-issue-scheduled-pickup-dry-run.timer
systemctl --user reset-failed stock-ai-github-issue-scheduled-pickup-dry-run.service
systemctl --user daemon-reload
```

Rollback affects only the user-level GitHub Issue pickup timer. It does not
touch n8n, production pipelines, production databases, cron, or trading.

## Still Disabled

V1 intentionally does not enable:

- runtime actions
- production pipelines
- n8n control
- Dify calls
- OpenAI API calls
- LINE, Email, or notification sending
- production DB mutation
- trading or orders
- Issue close/reopen
- default comment-back
- default label mutation
- arbitrary shell execution from Issue text
