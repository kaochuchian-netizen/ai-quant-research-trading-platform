# AI DevOps Orchestrator

This directory contains low-risk, reviewable assets for the AI DevOps Orchestrator workflow.

The initial Phase C implementation is intentionally limited to static templates, state formats, and read-only validation collection. It does not execute Codex autonomously, does not send email, does not create an approval endpoint, and does not run production commands.

## Current scope

- Define task state format.
- Define review bundle format.
- Define email summary draft format.
- Provide a read-only validation snapshot tool.
- Keep all Orchestrator artifacts human-reviewable.
- Preserve production safety gates.

## Explicit non-goals for this phase

- No approval endpoint.
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
- `templates/email_summary_template.md`: static email summary draft template with continue / pause approval actions.
- `../scripts/orchestrator/collect_validation_snapshot.py`: read-only tool that collects Git status, diff metadata, branch / HEAD, optional in-memory Python syntax validation, and forbidden-path flags.

Future phases may add email draft generation, email sending, approval-state handling, and carefully scoped automation, but each addition should remain scoped, reviewable, and guarded by explicit safety rules.
