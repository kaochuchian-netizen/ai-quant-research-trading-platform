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
--codex-executor
--readiness-gate
```

Without `--execute`, it does not call the executor helper. With `--execute`,
it still requires the readiness gate, lock, idempotency, and safety filters to
pass before calling the AI-DEV-067 executor helper.

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

The lock is created with exclusive file creation and contains owner, pid,
created time, and handoff path. If the lock exists, the runner returns
`decision=locked` and does not call the executor.

The idempotency key is:

```text
codex-handoff-scheduled-pickup:{handoff_path}:{sha256_prefix}
```

Only successful executor helper handling marks a key processed. Failed,
blocked, unsafe, or locked runs do not mark processed.

## Safety

The runner does not execute shell from handoff text. It does not mutate real
GitHub Issues, send notifications, modify production DBs, control n8n, trade,
or place orders.

AI-DEV-067's executor helper currently produces a sanitized executor result
artifact and remains conservative about direct Codex runtime invocation. This
keeps scheduled activation observable while preserving safe-stop behavior.

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
