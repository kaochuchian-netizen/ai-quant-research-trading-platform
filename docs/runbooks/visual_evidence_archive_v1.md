# Visual Evidence Archive V1 Runbook

## Boundary

Visual Evidence is a read-only QA projection created after canonical snapshot admission and Dashboard route identity verification. Screenshot, HTML and rendered text are never inputs to Research, Prediction, Decision, notification or trading layers.

## Capture contract

The production-safe hook runs after `synchronize_admitted_latest()` reports `verified`, or after an admitted manual rerun rebuilds its latest route. It opens the local production-rendered archive route with pinned Playwright Chromium using a 1440 × 1200 viewport, waits for the canonical `body[data-snapshot-id]` identity, and captures the full page.

Failures are bounded and non-blocking. The caller receives `FAILED` with a sanitized reason code, while the production batch continues unchanged. Unadmitted, fixture, dry-run or unavailable routes are not valid evidence.

## Archive layout

```text
artifacts/archive/visual_evidence/
  index.json
  YYYY-MM-DD/<MARKET>/<window>/revision_NNN/
    screenshot_full.png
    rendered_page.html
    rendered_text.md
    canonical_reference.json
    manifest.json
  YYYY-MM-DD/<MARKET>/<window>/failures/*.json
  daily_reviews/YYYY-MM-DD/
    review_manifest.json
    review_summary.md
    <MARKET>/<window>/...
```

Revision directories are immutable. An identical capture identity is suppressed; a conflicting identity fails closed. The daily review directory is a mutable aggregation that points to/copies only the latest valid revision while retaining all immutable revision bundles.

## Manual commands

Dry-run planning, with no capture or external side effect:

```bash
python3 scripts/orchestrator/capture_visual_evidence.py \
  --market TW --window intraday_1305 --dry-run --pretty
```

Capture the latest admitted local route:

```bash
python3 scripts/orchestrator/capture_visual_evidence.py \
  --market TW --window intraday_1305 --pretty
```

Build/rebuild a self-contained review directory:

```bash
python3 scripts/orchestrator/build_visual_review_bundle.py \
  --date YYYY-MM-DD --pretty
```

## Runtime dependency

Python dependency: `playwright==1.54.0`.

One-time repo-user browser install on a new host:

```bash
python3 -m playwright install chromium
```

If the host does not already provide Chromium runtime libraries, download the Playwright-reported Ubuntu packages with `apt-get download` (not `apt-get install`) and extract each `.deb` using `dpkg-deb -x` below `~/.cache/stock-ai-playwright-libs/root`. The capture service automatically adds that user-scoped library directory to Chromium's process environment. CI installs Chromium and its ephemeral runner dependencies deterministically. No privileged production system-package mutation is part of the application workflow.

## Reason codes

`ROUTE_NOT_FOUND`, `PAGE_HTTP_ERROR`, `PAGE_RENDER_TIMEOUT`, `BROWSER_START_FAILED`, `SCREENSHOT_WRITE_FAILED`, `HTML_CAPTURE_FAILED`, `MANIFEST_WRITE_FAILED`, `BATCH_NOT_ADMITTED`, `DASHBOARD_NOT_READY`, `IDENTITY_MISMATCH`, `IDENTITY_CONFLICT`.

## Storage estimate

HTML, text, canonical reference and manifest are typically small. Screenshot size depends on page height and content; a planning estimate of 0.5–3 MB per window gives roughly 3.5–21 MB per complete seven-window day before the self-contained daily copy. V1 performs no destructive retention. A later policy may compress/cold-archive completed dates without rewriting evidence identities.
