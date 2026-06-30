# Controlled LINE Runtime Reactivation V1

Controlled LINE Runtime Reactivation V1 adds a gated runtime entrypoint for a
single explicit LINE test push. It builds on the LINE Delivery Gate, Unified
Delivery Gate Summary, Production Scheduler Gate Runtime Activation, and
Shioaji pre-delivery readiness repair work.

This contract does not modify cron, systemd, timers, services, scheduler
configuration, `.env`, Google Sheet settings, GitHub remotes, production data,
Email delivery, dashboard deployment, or trading behavior.

## Runtime Entrypoint

Use:

```bash
python3 scripts/orchestrator/controlled_line_runtime.py \
  --input templates/controlled_line_runtime_input.example.json \
  --output /tmp/controlled_line_runtime_result.json \
  --summary-output /tmp/controlled_line_runtime_summary.json \
  --pretty
```

The default mode is dry-run/no-send. It does not import the LINE sender, read
runtime LINE token values, or call LINE APIs.

## Gate Preconditions

The helper requires all of the following before any controlled test push can be
attempted:

- `delivery_allowed: true`
- `approval_status: approved`
- `line_channel_enabled: true`

If any precondition is missing, the result decision is
`line_push_blocked_by_gate`, `push_attempted` remains false, and no LINE API call
is made.

## Controlled Test Push

The only command that can attempt a LINE push is:

```bash
python3 scripts/orchestrator/controlled_line_runtime.py \
  --input templates/controlled_line_runtime_input.example.json \
  --output /tmp/controlled_line_runtime_result.json \
  --summary-output /tmp/controlled_line_runtime_summary.json \
  --pretty \
  --send-test-line
```

Run this only after explicit confirmation for the test push. The test message is
clearly marked with `[Stock AI Controlled LINE Runtime Test]`. The result records
only success/failure metadata, recipient count, and HTTP status code counts. It
does not print token values, user IDs, authorization headers, response bodies,
or secret values.

Formal scheduler LINE delivery remains disabled and requires a separate explicit
confirmation after this controlled test.

## Result Contract

Required top-level fields:

- `schema_version`
- `task_id`
- `run_id`
- `generated_at`
- `mode`
- `gate_status`
- `line_runtime_status`
- `delivery_allowed`
- `approval_status`
- `line_channel_enabled`
- `push_attempted`
- `push_status`
- `test_message_sent`
- `secret_safety`
- `side_effects`
- `safety`
- `ok`
- `decision`
- `next_recommendation`

Allowed decisions:

- `controlled_line_runtime_reactivation_completed`
- `controlled_line_runtime_reactivation_completed_with_test_push`
- `line_push_blocked_by_gate`
- `line_push_test_failed`
- `validation_failed`
- `blocked`

## Validation

Use:

```bash
python3 -m py_compile scripts/orchestrator/controlled_line_runtime.py scripts/orchestrator/validate_controlled_line_runtime_result.py
python3 scripts/orchestrator/controlled_line_runtime.py --input templates/controlled_line_runtime_input.example.json --output /tmp/controlled_line_runtime_result.json --summary-output /tmp/controlled_line_runtime_summary.json --pretty
python3 scripts/orchestrator/validate_controlled_line_runtime_result.py --input /tmp/controlled_line_runtime_result.json --pretty
python3 scripts/orchestrator/validate_controlled_line_runtime_result.py --input templates/controlled_line_runtime_result.example.json --pretty
python3 scripts/orchestrator/validate_ai_branch.py
git diff --check
```

The validator confirms gate enforcement, dry-run default behavior, secret-safety
flags, restricted side effects, scheduler non-mutation, and absence of
secret-like values in the result JSON.
