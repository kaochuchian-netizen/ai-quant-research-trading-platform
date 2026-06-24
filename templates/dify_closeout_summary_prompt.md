# Dify Prompt: AI-DEV Closeout Summary

## Purpose

Draft a post-merge AI-DEV closeout summary from supplied PR, merge, queue,
branch cleanup, and validation data.

## Required Inputs

- Task id
- PR number and URL
- Merge commit
- Post-merge inspector output
- Post-merge validator output
- Pending queue status
- Completed queue status
- Local and remote branch cleanup status
- Safety boundary text

## Required Output

Produce a closeout summary with:

- completion status
- PR and merge commit
- inspector result
- post-merge validator result
- pending queue summary
- completed queue summary
- branch cleanup summary
- blocker status
- safety confirmation

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

Do not claim archive or branch cleanup happened unless supplied inputs show it.
Do not instruct automatic merge, production execution, notification sending, or
trading.

## Output Format

Return Markdown with these sections:

- Status
- PR
- Merge Commit
- Inspector
- Post-Merge Validator
- Queues
- Branch Cleanup
- Safety
- Blocker

## Non-Goals

Do not perform closeout actions. Do not modify runtime queues. Do not delete
branches. Do not merge PRs. Do not send notifications, publish dashboards, use
paid sources, access secrets, or run production jobs.
