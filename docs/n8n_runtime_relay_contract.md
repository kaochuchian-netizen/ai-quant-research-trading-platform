# n8n Runtime Relay Contract

## Purpose

This contract defines how a future GCP resident pickup loop may relay an
approved request to n8n without exposing runtime credentials or letting Codex App
operate GCP directly.

AI-DEV-054 only adds repo-side docs, examples, and validators. It does not start,
stop, modify, or call production n8n.

## Trigger Source

The only approved trigger source is a GCP resident loop that has already:

- picked up a merged repository request
- validated the request locally
- confirmed idempotency
- confirmed the requested action is allowlisted
- confirmed dry-run mode or a separately approved runtime mode

Webhook, manual UI, chat, scheduled, or external notification triggers are not
part of this repo-side contract unless a later reviewed task explicitly adds
them.

## Payload Schema

The relay request payload is represented by:

```text
templates/gcp_runtime_relay_request.example.json
```

The top-level payload must include:

- schema identity
- request identity
- source repository and merge metadata
- trigger contract
- validation contract
- execution mode
- exactly one allowlisted action
- forbidden action list
- result output contract
- retry and idempotency policy
- sensitive value redaction policy
- audit and closeout policy

Validate with:

```bash
python3 scripts/orchestrator/validate_gcp_runtime_relay_request.py --input <request.json> --pretty
```

## Validation Point

Validation happens before n8n receives a runtime call. n8n must not be the first
place where malformed, unsafe, or non-allowlisted payloads are rejected.

A future n8n workflow may perform its own defensive validation, but the GCP
resident loop remains responsible for fail-closed validation before relay.

## Allowlisted Actions

AI-DEV-054 allows only dry-run/spec-level actions:

- `validate_relay_request`
- `prepare_runtime_plan`
- `write_sanitized_result`

The request must not allow:

- trading or order execution
- LINE, Email, webhook fanout, or notification delivery
- production database mutation
- scheduler, systemd, cron, or production n8n mutation
- Dify runtime calls
- OpenAI or ChatGPT API calls
- reading, printing, or returning sensitive values

## Result Schema

The relay result payload is represented by:

```text
templates/gcp_runtime_relay_result.example.json
```

The result must include:

- request/result identity
- terminal status
- runtime execution flag
- validation summary
- action outcome
- sanitized artifact references
- retry summary
- idempotency summary
- safety gate summary
- audit event summary
- closeout checklist

Validate with:

```bash
python3 scripts/orchestrator/validate_gcp_runtime_relay_result.py --input <result.json> --pretty
```

## Retry Policy

Retries are allowed only for transient relay failures after validation passes.
Retries must not be used for:

- safety gate failures
- validation errors
- forbidden action requests
- missing action mappings
- duplicate terminal requests

The retry budget must be explicit, finite, and recorded in the result. Retry
records must not include raw headers, request bodies containing sensitive
values, workflow credentials, or production config content.

## Idempotency Policy

n8n relay processing must use the resident loop idempotency key:

```text
relay_request_id + ai_dev_id + source.merge_commit + action.name
```

If the same key already has a terminal result, the relay must not repeat runtime
work. It should return or write a sanitized `skipped` result referencing the
existing terminal artifact.

## Sensitive Value Redaction Policy

All relay request and result artifacts must be safe for repository review.
Policy fields may describe sensitive handling, but artifacts must not include
actual credentials, tokens, API keys, environment files, headers with bearer
values, private keys, cookies, or production config values.

Validators scan for common sensitive value patterns. The policy is still
fail-closed: absence of a pattern match is not permission to include sensitive
content.

## Runtime Impact

This contract is dry-run/spec-level only. AI-DEV-054 performs no runtime action,
no n8n action, no Dify action, no OpenAI API action, no notification delivery,
no trading, and no production data mutation.
