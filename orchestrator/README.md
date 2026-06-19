# AI DevOps Orchestrator

This directory contains low-risk, reviewable assets for the AI DevOps Orchestrator workflow.

The Phase C implementation is intentionally scoped to templates, state formats, read-only validation collection, controlled notice rendering, VM-side validation, and explicit user-approved stage notifications. It does not create an approval endpoint, does not run production commands, and does not execute trading or formal pipelines.

## Current scope

- Define task state format.
- Define VM validation task state format.
- Define review bundle format.
- Define email summary format.
- Provide a read-only validation snapshot tool.
- Provide a stage notification runner that defaults to preview mode.
- Provide a VM-side validation runner for allowlisted checks.
- Allow VM-side notification only when explicitly requested with `--notify`.
- Allow VM-side email delivery only when explicitly requested with both `--notify` and `--send`.
- Allow controlled `git pull --ff-only` only when explicitly requested with `--pull` and task state allows it.
- Keep all Orchestrator artifacts human-reviewable.
- Preserve production safety gates.

## Explicit non-goals for this phase

- No approval endpoint.
- No automatic production email approval handling.
- No automatic Git push or merge from approval actions.
- No production database changes.
- No migration execution.
- No LINE sending.
- No cron changes.
- No formal pipeline execution.
- No automatic order placement.

## Files

- `templates/task_state.example.json`: example task state file for a single Orchestrator task.
- `templates/task_state.vm_validation.example.json`: example task state file for VM-side validation tasks.
- `templates/review_bundle_template.md`: markdown template for summarizing task results before approval.
- `templates/email_summary_template.md`: static email summary draft template with continue / pause approval actions.
- `../docs/ai_devops_orchestrator_phase_c_design.md`: Phase C autonomous-assisted workflow design.
- `../docs/orchestrator_vm_stage_runner_design.md`: Phase C-6 VM-side stage validation runner design.
- `../scripts/orchestrator/collect_validation_snapshot.py`: read-only tool that collects Git status, diff metadata, branch / HEAD, optional in-memory Python syntax validation, and forbidden-path flags.
- `../scripts/orchestrator/render_notice_from_template.py`: renders a notice from the email summary template and task state.
- `../scripts/orchestrator/notify_stage_report.py`: sends or previews an orchestrator stage report through the configured mail adapter.
- `../scripts/orchestrator/run_stage_notification.py`: one-shot stage notification runner that chains snapshot, notice rendering, and preview/send notification.
- `../scripts/orchestrator/run_vm_stage_validation.py`: VM-side validation runner that checks branch / clean tree, optionally performs controlled `git pull --ff-only`, executes allowlisted validation commands from task state, and can optionally trigger stage notification.

## VM-side validation runner safety defaults

`run_vm_stage_validation.py` is designed with conservative defaults:

- `--pull` is required before any `git pull --ff-only` can run.
- Task state must also set `vm_validation.sync.git_pull_allowed=true` before `--pull` is accepted.
- `--notify` is required before any stage notification is triggered.
- `--send` is only accepted together with `--notify`.
- Without `--send`, notification remains preview mode.
- The runner does not use `shell=True`.
- The runner only executes allowlisted validation command types.

Future phases may add approval-state handling and carefully scoped automation, but each addition should remain scoped, reviewable, and guarded by explicit safety rules.
