# AI-DEV-287 — Deployment schema compatibility and historical recovery stop

## Call graph and blocker matrix (before implementation)

| Boundary | Finding | Action / stop condition |
|---|---|---|
| Producer | `tw_four_window_decision` freezes `prediction_presentation_v1` into `frozen_delivery_prediction_v1` | No producer changes |
| Consumer | `afternoon_report_pipeline` selects same-session admitted natural pre-open snapshot; `bind_universe` strictly validates projection before market acquisition | Preserve strict admission; never enable `allow_legacy` here |
| Deployment | Existing source deployment is an approved operator `git fetch` + `git merge --ff-only`; expanded dirty-path governance alone does not inspect candidate/input compatibility | Add mandatory read-only candidate gate to native governance entry; nonzero exit stops source-sync approval |
| Correction | Existing `codex_delivery_correction.prepare` requires independently identified pre-open AND post-close snapshots, then correction → evaluation → quality → render | Do not fabricate the missing post-close snapshot |
| Historical delivered evidence | Batch completion and archived Dashboard are present, but actual channel payload/recipient transport receipt were not found in inspected local receipt/outbox paths | BLOCKED: cannot prove per-symbol delivered prediction from Dashboard alone |
| Historical actual evidence | Dated formal outcome was generated before close; all actual OHLC fields missing. Mutable historical CSV now has dated rows | BLOCKED: cannot relabel those rows as the original sealed official outcome |
| Historical recovery | Required evidence incomplete | STOP before adapter/evaluation/render; no QUALIFIED output |

The private incident audit identified a producer/consumer transition between the
morning freeze and afternoon consumption. No Production payload, IDs, receipt,
recipient data or historical numerical fixture is included in this PR.

## Prevention implementation and exact operator contract

The native `validate_post_merge_status.py --tw-deployment-preflight` executes the
**candidate checkout's** strict `bind_universe`, never the old Production consumer.
It returns terminal `PASS` or `BLOCKED` (exit 2), and explicitly reports registry
`NOT_EXECUTED`. This is an additional prerequisite, not a replacement for existing
registry, worker/window, worktree, PM approval or preserved-artifact gates.

Read the current Asia/Taipei session's immutable pre-open revision(s) from
Production, without modifying them, into an isolated local snapshot-root copy.
Record the independently approved snapshot ID, original raw-file SHA256 and
candidate commit. Do not copy secrets, notification recipients or runtime state.
From the clean candidate checkout on Mac (or an isolated Linux gate checkout):

```sh
PYTHONDONTWRITEBYTECODE=1 python3 scripts/orchestrator/validate_post_merge_status.py \
  --tw-deployment-preflight "$READONLY_FROZEN_SNAPSHOT_ROOT" \
  --expected-pre-open-id "$APPROVED_PRE_OPEN_ID" \
  --expected-candidate-sha "$CANDIDATE_SHA" --pretty
```

The root contains `tw/pre_open_0700/<today>/revision-NNNN.json`. The CLI derives
**today** from Asia/Taipei; it has no date override. Dirty/untracked candidate
source, wrong candidate SHA, missing/ambiguous revision, wrong date/market,
non-natural snapshot, hash/identity/projection conflict or source change blocks.
A missing snapshot, including before morning freeze/on a non-trading day, is
conservatively BLOCKED; it is not evidence that legacy inputs are safe.

Immediately before any separately approved fast-forward, compare candidate SHA,
current Taipei date, source ID/revision and raw SHA256 to the gate result and
re-read Production revision inventory. Any change requires a fresh gate. No
snapshot conversion or Production write occurs in this command. Never ignore
its nonzero status or substitute full registry PASS for compatibility PASS.

There is no autonomous source-sync daemon/central Git wrapper in this workflow:
this command prevents approval through the documented native gate, not arbitrary
manual `git merge` outside the runbook. Existing Git/PM controls remain required.

## Historical recovery boundary

The evidence prerequisite failed. No new historical adapter, reconstructed
post-close snapshot, evaluation, renderer output or correction revision was
created. Existing explicit isolated legacy correction is not sufficient when
its required official post-close snapshot is absent. This task must not claim
historical recovery PASS or generic no-input reconstruction capability.

To unblock, supply independently verifiable actual morning LINE/Email payloads
with matching source/content identities and accepted transport evidence, plus
complete official session OHLC with source/date/finality provenance. Current CSV
availability and a morning `completed` log cannot establish these facts alone.
Then validate the known legacy representation field-by-field in isolation,
without changing the original snapshot or current strict consumer. Preserve all
source/transformation hashes and dynamic universe; use existing scoring and
renderers only after evidence admission. That implementation/acceptance remains
blocked, not silently replaced by fixtures.

## Tests and scope

Synthetic cases cover current/legacy/missing projection, malformed schema,
independent snapshot pin, digest corruption, wrong market/date/revision,
manual source, absent same-session source, candidate mismatch/dirty state,
ambiguous revisions, changing source, symlink, invalid JSON, dynamic 8/15/30
universes and native entry terminal behavior. No evaluation is called by the
preflight. Existing correction/publisher/native governance regressions remain.
CI runs the added tests in the existing workflow with no bypass/quarantine.

Publication and notification plans remain **BLOCKED_EVIDENCE**, not approved:
no correction URL/revision or recipient/send plan may be asserted before real
isolated acceptance. A later approved correction must use a dated route, retain
original/latest, and use new explicit per-channel correction identities. This
PR does not send, publish, change scheduler/DB/trading or touch AI-DEV-282.
