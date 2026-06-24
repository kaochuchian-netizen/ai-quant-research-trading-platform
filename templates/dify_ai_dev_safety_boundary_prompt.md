# Dify Prompt: AI-DEV Safety Boundary

## Purpose

Provide reusable AI-DEV safety boundary text for Dify prompts, task drafts,
Codex packages, PR reviews, validation summaries, and closeout summaries.

## Required Inputs

- Task id or workflow name
- Requested action
- Files or systems in scope
- Human approval status
- Known risk flags

## Required Output

Produce a safety boundary section that identifies:

- allowed actions
- prohibited actions
- human-gated actions
- required validation
- blocker conditions

## Safety Rules

Prohibited:

- trading / order execution
- secrets / `.env` / credentials
- production DB writes
- production-approved runner execution
- auto PR merge
- formal LINE / Email / notification sending
- paid data source integration
- public dashboard publishing

Additional prohibited actions unless explicitly approved by a human:

- production pipeline changes
- cron, systemd, or timer changes
- Dify runtime app or knowledge base creation
- n8n workflow creation
- GitHub credential setup
- runtime queue mutation
- branch cleanup
- completed task archive

## Output Format

Return Markdown with these sections:

- Allowed
- Prohibited
- Human-Gated
- Required Validation
- Stop Conditions

## Non-Goals

Do not authorize execution. Do not replace human approval. Do not create Dify
resources, n8n workflows, GitHub credentials, production jobs, notification
flows, paid source integrations, public dashboards, or trading actions.
