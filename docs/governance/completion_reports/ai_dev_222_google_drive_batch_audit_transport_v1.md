# AI-DEV-222 — Google Drive Batch Audit Transport V1

## Repository

- Starting main: `3771850a276adbffe429736b9efbf95b8a0f2ee8`
- Branch: `ai-dev/222-google-drive-batch-audit-transport-v1`
- PR, CI, implementation and merge identities are recorded in governed GitHub history.

## Architecture

The existing immutable snapshot, Visual Evidence and notification provenance
remain authoritative. AI-DEV-222 consumes those identities after admission and
rendering, creates a deterministic seven-window audit outbox item, and delegates
network delivery to an independent bounded worker. Drive failure cannot change
batch, notification, Decision, trading-date or archive results.

Each bundle carries report HTML/PDF/PNG, immutable snapshot wrapper, actual
rendered LINE/Email evidence, delivery status, hashes, retention metadata and a
sanitized manifest. Email preview PDF is rendered asynchronously; failure is
truthfully degraded. Upload state is per-file, resumable and checksum guarded.

## Authentication correction

The destination is My Drive, not Shared Drive. No service account, JSON key,
attached-VM identity change, Token Creator grant or impersonation was created.
Production uses one-time human OAuth consent with `drive.file`; client secret and
refresh token live only in the approved GCP Secret Manager mechanism. The app
creates an app-owned root rather than assuming access to the existing
connector-created folder. Full Drive scope is not used.

## Validation and safety

The ACTIVE required validator covers all seven windows, market/date isolation,
admission, notification parity, secret rejection, deterministic paths,
idempotency, partial recovery, conflicts, Drive degradation, archive stability,
US calendar/20:00→23:00 lineage, disabled mode and fake CI transport.

- Production/manual batch: false.
- LINE/Email send: false.
- Trading/orders: false.
- Service account/IAM/credential activation: false.
- Production DB/archive mutation: false.
- Scheduler/systemd/nginx/network mutation: false.

## Remaining hard gate

PM interactive OAuth consent, approved Secret Manager activation, controlled
no-send TW/US upload, ChatGPT Drive readback and natural lifecycle verification
remain pending.

## Secret access infrastructure closure

Controlled activation correctly failed closed because the production VM's
legacy OAuth scopes do not authorize Secret Manager. The VM default Compute
identity also retains project Editor, so adding `cloud-platform` would expose a
materially broader effective permission set. No IAM, scope, identity or VM
mutation was performed. The repository now normalizes base secret resources to
`/versions/latest`, accepts explicit positive numeric versions for rollback,
returns sanitized failure reasons, pins the compatible Secret Manager/protobuf
stack, and registers an ACTIVE required preflight validator.

The recommended production architecture is a separate least-privilege uploader
execution boundary with access to only the OAuth-envelope secret. The uploader
remains disabled pending one PM-approved integrated infrastructure change and a
separately authorized controlled activation.

- Hard-gate implementation commit: `d1071db`
- Pull request: `#296`
- CI and final merge identity: governed GitHub history for PR `#296`

The declared compatibility set (`google-cloud-secret-manager==2.29.0`,
`protobuf==5.29.6`, `grpc-google-iam-v1==0.14.4`,
`grpcio-status==1.71.2`) was installed with the OAuth/Drive dependencies and
`google-ai-generativelanguage==0.6.15` in an isolated environment; `pip check`
reported no broken requirements.

## Fixed-loopback activation hardening

The post-merge activation review found that an unpinned VM loopback callback
cannot be reached by a consent flow opened on the PM's Mac. The helper now uses
an explicit callback port (default `8765`), binds only `127.0.0.1`, displays the
authorization URL, and supports a native Mac SSH local-port tunnel. Callback
timeout, cancellation, occupied port, authorization failure and Secret Manager
write failure all fail closed with sanitized reason codes. A required ACTIVE
validator covers the loopback, output, credential-file and uploader-disabled
boundaries. No OAuth activation or credential handling occurred during this
repository-side hardening.

`IMPLEMENTED_PENDING_NATURAL_VERIFICATION`
