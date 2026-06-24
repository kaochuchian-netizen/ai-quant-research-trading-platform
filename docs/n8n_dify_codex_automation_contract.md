# n8n Dify Codex Automation Contract

## Purpose

This contract defines how n8n, Dify, ChatGPT, GCP tmux Codex, and GitHub may
exchange AI-DEV automation artifacts without creating a runtime workflow in this
task.

AI-DEV-033 is documentation and JSON examples only. It does not create,
configure, or run an n8n workflow, Dify app, Dify knowledge base, GitHub
credential, production pipeline, notification workflow, database write, or
trading workflow.

## Scope

This contract covers:

- ChatGPT-approved Codex task package payloads
- n8n to Dify draft request and response payloads
- n8n to GCP tmux Codex relay payloads
- n8n GitHub PR status collection payloads
- Dify to ChatGPT-ready summary payloads
- ChatGPT merge gate decision payloads
- n8n auto-merge execution payloads
- post-merge closeout payloads

All examples are static JSON templates under `templates/`.

## Non-Goals

This contract does not:

- create an n8n runtime workflow
- create or configure a Dify runtime app or knowledge base
- configure Dify, n8n, GitHub, LINE, Email, or data-source credentials
- run production-approved runners
- run `python3 main.py`
- modify cron, systemd, or timer jobs
- write to production databases
- send notifications
- execute trading or order logic
- merge, archive, or close out AI-DEV-034

## Roles and Responsibilities

ChatGPT is the PM, approval owner, and merge gate owner. ChatGPT approves task
scope before Codex work starts and returns the final merge gate decision.

n8n is the coordination and transport layer. n8n may collect GitHub status,
relay approved task packages, call Dify for drafts or summaries, and execute a
merge only after ChatGPT decision is `PASS`. n8n does not decide merge itself.

Dify is the drafting and summarization layer. Dify may draft task packages,
summarize PR status, and prepare ChatGPT-ready summaries from supplied inputs.
Dify must never modify the repository, merge PRs, run production, configure
runtime systems, send notifications, or execute shell commands.

GCP tmux Codex is the official repo developer. It performs repository edits,
local validation, commits, pushes, and PR creation only within approved task
scope.

GitHub is the source of truth for PR state, CI status, mergeability, reviews,
changed files, merge commits, and branch state.

## End-to-End Automation Flow

1. ChatGPT approves an AI-DEV task package.
2. n8n receives the approved package and records transport metadata.
3. n8n may ask Dify to draft or refine a Codex-ready package.
4. n8n relays the approved package to GCP tmux Codex.
5. GCP tmux Codex implements the approved scope, validates, commits, pushes,
   and opens a PR.
6. n8n collects GitHub PR and CI status from GitHub.
7. n8n may ask Dify to summarize the PR status into a ChatGPT-ready report.
8. ChatGPT reviews the report and returns a merge gate decision.
9. n8n may auto-merge only when ChatGPT decision is `PASS` and all eligibility
   rules are true.
10. n8n may produce a post-merge closeout payload from GitHub and validation
    evidence. Archive and cleanup remain human-gated unless separately approved.

## ChatGPT-Approved Payload Contract

The approved task package is the only artifact that can authorize Codex to work
on repository files.

Required fields:

- `schema_version`
- `task_id`
- `approved_by`
- `approval_status`
- `repository`
- `branch`
- `base_branch`
- `commit_message`
- `pr_title`
- `files_to_create`
- `files_to_modify`
- `validation_commands`
- `restrictions`
- `human_gates`

`approval_status` must be `APPROVED` before n8n relays the package to Codex.

## n8n to Dify Request / Response Contract

n8n may send Dify a bounded request containing approved task context, safety
rules, and requested output type.

Dify responses are draft artifacts only. They must include:

- source task id
- draft status
- generated Markdown or JSON summary
- assumptions
- missing inputs
- safety confirmation

Dify output must not be treated as approval, merge authorization, or permission
to mutate the repository.

## n8n to GCP tmux Codex Relay Contract

The relay payload instructs the official GCP tmux Codex developer to execute an
approved task package.

Required fields:

- task id and branch
- approved scope
- exact files in scope
- validation commands
- commit message
- PR title and body sections
- prohibited actions
- final report requirements

The relay must state that Codex cannot run production pipelines, touch secrets,
send notifications, execute trading logic, or run AI-DEV-034.

## n8n GitHub PR Status Collection Contract

n8n may collect read-only GitHub evidence:

- PR state
- draft status
- head SHA
- base branch
- mergeable flag
- merge state status
- GitHub Actions status
- changed files
- review state
- merge commit, after merge

GitHub remains the source of truth. n8n must not infer success when GitHub does
not report success.

## Dify to ChatGPT-Ready Summary Contract

Dify may summarize supplied GitHub, validation, and safety evidence into a
ChatGPT-ready merge gate report.

The summary must separate:

- raw GitHub values
- validation evidence
- safety flags
- Dify observations
- fields that still require ChatGPT decision

Dify must not output a merge decision. It may recommend review focus areas only.

## ChatGPT Merge Gate Decision Contract

ChatGPT returns the authoritative merge gate decision.

Allowed decision values:

- `PASS`
- `FAIL`
- `NEEDS_HUMAN_REVIEW`

n8n may auto-merge only after ChatGPT decision is `PASS`. n8n does not decide
merge itself.

## n8n Auto-Merge Execution Contract

n8n may execute merge only when the ChatGPT merge gate decision is `PASS` and
all auto-merge eligibility rules are true.

The merge execution payload must include:

- ChatGPT decision id
- PR number and URL
- expected head SHA
- eligibility checklist
- merge method
- execution status
- GitHub merge result

n8n must abort if any eligibility field is false or unknown.

## Post-Merge Closeout Contract

After merge, n8n may assemble a closeout payload containing:

- task id
- PR number and URL
- merge commit SHA
- post-merge validation evidence
- inspector result
- branch cleanup status, if separately approved
- archive status, if separately approved
- residual blockers

Post-merge closeout reporting does not authorize archive or branch cleanup by
itself.

## Safety Boundaries

Permanent restricted scope:

- trading/order execution
- secrets/.env/credentials
- production DB writes
- production-approved runner
- formal LINE/Email/notification sending
- cron/systemd/timer modification
- Dify/n8n credential setup
- paid data source integration
- public dashboard publishing
- trading/order logic

AI-DEV-033 also prohibits runtime workflow creation, production pipeline
execution, Dify runtime settings changes, Dify knowledge base changes, GitHub
credential changes, and AI-DEV-034 execution.

## Human-Gated Actions

Human approval is required for:

- task scope approval
- repository mutation outside an approved Codex task package
- PR merge decision through ChatGPT
- archive of completed tasks
- branch cleanup
- production deployment
- scheduler changes
- notification sending
- credential setup
- paid data source integration
- public dashboard publishing
- trading/order logic changes

## Auto-Merge Eligibility Rules

All fields must be true before n8n may merge:

- `chatgpt_decision=PASS`
- `github_actions_status=success`
- `merge_state_status=CLEAN`
- `pr_state=OPEN`
- `draft=false`
- `head_sha unchanged`
- `validate_ai_branch=pass`
- `inspector_ok=true`
- `prohibited_scope_touched=false`
- `human_gate_required=false`

If any value is false, missing, stale, or inconsistent with GitHub, n8n must
abort auto-merge and return a report for human review.

## Error Handling

Errors must be reported as structured failure states, not silent retries.

n8n should stop and report when:

- Dify response is malformed
- GitHub status is missing or stale
- head SHA changed after ChatGPT decision
- GitHub Actions is not successful
- merge state is not `CLEAN`
- validation evidence is absent
- prohibited scope is touched
- a human gate is required
- credential, runtime, notification, scheduler, DB, production, or trading
  scope is detected

## Acceptance Criteria

AI-DEV-033 is complete when:

- this contract document exists
- all required sections are present
- all listed JSON examples exist under `templates/`
- JSON examples parse with `python3 -m json.tool`
- the contract states n8n may auto-merge only after ChatGPT decision is `PASS`
- the contract states n8n does not decide merge itself
- the contract states Dify only drafts and summarizes
- the contract states GCP tmux Codex is the official repo developer
- the contract states GitHub is the source of truth
- the contract states ChatGPT is PM, approval, and merge gate owner
- auto-merge eligibility rules include every required field
- permanent human-gated scope is listed
- no runtime workflow, credential, production, notification, database, scheduler,
  or trading files are changed
