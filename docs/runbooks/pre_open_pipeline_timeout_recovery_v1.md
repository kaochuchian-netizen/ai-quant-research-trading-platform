# AI-DEV-174A Pre-open Pipeline Timeout Recovery V1

## Incident
On 2026-07-13, the 07:00 TW pre-open scheduler triggered normally, but the child production pipeline exceeded the 1800 second guard. Dashboard, Email, and LINE were intentionally not attempted.

## Root cause evidence
The approved delivery wrapper recorded `child_pipeline_timeout`. `shioaji.log` showed repeated Shioaji login/contracts loading in the same pipeline PID, with no Python traceback. Local stock-name maps were absent, so stock-name fallback could invoke Shioaji contracts during per-stock processing.

## Fix
- Cache the Shioaji API object once per process.
- Set an explicit Shioaji contracts timeout via `STOCK_AI_SHIOAJI_CONTRACTS_TIMEOUT_MS`, defaulting to 15000 ms.
- Add `artifacts/runtime/pre_open_stage_timing_latest.json` so the last entered production stage is visible if a future timeout occurs.
- Flush key pre-open stage markers to `logs/daily.log`.

## Safety
This hotfix does not change scheduler times, delivery policy, formulas, trading behavior, or secrets. It does not send LINE or Email during validation.

## Recovery guidance
1. Confirm no residual `run_pipeline.py` / `approved_pre_open_delivery.py` process is running.
2. Run validation only first.
3. If recovery is needed, prefer artifact/Dashboard refresh without notification.
4. If a delayed notification is approved later, label it explicitly as delayed and use the recovered artifact only once.

## Validation
```bash
python3 -m py_compile app/market/shioaji_client.py app/pipelines/pre_open_pipeline.py scripts/orchestrator/validate_pre_open_pipeline_timeout_recovery_v1.py
python3 scripts/orchestrator/validate_pre_open_pipeline_timeout_recovery_v1.py --pretty
```
