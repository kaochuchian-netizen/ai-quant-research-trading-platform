# GCP Runtime Runner Handoff Package

## Purpose

AI-DEV-053 defines a repo-side runtime handoff package for work that cannot be
performed directly from Codex App. The current Codex App session is not a GCP
runtime operator and should not be designed to open a direct shell connection to
GCP when the sandbox blocks that path.

This package lets Codex App contribute a reviewed GitHub change that a future
GCP resident runner or n8n relay can pick up from the repository. Runtime work
that needs GCP local state, n8n, or Dify remains on the GCP side.

## Why Codex App Does Not Directly Connect To GCP

The observed connection failure is:

```text
ssh: connect to host 35.201.242.167 port 22: Operation not permitted
```

That is a sandbox/network boundary, not a task failure. The correct design is to
avoid direct Codex App to GCP runtime execution and instead use GitHub as the
handoff surface.

AI-DEV-053 does not attempt to fix the connection, request escalation, read
connection material, or start runtime services.

## Responsibilities

### Codex App

Codex App owns repo-side artifacts:

- create and validate handoff request examples
- document the handoff lifecycle
- provide non-destructive runner skeletons
- open and merge PRs only after validation gates pass
- never include raw local-only runtime outputs in git

### GitHub

GitHub is the coordination surface for:

- reviewed request contracts
- PR checks and merge gates
- sanitized result packages
- historical audit trail

### GCP Resident Runner

A future GCP resident runner may:

- read a merged handoff request from the repo
- validate the request locally
- perform approved GCP-local runtime work
- write local-only raw outputs under runtime state paths
- publish only sanitized summaries back through a future repo PR

### n8n Relay

A future n8n relay may:

- receive the validated request
- route safety gates
- call approved runtime workflows
- collect sanitized status summaries

It must not send notifications, mutate production data, trade, or expose secret
values.

## Runtime Handoff Lifecycle

- `requested`: repo-side request exists in a PR.
- `validated`: request validator passed.
- `merged`: request PR merged to `main`.
- `picked_up`: GCP resident runner or n8n relay has read the merged request.
- `running`: approved local runtime work is in progress on GCP.
- `succeeded`: sanitized result summary is available.
- `blocked`: safety gate, missing mapping, or runtime preflight blocked the run.
- `skipped`: runner intentionally skipped runtime work because no approved action
  existed.

## Safety Gates

The handoff request and runner must block:

- trading, order placement, and order execution
- reading, printing, committing, or creating sensitive values
- LINE, Email, notification, or external delivery
- production database mutation
- scheduler or production infra mutation
- raw runtime output committed to git
- direct Codex App connection attempts to GCP runtime

## Local-Only Runtime Outputs

Raw runtime outputs belong only in GCP local runtime state paths such as:

```text
~/.local/state/stock-ai-orchestrator/runtime_exports/<ai-dev-id>/
```

Raw outputs must not be committed. A later task may package a sanitized summary
only after validation confirms that no sensitive value is present.

## Sanitized Runtime Result Policy

A sanitized result package should include:

- request id and AI-DEV id
- runtime status
- whether runtime work was executed
- whether fallback or blocked policy was used
- output paths described as local-only references
- safety gate results
- secret scan counts without values

## No-Manual-Terminal Workflow

The intended long-term path is:

1. Codex App commits a handoff request to GitHub.
2. GitHub checks validate the request.
3. Conditional auto-merge completes if gates pass.
4. GCP resident runner or n8n relay picks up the merged request.
5. Runtime outputs stay local-only.
6. A sanitized result package returns through a separate PR.

This avoids repeated manual terminal copying while keeping the runtime boundary
explicit.

## Fallback / Blocked Report Policy

If the GCP runner cannot find an approved workflow, runtime mapping, or safe
credential configuration, it should produce a blocked report instead of forcing a
runtime call. Blocked reports are valid outputs when they prevent unsafe action.

## Follow-Up Tasks

AI-DEV-054 should define the GCP resident pickup loop or n8n relay contract that
reads merged handoff requests without requiring Codex App to connect to GCP.

AI-DEV-055 may define sanitized runtime result packaging once the pickup path is
available.

## Validation

Run:

```bash
python3 -m py_compile scripts/orchestrator/validate_gcp_runtime_handoff_request.py scripts/orchestrator/gcp_runtime_handoff_runner.py
python3 scripts/orchestrator/validate_gcp_runtime_handoff_request.py --request templates/gcp_runtime_handoff_request.example.json --pretty
python3 scripts/orchestrator/gcp_runtime_handoff_runner.py --request templates/gcp_runtime_handoff_request.example.json --pretty
python3 scripts/orchestrator/inspect_ai_platform_status.py --pretty
python3 scripts/orchestrator/validate_ai_branch.py --pretty
git diff --check
```

## Runtime Impact

AI-DEV-053 is repo-side only. It does not start n8n, call Dify runtime, connect
to GCP, send external delivery, trade, write production data, or read sensitive
values.
