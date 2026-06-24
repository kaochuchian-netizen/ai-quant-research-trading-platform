# Dify AI-DEV Knowledge Base Plan and Prompt Pack

## Purpose

This document defines a documentation-only plan for a future Dify AI-DEV
knowledge base and prompt pack. The goal is to reduce repeated Codex context
loading by giving Dify reusable source documents and prompt templates for safe
AI-DEV planning, review, validation, and closeout drafting.

AI-DEV-032 does not create a Dify knowledge base, Dify app, n8n workflow, GitHub
credential, runtime integration, production job, notification workflow, or
trading workflow.

## Scope

This plan covers:

- AI-DEV task generation
- Codex task package generation
- PR review drafting
- validation summary drafting
- closeout summary drafting
- safety boundary reuse
- Dify knowledge base source document planning
- prompt template inventory
- read-only integration points for n8n, Codex, and GitHub

The current deliverable is limited to planning documents and Markdown prompt
templates that can be copied into Dify later.

## Non-Goals

AI-DEV-032 does not:

- create or configure a Dify knowledge base
- create or configure a Dify app
- create or configure an n8n workflow
- configure GitHub credentials
- modify runtime queue files
- modify production pipeline code
- write to production databases
- modify cron, systemd, or timer configuration
- read or modify secrets, `.env`, credentials, keys, or tokens
- send LINE, Email, or other notifications
- execute trading or order logic
- merge or archive future tasks
- execute AI-DEV-033

## Dify Knowledge Base Source Documents

The future Dify knowledge base should use curated, documentation-only source
documents. Candidate sources include:

- `docs/ai_dev_closed_loop_runbook.md`
- `docs/ai_development_closed_loop.md`
- `docs/dify_n8n_automation_operating_model.md`
- `docs/n8n_github_pr_status_workflow_spec.md`
- `docs/roadmap_v6_reconciliation.md`
- `docs/orchestrator_operations_index.md`
- `docs/orchestrator_current_state_summary.md`
- `docs/source_inventory_registry.md`
- `docs/schema_registry_governance.md`
- `templates/n8n_pr_status_report.example.json`
- this AI-DEV-032 plan document
- the AI-DEV-032 prompt templates in `templates/`

Knowledge base updates should be human-approved and versioned through PRs. Dify
should treat these documents as retrieval context only, not as permission to
perform runtime actions.

## Dify Role in the AI-DEV Workflow

Dify is the planning and drafting layer.

Dify may:

- generate candidate AI-DEV tasks
- assemble Codex-ready task packages
- summarize GitHub PR state from provided inputs
- draft validation summaries from provided command output
- draft closeout summaries from provided post-merge status
- reuse safety boundaries across prompts
- identify missing context that a human or Codex must supply

Dify must not:

- mutate the repository
- call production services
- execute shell commands
- approve or merge PRs
- archive completed tasks
- create credentials or workflows
- send notifications
- trade or place orders

## Prompt Pack Inventory

The prompt pack contains these templates:

- `templates/dify_ai_dev_task_generation_prompt.md`
- `templates/dify_codex_task_package_prompt.md`
- `templates/dify_pr_review_prompt.md`
- `templates/dify_validation_summary_prompt.md`
- `templates/dify_closeout_summary_prompt.md`
- `templates/dify_ai_dev_safety_boundary_prompt.md`

Each template is Markdown-first and can be copied directly into Dify as a
prompt. Runtime variables should be supplied by Dify workflow inputs or human
operators.

## Input / Output Contracts

### Task Generation Input

Expected inputs:

- roadmap context
- current AI-DEV status
- desired task area
- known blockers
- safety boundary prompt

Expected output:

- task id proposal
- title
- purpose
- scope
- non-goals
- files likely to change
- validation checklist
- safety notes

### Codex Task Package Input

Expected inputs:

- approved task title and scope
- target branch name
- files to create or modify
- validation commands
- prohibited actions

Expected output:

- Codex-ready task instruction
- branch name
- commit message
- PR title
- PR body outline
- validation commands
- explicit restrictions

### PR Review Input

Expected inputs:

- PR URL
- changed files
- diff summary
- validation output
- safety boundary prompt

Expected output:

- findings
- risks
- missing validation
- safety boundary assessment
- human merge-gate recommendation

### Validation Summary Input

Expected inputs:

- command list
- command outputs
- changed files
- risk flags

Expected output:

- pass/fail status
- notable warnings
- blockers
- residual risk
- recommended next step

### Closeout Summary Input

Expected inputs:

- merged PR metadata
- merge commit
- post-merge validator output
- queue status
- branch cleanup status

Expected output:

- closeout status
- PR and merge commit
- inspector result
- post-merge validation result
- queue summary
- branch cleanup summary
- blocker

## Safety Boundaries

All Dify prompts must include the following prohibited actions.

Prohibited:

- trading / order execution
- secrets / `.env` / credentials
- production DB writes
- production-approved runner execution
- auto PR merge
- formal LINE / Email / notification sending
- paid data source integration
- public dashboard publishing

Additional AI-DEV restrictions:

- do not execute `python3 main.py`
- do not mutate runtime queues unless explicitly approved for closeout
- do not create Dify apps or knowledge bases from this planning task
- do not create n8n workflows from this planning task
- do not configure GitHub credentials
- do not bypass GitHub Actions or validators

## Human-Gated Actions

Human approval is required before:

- PR merge
- branch cleanup
- completed task archive
- repository mutation through Codex
- production pipeline changes
- scheduler changes
- notification workflow changes
- public dashboard deployment
- paid source integration
- any credential or secret handling

Dify may draft instructions for these actions, but it must label them as
human-gated and must not present the draft as already approved.

## n8n Integration

n8n may provide read-only status inputs to Dify, including:

- PR number and URL
- branch and base branch
- mergeable state
- merge state status
- GitHub Actions status
- changed files
- risk flags
- validation report links

n8n must not use this prompt pack to auto-merge PRs, mutate repositories, send
notifications, configure credentials, or execute production workflows.

## Codex Integration

Codex remains the implementation and local validation layer. Dify may generate a
Codex task package, but Codex must still:

- inspect the repo before editing
- keep changes scoped
- run the requested validation commands
- commit only explicit task files
- open a PR for human review
- avoid prohibited operations

Dify output should be treated as draft instructions, not as authority to bypass
Codex safety checks.

## GitHub Integration

GitHub remains the source of truth for:

- PR state
- branch comparison
- review comments
- GitHub Actions results
- mergeability
- merge commit
- branch cleanup evidence

Dify may summarize GitHub status from supplied inputs. It must not own GitHub
credentials or perform GitHub mutations for this planning task.

## Validation Checklist

AI-DEV-032 is complete when:

- this plan document exists
- all prompt templates exist under `templates/`
- each prompt template contains Purpose, Required Inputs, Required Output,
  Safety Rules, Output format, and Non-goals
- prohibited actions are listed explicitly
- Dify runtime creation is excluded
- n8n workflow creation is excluded
- GitHub credential setup is excluded
- no production, DB, cron, secrets, notification, or trading files are changed
- `git diff --check` passes
- `python3 -m py_compile scripts/orchestrator/validate_ai_branch.py` passes
- `python3 scripts/orchestrator/validate_ai_branch.py --base origin/main --head HEAD --pretty` passes
- `python3 scripts/orchestrator/inspect_ai_platform_status.py --pretty` passes

## Future Roadmap Notes

Future tasks may separately define:

- Dify knowledge base import procedure
- Dify app configuration design
- n8n to Dify read-only status handoff
- GitHub PR review assistant prototype
- merge gate assistant with explicit human approval
- closeout assistant with explicit human approval
- dashboard payload drafting workflow

Each future task must restate its safety boundary and must not inherit runtime
permission from this planning document.
