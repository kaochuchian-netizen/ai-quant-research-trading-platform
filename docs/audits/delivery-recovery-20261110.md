# Delivery recovery boundary repair — 2026-11-10

Status: IMPLEMENTED_PENDING_NATURAL_VERIFICATION. Draft only; no merge or deployment authorization.

TW previously bounded only analysis; US subprocess failure lost admission and channel policy context. Both scheduled delivery parents now supervise the entire worker with a unique run identity and run-scoped result, stage and termination evidence. US retains admission facts when the worker fails later. LINE policy matches the existing three-window sender behavior.

Channel attempts claim snapshot/channel identity before transport, including changed rendered content; prior failures and uncertain attempts never auto-retry. Recipient counts are normalized across LINE chunks. Dashboard publication serializes by market and verifies retained identity before suppressing a repeat.

Governance accepts only exact receipt/claim paths bound to admitted immutable source identity and hashes, and completed Supervisor evidence with a run-bound manifest and verified file hashes. Unknown, malformed, modified, symlinked or extra evidence remains fail-closed. Incomplete in-flight supervisor output is intentionally not classified as completed preserved evidence.

## Validation

- Prior implementation: 29 affected tests PASS; no wholesale repeat this turn.
- Governance/manifest changes: 19 relevant tests PASS (new governance tests, affected receipt governance and supervisor tests).
- Existing local 11/06 TW 07:00 and US 06:30 immutable sources reused without download or analysis. US effective trading date is 11/05.
- `rehearse_delivery_recovery.py` ran production render/publish helpers against temporary roots, with network denied and filesystem mutations restricted to its temporary root. Source bytes and isolated archive hashes remained unchanged.
- Both market pages passed identity verification; repeat publication was suppressed. Four channel paths each simulated two recipient outcomes (one accepted, one rejected); duplicate attempts were suppressed. These are injected transport results, not actual provider receipts or end-user delivery.
- No Production connection, formal batch, formal publish, notification, credentials or trade was performed by the rehearsal. Production immutability is enforced by isolation/write denial, not a fresh remote inventory.
- Machine-readable results: `delivery-recovery-20261110-rehearsal.json`.

## Remaining authorization

CI must pass before review readiness. Actual historical publication/resend needs a separate explicit authorization and a recipient/receipt plan; this change neither deletes prior receipts nor bypasses failure suppression. Natural verification remains pending.

## CI correction 1

The first CI branch gate passed every registered semantic validator but rejected `reports/line_report_sender.py` as outside the existing allowed source paths. The legacy sender extension was removed from the PR without changing any governance allowlist or threshold. Receipt adapters retain known returned outcomes; when the legacy LINE sender raises before returning per-recipient responses, unobservable recipients remain unknown and cannot establish transport acceptance. No resend is authorized by that uncertainty.
