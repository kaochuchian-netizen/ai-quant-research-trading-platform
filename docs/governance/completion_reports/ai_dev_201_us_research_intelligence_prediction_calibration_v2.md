# AI-DEV-201 Completion Report V2

Task ID: AI-DEV-201

## Repository

- Starting main: `3dd06793496a2227a891b1d9bf3013e385ef9cb9`.
- Feature branch: `ai-dev/201-us-research-prediction-continuity-v2`.
- Implementation commit(s): recorded in the final merged handoff.
- Pull request / merge commit: recorded in the final merged handoff.
- Existing runtime/generated dirty paths were preserved, not staged, cleaned, overwritten or committed.

## Implementation

The implementation adds a deterministic V2 research/evaluation module and extends the existing admitted institutional bundle, live pipeline, lifecycle evidence resolver, renderer, preview formatter and Operations provenance. It preserves V1 compatibility fields and all Decision Layer functions.

## Architecture summary

AI-DEV-201 extends the existing AI-DEV-197 institutional bundle instead of introducing a disconnected artifact:

`existing sources → canonical evidence → Research Intelligence V2 → existing Decision Layer → Dashboard / Archive / Email preview / LINE preview / Operations`.

The admitted 20:00 bundle retains the immutable `research_identity`. A deterministic `window_research_identity` records the research projection after 20:00, 23:00 and 06:30 evidence. This permits explainable research evolution without changing source-plan ownership or Decision Layer actions.

Layer boundaries remain explicit: Evidence owns facts/provenance; Research owns interpretation/hypothesis; Prediction/Evaluation owns forecast review; Decision owns action/eligibility/ranking; notification owns delivery only.

## User-visible Outcome

US reports now lead with a differentiated Research Brief, effective coverage, broad-versus-sector regime and current hypothesis state. Expandable details show supporting/opposing/missing evidence, trigger, invalidation, counterargument and per-window update. The 06:30 report retains prediction width/errors and no-trade learning instead of treating no-trade as nothing to review.

## Source inventory and source-quality policy

Actually connected by the existing repository contract: SEC EDGAR and Yahoo Finance/yfinance when observed data is returned. Company IR remains configured metadata unless a collector returns evidence. NASDAQ, NYSE, FMP, Finnhub, Polygon, Reuters, AP, Bloomberg, CNBC, MarketWatch, Barron's, official macro adapters, options, analyst and insider providers remain explicitly not configured/not licensed/unavailable as applicable.

No credential was accessed and no provider was falsely marked connected. Tier 1 covers regulator/company/government primary evidence; Tier 2 covers exchange/official macro/market feeds; Tier 3 covers recognized financial media; Tier 4 secondary aggregators; Tier 5 weak/unverified references. Lower-quality evidence cannot silently override primary evidence.

## Evidence contract

V2 evidence retains source, source class, quality tier, published/observed time, freshness, stale flag, materiality, direction, confidence, novelty, time horizon, primary-source confirmation, supporting/opposing/neutral role, related hypothesis, provenance and dedup identity. Missing, stale and failed sources do not create neutral facts.

News normalization performs deterministic deduplication, event/materiality/direction/time-horizon normalization and explicit live-source missing behavior. No live news is fabricated.

SEC form/item/summary rules classify earnings, guidance, M&A, agreements, financing, issuance, buybacks, management, legal/regulatory, cybersecurity, restructuring, business updates and insider-related events. Insufficient metadata remains `other`/neutral.

## Research contract

Every US symbol receives a Research Brief, supporting/opposing/missing evidence, company knowledge context, decomposed broad/growth/sector regime, hypothesis, trigger, invalidation, counterargument, confidence explanation, effective coverage and identities. Effective coverage is weighted by research utility; `not_applicable` is not penalized and duplicates are counted once. Coverage is explicitly not a trading score.

Options, analyst and insider schemas remain safe coverage states where no actual source is available. They cannot create trade actions.

## Hypothesis continuity

- 20:00 creates the initial evidence-backed hypothesis.
- 23:00 appends Gap, volume and relative market evidence and classifies confirmed/strengthened/unchanged/weakened/contradicted/invalidated/insufficient-new-evidence.
- 06:30 evaluates the originating prediction, retains the intraday hypothesis result, creates no-trade learning and exports bounded next-session research carryforward.

The 23:00 research layer may state that a premarket hypothesis was contradicted while the Decision Layer remains watch/no-trade. It cannot generate a trade plan or promote eligibility.

## Prediction and calibration contract

The existing deterministic price-range forecast function is unchanged. V2 separately represents range, direction, regime and setup evaluation. It records interval width, high/low/midpoint errors, direction hit and Brier score only where a deterministic probability plus method metadata exists. A range hit is never labeled sufficient model success without interval-width/error context.

No-trade cases still evaluate forecast usefulness, direction correctness, conservative-decision review, possible missed opportunity, trigger strictness candidate, evidence quality and carryforward. No automatic learning, threshold change or weight change occurs.

## 2026-08-07 deterministic reference behavior

- NVDA: broadly flat/mixed context and bullish SOXX sector context remain separate; +1.25% Gap continuation with 1.45x volume strengthens the compatible hypothesis.
- TSLA: a bearish/mean-reversion hypothesis encountering +2.60% Gap continuation with 1.94x volume becomes invalidated in research, without changing Decision Layer ownership.
- AAPL: an 8-K item 2.02 is classified as earnings; absent live news remains an explicit gap.
- Post-close: interval width/errors, direction and setup evaluation are present; no-trade creates learning and next-session carryforward.

Different evidence produces distinct research stance/identity instead of universal score 50/confidence 48.5 defaults. Sparse evidence may still legitimately remain insufficient.

## Evidence

The deterministic 2026-08-07 fixtures, source-quality/SEC/news assertions, three-window replay identities, channel parity bindings and AST comparison of Decision Layer functions provide the implementation evidence. All evidence is replay or read-only; none is claimed as natural production verification.

## Channel parity and UX

Dashboard/Archive render the Research Brief first and place supporting/opposing/missing evidence, hypothesis, trigger, invalidation and counterargument in an expandable section. Email preview reads the same V2 projection. LINE remains concise. Operations records both origin and window identities plus hypothesis state. No channel recomputes research.

## Changed files

- `app/us_stock/research_intelligence_v2.py`
- `app/us_stock/institutional_research.py`
- `app/us_stock/live_pipeline.py`
- `app/us_stock/three_window_lifecycle.py`
- `app/dashboard/multi_market_dashboard.py`
- `app/dashboard/window_snapshot_archive.py`
- `app/reports/presentation_normalization.py`
- `scripts/orchestrator/approved_us_stock_delivery.py`
- `app/runtime/operations_provenance.py`
- `scripts/orchestrator/validate_ai_dev_201_us_research_intelligence_v2.py`
- `scripts/orchestrator/validate_ai_dev_201_us_historical_replay_v1.py`
- `docs/runbooks/us_research_intelligence_prediction_calibration_v2.md`
- `config/governance/pending_natural_verification.json`
- `config/governance/platform_health_score.json`
- this completion report.

## Validation and replay evidence

The final merged handoff records exact commands and PASS/FAIL results. Mandatory task gates include Python compile, `git diff --check`, AI-DEV-201 semantic gate, deterministic 20:00→23:00→06:30 replay, AI-DEV-197/198/199/200 compatibility, US/TW lifecycle regressions, Archive/notification/landing integrity, governance bundle, branch gate, CI and post-merge validation.

Replay uses only a temporary directory. Same evidence produces the same identity; changed evidence produces a new identity; admitted origin snapshot/revision/hash remains linked; channels consume the same window projection; 06:30 links evaluation to its originating prediction.

The production Landing integrity gate initially exposed an existing performance defect: each market/window lookup reparsed all 132 admitted files (106 MB) from disk. The resolver now caches admitted snapshots only while the archive path/size/mtime signature is unchanged; any immutable addition or replacement invalidates the cache. Latest/Previous ordering is unchanged. The complete Landing gate passed in 12.55 seconds after this fix, and admission-to-public parity remained 7/7.

## Quality Gate

- Correctness: PASS deterministically — evidence, hypothesis and evaluation ownership is explicit.
- Completeness: PASS for implemented contracts — unavailable external providers remain explicit limitations.
- Consistency: PASS deterministically — one canonical bundle feeds all channel adapters.
- Explainability: PASS — supporting/opposing/missing evidence, trigger, invalidation and counterargument are present.
- Source Quality: PASS — tier, provenance, freshness and safe unavailable behavior are validated.
- Freshness: PASS — stale/missing/failed are distinct and cannot become neutral evidence.
- Truthfulness: PASS — no live news, probability or direction is fabricated.
- Readability: PASS — Research Brief first; detailed research is expandable.
- Localization: PASS — primary public explanation is Traditional Chinese with bounded English research terminology.
- Cross-window Continuity: PASS deterministically — natural lifecycle pending.
- Cross-channel Parity: PASS deterministically — natural delivery identity pending.
- Production Usability: CONDITIONAL_PASS — implementation is production-ready but a natural full US lifecycle is required.

## Known Limitations

1. Paid/licensed news, options, analyst and insider feeds are not connected; their state remains explicit rather than fabricated.
2. Macro provider adapters are structurally represented but actual evidence depends on existing runtime availability.
3. Regime and probability evaluation remains `insufficient_evidence` where no deterministic forecast/method exists.
4. Existing V1 fields remain for backward compatibility.

These limitations do not block merge because the product fails truthfully and no Decision Layer threshold, score, rank or action is changed.

## Deferred Enhancements

Connecting paid/licensed providers, expanding macro adapters, introducing validated probabilistic models, changing prediction weights, automatic learning and threshold optimization are deferred. Each requires a separately governed task and cannot be inferred from this implementation.

## Natural Verification

Required status: `IMPLEMENTED_PENDING_NATURAL_VERIFICATION`.

Observe at least one natural US `20:00 → 23:00 → 06:30` lifecycle and confirm source availability/coverage, differentiation, SEC/news behavior, broad/sector divergence, meaningful hypothesis evolution, no-trade learning, origin/window identity parity, and absence of Decision Layer/scheduler/notification/trading regression.

## Phase Contribution

AI-DEV-201 raises the US side from a static institutional bundle to a traceable research lifecycle and creates the calibrated evaluation contracts required by the roadmap's prediction-evaluation phase. It does not change the current phase registry status; natural verification remains an exit dependency.

## Regression

AI-DEV-197 through AI-DEV-200 compatibility, US source-plan/direction/outcome gates, TW seven-window protection, Archive/notification/admission/manual-revision/landing integrity, governance, compile and diff checks are part of the required merge matrix. Exact final results are recorded in the merged handoff.

## Production Usability

At 20:00 a PM can distinguish broad market from sector context and see why a hypothesis exists. At 23:00 the report explains whether actual Gap/volume evidence strengthened or contradicted it without silently creating an action. At 06:30 the PM sees forecast quality, no-trade learning and what must carry into the next session. Natural usability confirmation remains pending.

## Final Status

`IMPLEMENTED_PENDING_NATURAL_VERIFICATION`

## Safety

Production execution: false. Controlled publish: false. Email attempted: false. LINE attempted: false. Trading: false. Scheduler changed: false. Secrets accessed: false. Immutable history rewritten: false. Production DB written: false. Existing dirty artifacts cleaned: false.
