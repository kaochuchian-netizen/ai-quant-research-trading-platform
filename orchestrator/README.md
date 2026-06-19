# AI DevOps Orchestrator

This directory contains low-risk, reviewable assets for the AI DevOps Orchestrator workflow.

The initial Phase C implementation is intentionally limited to static templates and state formats. It does not execute Codex, does not send email, does not create an approval endpoint, and does not run production commands.

## Current scope

- Define task state format.
- Define review bundle format.
- Keep all Orchestrator artifacts human-reviewable.
- Preserve production safety gates.

## Explicit non-goals for this phase

- No shell scripts.
- No endpoint.
- No email sending.
- No automatic Git push or merge.
- No production database changes.
- No migration execution.
- No LINE sending.
- No cron changes.
- No formal pipeline execution.
- No automatic order placement.

## Files

- `templates/task_state.example.json`: example task state file for a single Orchestrator task.
- `templates/review_bundle_template.md`: markdown template for summarizing task results before approval.

Future phases may add read-only collection scripts, email draft generation, and approval-state handling, but each addition should remain scoped, reviewable, and guarded by explicit safety rules.
