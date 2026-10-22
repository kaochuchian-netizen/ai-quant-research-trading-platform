# AI-DEV-284 — Date-specific TW correction publication

## Scope and root cause

The existing latest publisher resolves admitted natural snapshots and cannot
select an isolated correction bundle. The correction renderer deliberately
labels its output unpublished. Copying that preview into latest would bypass
identity selection and could replace a newer report.

The new explicit publisher reuses the existing renderer, canonical correction
validator, quality gate, and atomic-copy primitive. It publishes exclusively to:

`/dashboard/archive/tw/post_close_1500/<session>/corrections/<correction-id>/index.html`

It does not modify the resolver, existing route publishers, scheduled batches,
canonical evaluations, immutable snapshots, latest, notifications, or databases.
The source correction remains `isolated_correction` / `admitted=false`; a separate
publication receipt records public availability without relabelling source data.

## Guards

- Explicit pre-open and post-close immutable inputs; full envelope hashes,
  revision, natural source identity, market/date/window, dynamic universe and
  canonical correction identity must validate.
- Recomputed correction must equal the saved correction. The receipt binds the
  provenance, universe, qualified quality gate and exact output hashes.
- Saved HTML must equal the existing renderer's deterministic output. Only
  known publication labels and route metadata change; individual cards and
  original metrics are preserved. The final HTML receives a new SHA-256.
- Original HTML requires an operator-confirmed SHA-256 and matching six-field
  original snapshot identity. Latest identity is recorded, including a newer
  trading date when present. Neither original nor latest is ever a write target.
- Source/latest changes during staging abort. Symlinks, route collision and
  unverified prior attempts fail closed. A route-scoped nonblocking flock
  prevents concurrent publishers using different audit roots.
- Public directories created by this publisher are 0755 and HTML is 0644 even
  under restrictive umask. Existing inaccessible directories cause failure;
  existing permissions are never relaxed.
- The existing atomic-copy helper stages bytes; an exclusive same-filesystem
  hard link makes the verified page visible atomically without overwriting a
  racing file. Public read verification checks HTTP 200, unchanged URL and
  exact response SHA-256, with a bounded timeout and no retry.

## Durable rollback evidence

Before publication, a private directory outside public/source trees holds:
`original.html`, `latest.before.html`, `original.snapshot.json`, `prepared.json`,
and the final candidate `published.html`. Original metrics remain recoverable
from the exact original HTML and snapshot; correction metrics, original identity,
source hashes, route and provenance are bound in the preparation manifest.
Files and preparation directory are fsynced before the public name is created.
A successful attempt appends `published.json`; failure appends `failed.json`.

Verification failure retracts only the newly created link when its inode and
hash still belong to this attempt. It never restores old HTML over latest or
removes a foreign replacement. Candidate bytes and failure evidence remain
private. Interrupted attempts and failed attempts require explicit review;
they are not automatically retried. A proven identical successful publication
returns idempotently without changing public mtime or writing another page.

## CLI and activation

`scripts/orchestrator/publish_tw_correction_dashboard.py` defaults to read-only
preview. Inputs are `--source-dir`, `--pre-open-input`, `--post-close-input` and
`--expected-correction-id`. It prints only route, metrics and the final HTML hash.

After separate deployment and publication approval, `--publish` additionally
requires `--static-root`, `--original-html`, `--expected-original-hash`, a durable
private `--audit-root`, and the actual `--public-base-url`. It does not support
send options. Do not use temporary storage for the production audit root.
Original HTML must be retained independently if latest has moved to a new date.

Production activation must first check source SHA, active jobs, governance,
source bundle identity and the approved original HTML/hash. Preserve the exact
private evidence directory for any subsequent rollback review. No public URL
or notification is claimed delivered until the corresponding gate passes.

## Validation

Public fixtures are entirely invented, reused from AI-DEV-283. No production
payload, identity, values, receipt, recipient or fixture is added to this PR.

- 23 targeted publication tests plus existing delivery, presentation and route
  regressions: 67 tests PASS.
- Covers dynamic universes, hashes/identity, collisions, partial staging,
  rollback/foreign replacement, concurrent entry, idempotency, newer latest,
  source preservation, permissions and default preview/no-send.
- Isolated local HTTP returns 200 with exact bytes. This is not production HTTP
  acceptance.
- Chromium at 393px: no horizontal overflow, all synthetic cards present, all
  details initially collapsed and expansion works. Actual production rendering
  remains a separately approved publication acceptance.
- CI explicitly runs the new tests with the existing branch gate; no Registry
  or quarantine exception is added.

AI-DEV-282 remains paused. Production deployment and publication each require
PM approval. LINE/Email sending is outside this publisher and this task.
