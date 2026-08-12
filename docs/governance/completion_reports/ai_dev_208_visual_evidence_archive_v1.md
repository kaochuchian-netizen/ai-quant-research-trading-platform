# AI-DEV-208 — Cross-Market Batch Visual Evidence Archive V1

## Status

IMPLEMENTED_DETERMINISTIC_QA_PASS_PENDING_NATURAL_VERIFICATION

## Repository

- Starting main: `c82e208e3223745ad93eaaf5b59a24414b62b984`
- Feature branch: `ai-dev/208-visual-evidence-archive-v1`
- Implementation commits: `9b486aa0a6ddd961ab3aa30c988f0d727a1f97b9`, `a42bd021ef811a9af73f2647fb565e8c1cb91c09`, `b099a54ca929c5f9122494489f9cc606efbc90b3`
- PR: [#256](https://github.com/kaochuchian-netizen/ai-quant-research-trading-platform/pull/256)
- Final AI-DEV-208 V1 GitHub Actions: run `31578542230` PASS, including Chromium installation and real-browser registry execution
- V1 merge/current main before Hardening V2: `70c817eb479334d56b9917765d1dd762488302ad`
- Hardening V2 issue: [#257](https://github.com/kaochuchian-netizen/ai-quant-research-trading-platform/issues/257)
- Hardening V2 branch: `ai-dev/208-visual-evidence-hardening-v2`
- Hardening V2 implementation commit: `5348999d5a59ae3601b316f1b3eda3a238fcee83`
- Hardening V2 PR: [#258](https://github.com/kaochuchian-netizen/ai-quant-research-trading-platform/pull/258), merged
- Hardening V2 final GitHub Actions: run `31587698210` PASS
- Hardening V2 merge/current implementation main: `e1637701dee8c2e47fd06a4d4283765a32c8d78d`
- Production pipeline executed: false

## Architecture

AI-DEV-208 adds a strictly downstream Visual Evidence Capture layer:

`admitted immutable snapshot → verified Dashboard archive route → Playwright Chromium capture → immutable visual revision → index → incremental daily review bundle`.

The implementation supports all seven canonical windows from `MARKET_WINDOWS`. It captures the final browser DOM, visible text and a full-page PNG. Every successful revision contains `manifest.json`, `screenshot_full.png`, `rendered_page.html`, `rendered_text.md`, and `canonical_reference.json`. SHA-256, snapshot identity, payload hash, route, revision and capture origin remain traceable.

The capture source is the local production-rendered archive route. This matches the user-visible page contract without adding public-network availability as a capture dependency.

Changed scope consists of the capture/archive module; two safe CLIs; TW/US downstream delivery hooks; the dedicated validator; post-merge generated-artifact classification; pinned runtime/CI browser dependencies; validator and pending-natural-verification registries; runbook; workflow; and this completion report.

Representative manifest fields:

```json
{
  "schema_version": "visual_evidence_manifest_v1",
  "visual_evidence_id": "sha256 identity",
  "market": "TW",
  "window": "intraday_1305",
  "effective_trading_date": "2026-08-13",
  "snapshot_id": "canonical snapshot sha256",
  "revision": 1,
  "dashboard_route": "/dashboard/archive/tw/intraday_1305/latest/index.html",
  "capture": {
    "status": "SUCCESS",
    "renderer": "playwright-chromium",
    "viewport": {"width": 1440, "height": 1200},
    "full_page": true
  },
  "capture_hash": "sha256 file map",
  "screenshot_hash": "sha256 PNG",
  "rendered_text_hash": "sha256 visible text"
}
```

## Capture Technology

- `playwright==1.54.0`
- Playwright-managed Chromium
- deterministic 1440 × 1200 viewport
- `full_page=true`
- readiness signal: canonical `body[data-snapshot-id]` after network idle
- bounded 45-second render timeout
- optional user-scoped Ubuntu library bundle under `~/.cache/stock-ai-playwright-libs/root`; no system package mutation

GitHub Actions installs the pinned Python dependency and Chromium runtime before executing the registered validator.

## Admission, Identity and Failure Isolation

Fixture, validator, test, failed, incomplete and unadmitted batches are excluded by the existing snapshot admission contract. Capture verifies market, window, effective trading date, snapshot ID, revision and payload hash against final browser DOM identity.

An identity mismatch is not archived as valid evidence. Browser/route/render failures create sanitized failure manifests and index records. The production-safe hook catches all exceptions and returns `production_batch_continues=true`; visual QA never changes batch success, delivery, Decision or trading.

## Archive and Review Semantics

The immutable root is `artifacts/archive/visual_evidence/<date>/<market>/<window>/revision_NNN`. Reruns create a new revision and do not overwrite earlier evidence. Identical identity/hash capture requests are suppressed.

`index.json` provides deterministic cross-date lookup. `daily_reviews/<date>` incrementally aggregates the latest valid revision for each of seven windows and marks unavailable windows `PENDING` or `FAILED`; it never fabricates missing captures. The directory is self-contained for PM upload or later ChatGPT review.

Hardening V2 separates the latest usable evidence from the latest capture attempt. Each window records `latest_valid_revision`, `latest_attempt_revision`, and `latest_attempt_status`. A later failed attempt with an older valid revision is `DEGRADED`, not silently `SUCCESS`; the valid revision remains available for review while failed/degraded counts and the PM-facing summary expose current attempt truthfully.

Hardening V2 also makes production-wrapper pre-browser `IDENTITY_MISMATCH` durable. The sanitized failure manifest records requested/archive identity and safely resolved observed identity, the deterministic index records the failed attempt, and the daily review reflects it. It remains invalid visual evidence and `production_batch_continues=true` preserves batch availability.

## Deterministic Fixture Coverage

The dedicated registered validator exercises a real headless browser against isolated local HTML and covers:

- admitted TW 13:05 and US 20:00 capture
- ineligible exclusion and identity mismatch
- browser timeout isolation
- non-empty PNG signature, final DOM HTML and visible text
- manifest hashes and canonical source immutability
- same-day revisions 1/2 and latest-review selection
- `revision_001 SUCCESS → revision_002 FAILED` with valid revision 1 preserved and latest attempt 2 reported `DEGRADED`
- archive-write snapshot A versus resolved latest snapshot B with durable `IDENTITY_MISMATCH` manifest/index/review evidence
- truthful pending/failed windows
- duplicate suppression
- isolated temporary output and cleanup
- all seven canonical windows

Initial GCP deterministic result: 24 semantic checks PASS; real-browser rendering exercised; temporary archive removed; no network dependency during capture. AI-DEV-207, window snapshot archive, admission/public parity, notification provenance, cross-feature and production landing regressions also PASS. The committed executable branch registry selected 21 validators, executed and passed 20 leaf validators, failed 0, skipped only the branch orchestrator through the deterministic recursion guard, and reported no unexplained skips.

Hardening V2 deterministic result: all original 24 checks plus the two Issue #257 remediation cases PASS (26/26); real-browser rendering remains exercised. AI-DEV-207, window snapshot archive, admission/public parity, notification provenance, cross-feature, production landing and source-inventory regressions remain PASS.

Final command results are recorded after branch and post-merge registry execution.

## Storage and Review Workflow

Expected screenshot growth is approximately 0.5–3 MB per window, or 3.5–21 MB per complete day before the self-contained daily copy. V1 deliberately implements no retention/deletion. Operators can run `build_visual_review_bundle.py --date YYYY-MM-DD --pretty` and upload the resulting daily directory without searching across runtime paths.

## Safety

- Trading Strategy / scoring / prediction / ranking / eligibility / action changed: false
- Entry / stop / target / position sizing / execution changed: false
- LINE or Email attempted: false
- Scheduler, cron, systemd, notification runtime changed: false
- Secrets accessed: false
- Production DB written: false
- Immutable historical snapshots rewritten: false
- Public archive exposure enabled: false

## Natural Verification

Deterministic fixtures do not constitute natural verification. The next eligible TW and US lifecycle must prove automatic post-publish capture, screenshot fidelity, identity parity, immutable revision behavior, daily bundle updates and non-blocking failure behavior across:

- TW: `07:00 → 13:05 → 13:35 → 15:00`
- US: `20:00 → 23:00 → 06:30`
