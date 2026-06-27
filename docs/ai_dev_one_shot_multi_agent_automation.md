# AI-DEV One-Shot Multi-Agent Automation

## Purpose

This document defines the AI-DEV one-shot automation model for ChatGPT, GitHub,
n8n, Dify, and Codex. The goal is to reduce repeated manual shell instruction
handoffs while keeping the existing AI-DEV safety gates strict.

The expected operator experience is:

1. The user describes one AI-DEV task in ChatGPT.
2. ChatGPT creates a task request, GitHub-facing plan, and approval packet.
3. Codex receives one concise start instruction.
4. Codex implements repo changes, validates, opens a PR, checks gates, and may
   conditionally auto-merge if every safety and validation condition passes.
5. n8n and Dify provide future orchestration and review-package surfaces without
   direct production mutation.
6. The flow stops only when a safety gate, validator failure, GitHub check
   failure, merge conflict, or scope expansion is detected.

AI-DEV-048 is a repo design, contract, runner skeleton, and validator package. It
does not start n8n, call Dify runtime, call ChatGPT or OpenAI APIs, or mutate
production systems.

## Scope

AI-DEV-048 adds:

- one-shot automation governance documentation
- ChatGPT task request contract
- n8n webhook/manual-trigger orchestration template
- Dify review input/output contracts
- Codex one-shot execution request and plan templates
- a dry-run one-shot plan runner
- a read-only validator
- runbook integration notes

## Non-Goals

AI-DEV-048 does not:

- start n8n
- call Dify runtime
- call ChatGPT, OpenAI, or any external API
- read or write secrets, tokens, API keys, credentials, or `.env`
- send LINE, Email, or external notifications
- write production databases
- modify cron, systemd, or timers
- execute `python3 main.py`
- trade, place orders, route orders, or produce order instructions
- auto-merge without all required gates passing
- execute AI-DEV-049

## Agent Roles

### ChatGPT

ChatGPT owns the task-management and review surface:

- convert user intent into an AI-DEV task request
- define scope, acceptance criteria, safety constraints, and stop gates
- produce GitHub-facing metadata such as branch name, PR title, and PR base
- produce the one-shot Codex start instruction summary
- review final summaries and blocked states

ChatGPT App itself is not automatically operated by n8n. Future OpenAI or
ChatGPT API integration requires a separate credential gate and approval task.

### GitHub

GitHub is the source of truth for:

- branch and PR state
- changed files
- checks and validator status
- `mergeStateStatus`
- merge commit identity
- PR audit trail

### n8n

n8n may later orchestrate the lifecycle from webhook or manual trigger:

- receive ChatGPT-approved `task_request`
- route through safety gate checks
- collect GitHub PR and CI status
- prepare Codex execution requests
- call Dify for summary/review package generation
- assemble final ChatGPT-ready status reports

The n8n template remains sanitized and inactive in this task. It must not contain
real credentials, notification nodes, production DB write nodes, cron activation,
or unconditional auto-merge behavior.

### Dify

Dify may later generate:

- task summaries
- implementation summaries
- validation summaries
- PR gate summaries
- safety summaries
- blockers and next-action recommendations
- ChatGPT-ready reports

Dify must not receive secrets and must not perform production mutations.

### Codex

Codex owns repo execution:

- inspect repo context
- create branch
- implement scoped repo changes
- run validators
- create PR
- perform PR gate checks
- conditionally auto-merge only when every gate passes
- run post-merge validation
- close out runtime completed queue using the existing backfill tool
- stop and report if a safety or validation gate fails

## Conditional Auto-Merge Policy

Conditional auto-merge is allowed only when all of these conditions are true:

- PR exists and is not draft
- PR state is `OPEN`
- base branch is `main`
- `mergeStateStatus` is `CLEAN`
- GitHub checks are successful
- required validators return `ok:true`
- `git diff --check` passes
- `git status --short` is clean
- changed files stay inside allowed paths
- no forbidden paths are changed
- no secret, token, API key, credential, or `.env` value is found
- no LINE, Email, or external notification send path is added or executed
- no trading, order placement, order routing, or order execution path is added or executed
- no production DB, cron, systemd, timer, or production pipeline behavior is changed
- task scope remains inside the AI-DEV request

If any condition fails, the flow must stop and report the blocker. It must not
merge.

## Stop Gates

The one-shot runner and operator workflow stop on:

- trading or order execution
- password, API key, token, secret, credential, or `.env` value exposure
- LINE, Email, notification, or external delivery path
- production DB writes
- cron, systemd, timer, or production infra changes
- production-approved runner execution
- GitHub checks not successful
- `mergeStateStatus` not `CLEAN`
- validator failure
- dirty git status
- changed files outside scope
- runtime credential approval required
- closeout dry-run showing unexpected runtime queue mutation

## Lifecycle

1. ChatGPT produces `templates/chatgpt_ai_dev_task_request.example.json` style input.
2. n8n receives the request through webhook or manual trigger and routes safety gates.
3. Codex receives `templates/codex_ai_dev_one_shot_execution_request.example.json` style input.
4. Codex generates a dry-run execution plan using `run_ai_dev_one_shot_plan.py`.
5. Codex implements scoped repo changes and validates.
6. Codex creates PR and checks GitHub gates.
7. Codex conditionally auto-merges only if every gate passes.
8. Codex runs post-merge validation.
9. Codex performs runtime closeout using `backfill_completed_ai_task_record.py` dry-run/apply.
10. Dify can generate a ChatGPT-ready final report from the review contract.

## Closeout Policy

Runtime closeout must use the existing completed-record backfill path:

```bash
python3 scripts/orchestrator/backfill_completed_ai_task_record.py   --task-id AI-DEV-XXX   --pr-number <PR_NUMBER>   --pr-url <PR_URL>   --branch-name <BRANCH>   --base-branch main   --merge-commit <MERGE_COMMIT>   --pretty
```

Only if dry-run is clean may the same command be run with `--apply`. The expected
mutation is limited to runtime `completed_tasks.json`. `pending_tasks.json` must
not be modified unless a future tool explicitly reports a safe, expected pending
entry cleanup.

## Runtime Policy

AI-DEV-048 is repo-only. It does not start n8n, call Dify runtime, call ChatGPT
or OpenAI APIs, use credentials, send notifications, or run production entry
points. Future runtime automation requires separate explicit approval.

## Validation

Run:

```bash
python3 scripts/orchestrator/run_ai_dev_one_shot_plan.py --pretty
python3 scripts/orchestrator/validate_ai_dev_one_shot_multi_agent_automation.py --pretty
python3 scripts/orchestrator/inspect_ai_platform_status.py --pretty
python3 scripts/orchestrator/validate_ai_branch.py --base origin/main --head HEAD --pretty
git diff --check
```
