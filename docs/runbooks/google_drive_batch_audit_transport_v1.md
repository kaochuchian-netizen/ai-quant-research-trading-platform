# Google Drive Batch Audit Transport V1

## Boundary

AI-DEV-222 transports already-admitted TW/US evidence. It does not create a
snapshot, recompute Research/Decision, resend a notification, or execute a
trade. `STOCK_AI_BATCH_AUDIT_ENABLED` is disabled by default and failures are
always non-blocking.

The target is Google **My Drive**. A service account cannot own My Drive files,
so service accounts, JSON keys, attached-VM identity, Token Creator grants and
impersonation are prohibited. Production uses one explicitly authorized human
OAuth identity with the minimal `drive.file` scope.

## OAuth activation hard gate

Repository and CI validation use `FakeDriveBackend`. Do not run activation until
PM authorizes the one-time browser consent and the approved GCP Secret Manager
resource exists.

1. Create a Google OAuth Desktop client under the governed Google project.
2. Prepare an existing Secret Manager secret for the OAuth envelope. Do not put
   its value in shell history, logs, artifacts or Git.
3. Run `scripts/orchestrator/activate_google_drive_batch_audit_oauth.py` with the
   local client JSON and Secret Manager resource. The helper requests only
   `drive.file`, writes the envelope to Secret Manager over stdin, suppresses
   command output and never writes tokens to the repository.
4. Configure only the secret **resource name** as
   `STOCK_AI_DRIVE_OAUTH_SECRET_RESOURCE`, then set
   `STOCK_AI_BATCH_AUDIT_ENABLED=1` through the approved production mechanism.

The uploader creates its own app-owned `Stock-AI-Batch-Audit` root. It does not
assume `drive.file` can access the existing connector-created folder
`1JCCyIV5fRVepN5hOotxNjq6Xqko1n3hy`; that folder remains untouched. Never
silently expand to full Drive scope.

## Operation

The production runner enqueues after admission, public/visual evidence and
notification rendering. The outbox is
`artifacts/runtime/chatgpt_batch_audit_outbox/DATE/MARKET/WINDOW/revision-NNNN`.
Run the independent worker:

```bash
python3 scripts/orchestrator/upload_google_drive_batch_audit.py --pretty
```

This command uploads only allowlisted bundle files. It uses per-file checksums,
does not overwrite a different remote body, resumes partial state, and renders
the captured Email body PDF asynchronously. `403`, `404`, `429`, timeouts and
`5xx` become a sanitized `DEGRADED` upload state; the production batch remains
successful. Diagnose folder access, OAuth revocation, quota and provider health
without rerunning or resending the batch.

## Controlled no-send validation

After PM OAuth authorization, select one existing admitted TW and one admitted
US snapshot. Build/upload from immutable evidence only; do not create a new
revision and do not invoke delivery functions. Confirm Drive folder hierarchy,
manifest identity, file hashes and `delivery_status.json`. ChatGPT Drive
retrieval is PASS only when the connector can search the new app-owned folder
and read the same snapshot/revision/hash. Upload success alone is not ChatGPT
readback success.

## Rotation, revocation and rollback

- Rotation: repeat consent only with PM authorization, add a new Secret Manager
  version, validate no-send upload, then disable the old version.
- Revocation: revoke the Google OAuth grant, disable
  `STOCK_AI_BATCH_AUDIT_ENABLED`, and retain outbox evidence for review.
- Pause/rollback: set the enabled flag to `0`. Core batches and notifications
  continue; no scheduler, runner, archive or Drive deletion is required.
- Outbox cleanup is a separate governed retention action. Never use broad
  `rm -rf`; verify every item is uploaded and retained before targeted cleanup.
- No Drive deletion is implemented in AI-DEV-222. Visual retention metadata is
  90 days and structured evidence is long-term, pending a future policy task.

## Failure and security rules

Never print or commit client secret, refresh/access token, request headers,
recipient authorization, environment dumps or provider responses containing
credentials. Never mark API success as recipient receipt. Never share the root
publicly. TW/US paths use their canonical markets, calendars and snapshots and
cannot fall back across markets.
