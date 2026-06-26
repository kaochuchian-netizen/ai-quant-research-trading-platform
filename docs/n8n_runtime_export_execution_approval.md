# n8n Runtime Export Execution Approval

## Purpose

AI-DEV-042 defines the final supervised approval package and preflight gate for
a future human-approved n8n runtime workflow export.

This task is not runtime export. It is Stage 1 only: repository documentation,
JSON templates, and a validator. A real export needs separate AI-DEV-043 or
later human-approved task.

A real export needs separate AI-DEV-043 or later human-approved task.

## Scope

This package defines:

- planning approval
- preflight approval
- runtime execution approval
- post-export sanitize approval
- cleanup and closeout

It extends the AI-DEV-039 sanitizer package, AI-DEV-040 runtime export approval
procedure, and AI-DEV-041 synthetic rehearsal package. It does not grant runtime
access by itself.

## Non-Goals

AI-DEV-042 does not:

- start n8n
- log in to or call Dify runtime
- export a real raw n8n workflow
- read, print, save, or commit secrets, API keys, tokens, `.env`, or credentials
- modify runtime queues
- modify production databases
- modify cron, systemd, or timers
- send LINE, Email, or other notifications
- send a real Codex execution task
- perform auto-merge
- run `python3 main.py`
- run AI-DEV-043

## Planning Approval

Planning approval only confirms that a future operator may prepare an export
plan. It does not approve runtime access, n8n startup, raw export creation, or
credential handling.

Planning approval must define:

- `task_id`
- `approval_scope`
- expected workflow identity
- allowed local-only raw export handling
- required sanitizer and validator commands
- cleanup and closeout requirements
- `approval_expiry`

## Preflight Approval

Preflight approval confirms environment conditions before any future runtime
task may proceed. The preflight checklist must record:

- n8n container state
- SSH tunnel state
- browser-only UI export requirement
- local-only raw path
- confirmation that the raw path is ignored and not a repo path
- sanitizer and validator commands
- cleanup and rollback steps

Preflight approval is still not runtime execution approval.

## Runtime Execution Approval

Runtime execution approval is a separate human decision. Without it, future
operators must not start n8n, open a tunnel, use the n8n UI, or create a raw
export.

Approval gates must include:

- `task_id`
- `approval_scope`
- `approved_by_human`
- `approved_runtime_access`
- `approved_n8n_start`
- `approved_raw_export_local_only`
- `approved_sanitize_after_export`
- `approved_no_publish`
- `approved_no_active_workflow`
- `approved_no_notification`
- `approved_no_auto_merge`
- `approved_no_trading`
- `approved_no_secret_disclosure`
- `approval_expiry`

These gates default to false in templates except non-execution safety
constraints that explicitly mean "must not happen".

## Post-Export Sanitize Approval

Post-export sanitize approval must happen before any sanitized output can be
considered for repository inclusion. Raw export commit is forbidden. Raw export
must remain local-only.

Raw export must remain local-only.

Sanitize before repo inclusion is mandatory:

```text
python3 scripts/orchestrator/sanitize_n8n_workflow_export.py --input <local-raw-export.json> --output <local-sanitized-output.json>
```

The sanitized output must pass the recovery and execution approval validators
before any repo update is proposed.

## Cleanup And Closeout

Cleanup and closeout must verify:

- raw export local path was outside the repository
- raw export was not committed
- sanitized output path is safe for review
- redaction count is recorded
- validators passed
- n8n is stopped
- no secret leak occurred
- no notification, auto-merge, trading, production, scheduler, runtime queue,
  or Codex real task action occurred
- recovery package update status is recorded

Closeout must not include raw export contents or secret values.

## Safety Boundaries

Human approval before runtime access is mandatory. AI-DEV-042 itself must not
access runtime systems.

Raw export local-only handling is mandatory. Raw export commit is forbidden.
Sanitize before repo inclusion is mandatory.

This package does not permit n8n publish, active workflow state, notification,
auto-merge, trading/order execution, secret disclosure, production mutation, or
runtime queue mutation.

## Acceptance Criteria

AI-DEV-042 is complete when:

- this document exists
- approval request, preflight checklist, and closeout JSON templates exist
- templates parse as JSON
- templates include all required approval gates
- runtime approval gates default false unless they are dry-run or safety flags
- validator passes
- docs forbid raw export commit
- docs require raw export local-only
- docs require sanitize before repo inclusion
- docs require human approval before runtime access
- no n8n, Dify, real raw export, secret handling, runtime queue mutation,
  production mutation, notification, Codex real task, auto-merge,
  `python3 main.py`, or AI-DEV-043 action occurred
