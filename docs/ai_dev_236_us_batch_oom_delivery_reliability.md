# AI-DEV-236 US Batch OOM & Delivery Reliability Hardening

## Purpose

AI-DEV-236 hardens US 20:00 and 23:00 batch execution after the
2026-09-08 Asia/Taipei incident where `us_pre_market_2000` was OOM-killed
before delivery and `us_intraday_2300` had no observable scheduler invocation.

## Scope

- Add a durable `US_BATCH_EXECUTION_RELIABILITY_CONTRACT`.
- Supervise production-approved US delivery workers from a lightweight parent
  process.
- Persist fail-closed status when the worker times out, exits non-zero, emits
  invalid JSON, or is terminated by signal.
- Preserve truthful notification provenance: `sent` requires `attempted`.
- Keep 20:00 and 23:00 contracts independent.
- Add behavioral contract validation and offline memory profiling.

## Non-goals

- No production rerun.
- No LINE or Email send during validation.
- No production DB or Sheet write.
- No scheduler, cron, systemd, nginx, firewall, IAM, SSH metadata, credential,
  or infrastructure mutation.
- No trading or order execution.
- No TW behavior change.

## Reliability Contract

The contract covers:

- `us_pre_market_2000`: timeout 75 minutes; Email and LINE are eligible only
  after the required runtime/snapshot/publication lifecycle completes.
- `us_intraday_2300`: timeout 45 minutes; Email is eligible, LINE is not
  attempted under current intended policy.

Both windows require independent scheduler ownership and fail-closed delivery
semantics.

## Supervised Worker Boundary

`approved_us_stock_delivery.py` now runs production-approved execution through a
lightweight parent process. The parent invokes the same script in hidden
`--worker-mode`; the worker owns the existing runtime, snapshot, Dashboard, and
notification path.

If the worker fails before returning a valid successful result, the parent writes
durable failure evidence to the existing US delivery status paths. Failure status
marks:

- `pipeline_completed=false`
- `runtime_artifact_admitted=false`
- `snapshot_admitted=false`
- `dashboard_publication_verified=false`
- `delivery_success_claimed=false`
- `email_attempted=false`
- `line_attempted=false`

This does not guarantee recovery from a host-level kill of all processes, but it
does cover worker-level timeout, non-zero exit, invalid JSON, and SIGKILL/OOM
equivalent termination where the parent survives.

## Notification Provenance

The contract helper validates channel state deterministically:

- `sent => attempted`
- failed-closed status cannot mark any channel as sent
- duplicate retry state is represented as suppressed/not attempted
- partial channel failure keeps per-channel attempted/sent truth separate

## Memory Profile

The validator runs offline `tracemalloc` over fixture artifact construction. This
confirms the test path is small and deterministic. It does not claim to reproduce
the production OOM owner, because the incident involved live provider/runtime
execution and production-local logs were not available through SSH/IAP.

Production-only memory ownership still requires read-only access to:

- `logs/us_stock/us_pre_market_2000.log`
- local system journal around `2026-09-08 20:00-21:10 Asia/Taipei`
- local resource telemetry or process accounting

## Production-only Blockers

- The exact `us_intraday_2300` absence remains production-only until local cron
  and journal evidence can be read.
- The precise OOM owner by live stage remains production-only until the redirected
  `logs/us_stock/us_pre_market_2000.log` can be read.

Application code must not encode an infrastructure workaround for those findings
without separate authorization.

## Validation

```bash
./venv/bin/python -m py_compile \
  app/us_stock/batch_reliability.py \
  scripts/orchestrator/approved_us_stock_delivery.py \
  scripts/orchestrator/validate_us_batch_execution_reliability_contract_v1.py

./venv/bin/python scripts/orchestrator/validate_us_batch_execution_reliability_contract_v1.py --pretty
./venv/bin/python scripts/orchestrator/validate_us_stock_dedicated_batch_lifecycle_v1.py --pretty
./venv/bin/python scripts/orchestrator/validate_us_pre_intraday_post_close_continuity_v1.py --pretty
./venv/bin/python scripts/orchestrator/validate_notification_delivery_provenance_v1.py --pretty
./venv/bin/python scripts/orchestrator/validate_tw_preopen_lifecycle_contract_v1.py --pretty
./venv/bin/python scripts/governance/validate_validator_registry.py --pretty
./venv/bin/python scripts/orchestrator/validate_ai_branch.py --base main --head HEAD --pretty
```

All commands are repo-local and do not send notifications or run production
pipelines.
