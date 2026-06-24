# Dify Prompt: Codex Task Package Generation

## Purpose

Convert an approved AI-DEV task into a Codex-ready task package that can be
copied into Codex for scoped implementation, validation, commit, push, and PR
creation.

## Required Inputs

- Approved task id
- Approved task title
- Task scope
- Target branch name
- Files to create or modify
- Required validation commands
- Commit message
- PR title
- Safety boundary text

## Required Output

Produce a Codex task package with:

- repository preflight checks
- branch instruction
- exact files in scope
- implementation requirements
- validation commands
- commit message
- PR title
- PR body outline
- explicit restrictions
- final reporting checklist

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

The package must instruct Codex not to run `python3 main.py`, not to modify
production, DB, cron, systemd, timer, secrets, credentials, `.env`, Dify runtime
settings, n8n workflows, GitHub credentials, notification systems, or trading
logic.

## Output Format

Return Markdown with these sections:

- Task
- Repo Preflight
- Branch
- Implementation Scope
- Validation
- Commit and PR
- Safety Restrictions
- Completion Report

## Non-Goals

Do not write the code directly. Do not issue merge approval. Do not create or
modify Dify apps, Dify knowledge bases, n8n workflows, production systems, or
credentials.
