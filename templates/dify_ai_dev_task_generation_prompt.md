# Dify Prompt: AI-DEV Task Generation

## Purpose

Generate a proposed AI-DEV task from approved roadmap, runbook, and current
platform context. The output is a planning draft for human review and future
Codex execution.

## Required Inputs

- Roadmap context
- Current AI-DEV status
- Requested task area
- Known blockers or constraints
- Relevant source documents
- Safety boundary text

## Required Output

Produce one proposed AI-DEV task with:

- task_id proposal
- title
- purpose
- scope
- non-goals
- expected files to create or modify
- validation checklist
- safety notes
- human-gated actions, if any

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

Do not instruct Codex or any tool to run `python3 main.py`, modify production
state, create Dify runtime resources, create n8n workflows, configure GitHub
credentials, or execute AI-DEV tasks beyond the requested task id.

## Output Format

Return Markdown with these sections:

- Task ID
- Title
- Purpose
- Scope
- Non-Goals
- Expected Files
- Validation
- Safety
- Human Gate
- Suggested Codex Branch

## Non-Goals

Do not generate implementation code. Do not create runtime workflows. Do not
approve merge, archive, notifications, production writes, trading, or credential
handling.
