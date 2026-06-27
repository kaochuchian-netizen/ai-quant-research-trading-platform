# Dify Review Workflow Mapping Setup

## Purpose

AI-DEV-052 defines a credential-safe setup package for identifying the Dify
review workflow or app used by the AI-DEV one-shot review path.

AI-DEV-051 stopped safely because no Dify review workflow/app mapping could be
identified from workflow names and IDs alone. This package fixes the repo-side
contract gap by defining:

- a safe metadata-only mapping contract
- a runtime-safe lookup rule
- a sanitized ChatGPT-ready summary shape
- a validator for the mapping setup package
- an AI-DEV-053 readiness checklist

This package does not start n8n, call Dify runtime, inspect credentials, read
node parameter payloads, send notifications, modify production data, change
schedulers, trade, place orders, or execute AI-DEV-053.

## Credential-Safe Mapping Contract

The mapping contract is stored in:

```text
templates/dify_review_workflow_mapping.example.json
```

The contract may use only safe metadata:

- `workflow_name`
- `workflow_id` when visible from workflow listing without credential inspection
- `node_display_name`
- `contract_version`
- `task_id`
- `template_file`
- `sanitized_placeholder`

The contract must not contain authorization header values, bearer values, API
key values, token values, passwords, credential secrets, `.env` content, raw
node credential payloads, or raw node parameter payloads.

The mapping should make the intended Dify review package discoverable by label
and contract version before any future runtime call is considered.

## Runtime-Safe Lookup Rule

Future runtime lookup may list n8n workflow or Dify app metadata only when the
task explicitly allows runtime inspection. The lookup must use this order:

1. Match `contract_version` and `task_id` from the repo mapping contract.
2. Match `workflow_name` from a safe workflow/app listing.
3. Match `workflow_id` only when the ID is visible in the listing metadata.
4. Match `node_display_name` only when it is visible without opening credential
   or raw node parameter details.
5. Confirm `template_file` points to the repo template used by the review path.
6. If any step requires credential values, raw node credentials, raw node
   parameters, `.env`, or secret inspection, stop and produce a readiness gap.

The runtime lookup must not infer a mapping from a generic Dify workflow name
when it cannot distinguish the AI-DEV one-shot review package.

## Sanitized Summary Template

The setup result example is stored in:

```text
templates/ai_dev_052_dify_review_mapping_setup_result.example.json
```

The sanitized result records:

- whether a safe repo mapping contract exists
- whether runtime lookup was attempted
- whether n8n was started and stopped
- whether Dify runtime was called
- whether a safe mapping was found
- secret scan pattern counts only
- placeholder status
- readiness gaps
- AI-DEV-053 readiness checklist state

It may report counts and placeholder status only. It must not display secret
values or raw runtime payloads.

## AI-DEV-053 Readiness Checklist

AI-DEV-053 may attempt a controlled runtime lookup or review package call only
after all readiness items are true:

- repo mapping contract validates
- mapping uses safe metadata only
- `sanitized_placeholder` is true
- workflow/app name is explicit for AI-DEV one-shot review packages
- workflow ID, if used, is visible without credential inspection
- node display name is visible without credential or raw node parameter
  inspection
- no authorization, bearer, API key, token, password, credential, `.env`, raw
  credential payload, or raw node parameter payload is present in repo
- n8n startup, if needed, is explicitly controlled and followed by shutdown
- Dify runtime call is skipped unless a safe mapping is confirmed
- LINE, Email, external delivery, production DB writes, scheduler changes,
  trading, and order execution remain blocked

If any checklist item fails, AI-DEV-053 must produce a readiness gap or blocked
report instead of requesting credentials or inspecting unsafe runtime payloads.

## Readiness Gap Policy

When no safe mapping can be found from metadata, the correct output is a
readiness gap, not a credential request. The gap should state:

- which safe metadata field was missing or ambiguous
- whether runtime lookup was attempted
- whether n8n was started and stopped
- whether Dify runtime was not called
- which readiness checklist items remain incomplete

## Validation

Run:

```bash
python3 -m py_compile scripts/orchestrator/validate_dify_review_workflow_mapping_setup.py
python3 scripts/orchestrator/validate_dify_review_workflow_mapping_setup.py --pretty
```

The validator is read-only. It checks the new docs and JSON templates, verifies
required mapping fields, enforces the allowed metadata-only contract, validates
the AI-DEV-053 readiness checklist, and scans for secret-like value patterns
without displaying values.

## Safety Confirmation

AI-DEV-052 is a repo setup package only:

- no n8n startup was required by this package
- no Dify runtime call was made
- no credentials, secrets, tokens, passwords, API keys, `.env`, raw credential
  payloads, or raw node parameter payloads were read or written
- no LINE, Email, notification, or external delivery was sent
- no production DB, cron, systemd, timer, production pipeline, trading, order,
  or runtime queue behavior was changed by the setup package
- AI-DEV-053 was not executed
