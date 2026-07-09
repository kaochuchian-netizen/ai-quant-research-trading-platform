# Manual Rerun Runtime Activation Runbook

## Purpose

Use this runbook after AI-DEV-163 is merged to deploy and verify the Dashboard manual rerun bridge without exposing the six-digit PIN.

## Setup Flow

1. SSH to the GCP host and enter `~/stock-ai`.
2. Generate a runtime-only PIN hash interactively:

```bash
python scripts/orchestrator/hash_manual_rerun_pin_v1.py --pretty
```

3. Enter the six-digit PIN only in the GCP shell prompt.
4. Store only the hash in `STOCK_AI_MANUAL_RERUN_PIN_HASH` or `/home/kaochuchian/.config/stock-ai/manual_rerun_pin_hash`.
5. Do not commit the PIN or hash. Do not paste the PIN into chat, Codex, GitHub, docs, templates, artifacts, or logs.

## Bridge Commands

Dry-run activation simulation:

```bash
python scripts/orchestrator/manual_rerun_runtime_bridge.py --simulate --pretty
python scripts/orchestrator/validate_manual_rerun_runtime_activation_v1.py --pretty
```

Health/status examples after operator deployment:

```bash
python scripts/orchestrator/manual_rerun_runtime_bridge.py --status --pretty
```

If the bridge is served behind a route, expected routes are:

- POST `/stock-ai-dashboard/api/manual-rerun`
- GET `/stock-ai-dashboard/api/manual-rerun/status`
- GET `/stock-ai-dashboard/api/manual-rerun/healthz`

## Verification Checklist

- Missing PIN hash returns `manual_rerun_disabled`.
- Wrong PIN returns `unauthorized`.
- Non-six-digit PIN returns `invalid_pin_format`.
- All-windows and array requests are rejected.
- `send_line`, `send_email`, `full_delivery`, and `trade` modes are rejected.
- Accepted mock verification keeps `line_attempted=false` and `email_attempted=false`.
- Audit and status artifacts contain no PIN, hash, token, or secret.
- Dashboard still shows the four buttons and six-digit PIN wording.

## Rollback

Remove the runtime PIN hash and stop the bridge or proxy route. The Dashboard remains visible, but manual rerun stays disabled. This rollback does not affect scheduler, LINE, Email, Dashboard static content, forecast artifacts, or snapshots.

## Tomorrow Manual Verification

After operator deployment, test only with the operator-owned PIN in the browser. Confirm that each button asks for a PIN, rejects invalid input, and only accepts the selected window. Do not enable LINE or Email resend in V1.
