# AI-DEV-221 — US Production Reconciliation V1

## Repository

- Starting main: `75219d3e36fd8d697a7fc2d4f099dd041f2ba028`
- Branch: `ai-dev/221-us-production-reconciliation-v1`
- Implementation commit, PR, CI and merge identity are recorded by the governed GitHub history.
- Target state: main/origin-main identical, ahead/behind 0/0, task branch removed.

## Root-cause audit

The approved US runner assigned `batch_reference.astimezone(America/New_York).date()` directly to `effective_trading_date`. Snapshot admission validated only ISO syntax, so a weekend manual rerun could be admitted as a Saturday. The live pipeline independently used the same New York wall-clock date for session lineage.

AI-DEV-220 projections were generated in `build_live_runtime_artifact()` and consumed by the window-specific Dashboard card and LINE formatter. However, the US window contract, report introduction and compatibility Email/card surfaces retained the older Premarket/Gap/Entry/Stop/Target-first hierarchy. This allowed an admitted new-schema payload to remain product-visible through legacy-first descriptions and secondary renderers. The manual bridge calls the governed `approved_us_stock_delivery.py` command in the repository working tree; it is not a separate US data pipeline. Deployment scripts also invoke that repository entrypoint rather than a copied TW artifact.

The landing overview is built from `resolve_snapshots()` and therefore must share the same immutable latest identity as archive/latest. AI-DEV-221 adds an executable identity mutation check: a stale overview date fails parity instead of being accepted by route existence alone.

The observed Research combination—high coverage, no major gap, zero supporting/opposing evidence and `insufficient_evidence`—is valid when available inputs contain no company-owned directional evidence. The defect was unexplained presentation, not evidence loss. The Research brief now states this distinction explicitly and does not fabricate bullish/bearish evidence.

## Trading-date and session contract

`app.us_stock.trading_calendar` is the canonical dependency-free US market-date boundary. It resolves all three US windows through America/New_York plus NYSE/Nasdaq weekend and holiday semantics. Saturday, Sunday and holidays roll to the previous valid US trading session. Snapshot admission independently rejects any US non-trading effective date.

Session availability is separate from transport health. A weekday before 04:00 New York is `PREMARKET_SESSION_NOT_STARTED`; a non-trading wall-clock execution is `OFF_SESSION_VERIFICATION`. Neither is an acquisition failure. Actual provider DNS, connection, authentication and timeout failures retain their existing acquisition semantics.

## US 20:00 product activation

The canonical first-level order is now Direction, Forecast target, Forecast range, Short judgment, News funnel, Selected news and Action. Entry, Stop and execution Target remain secondary and do not own forecast identity. WATCH/no-trade cards retain forecast direction and interval when the prediction exists. Dashboard and LINE consume the same `us_premarket_product_projection_v1` and `us_news_product_projection_v1`; no TW source, snapshot, provider or calendar fallback was added.

## Archive and manual safety

The archive resolver, public latest sync and landing overview all derive identity from the admitted immutable snapshot. The dedicated validator proves equal latest/overview identity and rejects a stale overview mutation. Manual rerun still updates only governed runtime/archive/Dashboard paths and does not send LINE/Email because notification delivery remains gated by `production_approved` and excludes `manual_rerun` publication/delivery behavior.

## Validation

- AI-DEV-221 dedicated: PASS.
- AI-DEV-220, AI-DEV-216, AI-DEV-214, AI-DEV-212 H3, AI-DEV-201 US Research: PASS.
- Admission/public-latest parity: PASS.
- Compile and diff-check: PASS.
- Real Chromium desktop/mobile PNG and browser PDF: PASS; Direction/target/range/short judgment/news/action and explicit off-session wording are readable without clipping.
- Local notification-provenance execution is blocked by the macOS Python 3.9 parser on repository Python-3.10 union syntax; the authoritative pinned GitHub branch gate covers it.

## Safety

- Production/manual rerun: false.
- LINE/Email: false.
- Trading/orders: false.
- Strategy, model, scoring, prediction weights, ranking, eligibility and trading rules: unchanged.
- Scheduler, cron, systemd, nginx, firewall and network: unchanged.
- Secrets and production DB: untouched.
- Immutable archives: not rewritten.

## Status

`IMPLEMENTED_DETERMINISTIC_QA_PASS_PENDING_CONTROLLED_VERIFICATION`

Next gate: PM-triggered US 20:00 production reconciliation controlled verification.
