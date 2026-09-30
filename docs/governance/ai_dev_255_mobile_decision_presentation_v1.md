# AI-DEV-255 mobile decision presentation
## Scope
255A: one seven-window field projection for Dashboard and LINE.
255B: Traditional Chinese display mapping, source parity and immutable field preservation.
255C: collapsed evidence and 393px mobile rendering. No deployment or notification.

The canonical field order is LABELS in app/reports/mobile_decision_presentation.py.
The version discriminator is mobile_decision_presentation_v1. Every projection
retains the entire source card and its SHA-256; no artifact/schema migration occurs.
Both channels use the same human-summary projection and same admitted window payload.
US selects dashboard_ready_contract.cards; TW selects the explicit structured window list.
An explicit empty list never falls back to another list or window.

## Source semantics
TW pre-open direction/target/range use existing governed human-summary projection.
US pre-open direction uses the existing product forecast; execution entry/stop/target
remain separate and are displayed only when existing actionable eligibility permits.
LINE stock-price range remains the same formal forecast interval preserved in evidence.
There is no range-midpoint inference, technical-model change or new strategy decision.

Current intraday products inherit pre-open forecasts. They do not establish a new
now-to-close forecast. The requested now-to-close field is visible, but truthfully
states the missing horizon; the inherited forecast remains in evidence. Do not
rename an inherited forecast or create a model in this presentation change.

Review direction and range results are displayed separately. The overall line
concatenates those canonical results; it is not a new score. Actual direction must
already be explicit. Missing data is never inferred from predicted direction.

## Localization and evidence
Use existing finalized news chinese_summary first, retaining publisher attribution.
Chinese content summaries are displayed; generic investment impact text is not a
substitute for article content. Missing Chinese summary renders an explicit
translation gap. Raw English remains in the original card/artifact and folded
legacy evidence. No runtime network translator or model call is introduced.
Internal enums remain unchanged; unknown display enums render a Chinese missing
state instead of leaking an internal token.

All prior detailed report HTML is retained under a closed details element, including
technical/confidence/quality, research/lineage/diagnostics and review detail.
Original source fields, unknown future fields, regression and backtest data survive
byte-equivalent JSON comparisons. Primary fields have a single channel-shared source.

## Validation
Synthetic fixtures cover TW four windows and US three windows. Tests cover exact
field order, source priority, immutable source hashes, recursive field preservation,
determinism, missing/reversed/non-finite values, escaping, no-trade plan suppression,
honest translation gaps and formatter-only delivery functions.
A separate Playwright validator renders the actual report entrypoints at 393x852,
blocks HTTP(S), verifies no overflow before/after expansion and closes the browser.
All output goes to a temporary target outside the repository. CI runs both validators.

Presentation expectations in existing validators may be updated to the approved
255 field list; model, threshold, admission and evidence checks must remain intact.
No preserved production artifact is read, moved, overwritten or committed.

## Delivery boundary
PR only; no merge/deploy. No DB, scheduler, cron, systemd, nginx, production pipeline,
notification, strategy/weight/watchlist, model, evaluation or trading mutation.
Missing now-to-close forecasts and missing source translations are coverage limitations,
not permission to manufacture data or alter the prediction engine.
