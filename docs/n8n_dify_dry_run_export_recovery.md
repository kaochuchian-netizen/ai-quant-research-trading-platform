# n8n Dify Dry-Run Export Recovery

## Purpose

AI-DEV-039 defines a Stage 1 repo package for recovering a safe, sanitized
example of the n8n and Dify dry-run workflow after a manual runtime dry-run.

This package is documentation, sanitized examples, a sanitizer, and a validator
only. It does not export a live n8n workflow, call Dify, log in to any runtime
system, activate automation, or preserve raw credentials.

## Scope

This recovery package covers:

- a sanitized n8n manual dry-run workflow example
- a Dify task draft reconstruction example
- a repo-local sanitizer for n8n workflow JSON exports
- a repo-local validator for the recovery package
- safety rules for handling any future manually exported workflow data

The intended recovery path is:

```text
Human operator obtains a workflow export outside the repo
  -> operator runs sanitizer locally
  -> sanitizer writes a sanitized JSON copy
  -> validator checks only repo-safe artifacts
  -> ChatGPT reviews sanitized output before any follow-up task
```

## Non-Goals

AI-DEV-039 does not:

- start n8n
- call, log in to, or configure Dify
- export a raw n8n workflow from runtime
- read, print, save, or commit real secrets, tokens, API keys, `.env`, or
  credentials
- modify production databases
- modify cron, systemd, timers, or runtime queues
- send LINE, Email, or other notifications
- send a real Codex execution task
- run `python3 main.py`
- perform auto-merge
- run AI-DEV-040

## Recovery Model

The sanitizer is a local file-to-file tool. It accepts an input JSON path and an
output JSON path. By default, it refuses to overwrite the output file. Operators
must use placeholders only in repo examples:

- `DIFY_API_KEY_STORED_IN_N8N_ONLY`
- `DO_NOT_COMMIT_REAL_SECRET`

Raw workflow exports must stay outside the repository unless they are already
sanitized and reviewed. The sanitizer must never print secret values in terminal
output or JSON summaries.

## Sanitizer Behavior

`scripts/orchestrator/sanitize_n8n_workflow_export.py`:

- parses a JSON workflow export
- redacts authorization headers, bearer tokens, API keys, token-like fields,
  secret-like fields, credential-like fields, and password-like fields
- replaces redacted values with `DO_NOT_COMMIT_REAL_SECRET`
- preserves structural JSON needed for review
- writes only to the explicit output path
- refuses to overwrite an existing output path unless `--force` is provided
- prints a JSON summary with counts and paths only, never original secret values

The sanitizer is not a runtime export tool. It must be run only on a local file
that a human operator has already obtained through an approved process.

## Validator Behavior

`scripts/orchestrator/validate_n8n_dify_export_recovery.py`:

- checks required docs, templates, sanitizer, and validator files exist
- parses the JSON templates
- checks the sanitized workflow example includes a Manual Trigger concept
- checks required safety markers exist:
  - `dry_run`
  - `no_auto_merge`
  - `no_notification`
  - `no_trading`
  - `no_secrets`
- rejects real bearer/API-key/token-looking patterns in repo examples
- runs sanitizer tests only against synthetic temp files
- does not read raw runtime exports
- does not call n8n, Dify, GitHub, notification systems, production systems, or
  runtime queues

## Safety Boundaries

Permanent safety boundaries:

- no secrets in repo
- no production mutation
- no notification
- no trading
- no auto-merge
- no runtime queue mutation
- no Dify or n8n runtime activation
- no raw export committed to git
- no AI-DEV-040 execution

The recovery package is `dry_run` documentation and tooling only. It is not
approval to run or activate automation.

## Human-Gated Actions

Human approval is required before:

- exporting anything from n8n runtime
- handling a raw workflow export
- configuring Dify or n8n credentials
- importing a sanitized workflow into n8n
- activating any n8n workflow
- sending notifications
- sending real Codex execution tasks
- merging or auto-merging PRs
- changing production, DB, cron, systemd, timer, runtime queue, secrets, or
  trading/order logic

## Acceptance Criteria

AI-DEV-039 Stage 1 is complete when:

- this document exists
- sanitized n8n and Dify reconstruction JSON examples exist and parse
- sanitizer exists, compiles, and redacts synthetic temp-file secrets
- validator exists, compiles, and passes
- examples contain only placeholders and no real secrets
- validation confirms required safety markers
- no n8n, Dify, runtime, notification, trading, production, auto-merge, or
  AI-DEV-040 action is executed

## AI-DEV-043 Packaged Sanitized Export Result

AI-DEV-043 Stage 2 packages the supervised n8n export result after the runtime
export was completed outside this repo task.

Recorded result:

- raw export stayed local-only and was not added to the repository
- sanitized workflow artifact is packaged at
  `templates/n8n_dify_manual_dry_run_workflow.ai_dev_043_sanitized.example.json`
- sanitizer redaction count was `1`
- sanitized secret pattern hit count was `0`
- secret values leaked was `false`
- n8n stopped was `true`
- workflow not published / not active
- runtime queue was not modified
- AI-DEV-044 was not run

The repo artifact is derived only from the sanitized output. Raw workflow
contents remain out of scope and must not be committed.
