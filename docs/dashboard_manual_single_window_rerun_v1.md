# AI-DEV-162 Dashboard Manual Single-Window Rerun Control V1

AI-DEV-162 adds a disabled-by-default manual rerun control contract for the four-window Dashboard.

## Purpose

Operators can request one selected batch from the Dashboard:

- `pre_open_0700` / 07:00 盤前
- `intraday_1305` / 13:05 盤中
- `pre_close_1335` / 13:35 收盤快照
- `post_close_1500` / 15:00 盤後檢討

Each request is single-window only. There is no all-windows trigger.

## Security Model

Public unauthenticated rerun is forbidden. The frontend never knows the accepted PIN. The backend validates a runtime-only 6-digit PIN hash from `STOCK_AI_MANUAL_RERUN_PIN_HASH`.

The PIN must be exactly six digits. Plaintext PINs must not be committed to repo, frontend, templates, docs, artifacts, logs, or GitHub.

## Runtime Deployment Status

This PR provides repo code, Dashboard UI, handler, simulation, validator, and docs. Runtime activation remains disabled until an operator configures the PIN hash and separately approves any backend route deployment. This PR does not modify nginx, systemd, firewall, scheduler, cron, or timers.

## Mode

V1 only allows `dashboard_refresh_only`:

- refresh selected-window artifacts and Dashboard when runtime deployment is approved
- no LINE resend
- no Email resend
- no trading or order action
- no all-window execution

## Lock / Cooldown

The handler defines a global manual rerun lock, per-window lock paths, a 3-minute global cooldown concept, a 10-minute per-window cooldown, and a 600-second timeout model. Simulation validates lock busy and cooldown rejection.

## Audit

Audit artifacts are written under `artifacts/runtime/manual_rerun/` during simulation. Audit records do not contain PIN, plaintext PIN, submitted PIN, PIN hash, tokens, or secrets.
