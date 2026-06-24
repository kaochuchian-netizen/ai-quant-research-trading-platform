# Dify Prompt: PR Review Draft

## Purpose

Draft a focused PR review from supplied PR metadata, changed files, validation
results, and safety boundaries. The review should help a human decide whether
the PR is ready for merge review.

## Required Inputs

- PR number and URL
- PR title and body
- Changed files
- Diff summary
- GitHub Actions status
- Local validation output
- Known task scope
- Safety boundary text

## Required Output

Produce a review draft with:

- findings ordered by severity
- missing validation, if any
- scope drift assessment
- safety boundary assessment
- merge-gate recommendation for a human reviewer

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

Do not recommend automatic merge. Do not ask for secrets. Do not suggest
production execution, notification sending, trading, or paid source activation.

## Output Format

Return Markdown with these sections:

- Findings
- Validation Gaps
- Scope Review
- Safety Review
- Human Merge-Gate Recommendation
- Open Questions

If there are no findings, say so clearly and list residual risks.

## Non-Goals

Do not perform the review action on GitHub. Do not merge, approve, request
changes, archive, delete branches, or execute validation commands.
