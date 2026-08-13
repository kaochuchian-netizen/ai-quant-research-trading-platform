# AI-DEV-214 H3 Provenance Runtime Hot Repair V1

Task ID: AI-DEV-214

## Status

IMPLEMENTED_DETERMINISTIC_QA_PASS_PENDING_CONTROLLED_RECOVERY

## Repository

- Starting main: `7577aee3dac72b9aecdf9509b9a7d17909f5519b`
- Feature branch: `ai-dev/214-h3-provenance-runtime-hotfix`
- Implementation commit: `bb018c9bfdc669973644eaebd7465102af6137b7`
- Pull request: `#278`
- CI and merge/current main are recorded after governed completion.

## Root Cause

AI-DEV-212 H3 added a JSON round-trip while copying `entity_attribution` in `USResearchIntelligenceBuilder.material_news()` without importing `json`. The scheduled US 20:00 path reached qualified attributed news and raised `NameError` before aggregate artifact generation. Old H3 QA passed because it bypassed the production-shaped Research builder path.

## Implementation

The repair uses `copy.deepcopy()` for the ordinary nested dict/list provenance object. It preserves attribution content without imposing JSON normalization, isolates the admitted source object from downstream mutation, and removes the undefined runtime dependency. H3 QA now executes normalized qualified news through `material_news()`, `build_for_symbol()`, RRE normalization and finalized projection. A dedicated ACTIVE registry leaf adds executable mutations and a scoped Pyflakes check.

## User-visible Outcome

The repository-side Research provenance path can complete when qualified news contains nested attribution. No Decision, notification, schedule or trading behavior changes. A separate PM-authorized US 20:00 controlled recovery remains required before product verification can resume.

## Evidence

The AI-DEV-213 incident chain is: cron/process PASS → qualified attributed news PASS → `material_news()` undefined `json` → aggregate artifact absent → admission/publish/notification not reached. Deterministic fixtures reproduce the same production method calls without network, production pipeline execution, archive writes or notification sends.

## Quality Gate

The dedicated validator covers `material_news()`, `build_for_symbol()`, nested provenance continuity, source identity, input mutation isolation, finalized projection validation, three executable mutation failures and a module-scoped undefined-name gate. The executable branch registry selected 30 required validators, executed 29 leaves, recursion-guarded only the branch orchestrator, passed all 29 leaves, and reported zero failures or unexplained skips.

## QA Gap Closure

Old H3 QA passed because it bypassed the production-shaped Research builder path. AI-DEV-214 closes that validator blind spot by invoking both affected production methods and the downstream RRE/finalization path with deterministic adapters.

## Regression

AI-DEV-212 H3/H2/V1, AI-DEV-209 core/H2/H3, AI-DEV-210, AI-DEV-211, AI-DEV-207, AI-DEV-202, canonical US Research, TW RRE/Decision, seven-window cross-feature, admission/public parity, notification provenance, landing integrity, source inventory, governance, compilation, scoped Pyflakes F821, diff checks and executable branch registry pass. Post-merge registry is run after merge.

## Production Usability

The repair is production-path compatible but is not validated by a rerun in this task. Repository completion stops before controlled recovery, notification delivery, or any production write.

## Known Limitations

Production cron previously executed from a mutable feature-branch worktree. Immutable deployment checkout/release identity remains a follow-up governance risk and is not broadened into this hot repair.

## Deferred Enhancements

Immutable deployment worktree isolation and release promotion are deferred. No renderer change was made, so a new bespoke Chromium suite is outside the affected scope; registry regressions remain authoritative.

## Natural Verification

After a PM-authorized controlled US 20:00 recovery passes, eligible scheduled TW/US lifecycle batches must still verify runtime provenance and product semantics naturally.

## Phase Contribution

Closes a production executability gap between qualified attributed evidence and Research projection while strengthening deterministic QA at the actual failure boundary.

## Safety

- Production pipeline executed: false
- Controlled rerun executed: false
- LINE/Email sent: false
- Trading/orders: false
- Scheduler/cron/systemd/nginx changed: false
- Services restarted: false
- Secrets accessed/changed: false
- Production DB written: false
- Immutable archives rewritten: false
- Strategy/scoring/prediction/ranking/eligibility/action changed: false
- Entry/Stop/Target/sizing/execution changed: false

## Final Status

`IMPLEMENTED_DETERMINISTIC_QA_PASS_PENDING_CONTROLLED_RECOVERY`
