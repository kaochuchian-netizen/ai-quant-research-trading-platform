# AI-DEV-166 Manual Rerun Runtime Persistent Deployment Runbook

## Purpose

AI-DEV-166 makes the Dashboard manual single-window rerun runtime activation repeatable and durable. The Dashboard already contains four buttons and a 6-digit PIN form. This runbook documents how the bridge service and nginx route are deployed, validated, recovered, and rolled back without exposing the PIN or triggering a real rerun.

## Current Runtime Topology

The active Dashboard nginx is not the host `/etc/nginx/sites-enabled/linebot` service. It is the `docker-nginx-1` container-like nginx process running with `nginx -g daemon off;`.

The active nginx config is visible from the nginx namespace at:

`/proc/<nginx_master_pid>/root/etc/nginx/conf.d/default.conf`

The durable host bind mount for that namespace is:

`/home/kaochuchian/dify/docker/nginx/conf.d/default.conf`

`/etc/nginx/conf.d` inside the nginx container is bind-mounted from:

`/home/kaochuchian/dify/docker/nginx/conf.d`

That host path is the persistence target. Editing only `/proc/<pid>/root/...` is risky because a container/process recreation can discard namespace-local changes. The AI-DEV-166 deployment helper discovers the active nginx master, detects the bind mount, and updates the durable host config when available.

## Why 172.19.0.1 Is Used

The nginx process runs inside the Docker network namespace. `127.0.0.1` from nginx means the nginx container itself, not the GCP host. The manual rerun bridge listens on the host bridge address currently reachable from nginx:

`http://172.19.0.1:18080`

The persistent nginx routes proxy to that endpoint:

- `location = /stock-ai-dashboard/api/manual-rerun`
- `location ^~ /stock-ai-dashboard/api/manual-rerun/`

Both routes use:

`proxy_pass http://172.19.0.1:18080;`

## Runtime PIN Hash Setup

Never paste the 6-digit PIN into ChatGPT, Codex, GitHub, docs, logs, artifacts, or shell history.

Use the existing hash helper interactively on GCP. The PIN should be typed only into the GCP terminal prompt and must not be echoed.

The runtime-only PIN hash file is:

`/home/kaochuchian/.config/stock-ai/manual_rerun_pin_hash`

Required permissions:

`0600`

Verification without printing hash contents:

```bash
stat -c '%a %U %G %n' /home/kaochuchian/.config/stock-ai/manual_rerun_pin_hash
```

Expected mode:

`600 kaochuchian kaochuchian /home/kaochuchian/.config/stock-ai/manual_rerun_pin_hash`

If the PIN hash file is missing, the bridge must report `manual_rerun_disabled`. There is no unauthenticated fallback.

## Bridge Service Deployment

The systemd service is:

`stock-ai-manual-rerun-bridge.service`

Expected command:

`/usr/bin/python3 /home/kaochuchian/stock-ai/scripts/orchestrator/manual_rerun_runtime_bridge.py --serve --host 172.19.0.1 --port 18080`

Check service without printing secrets:

```bash
systemctl status stock-ai-manual-rerun-bridge.service --no-pager
python3 scripts/orchestrator/deploy_manual_rerun_bridge_service_v1.py --dry-run --pretty
```

Apply/re-apply service if needed:

```bash
python3 scripts/orchestrator/deploy_manual_rerun_bridge_service_v1.py --apply --pretty
```

The helper preserves the hardened service shape: `NoNewPrivileges`, `PrivateTmp`, `ProtectSystem=full`, and narrow `ReadWritePaths`.

## Nginx Route Deployment

Dry-run nginx discovery and route check:

```bash
python3 scripts/orchestrator/deploy_manual_rerun_runtime_route_v1.py --dry-run --pretty
```

Apply/re-apply route if needed:

```bash
python3 scripts/orchestrator/deploy_manual_rerun_runtime_route_v1.py --apply --pretty
```

The helper:

- Finds the active nginx master process.
- Detects the `/etc/nginx/conf.d` bind mount.
- Updates `/home/kaochuchian/dify/docker/nginx/conf.d/default.conf` when available.
- Inserts or replaces only the manual rerun route block.
- Creates a timestamped backup before modifying config.
- Runs nginx config test before reload.
- Reloads nginx via the active nginx container when needed.
- Verifies healthz.
- Is idempotent and must not duplicate location blocks.

## Health Checks

Direct bridge health:

```bash
curl -sS http://172.19.0.1:18080/stock-ai-dashboard/api/manual-rerun/healthz | python3 -m json.tool
```

Public nginx health:

```bash
curl -sS http://35.201.242.167/stock-ai-dashboard/api/manual-rerun/healthz | python3 -m json.tool
```

Expected runtime-ready indicators:

- `ok=true`
- `status=ready`
- `pin_config_source=runtime_config_file`

## Safe Rejection Tests

These tests do not use the real PIN and must not trigger a valid rerun.

Missing confirmation:

```bash
curl -sS -X POST http://35.201.242.167/stock-ai-dashboard/api/manual-rerun \
  -H 'Content-Type: application/json' \
  -d '{"window":"intraday_1305","mode":"dashboard_refresh_only","pin":"abc123"}' \
  | python3 -m json.tool
```

Expected:

- HTTP 403
- JSON response
- `reason=single_window_confirmation_required`

Invalid PIN format:

```bash
curl -sS -X POST http://35.201.242.167/stock-ai-dashboard/api/manual-rerun \
  -H 'Content-Type: application/json' \
  -d '{"window":"intraday_1305","mode":"dashboard_refresh_only","pin":"abc123","confirm_single_window_only":true}' \
  | python3 -m json.tool
```

Expected:

- HTTP 403
- JSON response
- `status=invalid_pin_format`

## Verify No Delivery Process Started

After rejection tests, inspect process list:

```bash
ps -ef | grep -E 'run_stock_analysis.sh|approved_pre_open_delivery.py|scripts/run_pipeline.py|manual_rerun_single_window.py' | grep -v grep || true
```

Expected: no delivery/pipeline/manual rerun execution process.

## Validator

Run:

```bash
python3 scripts/orchestrator/validate_manual_rerun_runtime_persistent_deployment_v1.py --pretty
```

The validator separates:

- repo static checks
- GCP runtime checks
- skipped runtime checks for offline/CI contexts

It confirms the bridge service, PIN file metadata, nginx route, public healthz, safe rejection behavior, and no delivery process start.

## Rollback

Stop and disable the bridge service:

```bash
sudo systemctl disable --now stock-ai-manual-rerun-bridge.service
```

Restore nginx config from a helper-created backup if needed:

```bash
sudo cp /home/kaochuchian/dify/docker/nginx/conf.d/default.conf.ai-dev-166-backup-YYYYMMDDHHMMSS \
  /home/kaochuchian/dify/docker/nginx/conf.d/default.conf
sudo docker exec docker-nginx-1 nginx -t
sudo docker exec docker-nginx-1 nginx -s reload
```

Or manually remove only the block between:

- `# STOCK-AI-MANUAL-RERUN-API-START`
- `# STOCK-AI-MANUAL-RERUN-API-END`

Then reload nginx and verify the public healthz route no longer reports ready.

## Persistence Warning

If the Dify/nginx container is recreated from a template that overwrites `default.conf`, rerun:

```bash
python3 scripts/orchestrator/deploy_manual_rerun_runtime_route_v1.py --apply --pretty
python3 scripts/orchestrator/deploy_manual_rerun_bridge_service_v1.py --apply --pretty
python3 scripts/orchestrator/validate_manual_rerun_runtime_persistent_deployment_v1.py --pretty
```

## Safety Boundaries

AI-DEV-166 does not run `python3 main.py`, does not run the production pipeline, does not trigger a valid manual rerun, does not send LINE/Email, does not modify scheduler/cron, does not write DB, does not trade/order, and does not read or print PIN hash contents.
