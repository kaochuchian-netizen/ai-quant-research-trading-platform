# n8n Dify Runtime Export Dry-Run Rehearsal

## Purpose

AI-DEV-041 defines a supervised export dry-run rehearsal package using a
synthetic fixture only. It rehearses the approval and sanitation path without
accessing n8n, Dify, credentials, runtime queues, production systems, or real
workflow exports.

This package is Stage 1 only: repo documentation, templates, a synthetic
fixture, and a validator. It does not perform a runtime export and does not
grant approval for AI-DEV-042.

## Scope

The rehearsal path is:

```text
approval request
  -> synthetic raw export placeholder
  -> sanitize synthetic fixture
  -> validator
  -> supervised result
  -> cleanup checklist
  -> closeout report
```

All inputs are repo-contained examples. The raw workflow fixture is synthetic
and intentionally includes fake, do-not-use Authorization and token values so
the sanitizer redaction path can be tested without handling secrets.

## Non-Goals

AI-DEV-041 does not:

- start n8n
- log in to or call Dify runtime
- export a real or raw n8n workflow from runtime
- read, print, save, or commit real secrets, tokens, API keys, `.env`, or
  credentials
- modify runtime queues
- modify production databases
- modify cron, systemd, or timers
- send LINE, Email, or other notifications
- send a real Codex execution task
- perform auto-merge
- run `python3 main.py`
- run AI-DEV-042

## Rehearsal Gates

Required gates:

- `dry_run`
- `raw_export_is_synthetic`
- `no_runtime_access`
- `no_secrets`
- `no_publish`
- `no_active_workflow`
- `no_notification`
- `no_auto_merge`
- `no_trading`

If any gate is false or missing, the rehearsal is invalid.

## Synthetic Fixture Rules

`templates/n8n_runtime_export_synthetic_raw_workflow.fixture.json` is the only
allowed raw-export-shaped input for this task. It must remain visibly synthetic:

- `synthetic_fixture` is true
- fake values include `FAKE` and `DO_NOT_USE`
- no real Bearer token, API key, `.env` value, secret, or credential appears
- the fixture must not be imported into n8n
- the fixture must not be treated as runtime evidence

The fixture exists only to test sanitizer behavior.

## Sanitization Procedure

The validator runs:

```text
python3 scripts/orchestrator/sanitize_n8n_workflow_export.py --input <synthetic-fixture> --output <temp-sanitized-output>
```

The sanitizer output is written to a temporary directory only. It is not
committed and is not used as a runtime export. The validator requires
`redaction_count > 0` and rejects sanitized output containing a real `Bearer`
pattern.

## Validation Procedure

Run:

```text
python3 scripts/orchestrator/validate_runtime_export_rehearsal.py --pretty
python3 scripts/orchestrator/validate_runtime_export_approval_procedure.py --pretty
python3 scripts/orchestrator/validate_n8n_dify_export_recovery.py --pretty
```

These commands must remain repo-local and read-only except for temporary
synthetic sanitizer output under the system temp directory.

## Cleanup Checklist

After the rehearsal validator runs:

1. Confirm only synthetic temp files were created.
2. Confirm no runtime export was created or read.
3. Confirm no raw workflow export entered the repository.
4. Confirm no secret value was printed or committed.
5. Confirm no n8n or Dify runtime access occurred.
6. Confirm no notification, trading, Codex real task, auto-merge, production,
   scheduler, or runtime queue action occurred.
7. Confirm AI-DEV-042 was not run.

## Closeout Report

The closeout report must include:

- branch name
- commit hash
- changed files
- sanitizer test result against the synthetic fixture
- validator result
- git status
- safety confirmation

The closeout report must not include raw runtime exports or secret values.

## Acceptance Criteria

AI-DEV-041 is complete when:

- this document exists
- request/result/fixture JSON files exist and parse
- the validator exists and passes
- sanitizer rehearsal uses only the synthetic fixture
- sanitizer redaction count is greater than zero
- sanitized output contains no real Bearer pattern
- required gates are present
- no n8n, Dify, runtime export, real secret handling, runtime queue mutation,
  production mutation, notification, trading, Codex real task, auto-merge,
  `python3 main.py`, or AI-DEV-042 action occurred

