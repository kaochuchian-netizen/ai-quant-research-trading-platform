# AI-DEV-237 Production Batch Stale-Lock Recovery and TW Market-Data Resilience

## Purpose

AI-DEV-237 hardens two production-adjacent failure modes without running production jobs:

- US scheduled delivery can recover from stale PID-lock residue left by SIGKILL/OOM or abnormal termination.
- TW market-data failures expose precise provider/transport evidence for DNS, connect, HTTP, and provider API failures.

## Scope

This is a repository-side implementation and validation release. It changes source code, validators, and governance registration only.

## Non-goals

- No production rerun.
- No LINE or Email send.
- No DB or Sheet write.
- No scheduler, cron, or systemd mutation.
- No forecast weight, rating, action, or trading-logic change.
- No nginx, Docker, Dify, firewall, IAM, SSH metadata, or infrastructure mutation.
- No trade or order execution.

## US Stale-Lock Recovery

`approved_us_stock_delivery.py` now uses atomic `O_CREAT | O_EXCL` PID-lock acquisition through `app.us_stock.batch_reliability`.

The lock policy is:

- Persist the owner PID in the lock file.
- If a lock exists and the owner PID is alive, do not remove the lock.
- If a lock exists and the owner PID is absent, malformed, or dead, recover it as stale residue.
- Release the lock on normal exit.
- Release the lock on SIGTERM when the current process owns it.
- Retain fail-closed notification behavior: lock contention does not send Email or LINE.

SIGKILL cannot run cleanup code, so the next invocation treats the leftover PID file as stale only when the owner process is not alive.

## TW Market-Data Failure Evidence

`app.market.shioaji_client` now exposes `transport_failure_evidence()` and classifies failures as:

- `dns_failure`
- `connect_failure`
- `connect_timeout`
- `http_failure`
- `provider_api_failure`
- `unknown_transport_failure`

`scripts/update_historical_csv.py` persists this evidence on Shioaji login/runtime and Kbars fetch failures while preserving the existing fallback contract:

- Shioaji remains the primary runtime market-data path.
- Existing CSV / yfinance fallback behavior is unchanged.
- The pipeline does not crash only because Shioaji is unavailable.
- Timeout and bounded Kbars window policy are unchanged.

## Validation

Run:

```bash
./venv/bin/python -m py_compile \
  app/us_stock/batch_reliability.py \
  app/market/shioaji_client.py \
  scripts/update_historical_csv.py \
  scripts/orchestrator/approved_us_stock_delivery.py \
  scripts/orchestrator/validate_ai_dev_237_stale_lock_tw_market_data_resilience_v1.py

./venv/bin/python scripts/orchestrator/validate_ai_dev_237_stale_lock_tw_market_data_resilience_v1.py --pretty
./venv/bin/python scripts/orchestrator/validate_us_batch_execution_reliability_contract_v1.py --pretty
./venv/bin/python scripts/orchestrator/validate_ai_dev_230_tw_preopen_structured_card_ordering_v1.py --pretty
./venv/bin/python scripts/orchestrator/validate_ai_branch.py --base main --head HEAD --pretty
```

The dedicated validator covers:

- live lock is not removed;
- stale lock is recovered;
- SIGKILL/OOM residue is recoverable;
- concurrent acquisition has a single owner;
- duplicate delivery remains not-attempted;
- TW DNS/provider API failure classification;
- TW updater persists transport evidence without changing fallback policy.

## Production Follow-up

AI-DEV-237 does not claim the full-day outage is closed. VM-local read-only evidence is still required to identify the exact production trigger and transport failure sequence for each formal window.
