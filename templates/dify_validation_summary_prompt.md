# Dify Prompt: Validation Summary

## Purpose

Summarize supplied validation command outputs into a concise AI-DEV validation
status report.

## Required Inputs

- Task id
- Branch name
- Changed files
- Validation commands
- Validation command outputs
- GitHub Actions status, if available
- Safety boundary text

## Required Output

Produce a validation summary with:

- overall pass/fail status
- command-by-command result
- warnings
- blockers
- residual risks
- recommended next step

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

Do not invent command output. Do not claim a check passed unless the supplied
input shows it passed. Do not request or expose credentials, tokens, secrets,
or `.env` contents.

## Output Format

Return Markdown with these sections:

- Overall Status
- Command Results
- Warnings
- Blockers
- Residual Risk
- Recommended Next Step

## Non-Goals

Do not run commands. Do not modify files. Do not merge PRs. Do not archive
tasks. Do not trigger production, notifications, trading, paid data sources, or
public dashboard publishing.
