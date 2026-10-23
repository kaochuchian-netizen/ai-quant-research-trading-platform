# AI-DEV-285 — Explicit trusted correction static root

## Finding and scope

The existing deployment uses a host static-root symlink into a directory shared
with the web server through a bind mount. The server alias maps to that same
physical directory. Read-only topology inspection verified the alias, physical
parents, mount relationship and server route; identifying runtime evidence stays
outside Git. The previous publisher rejects every symlink, including this root,
before writing a public correction. This is a publication-path compatibility
issue, not an evaluation or report-content defect.

Only the correction publisher and its CLI change. Existing non-symlink operation
remains the default. No root policy is installed, no Production file is changed,
and no report or notification is published by this task.

## Trust boundary

An operator must explicitly approve and supply `--trusted-static-root-config`.
The JSON must have exactly these fields:

```json
{
  "schema_version": "correction_static_root_trust_v1",
  "logical_root": "/example/static-alias",
  "physical_root": "/example/physical-static",
  "alias_identity": {"device": 1, "inode": 100, "uid": 0},
  "root_identity": {"device": 1, "inode": 101, "uid": 1000}
}
```

These are synthetic examples, not deployable values. Do not auto-discover or
accept a new inode on mismatch. Obtain values from separately reviewed read-only
topology evidence. Config must be a regular non-symlink file, owned by root or
the executing operator, without group/world write permission. No credentials
belong in this policy. Preview validates the policy without public writes.

Exactly one absolute alias is allowed, with matching path, device/inode/owner
and exact absolute readlink target. Chained and relative aliases are rejected.
All physical parents and descendants are opened with O_NOFOLLOW/O_DIRECTORY.
Root and every traversed directory are pinned and rechecked. Public reads,
staging, exclusive link promotion and owned-inode rollback use held directory
file descriptors; a rename cannot redirect operations through the replacement
path. No unrestricted resolve-and-write path is introduced. Path traversal,
unauthorized links, root replacement and mismatched identities fail closed.

The operator/config and OS remain trusted; this does not defend against a
privileged attacker able to rewrite process memory or the configured policy.
Concurrent unexpected root maintenance requires operator review, not retry.

## Publication guarantees

- Original six-field identity, input/output hashes and canonical content checks
  remain unchanged. Latest and original revision are never publication targets.
- Private durable backups and prepared/terminal receipts remain required.
- Route lock is shared across alias and physical callers. Nonregular/symlink
  locks are rejected. Reads reject special files without waiting on FIFOs.
- Exclusive hard-link promotion is atomic and does not overwrite collisions.
- Verification failure removes only the owned new inode with matching hash,
  using the held parent descriptor even after a directory rename.
- Existing successful receipts permit idempotent repeat; partial/unknown attempts
  require review. Failed HTTP verification does not silently retry.
- Receipt includes root mapping and pinned identities for later audit. These
  receipts remain private and are not committed as fixtures.

## Validation

Synthetic tests exercise accepted alias, missing policy, malformed policy,
wrong alias/root identity, chained/descendant symlinks, traversal, alias/root
replacement, post-link alias/child replacement, partial copy, HTTP rollback,
shared route locking, identity rejection, FIFO reads and config permissions.
Existing correction tests cover content binding, dynamic universe, original and
latest preservation, collisions, repeat publication and exact local HTTP bytes.
No Production-derived payload, snapshot, receipt or recipient is in fixtures.

Activation requires separate PM approval for installing reviewed policy,
source synchronization and the specific correction publication. This PR does
not authorize any of those operations. Production public HTTP acceptance remains
pending; local HTTP success is not Production acceptance. AI-DEV-282 stays paused.
