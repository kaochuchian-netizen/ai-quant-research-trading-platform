# Dashboard Manual Single-Window Rerun Runbook

## Operator Setup

1. Choose a private six-digit numeric PIN. Do not paste it into chat, docs, or commits.
2. On the runtime host, generate a hash interactively:

```bash
python scripts/orchestrator/hash_manual_rerun_pin_v1.py --pretty
```

3. Set the resulting hash as runtime-only `STOCK_AI_MANUAL_RERUN_PIN_HASH` in the backend service environment after runtime deployment is separately approved.

## Dashboard Use

1. Open the four-window Dashboard.
2. Select exactly one button: 07:00, 13:05, 13:35, or 15:00.
3. Enter the six-digit PIN.
4. Confirm that the action only refreshes Dashboard/artifacts, does not resend LINE/Email, does not trade, and does not run all windows.
5. Watch the job status.

## Failure Handling

- `manual_rerun_disabled`: PIN hash is not configured.
- `unauthorized`: PIN verification failed.
- `invalid_pin_format`: PIN is not exactly six digits.
- `invalid_window`: window is not allowlisted.
- `lock_busy`: another manual rerun is active.
- `cooldown_active`: wait and retry later.

## Validation

```bash
python scripts/orchestrator/simulate_dashboard_manual_rerun_v1.py --pretty
python scripts/orchestrator/validate_dashboard_manual_single_window_rerun_v1.py --pretty
```

## Forbidden

Do not send LINE/Email, change scheduler, run production pipeline, execute `python3 main.py`, write DB, trade, change nginx/systemd/firewall, or commit any plaintext PIN/hash secret.
