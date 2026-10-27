# AI-DEV-286 — Verified existing correction publication

## Inventory completed before implementation

No Production writes or write probes. Private topology/output evidence remains
outside Git. These are the initial findings, not a Production publication claim.

| Boundary | Initial state | Location / evidence | Minimal action / test / stop condition |
|---|---|---|---|
| CLI -> prepare -> correction -> evaluate | BLOCKED | `correction_publication.prepare`, `tw_delivery_evaluation.correction` loops over evaluate | Replace with stored identity/hash validation; trace must show zero computation calls |
| prepare -> batch_gate -> evaluate_card -> quality -> evaluate | BLOCKED | `post_close_quality_gate`, `tw_delivery_evaluation.quality` | Verify pinned saved gate against stored canonical components; do not call gate |
| prepare -> render_snapshot_archive_page -> projection/renderer -> quality/evaluate | BLOCKED | `multi_market_dashboard`, `mobile_decision_presentation` | Verify existing output bytes using independently pinned receipt; no render |
| receipt/output authentication | BLOCKED | Old receipt has output hashes but CLI has no external receipt pin | Require expected receipt SHA-256; reject rehashed malicious receipt |
| root alias, directory descriptors, inode reuse | PASS (read-only topology + prior synthetic tests) | `trusted_static_root`; publisher retains staging FD | Preserve guard; test swaps, traversal, ownership, cleanup |
| backup/staging permission and space | UNKNOWN for actual write | Read-only effective-user access and filesystem space can be checked | Add read-only preflight; test EACCES/ENOSPC; actual quota/ACL/write remains Production-only pending |
| atomic promotion | PASS mechanism, integration pending | private `_atomic_copy`, public staging plus exclusive same-directory hard link | Public source/target share parent FD/filesystem; failure never replaces latest |
| publication lifecycle | BLOCKED gap | No durable post-link/pre-HTTP record; old idempotency ignores failed evidence | Persist staged and promoted receipts; unknown/failed attempt blocks retry |
| interrupted cleanup | PASS fail-closed, operator review needed | missing final receipt cannot be assumed success | Crash tests; no automatic deletion/retry of unknown state |
| nginx route | PASS read-only configuration; public correction pending | existing alias and bind mount map same physical directory | Isolated alias-route HTTP test; actual public URL check only after approval |
| original/latest | PASS read-only identity and preserved source available | original archived visual HTML + newer latest | Copy original/latest before link, verify hashes through HTTP acceptance; never write either |
| DB/scheduler/trading/transport | PASS absent from publisher call graph | CLI imports publisher; HTTP callback only performs bounded GET | Patch forbidden calls and trace execution; no sends/no batch entrypoints |

Call graph before: CLI -> trust config read -> prepare -> correction/evaluate,
quality gate/evaluate, renderer/evaluate -> backup -> private staging -> public
staging -> exclusive link -> HTTP GET -> success receipt; failures remove only
owned inode/hash and retain private evidence. File writes occur only inside
publish (private audit, new route directories, lock, staged/new HTML, receipts).
No DB/scheduler/trading/notification calls were found. `_atomic_copy` is only a
local copy + replace helper; it is not an evaluator.

Production-only prerequisites: fresh approved root pins, external receipt pin,
no active worker, permitted time window, actual authorized writes, crash/power
loss durability and public HTTP/browser acceptance. Read-only access/space checks
cannot prove future quota, ACL or network behavior. No silent PASS for these.

## Implemented call graph and side effects

CLI -> optional reviewed StaticRoot policy -> `prepare` ->
`verify_receipt_pin` -> `verify_existing` -> compare saved output hashes ->
presentation-only label/route transformation -> optional read-only resource
preflight -> existing publisher lock/backup/stage/exclusive link -> bounded
public HTTP GET -> terminal publication receipt.

`verify_existing` only compares stored values, validates schemas/identities and
calculates integrity hashes. It never derives direction, hit/miss, price ranges,
OHLC or forecast projections. Saved canonical components must equal saved quality
components. The separately approved receipt digest anchors saved renderer bytes;
correction identity anchors evaluation/provenance digests. An unsupported schema,
missing renderer, changed source or mismatched component fails closed. No fallback
builder exists. No analysis engine, notification, DB or scheduler code was changed.

The only calculated report summary is a count of stored canonical result enums.
Original card dictionaries/payload/envelopes must match except the already-saved
correction fields. Primary HTML articles and overview remain byte-for-byte equal
across the enumerated label-only substitutions. Source and output hashes, receipt
pin and transformation version are retained in private publication provenance.

## Final blocker resolution / stopping evidence

| Initial blocker | Isolated result / proof | Production state |
|---|---|---|
| Three indirect recomputation paths | Removed; actual Python profiling rejects evaluate/correction/quality/freeze/bind/render/fetch/predict/transport calls after synthetic bundle construction | Existing private bundle passed read-only admission without computation |
| Saved output authenticity | Mandatory independent receipt SHA pin; edited HTML plus rehashed receipt rejected | Approved pin must be rechecked by operator; no policy installed |
| Missing resource preflight | `--preflight` checks effective access, private backup permissions, space/inodes, original/latest identity, route and static-root pins without writes | Read-only observations only; write/quota/network remain PENDING |
| Missing post-link state | fsynced `staged.json`, `promoted.json` before HTTP; final receipt only after exact HTTP bytes and source/latest recheck | No actual publication attempted |
| Unknown/crashed attempt | Simulated pre-link/post-link process interruption blocks retry; final receipt failure rolls back owned new route only | Actual power-loss/process-death state needs operator review |
| Idempotency | Success requires matching source/input hashes, metrics, target inode/hash, promoted evidence, no failed marker; HTTP checked again when requested | Prior unknown attempt is not recoverable automatically |
| Static root, collision, cleanup | Existing alias/child/root swaps, concurrent lock, partial writes, inode reuse, collision and rollback regressions retained | Fresh policy/root pins and no active worker are execution-time gates |
| Full public path | CLI preflight + publish + idempotent repeat via simulated nginx alias prefix and real local HTTP; 393px browser checks primary universe, scroll width and collapsible details | Actual nginx/public URL/browser acceptance PENDING |

## Test matrix and evidence policy

- Unit admission/lifecycle: mandatory receipt pin, saved quality/version/stage and
  source identity, missing output without fallback, read-only preflight, permission
  and space failures, persisted transitions, crash before/after link, final receipt
  failure, failed prior receipt, source mutation during HTTP and replaced inode.
- Existing regression suites retain dynamic 8/15/30-symbol and leading-zero cases,
  tamper rejection, original/latest protection, symlink/path-traversal guards,
  concurrency, partial writes, rollback and Linux inode-reuse protection.
- Synthetic E2E uses ten invented symbols and prices, a future synthetic date and
  a 5-hit/5-miss direction, 9-partial/1-miss range distribution. Fixture evaluation
  occurs only before the traced publisher execution. CLI then verifies the saved
  bundle, publishes to a pinned root alias, verifies exact HTTP bytes and repeats
  idempotently. No Production-derived fixture is committed.
- Local HTTP serves the same alias-prefix semantics; it is not a real nginx
  process. Real nginx bind-mount/alias configuration was inspected read-only.
  Absence of local nginx is explicitly not hidden as nginx integration PASS.
- Real stored correction compatibility was checked read-only with forbidden-call
  trace; private source/output/receipt identifiers stay outside Git. No original
  renderer bytes were rewritten and no new canonical evaluation was created.
- Mac affected regressions and Linux CI are separate evidence. An earlier combined
  Mac run passed 81 tests but could not import Playwright after temporary runtime
  files disappeared; the browser case is rerun in a persistent isolated local
  environment, not skipped or marked PASS by quarantine.

No quarantine, bypass, registry policy or Production preservation rule changes.
The normal Linux branch registry gate and the affected tests run in GitHub CI.
Production-only prerequisites remain pending regardless of CI result.

## Operator handoff

See [executable runbook](../architecture/ai-dev-286-correction-publication-runbook.md)
for command arguments, permissions, independent pins, write scopes and stop/
recovery conditions. Snapshot-builder/replay commands are deliberately absent.
Approval is still required for merge, source sync, trust config installation,
backup/publication and actual public acceptance. Notifications are not included.
The private review packet supplies real paths/identities; no raw runtime evidence,
recipient or credential is in this PR. Production mutation = NONE.
