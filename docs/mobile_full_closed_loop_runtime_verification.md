# Mobile Full Closed-Loop Runtime Verification

## Purpose

AI-DEV-070 defines the repo-side verification contract for the full mobile to
Codex implementation loop after AI-DEV-069 activation.

Expected flow:

```text
GitHub Mobile Issue
-> scheduled pickup
-> safety filter
-> handoff_created or needs_codex_execution
-> scheduled Codex handoff runner
-> readiness gate
-> Codex executor
-> branch, implementation, validation
-> PR
-> GitHub Actions validate-ai-branch
-> conditional auto-merge when checks pass and mergeStateStatus is CLEAN
-> cleanup
-> post-merge validation
-> sanitized verification artifact
```

This contract records what evidence a verification run must collect. It does
not require or permit mutating a real GitHub Issue by default.

## Source

Use this source identifier for AI-DEV-070 artifacts:

```text
mobile_issue_full_closed_loop_test
```

The source identifies a sanitized runtime verification attempt. It must not be
used to preserve secrets, private runtime payloads, credentials, `.env` values,
or raw Issue bodies containing unsafe material.

## Required Artifact

The example artifact schema lives at:

```text
templates/mobile_full_closed_loop_runtime_verification.example.json
```

A real verification artifact should include:

- `source`
- `run_id`
- `generated_at`
- `mobile_issue`
- `scheduled_pickup`
- `handoff`
- `readiness_gate`
- `codex_executor`
- `implementation`
- `pull_request`
- `github_actions`
- `conditional_auto_merge`
- `cleanup`
- `post_merge_validation`
- `validation_summary`
- `changed_files`
- `validations`
- `side_effects`
- `safety_confirmation`
- `overall_status`

The initial placeholder for `validation_summary` is:

```text
validation_summary_placeholder
```

Replace it only with sanitized validation evidence from a completed run.

## GitHub Issue Mutation Policy

Real GitHub Issue mutation is disabled by default.

The verification path must not comment on, close, reopen, relabel, assign, or
otherwise modify a real Issue unless an existing repository contract explicitly
allows that exact action and the run artifact records the permission source.

Default flags:

```text
issue_comment_created=false
issue_labels_changed=false
github_issue_mutated=false
```

## Safety Boundary

The verification must not:

- read, print, summarize, or modify secrets, tokens, credentials, passwords,
  `.env`, private runtime payloads, or production configuration
- send LINE, email, webhook, or other notifications
- trade or place orders
- mutate production databases
- control n8n, Dify, cron, systemd, timers, or production pipelines
- execute shell copied from Issue or handoff text
- perform unconditional auto-merge

The Codex executor may implement repo-side requested deliverables only through
the sanitized handoff contract and normal repository validation workflow.

## Verification Gates

### Scheduled Pickup

The scheduled pickup evidence must show that the candidate passed required
labels and safety filters, and reached one of these non-terminal implementation
states:

- `handoff_created`
- `needs_codex_execution`

The pickup artifact alone is not completion of requested deliverables.

### Readiness Gate

The readiness gate must record:

- whether it was called
- decision
- safe-to-call-executor flag
- safe-to-schedule flag
- blockers or warnings

The executor must not be called when readiness reports unsafe status.

### Codex Executor

Executor evidence must record:

- whether it was called
- decision
- exit status or sanitized return code
- implementation completion flag
- changed files from actual implementation

`implementation_completed=true` requires at least one changed file outside
`docs/mobile_issue_handoffs/`.

### Branch And PR

Implementation evidence must record the branch name, changed files, local
validation commands, and PR URL or number when a PR is created.

Changed files must stay inside the requested scope and allowed repository
paths.

### GitHub Actions Gate

The PR gate must include `validate-ai-branch` or the relevant required checks.
Conditional auto-merge is allowed only when all of these are true:

- required checks pass
- PR is not draft
- `mergeStateStatus` is `CLEAN`
- changed files remain in scope
- local validations passed
- no blocked side effects occurred

If any condition is missing or false, `conditional_auto_merge.performed` must be
false and the artifact must list the blocking reasons.

### Post-Merge Validation

Post-merge validation is required only after a real merge. It should record the
post-merge validator command, result, branch state, and merge commit when
available.

For a repo-only dry-run or blocked verification, record the post-merge step as
`not_run` with an explicit reason.

## Validation

For this repo-side contract and example template, use safe focused validation:

```bash
python3 -m json.tool templates/mobile_full_closed_loop_runtime_verification.example.json >/tmp/mobile_full_closed_loop_runtime_verification.example.json
git diff --check -- docs/mobile_full_closed_loop_runtime_verification.md templates/mobile_full_closed_loop_runtime_verification.example.json
```

For a real implementation PR produced by the closed loop, also run the normal
repository-side validators relevant to the changed files, including
`validate-ai-branch` where applicable. Do not run `python3 main.py` as part of
this verification contract.

## Completion Criteria

A full closed-loop verification is complete only when the artifact shows:

- scheduled pickup selected or packaged the mobile Issue safely
- readiness gate passed
- Codex executor completed actual repo-side implementation
- implementation changed files match requested deliverables
- local validations passed
- PR required checks passed
- conditional auto-merge either completed safely or was explicitly blocked
- post-merge validation ran after a real merge, or was explicitly not run for a
  documented non-merge outcome
- all side-effect safety flags remain false unless an existing repo contract
  explicitly permits the action and the artifact records that permission
