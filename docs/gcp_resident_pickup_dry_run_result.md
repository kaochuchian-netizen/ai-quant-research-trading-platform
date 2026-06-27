# GCP Resident Pickup Dry-Run Result

## Purpose

AI-DEV-055 proves the first safe GCP resident pickup loop dry-run artifact. It
shows that a merged repo-side request can be validated, treated as picked up,
converted into a sanitized result artifact, and validated again without crossing
any runtime boundary.

## Scope

This task adds a dry-run pickup helper, request example, result example,
validator, and runbook. It extends the AI-DEV-053 handoff package and AI-DEV-054
resident pickup / n8n relay contract.

## Non-Goals

AI-DEV-055 does not start n8n, call Dify, call OpenAI or ChatGPT APIs, send LINE
or Email, trade, place orders, mutate production databases, modify cron or
systemd, or inspect private runtime payloads.

## Dry-Run Pickup Flow

1. Read `templates/gcp_resident_pickup_request.example.json`.
2. Confirm the request is dry-run only.
3. Confirm handoff and relay request validation are represented as required
   preconditions.
4. Build a sanitized pickup result artifact.
5. Validate the result with `validate_gcp_resident_pickup_result.py`.
6. Keep any future raw runtime output local-only and out of git.

## Input Contract

The pickup request records:

- pickup request id and AI-DEV id
- source repository and required main commit
- handoff and relay request paths
- dry-run execution mode
- idempotency key fields
- safety gates
- sanitized result output policy

## Output Artifact

The result artifact records:

- terminal status
- dry-run execution flags
- validation summary
- pickup outcome
- local-only artifact references
- idempotency decision
- safety gate result
- audit events
- closeout checklist

The example result is safe for repo review and contains no raw runtime output.

## Idempotency Behavior

The idempotency key is:

```text
pickup_request_id + ai_dev_id + source.required_main_commit + dry_run_pickup_and_write_sanitized_result
```

A future resident runner should skip duplicate terminal results instead of
repeating runtime work.

## Failure Handling

Validation errors produce a `blocked` result. Missing mappings, unsafe runtime
requests, sensitive value patterns, or forbidden actions should also produce a
sanitized blocked result without crossing the runtime boundary.

## Closeout Behavior

Closeout is complete when the request is validated, the sanitized result is
validated, safety flags confirm no runtime action occurred, and the result is
ready for a repo-side PR.

## Why No Runtime Action Was Executed

AI-DEV-055 is a proof of pickup/result artifact generation only. Real runtime
execution remains reserved for a later GCP-owned approval path.

## Validation Commands

```bash
python3 -m py_compile scripts/orchestrator/gcp_resident_pickup_dry_run.py scripts/orchestrator/validate_gcp_resident_pickup_result.py
python3 scripts/orchestrator/gcp_resident_pickup_dry_run.py --input templates/gcp_resident_pickup_request.example.json --output /tmp/gcp_resident_pickup_result.example.json --pretty
python3 scripts/orchestrator/validate_gcp_resident_pickup_result.py --input templates/gcp_resident_pickup_result.example.json --pretty
python3 scripts/orchestrator/validate_gcp_resident_pickup_result.py --input /tmp/gcp_resident_pickup_result.example.json --pretty
python3 scripts/orchestrator/validate_gcp_runtime_relay_request.py --input templates/gcp_runtime_relay_request.example.json --pretty
python3 scripts/orchestrator/validate_gcp_runtime_relay_result.py --input templates/gcp_runtime_relay_result.example.json --pretty
```

## Safety Confirmation

The dry-run pickup package does not include secrets, token values, credential
values, `.env` contents, production database contents, raw runtime payloads,
notification sends, or order execution instructions.
