# AI-DEV-163 Manual Rerun Runtime Activation V1

AI-DEV-163 connects the AI-DEV-162 Dashboard manual rerun controls to a deployable runtime bridge while keeping the feature disabled until a runtime-only PIN hash is configured.

## Runtime Architecture

The Dashboard posts to `/stock-ai-dashboard/api/manual-rerun` and polls `/stock-ai-dashboard/api/manual-rerun/status`. The repo now includes `scripts/orchestrator/manual_rerun_runtime_bridge.py`, a small stdlib HTTP bridge that can be placed behind that route by an operator-owned deployment step.

The bridge calls `scripts/orchestrator/manual_rerun_single_window.py`, which enforces:

- exactly one allowed window
- `dashboard_refresh_only` mode only
- six-digit PIN format
- runtime-only PIN hash verification
- lock, cooldown, and timeout guards
- no LINE or Email attempt
- no trading or order action

## PIN Hash Model

The plaintext PIN must never be committed, printed into artifacts, pasted into Codex or ChatGPT, or added to GitHub. The accepted PIN is verified only by backend/runtime code.

Supported runtime-only hash sources:

- `STOCK_AI_MANUAL_RERUN_PIN_HASH` in the backend runtime environment
- `/home/kaochuchian/.config/stock-ai/manual_rerun_pin_hash` on the GCP host

If neither source exists, the bridge returns `manual_rerun_disabled`. There is no fallback to unauthenticated rerun.

## Operator Setup

Generate the hash interactively on GCP:

```bash
cd ~/stock-ai
python scripts/orchestrator/hash_manual_rerun_pin_v1.py --pretty
```

The operator enters the six-digit PIN directly in the GCP shell. Do not paste the PIN into Codex, ChatGPT, GitHub, docs, templates, artifacts, or logs. Store only the resulting hash in a runtime-only environment variable or config file.

## Disabled-State Verification

Before runtime PIN setup, POST requests must return `manual_rerun_disabled`; no rerun runs, no notification is sent, no production pipeline runs, and no DB write occurs.

## Single-Window Rule

Only these windows are accepted:

- `pre_open_0700`
- `intraday_1305`
- `pre_close_1335`
- `post_close_1500`

The bridge rejects all-windows, wildcard, array, empty, and unknown window requests.

## Rollback Plan

If the bridge is deployed and needs to be disabled, remove the runtime PIN hash and stop the bridge process or remove the reverse-proxy route. The static Dashboard remains usable; without a PIN hash, manual rerun returns `manual_rerun_disabled`.

## Safety Gates

This foundation does not change scheduler, cron, systemd, nginx, firewall, production DB, formula logic, rating/action/confidence/weight logic, LINE, Email, or trading behavior. Runtime deployment of a long-running service remains an operator-controlled step.
