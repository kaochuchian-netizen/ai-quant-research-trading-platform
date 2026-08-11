# AI-DEV-202 Completion Report V1

Task ID: AI-DEV-202

## Final Status

`IMPLEMENTED_PENDING_NATURAL_VERIFICATION`

The implementation and deterministic replay are complete. They validate architecture and enable forward sample collection; they do not prove predictive accuracy.

## Repository

- Starting main: `1b29a98fbe1fbdcc6616f179f367be0d32ec0b8f`.
- Feature branch: `ai-dev/202-tw-production-intelligence-data-foundation-v1`.
- Implementation commit(s): recorded in the final merged handoff.
- Pull request / merge commit: recorded in the final merged handoff.
- Starting main/origin-main: `0/0`; starting open PRs: `0`.
- Ninety-eight pre-existing runtime/generated dirty entries were preserved, not cleaned, staged or committed. Task staging is restricted to the changed source, validator, documentation and governance files listed below.

## Implementation

The implementation repairs the canonical history fallback, enriches existing technical/RRE evidence, adds an action-independent prediction/evaluation contract, carries source evidence across four windows, and exposes append-safe verification and channel identities. It extends existing builders rather than creating a disconnected production sidecar.

## User-visible Outcome

A PM can distinguish missing history from missing quotes, partial news metadata from usable news, and company evidence from ETF applicability. Each research note shows a compact independent forecast and identity. At 15:00, a no-trade symbol can still show whether its direction/range hypothesis was useful without implying that a trade existed.

## Evidence

Evidence consists of the audited nine 19-row CSVs, four admitted immutable 2026-08-11 snapshot identities, synthetic 60-bar positive/negative fixtures, read-only replay results, canonical channel identities, source inventory, regression matrix and governance outputs. None is represented as natural predictive validation.

## Root-cause audit

### Quote existed but technical evidence did not

Every canonical TW historical CSV for the nine-symbol universe contained exactly 19 daily rows, ending 2026-07-24. The 07:00 production pipeline requested 180 calendar days through Shioaji, but login/fetch failure fell directly back to the existing files. The fallback policy text incorrectly still claimed 30 days. The technical engine already supported MA5/10/20/60, RSI, MACD, ATR, volatility, volume and price structure, but `technical_contract` correctly requires at least 20 bars and MA20. Consequently all nine cards became ineligible even though current quote coverage was 9/9.

The fix retains Shioaji as primary and adds a credential-free yfinance fallback (`<symbol>.TW`, then `<symbol>.TWO`) before existing CSV reuse. It validates normalized date/OHLCV geometry, non-negative volume, deduplication and at least 20 bars. Per-symbol status retains source, bars before/after and bounded failure details. No network fallback was executed during this task.

### News 0/9

Google News RSS returned metadata (five items per symbol in the observed run), but the analysis path returned no safe direction and several items were stale/noisy. The public coverage calculation required a directional item, so “source returned partial metadata” collapsed into the same 0/9 outcome as “no source”. V2 deduplicates by identity, applies the 72-hour freshness contract, counts only fresh safely classified evidence as usable, and preserves stale/unclassified metadata as `partial` with `NO_RELIABLE_NEWS`/`OUTSIDE_LOOKBACK`. It does not infer headline sentiment or fake live news. MOPS/TWSE/TPEx official collectors remain explicitly registry/fixture-only until real production evidence proves connection.

### Research 9/9 insufficient

RRE received the unavailable technical contract. In afternoon windows it received current price, but the prior adapter encoded price as neutral and did not carry the pre-open technical/news/ADR evidence into observed cards. V2 carries admitted source evidence forward and converts open/current/high/low into directional session evidence with provenance. Canonical sector/industry/peer mappings distinguish companies and ETFs; ADR is applicable only to 2330. Different evidence now produces different notes and explicit strengthened/weakened/contradicted lifecycle states.

### Empty prediction evaluation

Legacy prediction fields used trade Entry→Target geometry and were set to `no_trade` when Decision abstained. Post-close then returned `not_applicable`, creating an evaluation deadlock. `tw_prediction_snapshot_v2` is independent of action: with at least ten bars, latest close and deterministic ATR evidence it stores direction, range, regime, confidence method, evidence/research/hypothesis identities, decision linkage and a pre-outcome timestamp. At 15:00 it evaluates range overlap, interval width, high/low/midpoint error, direction, confidence bucket and no-trade abstention while the trade outcome remains `no_trade`.

## Architecture

- Source foundation: Shioaji → yfinance TW/TWO → existing CSV, with per-source failure isolation and no credential logging.
- Technical evidence: reuses the existing engine; adds method version, period, bars, freshness, sufficiency, provenance and explicit reason code.
- Fundamental/official events: represented distinctly; no unavailable field is fabricated. ETF company fields are `not_applicable`.
- News: raw/partial/usable states, freshness and dedup are separate; a missing direction is not neutral.
- Market/sector/peer: canonical instrument mapping and directional intraday price evidence; ETFs and companies have different applicability.
- ADR: contextual and restricted to mapped symbols.
- Research: RRE consumes carried source evidence plus intraday session behavior and records a window-specific hypothesis state.
- Prediction: deterministic `tw_ohlcv_range_direction_v2`, separate from action and legacy trade-plan prediction fields.
- Evaluation: no-trade remains range/direction evaluable; no automatic strategy learning or threshold change.
- Verification registry: immutable prediction identity linked to later review identity; append-safe/replay-compatible record and sample-maturity summary.
- Channels: one canonical projection exposes research and prediction bundle identities to Dashboard, Archive payload, Email/LINE preview and Operations projection.

## Changed files

- `app/research/tw_production_intelligence_v2.py`
- `app/research/tw_daily_generator.py`
- `app/reports/tw_pre_open_quality.py`
- `app/reports/tw_four_window_decision.py`
- `app/reports/tw_decision_intelligence_v2.py`
- `app/dashboard/multi_market_dashboard.py`
- `scripts/update_historical_csv.py`
- `scripts/orchestrator/validate_ai_dev_202_tw_production_intelligence_v1.py`
- `scripts/orchestrator/validate_ai_dev_202_tw_0811_replay_v1.py`
- `config/governance/tw_source_inventory_v2.json`
- `config/governance/pending_natural_verification.json`
- `config/governance/platform_health_score.json`
- `docs/runbooks/tw_production_intelligence_data_foundation_v1.md`
- this completion report.

## 2026-08-11 read-only replay

Immutable admitted identities were read without modification:

- 07:00 `196ecf26336961a93383535ef37b5375b2ca9fde124ab9dccc4cf6e317760339`
- 13:05 `94ebf15edb0fc3d95b43e6e7658af6d093c1928c744403a042e53b37f04c33b0`
- 13:35 `fce87c722a8e023b3ae911813154d399fe3273536406bacbe2e7b1c1113487f8`
- 15:00 `443c1bdb4131adf3cc90730891c881b58dad39212a3dfc2d011ebc0cf6e9991a`

Observed audit: history bars 19 for all nine; intraday current/high/low available 9/9; trade outcomes no-trade 9. V2 replay created 9 predictions and 9 evaluations: range hit 3, partial hit 4, miss 2, not-applicable 0. Trade count remained 0 and no-trade count remained 9. Prediction tuples were differentiated across at least five distinct direction/range combinations. Maturity is `EARLY_SAMPLE`; this is replay evidence only.

The synthetic semantic fixture uses sufficient 60-bar OHLCV and produces nine differentiated RRE notes, nine no-trade predictions, and nine evaluations (hit 3, partial 6). It also covers 19-bar insufficiency, injected yfinance fallback, ETF applicability, ADR isolation, no-lookahead and channel identity parity.

## Validation matrix

PASS:

- Changed-file Python compile.
- `validate_ai_dev_202_tw_production_intelligence_v1.py`.
- `validate_ai_dev_202_tw_0811_replay_v1.py`.
- AI-DEV-198, 199, 200 and 201 semantic/replay gates.
- AI-DEV-190 seven-window and AI-DEV-191 cross-feature gates.
- AI-DEV-193 technical history/coverage/news diagnostics.
- TW four-window continuity, trade/prediction separation and post-close closure.
- Seven-window cross-feature regression.
- 14-route Archive navigation.
- Notification provenance/content parity.
- Admission/public-latest parity 7/7.
- Production Landing integrity.
- Governance phase, health, pending registry and full positive/negative bundle.
- `git diff --check` before commit.

One invocation issue was encountered: several legacy one-line wrapper validators import sibling modules and fail when invoked from repository root as a file/module. They passed from their canonical `scripts/orchestrator` working directory. No validator was deleted or weakened.

Exact final branch, CI and post-merge commands/results are recorded in the merged handoff.

## Quality Gate

- Correctness: PASS deterministically — sufficient history creates technical evidence; unexplained emptiness is rejected.
- Completeness: CONDITIONAL_PASS — official-event and reliable live-news production collectors remain unavailable.
- Consistency: PASS deterministically — canonical identities and no-trade semantics are shared.
- Explainability: PASS — source failure, technical sufficiency, hypothesis change and prediction errors are explicit.
- Source Quality: PASS for the implemented policy — unproven sources remain missing/partial.
- Freshness: PASS — stale news and historical period end are distinct.
- Truthfulness: PASS — no missing evidence becomes neutral and replay is not called predictive validation.
- Readability: PASS — Prediction V2 appears compactly inside expandable research notes.
- Localization: PASS under retained public-wording gates.
- Cross-window Continuity: PASS deterministically; natural confirmation pending.
- Cross-channel Parity: PASS deterministically; natural delivery confirmation pending.
- Production Usability: CONDITIONAL_PASS — source fallback and forward sample accumulation require a natural lifecycle.
- Decision Actionability: PASS boundary — no action/eligibility/ranking/weights were changed.

## Performance

The yfinance fallback runs only after primary failure, once per symbol, with `.TW` then `.TWO`, 20-second adapter timeout and per-run normalized result. Technical/RRE/prediction functions are pure in-memory transformations. Secondary-source failure cannot fail the Decision Layer. No production runtime benchmark is claimed because the production pipeline was not executed.

## Known Limitations

1. MOPS/TWSE/TPEx official-event ingestion is not proven production-connected.
2. Google News RSS does not guarantee trustworthy directional evidence; no paid news provider was added.
3. Prediction V2 is a deterministic baseline (MA alignment and ATR interval), not a validated profitable model.
4. The 10-bar minimum supports forward evaluability while the stricter 20-bar technical eligibility remains unchanged and visibly partial.
5. No true probabilistic setup model exists, so setup probability and Brier score remain unavailable.

Paid sources, production strategy changes, automatic learning, statistical calibration claims and backtest optimization are deferred behind separately governed work.

## Deferred Enhancements

Paid sources, production strategy changes, automatic learning, statistical calibration claims and backtest optimization are deferred behind separately governed work.

## Natural Verification

Registry state is `PENDING`. Observe a complete natural TW 07:00→13:05→13:35→15:00 chain and verify refreshed bar count/source provenance, technical features, official/news failure reasons, ETF/company applicability, differentiated RRE notes, hypothesis evolution, independent no-trade predictions, 15:00 errors, no-lookahead, registry growth and five-channel identity parity. Sample milestones 30/50/100 are maturity checkpoints, not proof.

## Phase Contribution

AI-DEV-202 repairs the TW evidence foundation required by Research Intelligence and unlocks forward Prediction Verifiability without changing the current phase registry or claiming Phase D completion. Platform implemented scores improve; verified scores and overall health remain unchanged pending natural evidence.

## Regression

The protected TW four-window lifecycle, US three-window research, AI-DEV-190/191/193/194/198/199/200/201 behaviors, seven-window rendering, archive navigation, notification provenance/content, admission/public identity, landing and governance contracts pass deterministically. Legacy wrappers were invoked from their canonical working directory.

## Production Usability

The next natural 07:00 run can refresh insufficient history through a truthful fallback, produce technical evidence when sufficient, and create evaluable predictions even when action remains no-trade. Afternoon windows carry evidence and hypothesis identity forward; 15:00 records a forward review sample. Natural runtime and source availability remain the final usability gate.

## Safety

- Production pipeline executed: false.
- Controlled/public publish: false.
- Email attempted: false.
- LINE attempted: false.
- Trading/orders: false.
- Scheduler/cron/systemd/nginx/firewall changed: false.
- Notification runtime changed: false.
- Secrets accessed: false.
- Production DB written: false.
- Immutable history rewritten: false.
- Existing dirty artifacts cleaned: false.
- Existing dirty artifacts staged/committed: false.
