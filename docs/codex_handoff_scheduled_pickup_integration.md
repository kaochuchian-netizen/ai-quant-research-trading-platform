# Scheduled Pickup To Codex Handoff Executor Integration

## Purpose

AI-DEV-069 activates the scheduled pickup integration path:

```text
GitHub Issue scheduled pickup
-> sanitized handoff
-> readiness gate
-> single-active lock
-> idempotency check
-> Codex handoff executor helper
-> verified repo implementation changes
-> sanitized result artifact
```

The operator explicitly approved modifying the user-level timer, systemd
service, and scheduled command for this task.

## Integrated Runner

The entrypoint is:

```bash
python3 scripts/orchestrator/codex_handoff_scheduled_pickup_runner.py
```

It supports:

```text
--dry-run
--execute
--pickup-artifact
--handoff-path
--output
--state-dir
--lock-file
--max-handoffs-per-run
--executor-timeout-seconds
--codex-executor
--readiness-gate
```

Without `--execute`, it does not call the executor helper. With `--execute`,
it still requires the readiness gate, lock, idempotency, and safety filters to
pass before calling the AI-DEV-067 executor helper. A successful helper process
is not enough: the runner requires `implementation_completed=true` and at least
one changed file outside `docs/mobile_issue_handoffs/` before it returns
`decision=executed_codex_handoff`.

## Systemd Command

The existing user service name is retained:

```text
stock-ai-github-issue-scheduled-pickup-dry-run.service
```

The name still says `dry-run`, but the command is upgraded to the integrated
runner. The timer cadence remains 30 minutes:

```text
stock-ai-github-issue-scheduled-pickup-dry-run.timer
OnUnitActiveSec=30min
```

The scheduled command should be equivalent to:

```bash
/usr/bin/python3 scripts/orchestrator/codex_handoff_scheduled_pickup_runner.py \
  --execute \
  --pickup-artifact /home/kaochuchian/.local/state/stock-ai-orchestrator/github_issue_scheduled_pickup_latest.json \
  --output /home/kaochuchian/.local/state/stock-ai-orchestrator/codex_handoff_scheduled_pickup/latest.json \
  --state-dir /home/kaochuchian/.local/state/stock-ai-orchestrator/codex_handoff_scheduled_pickup \
  --lock-file /home/kaochuchian/.local/state/stock-ai-orchestrator/codex_handoff_scheduled_pickup/lock \
  --max-handoffs-per-run 1 \
  --executor-timeout-seconds 3600 \
  --codex-executor scripts/orchestrator/codex_handoff_auto_executor.py \
  --readiness-gate scripts/orchestrator/codex_handoff_scheduled_readiness_gate.py
```

## Lock And Idempotency

State lives under:

```text
/home/kaochuchian/.local/state/stock-ai-orchestrator/codex_handoff_scheduled_pickup/
```

Artifacts:

```text
latest.json
runs/<timestamp>.json
processed_handoffs.json
lock
readiness_latest.json
executor_latest.json
```

The scheduled runner waits up to `--executor-timeout-seconds` for the executor
helper. The default is 3600 seconds. If the helper times out, the runner writes
a fresh `executor_latest.json` timeout artifact before returning
`decision=codex_executor_failed`, so an older executor result cannot be mistaken
for the latest executor outcome.

The lock is created with exclusive file creation and contains owner, pid,
created time, and handoff path. If the lock exists, the runner returns
`decision=locked` and does not call the executor.

The idempotency key is:

```text
codex-handoff-scheduled-pickup:{handoff_path}:{sha256_prefix}
```

Only verified implementation completion marks a key processed. Failed, blocked,
unsafe, locked, handoff-only, plan-only, or manual-only runs do not mark
processed.

If an older runner marked a handoff processed before implementation completion,
the integrated runner can safely unmark that key before retrying. The repair is
written under:

```text
/home/kaochuchian/.local/state/stock-ai-orchestrator/codex_handoff_scheduled_pickup/repairs/
```

For the Issue #74 / PR #75 incident, the repair artifact records:

```text
unmarked_reason=handoff_only_not_implemented
source_pr=75
safe_to_retry=true
```

## Safety

The runner does not execute shell from handoff text. It does not mutate real
GitHub Issues, send notifications, modify production DBs, control n8n, trade,
or place orders.

AI-DEV-067's executor helper now supports the explicit `--execute-headless`
path. It calls the official non-interactive `codex exec` command with
workspace-write repo scope, sends a safe implementation prompt derived from the
sanitized handoff, and does not execute shell copied from handoff text. The
helper writes a sanitized executor result artifact with:

```text
implementation_completed
implementation_changed_files
headless_run.returncode
```

The scheduled runner treats `headless_supported_manual_only`, `plan_created`,
and `executor_no_implementation` as non-terminal implementation failures.

## Activation Validation

Required checks:

```bash
systemctl --user status stock-ai-github-issue-scheduled-pickup-dry-run.timer --no-pager
systemctl --user status stock-ai-github-issue-scheduled-pickup-dry-run.service --no-pager || true
journalctl --user -u stock-ai-github-issue-scheduled-pickup-dry-run.service -n 80 --no-pager || true
python3 scripts/orchestrator/validate_codex_handoff_scheduled_pickup_result.py \
  ~/.local/state/stock-ai-orchestrator/codex_handoff_scheduled_pickup/latest.json
```

## Rollback

Rollback disables scheduled execution but preserves sanitized artifacts:

```bash
systemctl --user stop stock-ai-github-issue-scheduled-pickup-dry-run.timer
systemctl --user disable stock-ai-github-issue-scheduled-pickup-dry-run.timer
systemctl --user daemon-reload
```

If a service file backup was created during activation, restore it with:

```bash
install -m 0644 /home/kaochuchian/.config/systemd/user/stock-ai-github-issue-scheduled-pickup-dry-run.service.bak-ai-dev-069 \
  /home/kaochuchian/.config/systemd/user/stock-ai-github-issue-scheduled-pickup-dry-run.service
systemctl --user daemon-reload
```

## Next Step

AI-DEV-070 should verify the closed loop from a fresh mobile Issue through
scheduled pickup, handoff executor handling, PR flow, merge, cleanup, and
sanitized artifacts.
