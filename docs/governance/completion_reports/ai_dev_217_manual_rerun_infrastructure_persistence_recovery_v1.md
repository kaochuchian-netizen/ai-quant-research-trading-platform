# AI-DEV-217 Manual Rerun Infrastructure Persistence Recovery V1

## Repository

- Starting main: `25189f35d41704f424180c2ed0828d1f363a5f98`
- Branch: `ai-dev/217-manual-rerun-persistent-route-recovery-v1`
- GitHub PR, CI, merge SHA, and final main are recorded in the final execution handoff after protected-branch closure.

## Root cause

The 2026-08-15 controlled-verification request reached public nginx, but nginx returned its static 404 before the bridge. The bridge service was active and healthy at `172.19.0.1:18080`. The Dify nginx entrypoint regenerates `default.conf` from `default.conf.template` on container creation. The prior AI-DEV-166 route deployer changed only active `default.conf`, and its runbook required a manual redeploy after recreation. The GCE reset recreated nginx and erased the runtime-only route.

Classification: `POST_GCE_RESET_SERVICE_RECOVERY_FAILURE`.

AI-DEV-217 application code was not causal.

## Persistent ownership closure

- Repository canonical route: `config/nginx/manual_rerun_api_proxy_v1.conf`
- Host persistent template: `/home/kaochuchian/dify/docker/nginx/conf.d/default.conf.template`
- Generated active config: `/home/kaochuchian/dify/docker/nginx/conf.d/default.conf`
- Container mount: `./nginx/conf.d:/etc/nginx/conf.d`
- Dify entrypoint render: `envsubst ... default.conf.template > default.conf`
- Bridge target: `http://172.19.0.1:18080`

The exact POST endpoint and prefix status/health endpoint are inserted before the static Dashboard alias:

- `location = /stock-ai-dashboard/api/manual-rerun`
- `location ^~ /stock-ai-dashboard/api/manual-rerun/`
- `location ^~ /stock-ai-dashboard/`

PIN validation, request validation, task admission, and job creation remain owned by `stock-ai-manual-rerun-bridge`.

## Recovery evidence

- Deterministic dry-run: PASS
- Template changed: true
- Active config changed: true
- Persistent template SHA-256 before: `7bedcfe861a91af205a1727694d1eacea908829ebd744c52097e02aad229e8f4`
- Persistent template SHA-256 after: `edcd5057a2a705e863f6c74311bce034de175f7a1465ead1966dbf3dc9529edc`
- nginx container force recreation: completed
- Recreated container ID observed: `053a13aee8c0`
- `nginx -t`: syntax OK, test successful
- Persistent template exact/prefix counts: 1/1
- Re-rendered active exact/prefix counts: 1/1
- Bridge service: active
- Bridge status GET: HTTP 200, 5755 bytes
- Public status GET: HTTP 200, 5755 bytes
- Bridge/public status body parity: exact
- Static Dashboard GET: HTTP 200, 27801 bytes

No POST request was used for recovery validation.

## Regression protection

`validate_ai_dev_217_manual_rerun_nginx_persistence_v1.py` is an ACTIVE required leaf in branch and post-merge gates. It checks:

- canonical exact and prefix routes;
- correct bridge target;
- API precedence over the static alias;
- idempotent persistent rendering;
- container-recreation render simulation;
- missing route, wrong target, static swallow, and route-order mutations;
- transport-only nginx ownership with no PIN bypass.

Initial dedicated result: 16/16 PASS. Validator registry integrity: PASS.

## Safety

- GCE reboot/reset: false
- Manual/controlled rerun: false
- Production analysis pipeline: false
