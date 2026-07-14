# Window-Specific Dashboard Renderer Enforcement V1

Task: AI-DEV-178A

## Background

AI-DEV-178 introduced TW / US window report contracts and manual batch mappings, but the public Dashboard still rendered full generic stock cards after the contract description. The visible result was that 13:35 and 15:00 looked like they had a window contract, while the actual body still showed full tactical / research / news / technical detail sections.

## Root Cause

The contract was rendered as visible explanatory content by `render_window_contract_overview()`. It did not control the renderer.

TW used `render_tw_page()` to prepend contract cards and then unconditionally append the old generic template plus `render_tw_tactical_cards()`. US used one page renderer that unconditionally emitted generic section headings and full `decision_presentation_v3` cards for every US window.

`dashboard_sections` represented intended scope, but no projection layer enforced those sections before DOM generation. Suppressed sections were not applied to the HTML renderer.

## Contract vs Renderer Responsibility

The contract remains an internal scope definition. Public pages must not expose implementation fields such as `dashboard_sections`, `email_sections`, `line_summary_scope`, `suppressed_sections`, `required_sections`, or debug labels like `Dashboard scope` / `LINE scope`.

The renderer must resolve `market + window`, build a window-specific projection, and output only the cards and sections allowed for that window. Disallowed sections must not exist in final HTML; CSS hiding is not sufficient.

## Window Projection Architecture

The Dashboard projection is:

1. Load authoritative market runtime artifact.
2. Resolve window contract.
3. Project full presentation into a window-specific payload.
4. Render cards with explicit `data-report-type` and `data-card-type`.
5. Validate rendered HTML containers, not only contract objects.

## TW Windows

07:00 pre-open can show fuller decision information: market context, daily tactical plan, prediction, entry, stop, targets, risk, and compact research summary.

13:05 intraday is restricted to intraday change, setup trigger state, entry trigger state, target / stop proximity, volume / price confirmation, risk change, and whether action is still reasonable.

13:35 pre-close is restricted to close snapshot, late-session risk, avoid-chasing guidance, target / stop proximity, setup status, closing action, and next-day watch.

15:00 post-close is rendered as review cards. It focuses on prediction vs actual, entry / target / stop outcome, win / loss / not-triggered / no-trade, MFE / MAE, false breakout, rolling review, and next-day watch. If actual outcome is not available, it says the review is pending instead of falling back to a tactical plan.

## US Windows

20:00 pre-market can show setup, entry, stop, target, prediction range, earnings / SEC / news risk, and market context.

23:00 intraday is restricted to open-session change, gap follow-through, volume confirmation, entry trigger, target / stop proximity, and tactical adjustment.

06:30 review is restricted to prediction review, entry / stop / target outcome, win / loss / not-triggered, MFE / MAE, overnight event update, and next-session watchlist.

## Email and LINE Scope

Email follows the same window projection. 13:35 and 15:00 TW emails do not replay full generic reports. US 23:00 and 06:30 emails use compact intraday/review blocks instead of full research/tactical cards. LINE remains short and never includes contract field names or debug scope text.

## Validator

`scripts/orchestrator/validate_window_specific_dashboard_renderer_v1.py` builds preview HTML and checks the final DOM:

- no debug contract text in public/preview pages
- required markers exist per window
- suppressed full sections are absent from compact/review window containers
- card types and section sets differ across adjacent windows
- compact/review windows do not contain full decision-card markers
- Email / LINE do not leak debug scope or full-card content for compact/review windows

## Controlled Verification

Manual rerun validation must remain no-send:

- email attempted: false
- LINE attempted: false
- production-approved delivery: false
- trading/order: false
- scheduler changed: false
- `main.py` not executed
- secrets not accessed or printed

## Public Validation

After merge, run controlled publish and validate:

- Landing route loads
- TW route shows 13:35 snapshot and 15:00 review cards without full generic card leak
- US route shows 23:00 intraday and 06:30 review cards without full generic card leak
- debug contract labels are absent
- TW / US URL isolation remains valid

## Rollback

Use the publish helper rollback backup emitted by `publish_multi_market_dashboard_v2.py --apply --pretty` for public static files. Code rollback should revert the AI-DEV-178A PR only, leaving strategy, model, scheduler, notification approval, and runtime calculation changes untouched.

## Known Limitations

The 15:00 TW and 06:30 US review cards show pending review text when actual outcome artifacts are incomplete. This is intentional and safer than falling back to a full tactical plan.
