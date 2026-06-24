# n8n Dify Manual Trigger Workflow Pack

## Purpose

AI-DEV-034 defines the first repo-contained n8n and Dify workflow pack for a
manual-trigger automation path.

The workflow pack is designed for future AI-DEV-035 runtime dry-run activation.
This task only creates documentation, n8n-style workflow export examples,
payload examples, a validator, and this activation runbook. It does not activate
any runtime workflow.

## Scope

This pack covers a manual-trigger flow:

1. n8n receives a ChatGPT-approved payload.
2. n8n maps the payload into a Dify workflow API request.
3. Dify returns a task draft or Codex package draft.
4. n8n maps the Dify response into a ChatGPT-ready draft summary.

The deliverables are:

- workflow pack documentation
- n8n-style workflow export example
- approved payload example
- n8n to Dify request example
- Dify response example
- ChatGPT-ready summary example
- repo-local validator script

## Non-Goals

AI-DEV-034 does not:

- activate an n8n workflow
- create or configure Dify runtime apps or workflows
- create or configure Dify or n8n credentials
- call a live Dify API
- mutate the repository through automation
- run production pipelines
- run `python3 main.py`
- write to production databases
- modify cron, systemd, or timers
- send LINE, Email, or other notifications
- execute trading or order logic
- perform real auto-merge execution
- archive completed tasks or clean up branches

## Workflow Overview

The intended future runtime path is:

```text
Manual Trigger
  -> ChatGPT-approved payload input
  -> n8n validation and mapping
  -> Dify workflow API request
  -> Dify task draft / Codex package draft response
  -> n8n ChatGPT-ready draft summary output
```

This pack keeps the flow manual by design. A human operator must explicitly
trigger the workflow and provide the approved payload. The workflow must not
watch GitHub, poll queues, run timers, or self-activate.

## n8n Manual Trigger Design

The example workflow export uses these conceptual nodes:

- Manual Trigger
- Normalize ChatGPT Payload
- Build Dify Workflow Request
- Call Dify Workflow API
- Build ChatGPT-Ready Summary

The workflow export is an example only. It is not active, does not include real
credentials, and should not be imported into production without a separate
AI-DEV-035 dry-run approval.

The Manual Trigger node is the only entry point. Scheduled triggers, webhook
triggers, queue polling, and GitHub event triggers are intentionally out of
scope.

## ChatGPT-Approved Payload Input

The input payload must come from ChatGPT approval and must include:

- `schema_version`
- `artifact_type`
- `task_id`
- `approved_by`
- `approval_status`
- `requested_flow`
- `repository`
- `branch`
- `base_branch`
- `scope`
- `files_in_scope`
- `validation_commands`
- `safety_boundary`
- `human_gates`

`approval_status` must be `APPROVED`. If the payload is draft, missing, or
stale, n8n must stop before calling Dify.

## n8n to Dify Request Mapping

n8n maps the approved payload into a Dify workflow request with:

- task identity
- approved title and scope
- branch and base branch
- files in scope
- validation commands
- safety boundary
- requested output format

n8n must not pass secrets, tokens, `.env` values, private credentials, or
production runtime state to Dify.

## Dify Response Mapping

Dify may return:

- task draft Markdown
- Codex package draft Markdown
- assumptions
- missing inputs
- risk flags
- safety confirmation

Dify response content is draft material only. It must not be treated as approval
to mutate the repository, merge PRs, create credentials, run production, send
notifications, or trade.

## ChatGPT-Ready Summary Output

n8n maps the Dify response into a ChatGPT-ready summary with:

- task id
- draft status
- generated draft text
- missing inputs
- safety flags
- recommended ChatGPT review action
- blocker list

The summary is for ChatGPT review. It is not a Codex execution instruction until
ChatGPT explicitly approves a task package.

## Credential Requirements

Future runtime activation requires a human-configured Dify API credential in
n8n. This pack does not create, store, export, or validate a real credential.

The workflow example may reference placeholder credential names only, such as
`DIFY_HTTP_HEADER_AUTH_PLACEHOLDER`. Placeholder names are not secrets and must
be replaced only during an approved AI-DEV-035 dry-run setup.

Credential setup is permanently human-gated.

## Runtime Activation Runbook

Runtime activation is deferred to AI-DEV-035.

Before activation, a human operator must:

1. Review this workflow pack and validator output.
2. Confirm the imported workflow remains inactive.
3. Configure a Dify credential manually in n8n.
4. Use a non-production Dify workflow or sandbox endpoint.
5. Load only an example or approved dry-run payload.
6. Confirm no scheduler, webhook, queue polling, or notification node is active.
7. Confirm no production DB, trading, notification, or auto-merge action exists.

Activation must start as a manual dry-run only.

## Dry-Run Procedure

For AI-DEV-035, the dry-run should:

1. Run `python3 scripts/orchestrator/validate_n8n_dify_workflow_pack.py --pretty`.
2. Import the workflow export into a non-production n8n workspace.
3. Keep the workflow inactive.
4. Attach a human-created sandbox Dify credential.
5. Use `templates/n8n_chatgpt_approved_payload.example.json` as sample input.
6. Execute the Manual Trigger once.
7. Confirm Dify receives only approved, non-secret payload fields.
8. Confirm n8n produces a ChatGPT-ready summary.
9. Confirm no repo mutation, notification, scheduler, DB, production, merge, or
   trading action occurred.

## Rollback / Disable Procedure

If dry-run behavior is unexpected:

1. Disable the n8n workflow immediately.
2. Remove the Dify credential from the workflow.
3. Export the failed execution data after redacting any sensitive values.
4. Stop all follow-up runtime tests.
5. File a follow-up AI-DEV task with the failure summary.

No automated rollback should modify production systems, schedulers, databases,
notifications, trading logic, or GitHub state.

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

AI-DEV-034 also prohibits runtime activation, live Dify calls, GitHub credential
setup, notification sending, production pipeline execution, and AI-DEV-035
execution.

## Human-Gated Actions

Human approval is required before:

- importing the workflow into n8n
- configuring Dify or n8n credentials
- activating or dry-running the workflow
- turning any manual workflow into a scheduled or webhook workflow
- passing a draft to Codex as an approved task package
- merging PRs or running real auto-merge execution
- archiving tasks or cleaning branches
- sending notifications
- changing production, DB, cron, systemd, timer, dashboard, paid data, or
  trading/order logic

## Acceptance Criteria

AI-DEV-034 is complete when:

- this workflow pack document exists
- all required JSON examples exist
- the n8n workflow export is n8n-style JSON
- the workflow example includes a manual trigger concept
- JSON examples parse with `python3 -m json.tool`
- no example contains real secrets, tokens, or credentials
- the validator checks required files, JSON validity, manual trigger concept,
  credential safety, required safety keywords, and required payload fields
- the validator passes
- no production pipeline, DB, scheduler, secret, notification, dashboard,
  credential, merge, or trading runtime files are modified

## Follow-Up Tasks for AI-DEV-035

AI-DEV-035 should be a separately approved runtime dry-run task that:

- imports the example workflow into a non-production n8n workspace
- configures a human-created sandbox Dify credential
- executes exactly one Manual Trigger dry-run
- captures the ChatGPT-ready summary output
- confirms no prohibited runtime side effects occurred
- keeps activation, production use, notifications, and auto-merge disabled
