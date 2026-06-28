# Codex Handoff Auto Executor Feasibility

## Background

Mobile GitHub Issue pickup can now produce sanitized handoff artifacts for
repo-side tasks. The current flow reaches `needs_codex_execution`, but a human
still has to enter the GCP resident Codex session and execute the handoff.

AI-DEV-067 evaluates whether the GCP VM has a stable Codex CLI path for
non-interactive one-shot execution and adds a safe repo-only executor contract.

## Current State

The pickup flow supports:

```text
GitHub Issue -> scheduled pickup -> safety filter -> handoff_created -> needs_codex_execution
```

The unsupported step is:

```text
needs_codex_execution -> automatic GCP resident Codex execution
```

This task does not enable that automatic step. It only records feasibility and
adds a fixture-validatable executor plan/result boundary.

## Codex CLI Feasibility Checks

The GCP repo environment was checked with:

```bash
which codex || true
codex --version || true
codex --help || true
codex exec --help || true
codex run --help || true
```

Sanitized result:

- `which codex`: `/home/kaochuchian/.local/bin/codex`
- `codex --version`: `codex-cli 0.142.3`
- `codex --help`: available; lists `exec` as non-interactive
- `codex exec --help`: available; says `Run Codex non-interactively`
- `codex run --help`: no dedicated `run` command was found; the CLI returned
  top-level help
- `supported_command`: `codex exec`
- `headless_supported`: `true`
- `manual_one_shot_viable`: `true`
- `schedule_ready`: `false`
- `tmux_paste_required`: `false`

The help/version checks produced a local warning that PATH aliases could not be
created in the read-only shell environment. That warning did not expose secrets
and did not prevent CLI help/version output.

## Decision Standards

`headless_supported` may be true only when the installed CLI exposes a
documented non-interactive command. `manual_one_shot_viable` may be true when
that command can accept a prompt without TUI interaction and can be run only by
an explicit operator action.

`schedule_ready` remains false until a separate reviewed task proves:

- deterministic prompt construction
- idempotency and duplicate suppression
- safe branch, PR, CI, merge, and cleanup behavior
- no secrets or production payload exposure
- no notification, trading, DB, scheduler, n8n, Dify, Gemini, or external AI
  runtime side effects outside the explicitly intended Codex invocation
- auditable failure handling and rollback behavior

## Safe Executor V1 Scope

Safe Executor V1 is repo-only. It can:

- read a specified sanitized handoff markdown file
- require the handoff path to be under `docs/mobile_issue_handoffs/`
- scan the handoff for positive high-risk intents
- avoid blocking negated safety constraints such as `do not call OpenAI`,
  `no notification`, `不交易`, or `不修改 systemd`
- generate a sanitized Codex prompt and execution plan
- write a result JSON artifact
- support `--dry-run`, `--handoff-path`, and `--output`

By default it does not call Codex. Even when headless support is available, the
executor must require an explicit execution flag in a future reviewed change.

## Explicit Non-Goals

Safe Executor V1 must not:

- read, print, or commit secrets, tokens, credentials, `.env`, or private
  runtime payloads
- call Dify, OpenAI, ChatGPT, Gemini, or other external AI runtimes
- send LINE, Email, webhook, or notification payloads
- trade or place orders
- mutate production databases
- start, stop, or modify n8n
- run production pipelines
- modify cron, systemd, timers, or background services
- modify the mobile pickup timer
- mutate real GitHub Issues
- execute shell commands from Issue or handoff body text

## No Tmux Paste Automation

`tmux paste` automation is explicitly not an acceptable formal executor
strategy. It is brittle, hard to audit, and cannot provide a stable safety gate
for branch, PR, CI, merge, and cleanup behavior.

## No Schedule Activation

This task must not create a background service, cron job, systemd unit, timer,
or schedule. `safe_to_schedule` must remain false in V1 artifacts.

## If Headless Is Supported

The next step is a separate manual-only one-shot executor task that proves a
single explicitly requested `codex exec` run can safely:

- consume a sanitized prompt
- operate inside the repo workspace
- keep branch and PR behavior explicit
- emit a sanitized result artifact
- stop on validation or safety gate failure

That next step must still keep `safe_to_schedule=false`.

## If Headless Is Unsupported

If a future environment lacks `codex exec`, the fallback is manual GCP resident
Codex handoff execution. Do not emulate headless execution with terminal paste
automation and do not connect scheduler automation to an interactive session.

## AI-DEV-068 Recommended Path

AI-DEV-068 should implement a manual-only `codex exec` proof of execution using
an intentionally harmless fixture handoff. It should require an explicit
operator flag, write a sanitized local artifact, validate that artifact, open a
normal PR, and still keep schedule activation blocked.
