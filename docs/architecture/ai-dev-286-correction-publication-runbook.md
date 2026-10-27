# AI-DEV-286 — Verified-existing correction publication runbook

**Not authorization to execute.** Merge, source sync, trust-policy installation,
private backups and public publication each require PM approval. No notification,
evaluation, market acquisition, prediction, database, scheduler or service action
is part of this runbook. AI-DEV-282 remains paused.

Use the existing publisher CLI, not a batch/manual-rerun/correction-builder CLI.
All identifiers, input paths and approved hashes are supplied from the private
review packet; do not commit that packet. The receipt pin must come from the
independent approval record, **not** be calculated from the current receipt and
automatically trusted at invocation. Original source files are always read-only.

## Approved operator variables

Run from the approved checkout as the reviewed publication UID, using its existing
Python runtime. These shell checks deliberately stop if any reviewed value is
missing. Paths are absolute. `PUBLIC_BASE` is the real externally accessible nginx
prefix ending in `/stock-ai-dashboard`, not localhost and not a filesystem path.
`ORIGINAL_HTML` names the existing archived original HTML, not a presumed date
route. `AUDIT_ROOT` is a persistent private directory outside repo/public/source;
it must not be `/tmp`. The command writes one correction-ID subdirectory there.

```sh
: "${APPROVED_SHA:?}" "${REPO:?}" "${PYTHON:?}"
: "${SOURCE_DIR:?}" "${PRE_INPUT:?}" "${POST_INPUT:?}"
: "${CORRECTION_ID:?}" "${APPROVED_RECEIPT_SHA256:?}"
: "${STATIC_ROOT:?}" "${TRUST_CONFIG:?}" "${APPROVED_POLICY_FILE:?}"
: "${ORIGINAL_HTML:?}" "${APPROVED_ORIGINAL_SHA256:?}"
: "${AUDIT_ROOT:?}" "${PUBLIC_BASE:?}"
cd "$REPO"
export PYTHONDONTWRITEBYTECODE=1
```

## A. Fresh read-only deployment and scheduling gate

Permission: read only. Write scope: none. Do not install dependencies.

```sh
test "$(git branch --show-current)" = main
test "$(git rev-parse HEAD)" = "$APPROVED_SHA"
"$PYTHON" - <<'PY'
from pathlib import Path
from scripts.orchestrator.validate_post_merge_status import collect_expanded_git_status, classify_dirty_paths
rows,error=collect_expanded_git_status(Path.cwd())
assert error is None, error
result=classify_dirty_paths(rows)
print({k:len(v) for k,v in result.items()})
assert not result['blocking_task_residue'] and not result['unknown_dirty_paths']
PY
ps -eo pid,ppid,lstart,etime,comm
crontab -l
```

This native expanded classification is **not** the full registry gate. Record
registry PASS/TIMEOUT/PENDING as observed, never invent PASS. Save the expanded
preserved-path inventory in the operator's private evidence packet. Inspect
worker identity, bridge status/children, active task/lock ownership and the
currently configured schedule using the established read-only operations
procedure. Do not equate an idle bridge listener with an active batch, or process
name absence with proof that no worker exists. If any worker is active, any lock
owner is unknown, or publication overlaps an imminent natural batch, **STOP**.
No kill/unlock/rerun/scheduler change is authorized. Source synchronization is a
separate approval; a wrong HEAD stops this runbook.

## B. Topology, permissions and trust policy

Permission: read only until explicit policy installation approval. Write scope:
one reviewed policy file only; never edit alias, mount, nginx or parent ownership.

```sh
id
readlink "$STATIC_ROOT"
readlink -f "$STATIC_ROOT"
namei -l "$STATIC_ROOT"
findmnt -T "$STATIC_ROOT"
df -h "$STATIC_ROOT" "$AUDIT_ROOT"  # if audit root absent, inspect its existing parent
```

Compare every path/device/inode/UID with the separately approved policy. Inspect
all physical parents, the existing target parent and backup parent, effective
write/execute access, free space/inodes, actual nginx alias and bind mount from
read-only configuration. No write probes. Do not infer nginx access from the
host's symlink parent modes alone: its container mount path is the serving path.
Root pins after a reboot/replacement require renewed review, not auto-refresh.
Quota, SELinux/ACL restrictions, future space availability and external HTTP are
Production-only until actual approved publication.

After explicit approval, install the **already reviewed** minimal policy, with
exclusive create and no symlink following. Its parent must already be a reviewed
private directory; if absent, stop for the approved directory-creation plan.
This is not policy discovery. The source policy contains only schema version,
logical/physical root, alias/root device/inode/UID, no credentials.

```sh
export TRUST_CONFIG APPROVED_POLICY_FILE STATIC_ROOT
"$PYTHON" - <<'PY'
import os
from pathlib import Path
from app.dashboard.correction_publication import safe_path
from app.dashboard.trusted_static_root import StaticRoot, load_policy
src=safe_path(Path(os.environ['APPROVED_POLICY_FILE']))
dst=safe_path(Path(os.environ['TRUST_CONFIG']))
policy=load_policy(src)
with StaticRoot(os.environ['STATIC_ROOT'],policy) as root: root.check()
if dst.exists():
    assert dst.read_bytes()==src.read_bytes(), 'Existing policy differs; STOP'
    assert load_policy(dst)==policy
else:
    assert dst.parent.is_dir(), 'Missing reviewed private parent; STOP'
    fd=os.open(dst,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb') as out:
        out.write(src.read_bytes());out.flush();os.fsync(out.fileno())
    parent=os.open(dst.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try: os.fsync(parent)
    finally: os.close(parent)
with StaticRoot(os.environ['STATIC_ROOT'],load_policy(dst)) as root: root.check()
PY
```

Mismatch/unsafe ownership or permissions: STOP, no overwrite or broadening.
Interrupted policy installation: retain evidence, compare exact bytes before
any subsequent action. Do not remove an unrecognized existing config.

## C. Stored bundle, original/latest and read-only preflight

Permission: read only. Write scope: none. CLI requires independently pinned receipt
SHA-256, verifies all frozen/correction identities and saved quality components,
then authenticates renderer bytes. There is no evaluate/fetch/predict/render
fallback. Missing/incompatible evidence stops publication.

```sh
COMMON=(--source-dir "$SOURCE_DIR" --pre-open-input "$PRE_INPUT"
  --post-close-input "$POST_INPUT" --expected-correction-id "$CORRECTION_ID"
  --expected-receipt-hash "$APPROVED_RECEIPT_SHA256"
  --static-root "$STATIC_ROOT" --trusted-static-root-config "$TRUST_CONFIG"
  --original-html "$ORIGINAL_HTML" --expected-original-hash "$APPROVED_ORIGINAL_SHA256"
  --audit-root "$AUDIT_ROOT" --public-base-url "$PUBLIC_BASE")
"$PYTHON" scripts/orchestrator/publish_tw_correction_dashboard.py "${COMMON[@]}" --preflight
```

Record original and latest six-field identities and hashes immediately before
publication. Latest may be newer: it is backed up and protected, never targeted.
The new route must be the requested date-specific correction ID. Inspect output
metrics and complete dynamic universe against the private approval record; no
hard-coded watchlist is an admission criterion. A prior route/attempt makes this
read-only preflight stop for review, even if an operator believes it succeeded.
Do not erase prior evidence to retry. Space checks are conservative observations,
not a reservation; backup and public staging may be different filesystems because
the former is copied, never renamed to the public path. Public stage and final
name share one held parent FD/filesystem for exclusive link promotion.

## D. Atomic publish and durable evidence

Permission: **separate explicit publication approval**. Allowed writes: private
`AUDIT_ROOT/CORRECTION_ID`, new correction-route directories/lock/staged file/final
HTML. No other public or source writes. Do not replace this command with cp,
rsync, manual HTML edits or a latest publisher.

```sh
"$PYTHON" scripts/orchestrator/publish_tw_correction_dashboard.py "${COMMON[@]}" --publish
```

The existing CLI performs these transitions:

1. Acquire route-wide nonblocking flock (alias and physical callers share it).
2. Durable original HTML, latest HTML and original snapshot backup; `prepared.json`.
3. Presentation-only label/route transformation with original hashes retained;
   protected primary cards/overview cannot change. Save candidate HTML privately.
4. Copy to private staging, verify hash, create public same-parent stage and fsync;
   `staged.json` identifies inode/device/hash. Hold the inode FD against reuse.
5. Exclusive atomic hard link (no overwrite); fsync parent;
   `promoted.json` = `PUBLICATION_PENDING_HTTP` before network verification.
6. Bounded GET against **public nginx URL** must return 200, no redirect and exact
   expected bytes. Recheck root/target/source/latest/original; only then write
   `published.json` with `http_verified=true`.

A successful receipt plus unchanged pinned inode/hash permits idempotent repeat;
failed/unknown receipts never auto-resume. A no-HTTP library test is not public
acceptance. Never interpret `prepared`, `staged` or `promoted` as success.

## E. Public acceptance and preservation

Permission: read only. The CLI JSON supplies `route`; use that route verbatim.

```sh
: "${PUBLISHED_ROUTE:?from the matching publication receipt}"
curl --fail --silent --show-error --max-time 15 --output /dev/null \
  --write-out '%{http_code}\n' "$PUBLIC_BASE$PUBLISHED_ROUTE"
```

From the user's external network, inspect the exact route at 393px: date,
correction ID, full dynamic symbol set, primary metrics, navigation and collapsed
technical details. Compare publication HTML hash to public response. Check saved
`prepared.json` source/input hashes, original and latest before hashes against
unchanged files, and native expanded governance again. Preserve receipts/private
backups on persistent storage. Do not claim a pre-sync full inventory that was
not recorded. Production public acceptance remains PENDING until this step.

## F. Failure, rollback and unknown attempts

On an exception during owned publication, the publisher only unlinks the new
route if its current device/inode **and** bytes match the held staged FD/hash.
It never restores over original/latest because neither was a write target.
`failed.json` distinguishes owned rollback from blocked/foreign state. Private
backups and diagnostic receipts persist. Do not automatically retry.

SIGKILL/power loss can leave `prepared`, `staged` or `promoted` without a final
receipt. Re-entry refuses it. Inspect all receipts and current route identity;
**STOP** on unknown ownership, changed inode/hash, symlink/root replacement,
missing fsync evidence or foreign content. An operator may not unlink files based
on filename or a historical inode number alone (inode reuse). This PR does not
provide a force-recovery command. Any post-process manual rollback requires a
separately reviewed ownership proof and explicit PM approval; otherwise retain
all evidence. Failure to save a terminal receipt is also UNKNOWN, never success.

The automated owned-inode rollback is covered by tests; actual crash/power-loss,
external nginx availability and post-process recovery remain Production-only
pending. No service restart, notification or evaluation is a recovery step.
