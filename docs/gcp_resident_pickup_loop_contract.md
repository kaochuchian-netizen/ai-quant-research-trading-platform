# GCP Resident Pickup Loop Contract

## Purpose

AI-DEV-054 defines the repo-side contract for a future GCP resident pickup loop.
The loop consumes merged handoff requests from GitHub-visible repository state
without requiring Codex App to SSH into GCP or execute runtime actions directly.

This document is a contract and validation aid only. It does not start runtime
services, call n8n, call Dify, call OpenAI, send notifications, place orders, or
modify production data.

## Pickup Location

The resident loop should only pick up requests from merged repository content on
the default branch. A request is eligible when:

- the request file is present in a reviewed and merged PR
- the request validator passes on the GCP host
- the request action is allowlisted
- the request id has not already reached a terminal result state

The repo-side examples use:

```text
templates/gcp_runtime_relay_request.example.json
```

A production resident loop may map approved request packages into a local GCP
state path such as:

```text
~/.local/state/stock-ai-orchestrator/runtime_relay/requests/
```

Raw runtime output must stay outside git. Sanitized results may be returned in a
separate PR after validation.

## Request Validation

The pickup loop must validate before any runtime boundary is crossed:

```bash
python3 scripts/orchestrator/validate_gcp_runtime_relay_request.py --input <request.json> --pretty
```

Validation must reject requests that:

- omit required identity, source, validation, action, result, audit, or closeout
  fields
- request trading, order execution, external delivery, production database
  mutation, scheduler mutation, credential disclosure, or direct Codex App
  connection
- include sensitive value patterns
- disable dry-run defaults without separate approval
- lack idempotency or retry policy

Validation failure is terminal for that pickup attempt. The loop should write a
sanitized blocked result and stop.

## Dry-Run And Runtime Boundary

The default execution mode is `dry_run`. In dry-run mode the loop may:

- read the merged request
- validate the request
- compute a local execution plan
- check idempotency state
- write a sanitized result artifact

Dry-run mode must not:

- invoke n8n runtime workflows
- call Dify or OpenAI APIs
- send LINE, Email, or any notification
- trade or place orders
- mutate production databases
- modify production n8n, cron, systemd, or scheduler state

Runtime execution is outside this repo-side task. A future GCP-owned change must
explicitly define the approval gate and runtime implementation before any action
can move past dry-run planning.

## Sanitized Result Artifact

Every pickup attempt should produce a sanitized result object. The result must
contain:

- request id and AI-DEV id
- terminal status: `succeeded`, `blocked`, `skipped`, or `failed`
- whether runtime work was executed
- validation summary without sensitive values
- idempotency decision
- local-only artifact references
- safety gate decisions
- retry count and final retry decision
- closeout checklist state

The repo-side example is:

```text
templates/gcp_runtime_relay_result.example.json
```

Validate the result before it is proposed for git:

```bash
python3 scripts/orchestrator/validate_gcp_runtime_relay_result.py --input <result.json> --pretty
```

## Failure Handling

The loop should fail closed:

- validation error: write `blocked` result with validation errors only
- missing action mapping: write `blocked` result
- safety gate hit: write `blocked` result and do not cross runtime boundary
- transient runtime relay error: retry according to request retry policy
- repeated transient failure: write `failed` result after retry budget is spent
- duplicate terminal request id: write `skipped` result and reference the
  existing terminal artifact

Error messages must be sanitized and must not include environment values,
credentials, tokens, request headers, raw workflow payloads, or production config
contents.

## Idempotency

The resident loop must key idempotency by:

- `relay_request_id`
- `ai_dev_id`
- `source.merge_commit`
- `action.name`

Before processing, the loop should check local terminal state for the same key.
If a terminal result already exists, the loop should skip execution and emit a
sanitized duplicate report. Partial or interrupted state may be retried only
when the retry policy allows it and no terminal artifact exists.

## Audit Trail

The loop should record a local audit event for each state transition:

- `picked_up`
- `validated`
- `planned`
- `runtime_boundary_blocked`
- `relay_called` when future approved runtime mode exists
- `result_written`
- `closed_out`

Audit records may include timestamps, request id, action id, status, and local
artifact references. They must not include sensitive values or raw runtime
outputs.

## Closeout Procedure

Closeout is complete only when:

- request validation result is recorded
- result validation passes
- runtime side effects are explicitly marked
- local-only raw output paths, if any, are referenced without contents
- sanitized artifact is ready for a repo-side PR
- duplicate or retry state is finalized
- safety confirmation says no forbidden runtime action occurred

For AI-DEV-054, closeout remains dry-run/spec-level only.
