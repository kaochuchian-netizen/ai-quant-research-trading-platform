# GitHub Issue Scheduled Pickup Health Runbook

## Purpose

AI-DEV-062 adds a read-only health inspector for the 30-minute dry-run GitHub
Issue scheduled pickup timer enabled by AI-DEV-061.

The inspector does not enable live Issue discovery, mutate GitHub Issues, post
comments, change labels, edit schedules, start runtime services, or execute
Issue body text.

## Inspect Health

Run:

```bash
python3 scripts/orchestrator/inspect_github_issue_scheduled_pickup_health.py --pretty --output /tmp/github_issue_scheduled_pickup_health.json
```

Validate the report:

```bash
python3 scripts/orchestrator/validate_github_issue_scheduled_pickup_health.py --input /tmp/github_issue_scheduled_pickup_health.json --pretty
```

## What The Report Checks

The report includes:

- timer presence, enabled state, active state, and next trigger summary
- service presence and last service status summary
- latest dry-run artifact path, presence, validity, and sanitized summary
- lock file presence
- idempotency state presence
- sanitized log file presence
- side-effect flags from the latest artifact
- rollback and disable commands

The log file is checked for presence only. The inspector does not read log
content.

## Latest Artifact Validation

The latest artifact should remain:

- `dry_run=true`
- `scheduler_enabled=false`
- `github_issue_mutated=false`
- `runtime_action_performed=false`
- `daemon_or_background_service_created=false`

Any unexpected true side-effect flag should be treated as a stop condition.

## Side-Effect Violation Procedure

If `side_effect_flags_ok=false`:

1. disable the timer
2. preserve the latest artifact and sanitized logs
3. do not run live Issue discovery
4. do not enable comment-back
5. inspect the dry-run helper and latest artifact before any further activation

## Rollback / Disable

Disable the schedule:

```bash
systemctl --user disable --now stock-ai-github-issue-scheduled-pickup-dry-run.timer
systemctl --user reset-failed stock-ai-github-issue-scheduled-pickup-dry-run.service
systemctl --user daemon-reload
```

Optional unit file cleanup after disable:

```bash
rm ~/.config/systemd/user/stock-ai-github-issue-scheduled-pickup-dry-run.service
rm ~/.config/systemd/user/stock-ai-github-issue-scheduled-pickup-dry-run.timer
systemctl --user daemon-reload
```

## Before AI-DEV-063 Live Issue Discovery

Before live Issue discovery is considered, all of the following should be true:

- timer is present, enabled, and active
- service is present and last run succeeded
- latest artifact validates
- side-effect flags are all false
- lock, idempotency, and log files exist
- no GitHub Issue mutation has occurred
- no runtime action has occurred
- no comment-back is enabled

## Intentionally Disabled

These remain disabled:

- live GitHub Issue discovery
- GitHub Issue mutation
- Issue comments or comment-back
- label edits
- repo task execution from Issue content
- n8n, Dify, OpenAI, LINE, Email, notifications
- production pipelines and production DB mutation
- trading and order placement
