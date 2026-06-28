# Codex Handoff Scheduled Integration Readiness Gate

## Background

Mobile GitHub Issue pickup can produce sanitized handoff markdown under
`docs/mobile_issue_handoffs/`. Those handoffs may reach a
`needs_codex_execution` state, but a human operator still controls any actual
Codex execution.

AI-DEV-068 adds a repo-only scheduled integration readiness gate. The gate
decides whether one pending handoff is safe enough for a future scheduled
runner to call a separately reviewed executor. It does not call Codex and does
not enable scheduling.

## AI-DEV-067 Input

AI-DEV-067 concluded:

```text
headless_supported=true
manual_one_shot_viable=true
schedule_ready=false
decision=headless_supported_manual_only
```

That means the GCP VM appears to support a manual one-shot `codex exec` path,
but the platform still lacks the audited scheduling controls required for a
30-minute automated pickup loop.

## Why Headless Support Is Not Schedule Readiness

`headless_supported=true` proves only that a non-interactive Codex CLI path is
available. Scheduled execution still requires a separate gate for:

- exactly one selected handoff per run
- handoff source restrictions
- sanitized input checks
- high-risk intent filtering
- single-active-run locking
- deterministic idempotency
- duplicate suppression
- sanitized result artifacts
- operator-approved activation

Until those controls are reviewed in a separate activation task,
`schedule_ready` and `safe_to_schedule` must remain false.

## Scheduled Integration Risk Model

A scheduled runner can fail dangerously if it processes more than one handoff,
replays a previous task, trusts commands embedded in handoff text, leaks secret
material, mutates GitHub Issues, or triggers production side effects. The gate
therefore treats the handoff as untrusted planning input and emits only a
sanitized decision artifact.

## Readiness Gate Scope

The gate can:

- read one specified handoff markdown file
- require the path to stay under `docs/mobile_issue_handoffs/`
- check whether the handoff appears sanitized
- scan for positive high-risk intents while allowing negated safety constraints
- derive a deterministic idempotency key from the handoff path and content
- check single-handoff, lock, and idempotency contract fields
- write a sanitized readiness result JSON
- optionally write a sanitized activation proposal JSON

The gate cannot:

- call `codex exec`
- call any external AI runtime
- mutate GitHub Issues
- modify timers, systemd units, cron, or background services
- run production pipelines
- send notifications
- trade or place orders

## Lock Requirement

Future scheduled integration must have a single-active-run lock before calling
an executor. AI-DEV-068 models this as:

```text
single_active_lock_required=true
single_active_lock_present=true
```

If the lock contract is missing or false, the result must block with
`decision=lock_missing`.

## Idempotency Requirement

Future scheduled integration must derive and persist a deterministic
idempotency key before executor invocation. AI-DEV-068 derives:

```text
codex-handoff-readiness:{handoff_path}:{sha256_prefix}
```

If idempotency is disabled or the handoff was already processed, the result must
block with `decision=idempotency_missing` or `decision=already_processed`.

## Max Handoffs Per Run

`max_handoffs_per_run` is fixed at `1`. `selected_handoff_count` must never be
greater than `1`. This prevents batch behavior from hiding partial failures or
unreviewed side effects.

## Allowed Handoff Source

The only allowed handoff source is:

```text
docs/mobile_issue_handoffs/
```

Paths outside that directory are rejected with `decision=invalid_handoff_path`.
Missing files are rejected with `decision=handoff_missing`.

## Safety Filter

The safety filter blocks positive requests to read or expose secret material,
send LINE or Email notifications, trade, place orders, mutate production DBs,
modify cron/systemd/timers, start or modify n8n, call Dify/OpenAI/Gemini
runtimes, or execute shell commands from handoff text.

Negated constraints such as `do not call OpenAI`, `no notification`,
`不發 LINE`, `不交易`, `不修改 systemd`, and `不碰 production DB` are treated as
safety requirements, not blockers.

## Dry-Run Artifact Contract

The readiness result includes:

```text
task_id
ok
mode
handoff_path
handoff_exists
handoff_under_allowed_dir
handoff_sanitized
headless_supported
manual_one_shot_viable
schedule_ready
single_active_lock_required
single_active_lock_present
idempotency_required
idempotency_key
already_processed
max_handoffs_per_run
selected_handoff_count
safe_to_call_executor
safe_to_schedule
decision
blocked_reasons
side_effects
next_recommendation
```

Passing readiness means `safe_to_call_executor=true` and
`decision=readiness_pass_manual_only`. It still requires
`safe_to_schedule=false` and `schedule_ready=false`.

## Activation Proposal Contract

If requested, the helper writes an activation proposal artifact for a future
task. The proposal may set `activation_ready=true`, but it must keep:

```text
schedule_ready=false
safe_to_enable_now=false
requires_user_approval=true
proposed_next_task=AI-DEV-069
```

## No Schedule Activation

AI-DEV-068 must not enable timer, systemd, cron, mobile pickup integration, or
background services. It must not connect scheduled pickup to any Codex executor.

## AI-DEV-069 Recommended Path

AI-DEV-069 should be a separately approved activation task. It can wire the
scheduled pickup runner to call the readiness gate first, then call the Codex
handoff executor only when the gate passes. That future task must still require
explicit user approval before modifying timer, systemd, cron, or scheduled
commands.
