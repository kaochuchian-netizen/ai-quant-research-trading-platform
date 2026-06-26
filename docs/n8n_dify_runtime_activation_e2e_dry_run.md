# n8n Dify Runtime Activation E2E Dry-Run

## Purpose

AI-DEV-035 defines a repo-contained runtime activation E2E dry-run pack for the
n8n and Dify manual-trigger workflow introduced in AI-DEV-034.

This task does not activate runtime systems. It provides documentation, payload
examples, rollback checklists, dry-run reports, and a read-only validator for a
future human-operated dry-run.

## Scope

The dry-run pack covers:

- preflight activation checklist
- ChatGPT-approved dry-run payload
- n8n to Dify dry-run request and expected result shape
- n8n to Codex relay dry-run payload
- n8n merge-gate dry-run report
- runtime disable and rollback checklist
- repo-local validator for this pack

The intended dry-run path is:

```text
Human operator
  -> confirm checklist
  -> manually trigger n8n in a non-production workspace
  -> call sandbox Dify workflow with placeholder credential
  -> receive Dify draft output
  -> assemble ChatGPT-ready dry-run result
  -> stop before any production, notification, merge, archive, or trading action
```

## Non-Goals

AI-DEV-035 does not:

- activate n8n runtime workflows
- configure Dify or n8n credentials
- call production Dify apps
- mutate repository files through automation
- run production pipelines
- run `python3 main.py`
- write to production databases
- modify cron, systemd, or timers
- read or modify secrets, `.env`, credentials, keys, or tokens
- send LINE, Email, or other notifications
- execute trading or order logic
- perform real auto-merge execution
- merge, archive, close out, or run AI-DEV-036

## Runtime Activation Model

The only approved runtime model for this pack is a manual, non-production,
single-execution dry-run. The workflow must remain inactive before and after the
test unless a human explicitly approves otherwise in a later task.

n8n may be used only as the manual orchestration layer. Dify may draft and
summarize only. GitHub remains the source of truth for PR and CI state. ChatGPT
remains the approval and merge-gate owner. Codex remains the repository
developer and must receive a separate approved task package before making code
changes.

## Required Operator Preconditions

Before any future dry-run, a human operator must confirm:

- the n8n workspace is non-production
- the workflow is imported but inactive
- the trigger is Manual Trigger only
- Dify credential setup is manually approved and sandbox-only
- no scheduler, webhook, queue polling, notification, DB, production, merge,
  archive, or trading node is active
- only example payloads or explicitly approved dry-run payloads are used
- no secrets, `.env`, credentials, tokens, keys, or production data are included

## Dry-Run Procedure

1. Run `python3 scripts/orchestrator/validate_n8n_dify_runtime_activation_pack.py --pretty`.
2. Review `templates/n8n_dify_runtime_activation_checklist.example.json`.
3. In a non-production n8n workspace, import the AI-DEV-034 manual-trigger
   workflow example.
4. Keep the workflow inactive except for a single manual dry-run execution.
5. Attach a human-created sandbox Dify credential outside this repository.
6. Use `templates/n8n_dify_e2e_dry_run_payload.example.json` as the sample
   payload.
7. Confirm the Dify response matches the result contract.
8. Assemble the ChatGPT-ready dry-run report.
9. Disable the workflow and remove dry-run credentials if requested by the
   operator.
10. Confirm no prohibited side effects occurred.

## Dry-Run Success Criteria

A dry-run is successful only if:

- the workflow was manually triggered
- the workflow stayed non-production
- no real credential was stored in the repo
- Dify returned draft-only content
- n8n produced a ChatGPT-ready dry-run summary
- no repository mutation occurred through n8n or Dify
- no production, DB, scheduler, notification, trading, merge, archive, or
  branch cleanup action occurred
- rollback / disable checklist remains available and actionable

## Rollback and Disable Procedure

If the dry-run fails or the operator sees unexpected behavior:

1. Disable the n8n workflow.
2. Remove the sandbox Dify credential from the workflow.
3. Stop all follow-up executions.
4. Export only redacted dry-run execution metadata.
5. Confirm no production systems were touched.
6. File a follow-up AI-DEV task with the failure summary.

Rollback must not mutate production systems, databases, schedulers,
notifications, trading logic, GitHub state, or runtime queues.

## Safety Boundaries

Permanent human-gated scope:

- trading / order execution
- secrets / `.env` / credentials
- production DB writes
- production-approved runner
- formal LINE / Email / notification sending
- cron / systemd / timer modification
- Dify / n8n credential setup
- paid data source integration
- public dashboard publishing
- trading / order logic
- real auto-merge execution

AI-DEV-035 additionally prohibits production Dify or n8n runtime activation,
live production notifications, GitHub credential setup, task archive, branch
cleanup, and AI-DEV-036 execution.

## Human-Gated Actions

Human approval is required before:

- importing workflow exports into n8n
- creating or attaching Dify / n8n credentials
- running any dry-run
- activating workflow runtime
- passing draft output to Codex
- opening production access
- sending notifications
- executing merge, archive, or branch cleanup
- modifying production, DB, cron, systemd, timer, dashboard, paid data,
  notification, or trading/order logic

## Acceptance Criteria

AI-DEV-035 is complete when:

- this document exists
- all seven JSON and validator companion files exist
- every JSON example parses with `python3 -m json.tool`
- the validator passes
- dry-run payloads include only placeholders and example values
- checklist and rollback examples include all required safety gates
- no production, DB, cron, secret, `.env`, Dify runtime, n8n runtime,
  notification, trading, merge, archive, or AI-DEV-036 action is executed

## Follow-Up Tasks

AI-DEV-036 must be a separate explicitly approved task. It must not inherit
runtime permission from this dry-run pack.

## AI-DEV-037 Runtime Dry-Run Operation Record

AI-DEV-037 records the post-AI-DEV-036 runtime dry-run state without changing
runtime systems.

Recorded AI-DEV-036 outcome:

- Dify workflow API dry-run completed.
- n8n manual workflow was saved but not published.
- n8n workflow not active.
- Manual Trigger only.
- n8n container stopped.
- SSH tunnel closed.
- no secrets in repo.
- no production mutation.
- no notification.
- no Codex real execution task was sent.
- no auto-merge.
- no repo mutation from the runtime dry-run.

This section is an operation record and runbook extension only. It is not
evidence that n8n is active, published, scheduled, reachable by webhook, or
allowed to perform production actions.

## AI-DEV-037 n8n Enable / Disable Runbook

This runbook is for a future human operator. It must not be executed by this
repo task.

### Enable Preconditions

Before any future enable action, a human operator must confirm:

- the workflow remains saved but not published until approval
- workflow not active before the dry-run
- Manual Trigger only; no webhook, scheduler, queue polling, or GitHub trigger
- no secrets in repo and no `.env` or credential values copied into templates
- sandbox Dify credential is configured manually outside the repository
- no production DB, production pipeline, notification, trading, merge, archive,
  or branch cleanup node is present
- rollback checklist has been reviewed

### Enable Steps

1. Open the non-production n8n workspace.
2. Confirm the workflow is saved but not published.
3. Confirm the workflow not active state.
4. Attach only a human-created sandbox Dify credential.
5. Confirm Manual Trigger only.
6. Execute at most one approved dry-run manually.
7. Capture redacted execution metadata.
8. Disable the workflow after the dry-run.

### Disable Steps

1. Stop manual executions.
2. Set workflow active state to false.
3. Confirm n8n container stopped if the dry-run used a local container.
4. Confirm SSH tunnel closed if a tunnel was used.
5. Remove sandbox credential references from the workflow if requested by the
   operator.
6. Confirm no notification, production, trading, merge, archive, or Codex real
   execution task occurred.

### Stop Conditions

Stop immediately and escalate if any of the following is observed:

- workflow becomes active without approval
- workflow is published outside the approved workspace
- webhook, scheduler, queue polling, or GitHub trigger is present
- secret, `.env`, token, key, or credential value appears in repo files
- production endpoint is called
- notification is sent
- trading/order action is attempted
- auto-merge, archive, or branch cleanup is attempted
- AI-DEV-038 is started

## AI-DEV-037 Validation Artifacts

AI-DEV-037 adds:

- `templates/n8n_runtime_dry_run_operation_record.example.json`
- `templates/n8n_runtime_enable_disable_runbook_checklist.example.json`
- `scripts/orchestrator/validate_n8n_runtime_dry_run_runbook.py`

The validator is read-only. It checks that the operation record and runbook
preserve the runtime state and safety constraints, including saved but not
published, workflow not active, Manual Trigger only, no secrets in repo, no
production mutation, no notification, and no auto-merge.
