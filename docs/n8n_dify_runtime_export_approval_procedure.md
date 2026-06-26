# n8n Dify Runtime Export Approval Procedure

## Purpose

AI-DEV-040 defines a supervised approval procedure for a future n8n/Dify
workflow export. This is Stage 1 only: repo documentation, JSON templates, and a
validator.

AI-DEV-040 is not a runtime export. A real workflow export requires a separate
human approval and a separate future task. The rule is explicit: real workflow
export requires a separate human approval. This task must not start n8n, log in
to Dify, call Dify runtime, export a raw n8n workflow, handle secrets, activate
runtime automation, or run AI-DEV-041.

real workflow export requires a separate human approval.

## Scope

This procedure covers:

- pre-approval gates for a future supervised export
- runtime access boundaries
- raw export local-only handling
- sanitize requirements
- validation steps
- recovery verification
- cleanup
- closeout

It builds on the AI-DEV-039 sanitizer and export recovery package. Any raw
export must remain local-only, outside the repository, and must be sanitized
before review or commit.

## Non-Goals

AI-DEV-040 does not:

- start n8n
- log in to, call, configure, or export from Dify runtime
- export raw n8n workflow JSON
- read, print, save, or commit real secrets, tokens, API keys, `.env`, or
  credentials
- modify runtime queues
- modify production databases
- modify cron, systemd, or timers
- send LINE, Email, or other notifications
- send a real Codex execution task
- perform auto-merge
- run `python3 main.py`
- run AI-DEV-041

## Pre-Approval

A future runtime export may proceed only after a human operator approves all
required gates:

- `approved_by_human`
- `export_scope`
- `raw_export_local_only`
- `sanitize_required`
- `secrets_must_not_leave_runtime`
- `no_publish`
- `no_active_workflow`
- `no_notification`
- `no_auto_merge`
- `no_trading`

Approval must name the operator, the export scope, expected workflow identity,
allowed local temp directory, sanitizer command, and closeout expectations.

## Runtime Access

Runtime access is human-gated. The operator must verify:

- the n8n workflow remains unpublished
- the workflow is not active
- Manual Trigger remains the only approved trigger
- no webhook, scheduler, queue polling, GitHub trigger, notification, trading,
  production DB, or auto-merge node is active
- no Dify or n8n credential value will be copied into repo files
- no raw export will be pasted into chat, issue comments, PRs, logs, or repo
  files

AI-DEV-040 does not grant runtime access.

## Raw Export Local-Only Handling

If a future approved export happens, the raw export must stay outside the
repository. Raw export commit is forbidden.

The raw export must stay outside the repository.

The raw export must:

- stay outside the repository
- stay on the operator-controlled local machine or approved temp location only
- never be committed
- never be attached to a PR or issue
- never be pasted into chat
- never be printed in terminal output if it may contain secrets
- be deleted after sanitized recovery is verified

Raw export commit is forbidden. Raw export files must not enter `docs/`,
`templates/`, `scripts/`, runtime queue directories, or any tracked git path.

## Sanitize

Before any repo-safe review, the operator must run:

```text
python3 scripts/orchestrator/sanitize_n8n_workflow_export.py --input <local-raw-export.json> --output <local-sanitized-output.json>
```

The sanitizer output must be reviewed for placeholders only:

- `DIFY_API_KEY_STORED_IN_N8N_ONLY`
- `DO_NOT_COMMIT_REAL_SECRET`

If the sanitizer reports no redactions, the operator must still manually verify
that no secrets, tokens, API keys, `.env`, or credential values are present.

## Validation

The future operator must validate repo-safe artifacts only:

```text
python3 scripts/orchestrator/validate_n8n_dify_export_recovery.py --pretty
python3 scripts/orchestrator/validate_runtime_export_approval_procedure.py --pretty
```

Validation must not read a raw export. Validation must not call n8n, Dify,
GitHub runtime APIs, production systems, notification systems, trading systems,
or runtime queue writers.

## Recovery Verification

After sanitization, the operator verifies:

- sanitized output contains no real Bearer token, API key, token, secret,
  `.env`, or credential value
- workflow export shape is understandable from sanitized JSON
- safety gates remain true
- workflow remains unpublished
- workflow is not active
- no notification was sent
- no auto-merge happened
- no trading/order action happened
- no runtime queue was modified
- no Codex real task was sent

If any verification fails, stop and file a follow-up incident task. Do not
publish or activate the workflow.

## Cleanup

Cleanup must be human-supervised:

1. Delete the raw local export after sanitized recovery is verified.
2. Keep only sanitized, reviewed examples in the repository.
3. Confirm no secret values were copied into shell history, logs, notes, chat,
   GitHub, or repo files.
4. Confirm n8n remains unpublished and inactive.
5. Confirm no Dify or n8n credential setup changed.
6. Confirm no runtime queue, production DB, cron, systemd, timer, notification,
   trading, Codex real task, or merge action occurred.

## Closeout

Closeout requires a human-readable summary with:

- approver identity
- export scope
- raw export local-only confirmation
- sanitizer command used
- validation results
- recovery verification results
- cleanup result
- final safety confirmation

The closeout summary must not include raw exports or secret values.

## Acceptance Criteria

AI-DEV-040 is complete when:

- this document exists
- request and supervised result JSON templates exist and parse
- the validator exists and passes
- templates contain all required gates
- docs explicitly forbid raw export commit
- docs state AI-DEV-040 is not a runtime export
- docs state real export needs separate human approval
- no runtime export, n8n start, Dify login/call, secret handling, notification,
  trading, auto-merge, runtime queue mutation, production mutation, or
  AI-DEV-041 execution occurred
