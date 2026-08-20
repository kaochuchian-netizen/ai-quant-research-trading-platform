# AI-DEV-218A — TW 07:00 Pre-Open Product Intelligence Redesign V1

## Status

IMPLEMENTED_DETERMINISTIC_QA_PASS_PENDING_CONTROLLED_VERIFICATION

## Repository

- Starting main: `3658192320d454fad5e17d8de839c8d6a30d21bd`
- Branch: `ai-dev/218a-tw-preopen-product-intelligence-v1`
- Implementation commit: `d431237`
- Pull request: #285
- CI: run `32380579450` PASS
- Merge/current main: `964fcc821439e856aef232d99a2994a92467b673`

## Root causes

The 07:00 product exposed action, technical diagnostics and long research text before its forecast truth. The prediction snapshot owned direction and interval but had no canonical point forecast, Dashboard and LINE independently prioritized legacy presentation, and acquisition failure could collapse into a generic no-news message.

## Canonical product contract

`tw_preopen_product_intelligence_v1` is synthesized downstream of Prediction and Research. It owns:

- `today_direction`: BULLISH / BEARISH / SIDEWAYS;
- prediction-owned `target_price` with method, horizon and provenance;
- `predicted_low <= target_price <= predicted_high`;
- symbol-specific Traditional Chinese `daily_thesis`;
- no more than three attributed, quality-qualified important news items;
- explicit retrieval-failure diagnostics;
- Decision ownership preserved separately from forecast direction;
- technical indicators retained but excluded from the primary surface.

The target is explicitly not an execution take-profit, support, or resistance alias. Prediction weights and Decision rules are unchanged.

## Natural-shaped deterministic evidence

Fixtures cover 2330 bullish, 2337 bearish and 6873 sideways. Mutations reject reversed ranges, out-of-range targets, missing/unsupported direction, renderer-owned or execution targets, support/resistance aliases, confidence-owner aliasing and malformed news semantics. Tier-4 CMoney-like evidence is excluded from primary news and cannot establish direction. Acquisition failure remains distinguishable from no material news.

## Product projection

Dashboard cards now place direction, target, interval, reference price, daily thesis and important news before Decision metadata. The portfolio header provides bullish/bearish/sideways counts and priority names. LINE reuses the same canonical projection and keeps only direction, target, range and top news.

The 07:00 prediction identity, horizon and interval remain available to the AI-DEV-217 13:05 → 13:35 → 15:00 lineage.

## Visual validation

The dedicated validator exercises real Playwright Chromium rendering, full-page PNG/PDF creation, Noto Sans CJK TC loading and visible Traditional Chinese direction/target/range content. Responsive CSS keeps the core grid single-column at mobile width; no RSI/MACD/KD dump appears in the primary card.

## Validation

- AI-DEV-218A dedicated validator: PASS
- Python compile / JSON registry / diff check: PASS
- AI-DEV-202 and AI-DEV-217 prediction lineage regressions: PASS
- Full branch registry: PASS (34 selected; 33 executed leaves PASS; 1 recursion guard; 0 failures; 0 unexplained skips)
- CI and post-merge registry: PASS (34 selected; 33 executed leaves PASS; 1 recursion guard; 0 failures; 0 unexplained skips)

## Safety

- Strategy/scoring/prediction weights/ranking/eligibility/action rules: NO CHANGE
- Entry/Stop/execution target/sizing/order execution: NO CHANGE
- Production/manual rerun: false
- LINE/Email sent: false
- Trading/orders: false
- Scheduler/cron/systemd/nginx: unchanged
- Secrets / production DB / immutable archive: untouched
- Existing runtime/generated artifacts: preserved

## Controlled verification

Repository completion does not claim natural or controlled product verification. PM must trigger one new formal 07:00 controlled rerun after merge and inspect actual Dashboard/LINE evidence.

READY_FOR_TW_0700_PRODUCT_CONTROLLED_VERIFICATION
