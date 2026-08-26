# AI-DEV-222 Secret Access Infrastructure Hard Gate V1

## Confirmed evidence and boundary

The production VM is `dify-trading-server`. Its attached identity is
`40559730610-compute@developer.gserviceaccount.com`; the project-level binding
includes `roles/editor`, while the VM legacy OAuth scopes omit
`cloud-platform`. The controlled Secret Manager write returned
`ACCESS_TOKEN_SCOPE_INSUFFICIENT`. These facts establish a scope gate, not a
reason to grant the existing Editor identity a broad token scope.

Read-only Console inspection confirmed the VM is running and its effective
legacy scope profile is: Service Control enabled; Service Management and Cloud
Storage read-only; Logging, Monitoring and Trace write-only; Cloud Platform
disabled; other listed data/admin APIs disabled. Project IAM shows the default
Compute service account bound to Editor and flags it as over-privileged. No
Console mutation was performed.

No IAM policy, access scope, attached identity, VM state, secret value or
service definition is changed by this repository closure. The uploader remains
disabled. A service-account JSON key, impersonation, human ADC on the VM and a
plaintext refresh token are prohibited.

## Runtime dependency inventory

Repository-static evidence identifies these credential/runtime families:

| Capability | Current ownership | VM default SA dependency established? |
|---|---|---|
| Google Sheets stock universe | explicit service-account credential file in `app/loaders/google_sheet_loader.py` | No; explicit file path, separately governed |
| Market/news providers | provider credentials or unauthenticated HTTP, local files | No repository evidence |
| LINE/Email | existing application secret/environment contracts | No repository evidence |
| Dashboard/archive/outbox | local filesystem and governed publish paths | No |
| Google Drive API | human OAuth `drive.file` refresh token | No; SA does not call Drive |
| Secret Manager envelope read/write | Google ADC transport identity | Yes if run on the current VM; blocked by its OAuth scope |
| Cloud Logging/Monitoring | platform/agent concern | Live host inventory required before changing the VM identity |

The live systemd/API-call inventory could not be completed through the current
read-only SSH path. Therefore absence of a repository reference is not proof of
absence in production. This uncertainty is itself a fail-closed reason not to
alter the main VM identity or remove Editor in this task.

## Option comparison and permission-impact evidence

### A — migrate the main VM identity

This requires a complete live workload permission inventory, Policy Simulator
tests against every service, a replacement custom/predefined role set, and a
maintenance operation to change VM scopes/identity. `cloud-platform` would let
the token exercise every IAM permission still granted to the Editor identity;
adding it before removing Editor expands effective authority materially.
Editor itself does **not** include `secretmanager.versions.access`, so even that
scope expansion would not complete the runtime read contract without a further
Secret Accessor grant. Removing Editor first risks breaking unknown production
dependencies. This is not the recommended first move.

### B — isolated uploader execution boundary (recommended)

Create a dedicated uploader runtime identity with no Editor and no access to
the trading/runtime control plane. Grant only:

- `secretmanager.versions.access` on the single OAuth-envelope secret;
- the minimum logging permission required by that isolated runtime;
- only the narrowly designed read/ack transport needed for admitted outbox
  bundles, after that transport receives a separate design review.

The Drive call continues to use the human OAuth `drive.file` credential stored
in Secret Manager; the runtime service identity only authorizes reading that
one secret. The main production VM remains unchanged. Before activation, run
Policy Simulator (or a dry-run permission test under the new identity) proving
access to the named secret and denial of unrelated secrets, IAM mutation,
Compute administration, trading data stores and other project resources.

The current equivalent pre-change evidence is the conjunction of the Console
scope matrix, project IAM binding/security insight, repository-static
dependency inventory and a deny-by-design permission matrix. A real Policy
Simulator replay belongs to the PM-approved infrastructure change because the
candidate identity/policy does not yet exist. It must be captured before that
policy is applied.

### C — other keyless designs

KMS-encrypted local tokens still require a decrypting identity and durable
ciphertext lifecycle, and do not remove the main-VM scope issue. Workload
Identity Federation normally culminates in a service identity/token exchange
and introduces a larger trust configuration; impersonation is explicitly out
of scope. Operator-mediated access is not autonomous production and human ADC
must not remain on the VM. These are not preferable to B.

## Stage-complete activation and rollback

1. Keep uploader disabled; merge repository normalization, pins, diagnostics
   and preflight gates.
2. Inventory live services/API calls using the default Compute SA and export a
   read-only IAM/Policy Simulator evidence package. Do not alter the VM.
3. PM approves one integrated infrastructure change: provision the isolated
   uploader boundary and its single-secret least-privilege policy, including a
   reviewed outbox handoff.
4. Prove allow/deny expectations and Secret Manager access using a non-secret
   preflight; then conduct the separately authorized OAuth activation.
5. Enable only the isolated uploader after controlled no-send verification.

Rollback is immediate: disable the uploader boundary, revoke/disable the new
OAuth secret version, pin the previous numeric version if rollback validation
requires it, and retain the outbox. The main VM, scheduler, archive, delivery
and trading paths require no rollback because they were never changed.
