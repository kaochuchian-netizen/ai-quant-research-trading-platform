# Production Landing Route Ownership V1

## Incident

On 2026-07-15 the public root `/stock-ai-dashboard/index.html` displayed `Stock AI Legacy / Debug Landing` instead of the production multi-market overview. The production features—TW/US entry points, fourteen archive links, seven manual controls, and Operations Center—were therefore unavailable until a later multi-market publish replaced the page again.

## Root cause

The production Landing renderer is `app.dashboard.multi_market_dashboard.render_landing_page`; `build_pages` stages it as `index.html`, and `publish_pages` owns the public root.

Two older TW delivery paths also claimed the same root:

1. `approved_pre_open_delivery.post_delivery_artifact_wiring` invoked `publish_four_window_dashboard_preview_v1.py`. Its default behavior published the four-window route and then rewrote root `index.html` with a legacy link page.
2. The same approved TW runner subsequently called its local `publish_dashboard`, which wrote `Stock AI Legacy / Debug Landing` directly to the directory supplied as `/var/www/stock-ai-dashboard`.

The second write was the final 15:00 owner. The incident public hash matched that renderer exactly. A later scheduled US multi-market publish restored the formal Landing, proving that the visible page depended on whichever publisher ran last.

Existing public checks asserted HTTP 200 and market page availability, but did not inventory the root page's required features or reject legacy markers.

## Route ownership

| Route | Exclusive owner | Source |
|---|---|---|
| `/stock-ai-dashboard/index.html` | `app.dashboard.multi_market_dashboard.publish_pages` | `render_landing_page()` staged by `build_pages()` |
| `/stock-ai-dashboard/debug/legacy/index.html` | `approved_pre_open_delivery.publish_dashboard` | scheduler diagnostic `render_dashboard()` |
| `/stock-ai-dashboard/dashboard/decision-intelligence/four-window-preview/index.html` | four-window compatibility publisher / multi-market compatibility publish | four-window/TW compatibility renderer |

Legacy publishers may read root for diagnostics or backup discovery, but cannot write, replace, or link-page-export to root.

## Source, stage, and public paths

- Production source contract: `app/dashboard/multi_market_dashboard.py::render_landing_page`.
- Production staging: caller-selected isolated directory, normally `templates/multi_market_dashboard_v2` or `/tmp/...` for controlled publishing.
- Production public: `/var/www/stock-ai-dashboard/index.html`.
- Scheduler debug staging/public: `/var/www/stock-ai-dashboard/debug/legacy/index.html`.
- Four-window compatibility public: `/var/www/stock-ai-dashboard/dashboard/decision-intelligence/four-window-preview/index.html`.

## Atomic publish and order

The production publisher builds and validates the Landing contract before public writes. Files are copied to a sibling temporary filename and installed with `os.replace`. It never deletes the public Landing first and does not wildcard-copy the static root.

Archive rebuild, manual latest publish, Operations rebuild, TW/US static publish, and legacy exports are route-local. Their order cannot alter the production root. A full multi-market controlled publish may update root, but only after the production marker/count contract passes.

## Landing contract

The production root must contain:

- TW and US Dashboard links;
- exactly fourteen archive buttons, including empty-state routes;
- exactly seven real manual-window buttons using the existing PIN form and backend endpoint;
- exactly seven Operations rows with Latest, Previous, Revision, Runtime Provenance, Scheduler, Pipeline, Dashboard, Archive, LINE, Email, and Overall columns;
- shared navigation and mobile safe-area CSS.

It must not contain legacy/debug landing markers or raw pipeline status copy.

## Hash and marker validation

`validate_production_landing_integrity_v1.py` records production source/stage/public and legacy hashes. It deterministically executes production publish, archive rebuild, Operations rebuild, TW 15:00 publish, US publish, scheduler legacy publish, and four-window legacy publish in a temporary root. The production root hash and marker inventory must remain unchanged through every route-local step.

Use `--require-public` to inventory the actual HTTP root. HTTP 200 alone is insufficient.

## Rollback

Use the `backup_path` returned by the multi-market publisher to atomically restore the pre-publish Landing, TW, US, and compatibility pages. Do not remove or rewrite runtime/archive artifacts. If rollback restores a legacy root from an incident-era backup, immediately choose an earlier verified production Landing backup or rebuild the production Landing from the merged source and validate markers before replacement.

## Troubleshooting

1. Compare public root hash to the controlled production staging hash.
2. Run the integrity validator with `--require-public`.
3. Search publisher source for direct root `index.html` writes.
4. Verify legacy output exists only below `/debug/legacy` or its compatibility route.
5. Check exact counts: archive 14, manual 7, Operations 7.
6. Confirm no active scheduled publish before a controlled republish.

## Known limitations

The Operations table uses a labelled horizontal scroll container on narrow screens because twelve health columns cannot remain readable in a single viewport. Dashboard content and controls retain safe-area padding and one-column mobile layouts. Browser screenshot QA is separate from deterministic DOM/CSS validation.
