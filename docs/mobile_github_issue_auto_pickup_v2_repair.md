# Mobile GitHub Issue Auto-Pickup V2 Repair

## Background

AI-DEV-063 introduced the mobile GitHub Issue auto-pickup v1 path. It could read
eligible GitHub Issues and, with `approved-auto-run`, create a sanitized repo
artifact PR. Issue #62 proved the limitation: PR #63 merged only
`docs/mobile_issue_auto_runs/issue_62_mobile-auto-pickup-20260628T003112Z.json`
and did not implement the requested Daily Report Forecast V1 contract.

V1 also reported `decision=executed_repo_only`, which was too strong because no
requested deliverables were implemented.

## V1 Limitation

The deterministic mobile runner does not perform Codex reasoning or code
generation from the Issue body. The Issue body is task description only, never a
patch, shell command, or direct execution instruction. Therefore artifact-only
PRs are audit records, not completed repo-side work.

## V2 Decision Semantics

- `artifact_recorded`: only a sanitized artifact was created. The requested task
  remains pending.
- `handoff_created`: a sanitized GCP Codex handoff was created and can suppress
  duplicate handoff PRs. The requested implementation remains pending.
- `needs_codex_execution`: the Issue is eligible but needs a Codex coding run.
- `executed_repo_only`: reserved for a future path that actually implements,
  validates, creates a PR, and merges the requested deliverables.
- `rejected`: the Issue requests blocked actions or fails required labels.
- `already_processed`: a v2 idempotency record says this exact scope should not
  be repeated.

`executed_repo_only` is valid only when `idempotency_completion_scope` is
`actual_task_implemented`, `implementation_status` is `implemented_merged`, and
`safe_to_mark_processed` is true.

## Safety-Negative Phrases

V2 distinguishes prohibited requests from safety constraints. Text such as
`no Dify`, `do not call OpenAI`, `do not send notification`, `do not trade`, and
`do not modify cron/systemd` is allowed as a safety constraint. Positive action
requests such as `call Dify`, `use OpenAI API`, `send LINE notification`,
`place orders`, or `modify systemd timer` are still rejected.

## GCP Codex Handoff Flow

When a mobile Issue is eligible but cannot be completed deterministically, the
runner can write a sanitized handoff under:

```text
docs/mobile_issue_handoffs/
```

The handoff includes the Issue number and URL, title, sanitized task summary,
required labels, suggested branch, requested files, validation checklist, safety
constraints, and explicit GCP resident Codex instructions. It must not include
secrets, private runtime payloads, or raw shell commands from the Issue as
executable instructions.

## Idempotency

V2 idempotency stores scoped records. Artifact and handoff records can suppress
duplicate artifact or handoff PRs, but they do not mark the requested task fully
processed. Only an actual implementation record with
`safe_to_mark_processed=true` can mark the Issue scope complete.

The v1 `processed_keys` entry created by PR #63 is not treated as completion for
Issue #62 because it lacks a v2 completion scope.

## Issue #62 Status

After this repair, Issue #62 should not be rejected for safety-negative text and
must not be reported as `executed_repo_only`. It should be treated as
`needs_codex_execution` in read-only dry-run mode or `handoff_created` when the
handoff path is committed by the approved runner.

This repair adds a sanitized handoff at:

```text
docs/mobile_issue_handoffs/issue_62_ai_dev_064_handoff.md
```

## Safe Reprocessing Or Superseding

To reprocess Issue #62 safely, run the mobile pickup in read-only dry-run mode
first and confirm the decision is `needs_codex_execution` or `handoff_created`.
If a later Daily Report Forecast implementation PR merges, record that outcome
with `idempotency_completion_scope=actual_task_implemented`.

If a newer mobile Issue supersedes #62, create a new Issue with the same required
labels and mention that #62 is superseded. Do not mutate #62 automatically from
the pickup runner.

## Still Disabled

The repaired path still does not enable comment-back, label mutation, Issue
closeout, runtime actions, production pipelines, n8n control, Dify calls, OpenAI
API calls, notifications, production DB mutation, trading, or arbitrary shell
execution from Issue text.

## Mobile Expectation

From mobile, an approved repo-only Issue can now create an honest handoff for
GCP resident Codex. The user should expect the mobile pickup to classify and
package work, not to claim code implementation unless a future implementation
runner can prove the requested deliverables were merged.
