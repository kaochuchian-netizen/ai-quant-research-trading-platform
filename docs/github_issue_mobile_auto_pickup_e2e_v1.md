# Mobile GitHub Issue Auto-Pickup End-To-End V1

## Purpose

> Superseded semantics: see
> `docs/mobile_github_issue_auto_pickup_v2_repair.md` for the repaired v2
> decision model. V1 artifact-only PRs must not be interpreted as completed
> implementation work.

AI-DEV-063 upgrades the mobile GitHub Issue workflow from fixture-only dry-run
to a live-read, repo-only, scheduled path.

The v1 path was intentionally narrow. It could read eligible open Issues,
classify them, select at most one candidate per run, and, only when explicitly
approved with `approved-auto-run`, create a sanitized repo artifact through
controlled runner code. The Issue body is never executed as a command.

AI-DEV-064 repaired the semantics so artifact-only output is not called
`executed_repo_only`. Eligible tasks that require real code generation are now
reported as `needs_codex_execution` or packaged as `handoff_created`.

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

Blocked terms inside clear safety prohibition context are not treated as active
intent. Examples include `Must NOT`, `Do not`, `no`, `never`, `prohibited`,
`forbidden`, `禁止`, `不得`, `不要`, `不可`, and `不允許`. This exception is only
for blocked task-class detection. Secret/token value detection remains strict
and still rejects sensitive values anywhere in the Issue payload.

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

## Historical Repo-Only Artifact Behavior

In v1, when the selected Issue had `approved-auto-run`, the runner could perform
a controlled artifact-only repo change:

1. require current branch `main`
2. require clean git status
3. create a deterministic branch
4. write one sanitized artifact under `docs/mobile_issue_auto_runs/`
5. run local validation
6. open a PR
7. wait for GitHub checks
8. merge only when checks are successful and `mergeStateStatus` is `CLEAN`
9. delete the remote branch through the merge command
10. return to `main` and fast-forward pull

The Issue body is task description only. It is never shell, never a patch, and
never free-form execution instructions.

This historical artifact behavior was not actual implementation of arbitrary
requested deliverables. V2 uses explicit `artifact_recorded`,
`handoff_created`, and `needs_codex_execution` states instead.

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

Regression fixture checks:

```bash
python3 scripts/orchestrator/github_issue_mobile_auto_pickup.py --once --input templates/github_issue_mobile_auto_pickup_negated_safety_fixture.example.json --output /tmp/github_issue_mobile_auto_pickup_negated_safety_result.json --state-dir /tmp/github_issue_mobile_auto_pickup_negated_safety_state --pretty
python3 scripts/orchestrator/validate_github_issue_mobile_auto_pickup_result.py --input /tmp/github_issue_mobile_auto_pickup_negated_safety_result.json --pretty
python3 scripts/orchestrator/github_issue_mobile_auto_pickup.py --once --input templates/github_issue_mobile_auto_pickup_active_sensitive_fixture.example.json --output /tmp/github_issue_mobile_auto_pickup_active_sensitive_result.json --state-dir /tmp/github_issue_mobile_auto_pickup_active_sensitive_state --pretty
python3 scripts/orchestrator/validate_github_issue_mobile_auto_pickup_result.py --input /tmp/github_issue_mobile_auto_pickup_active_sensitive_result.json --pretty
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
