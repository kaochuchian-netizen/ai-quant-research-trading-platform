# n8n One-Shot Runtime Intake Dry-Run Package

## Purpose

AI-DEV-049 defines the repo-side n8n intake contract for the one-shot AI-DEV
workflow introduced in AI-DEV-048. It describes how a future n8n webhook or
manual trigger can receive a ChatGPT-approved `task_request`, normalize it into
an orchestration payload, route safety gates, and prepare Codex/Dify/GitHub
handoff summaries.

This task is repo-only. It does not start n8n, import a runtime workflow, call
Dify, call ChatGPT/OpenAI APIs, use credentials, send notifications, or modify
production systems.

## Scope

AI-DEV-049 adds:

- n8n one-shot intake payload example
- n8n one-shot intake result example
- validator for intake contract completeness and safety
- dry-run runner summary updates
- one-shot automation runbook references

## Non-Goals

AI-DEV-049 does not:

- start n8n
- call Dify runtime
- call ChatGPT or OpenAI APIs
- use API keys, tokens, secrets, credentials, or `.env`
- send LINE, Email, or notification
- write production DB records
- modify cron, systemd, or timers
- execute `python3 main.py`
- trade, place orders, route orders, or create order instructions
- modify runtime queues before post-merge closeout
- execute AI-DEV-050

## Intake Entry Points

The intake design supports two conceptual entry points:

1. **Webhook intake**: a future n8n webhook receives a ChatGPT-approved
   `task_request` payload.
2. **Manual trigger intake**: an operator manually supplies the same payload in a
   controlled n8n dry-run workflow.

Both entry points must produce the same normalized intake contract. The task is
keyed by `task_id` and must include ChatGPT metadata, safety gates,
autonomous permission profile, conditional auto-merge policy, expected outputs,
stop conditions, and Codex runner command summary.

## Intake Payload Contract

The normalized intake payload must explicitly carry `dry_run=true`.

The payload in `templates/n8n_one_shot_intake_payload.example.json` contains:

- `task_id`
- `dry_run: true`
- `intake_source`
- `chatgpt_task_request_metadata`
- `safety_gates`
- `autonomous_permission_profile`
- `conditional_auto_merge_policy`
- `codex_one_shot_runner_command`
- `expected_outputs`
- `stop_conditions`

The payload must not contain secrets, token values, API keys, credentials, or
`.env` values. Credential references can only be placeholders or policy names.

## Intake Result Contract

The result in `templates/n8n_one_shot_intake_result.example.json` records:

- whether intake validation passed
- normalized task id and branch
- safety gate routing result
- Codex execution request readiness
- Dify review package readiness
- GitHub gate collection readiness
- conditional auto-merge eligibility
- blocked reasons if any
- local dry-run side-effect summary

## n8n Workflow Template Alignment

The sanitized one-shot n8n workflow template includes webhook/manual-trigger
entry concepts, task request validation, an intake normalization step, safety
gate router, GitHub status collection placeholder, Codex execution request
builder, Dify review package placeholder, conditional auto-merge gate, and
ChatGPT-ready report formatter.

The template must remain inactive and sanitized. It must not contain real
Authorization headers, Bearer values, API key values, token values, credential
values, LINE send nodes, Email send nodes, production DB write nodes, cron
activation nodes, or unconditional auto-merge behavior.

## AI-DEV-050 Boundary

AI-DEV-050 is the earliest future task that may request an explicitly approved
runtime n8n intake dry-run. That future task must re-check runtime access,
credential containment, workflow inactive/publish state, no-notification policy,
no-production-write policy, and post-run cleanup.

AI-DEV-049 does not grant runtime access.

## Validation

Run:

```bash
python3 scripts/orchestrator/run_ai_dev_one_shot_plan.py --pretty
python3 scripts/orchestrator/validate_ai_dev_one_shot_multi_agent_automation.py --pretty
python3 scripts/orchestrator/validate_n8n_one_shot_runtime_intake_dry_run.py --pretty
python3 scripts/orchestrator/inspect_ai_platform_status.py --pretty
```

All validation is read-only and does not start n8n, call Dify, call ChatGPT or
OpenAI APIs, send notifications, modify production systems, or mutate runtime
queues.


## AI-DEV-050 Runtime Dry-Run Result

AI-DEV-050 executed the first controlled n8n one-shot intake runtime dry-run.
The runtime used a dry-run-only workflow with no external call, no credentials,
no notification delivery, no production write, and no trading or order behavior.
n8n was started for the dry-run and stopped afterwards. The sanitized result is
packaged in `templates/ai_dev_050_n8n_one_shot_runtime_intake_result.example.json`.
