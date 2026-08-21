# AI-DEV-218B — TW 07:00 Dashboard Readability & News Acquisition Transparency Remediation V1

## Repository

- Starting main: 0b7c48b24eec7c936cf61c3efa808aa1190b374c
- Implementation branch: ai-dev/218b-tw-news-readability-remediation-v1
- Implementation commit: 48678a2
- Implementation PR: #287
- CI run: 32440394895 — PASS
- Implementation merge/current main: 9f3c90d660e5ecbf91bea04ba8a6474018ff632

## Dashboard readability

The controlled product defect was inherited dark foreground text inside the primary intelligence card's dark navy gradient. The direction-first information architecture remains unchanged. The primary card now uses a governed light high-contrast surface, explicit dark foreground/secondary tokens, semantic direction color, and clear target/range typography.

The dedicated validator exercised real Playwright Chromium at desktop (1440 px) and mobile (390 px), produced non-empty PNG/PDF evidence, loaded Noto Sans CJK TC, verified visible Traditional Chinese, and enforced a WCAG-style primary foreground/background contrast threshold. No broad Dashboard redesign or new UI dependency was introduced.

## News root cause

The natural-shaped audit showed Google News RSS retrieval had returned candidates, but legacy failure_reason=FILTERED metadata was interpreted as a transport/acquisition failure. Therefore symbols with discovered/retrieved data could be rendered as acquisition failures. The source diagnostics also show official MOPS/TWSE/company-IR connectors as SOURCE_NOT_CONFIGURED; this task does not fabricate availability or lower quality gates.

The repair defines actual transport failure by explicit acquisition failure codes, uses discovered/retrieved stage truth plus raw candidate counts, and keeps filtered-to-zero separate from source failure. Existing Tier-4 restrictions remain intact.

## Canonical news funnel

The canonical 07:00 projection now provides retrieved/discovered, screened/qualified, finalized selected and not-selected counts, localized rejection-reason distribution, and retrieval/source-attempt status. Hard invariants enforce selected <= qualified <= retrieved. Dashboard and LINE consume the same canonical counts and selected items; neither surface recomputes news truth.

PM-facing states remain distinct:

- ACQUISITION_FAILURE: a source acquisition attempt actually failed.
- NO_MATERIAL_NEWS / DISCOVERED_BUT_FILTERED: data was retrieved but no item passed relevance, quality, freshness and materiality.
- SELECTED_NEWS_AVAILABLE: finalized selected items are available.

## Source presentation

Selected news displays title, underlying publisher, timestamp when reliable, impact, attribution and selection provenance. Google News RSS remains a discovery channel; when an underlying publisher is known, the publisher is shown. If unresolved, the truthful fallback is Google News RSS（原始來源未解析）.

The primary card displays no more than three selected items and summarizes rejection reasons instead of exposing raw internal evidence IDs.

## ETF behavior

The natural-shaped fixtures cover 00878 and 009816. Existing ETF-specific eligibility semantics remain in force. Tier-4 CMoney/community evidence remains sentiment-only and cannot establish direction. No materiality, attribution or source-quality threshold was weakened.

## Changed files

- app/reports/tw_prediction_explainability.py
- app/reports/tw_preopen_product_intelligence.py
- app/dashboard/multi_market_dashboard.py
- app/dashboard/visual_evidence_archive.py
- scripts/orchestrator/validate_ai_dev_218b_tw_preopen_news_readability_v1.py
- config/governance/validator_registry_v1.json

## Validation

- AI-DEV-218B dedicated validator: PASS, including real Chromium desktop/mobile PNG/PDF and all required mutations.
- AI-DEV-218A regression: PASS.
- AI-DEV-207 TW research evidence/news visibility: PASS.
- Window-specific Dashboard renderer: PASS.
- Admission/public-latest parity: PASS.
- Production landing integrity: PASS.
- Python compile / scoped F821 / diff check: PASS.
- Full executable branch registry: PASS — 35 selected; 34 required leaves executed and passed; 1 recursion guard; 0 failures; 0 unexplained skips.
- GitHub Actions: PASS.

Two obsolete, unregistered AI-DEV-193 standalone scripts reference a removed helper module and were not substituted for the executable registry. The current registry remained the source of truth and completed without skips or failures.

## Safety

- Strategy/scoring/prediction weights/ranking/eligibility/action rules: NO CHANGE
- Entry/Stop/trading target/sizing/execution: NO CHANGE
- Production/manual rerun: false
- LINE/Email sent: false
- Trading/orders: false
- Scheduler/cron/systemd/nginx: unchanged
- Secrets / production DB / immutable archives: untouched
- Existing controlled/runtime/generated artifacts: preserved

## Status

AI-DEV-218B: IMPLEMENTED_DETERMINISTIC_QA_PASS_PENDING_CONTROLLED_VERIFICATION

READY_FOR_TW_0700_NEWS_READABILITY_CONTROLLED_VERIFICATION
