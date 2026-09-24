# AI-DEV-251A Prediction Regression Data Contract & Inventory v1

Status: CONTRACT_READY_WITH_DATA_GAPS. Program AI-DEV-251A–251E; existing AI-DEV-250 is unrelated and untouched.

This document and `config/governance/prediction_regression_data_contract_v1.json` are the canonical **cross-source review contract**, not a new authority for market data, predictions, evidence, or delivery. JSON owns executable fields/weights/policies. The generated block below must match JSON exactly; the offline validator rejects drift. All artifact readers and writers remain inactive in production in phase A.

## Reuse decision and inventory evidence

- Prediction: `app/prediction/schemas.py`, formal prediction runtime/AI-DEV-155 archives, and current TW `prediction_snapshot_v2` / US `prediction` preserved in admitted window archives. They are different producer schemas: normalize by explicit adapters, never silently select one and overwrite another.
- Outcome/evaluation: `app/evaluation/{schemas,actual_outcome,evaluator}.py`; existing formal outcome/review snapshots and backtest reports are distinct observations/derived results. Preserve the old definitions; new review metrics are versioned overlays, not replacements for historical scores.
- History: `app/history/{schemas,historical_store,deduplication}.py` owns provenance/indexing. The eleven logical entities below use references to those authorities. `extension` means a future schema addition under the existing owner, **not** a claimed existing operational ledger or a second database. Phase A writes no data stores.
- Findings/fixes: reuse `CalibrationFinding`/`CalibrationRecommendation`; TW/US evidence regression ledgers remain evidence authorities, not proof an intervention was approved or worked. No finding/fix lifecycle/D+3/D+10 closure was found.
- Reports: `app/dashboard/window_snapshot_archive.py` owns immutable per-window revisions; `app/runtime/batch_audit_bundle.py` owns bundle manifests and delivery status. Extend these identities for 17:00 manifests; do not create another raw report/delivery history. Formal forecast archive's legacy `--overwrite` capability is **not allowed** for this program.
- Existing AI-DEV-017/065/066/072/073/074/122/124/129/151/155 contracts remain valid; this contract adds as-of, chain, revision and review-window constraints, without executing or changing their engines.

Inventory was collected read-only from the fixed allowlist by `scripts/orchestrator/inventory_prediction_regression_data_contract_v1.py`, sending source over SSH stdin with no VM file writes. Only schemas, field-presence counts, date bounds and missingness aggregates are committed in `docs/governance/prediction_regression_inventory_v1.json`. No symbols, prices, holdings, message bodies, recipient identities or production rows are committed. The live scan is not an atomic database snapshot; files may advance while natural jobs run. Per-family bounds/denominators are authoritative for the observation, not a promise of full historical retention.

Observed: TW 138 window revisions / 382 selected pre-open card rows (2026-07-15–2026-09-24); US 135 window revisions / 810 item rows (2026-07-14–2026-09-23); formal prediction/outcome/review each 48 files /443 rows (2026-07-06–2026-09-24); historical OHLCV 12 files /1472 rows (2025-12-04–2026-09-23). Repeated stocks/windows/revisions are **not independent samples**. TW row selection excludes windows without pre-open cards; US uses items. Missingness counts null/absent/empty-string/empty-object only; false fallback flags and explicit empty missingness arrays count as present. A present object/status or latest quote does not establish a complete, timely or final feature/outcome.

Formal archived outcome OHLCV fields are null/absent in 97.97% of 443 rows (only 9 rows structurally populated); archive file count must not be called realized-outcome coverage.

TW prediction-v2 confidence/ranges/model provenance are absent in about 50.52% of selected rows; original generated_at at that path is absent in 100%. US strategy confidence exists but its meaning differs from forecast-event probability, and monthly trend cannot be a same-session trend. Frozen per-feature availability times, ATR-at-prediction and per-record Git SHA are missing at audited paths. Batch stage timing exists but cannot substitute for per-feature latency. Do not infer AVAILABLE from a schema field alone or from an admission timestamp.

## Phase boundaries and readiness

251B may start **offline fixture-driven engine/adaptor development** against this contract. Production score readiness is BLOCKED: original prediction timestamps, event-calibrated confidence, pre-prediction ATR, authoritative complete exchange calendars, aligned final US OHLCV/path/benchmark/cost assumptions, implemented-fix cohorts, and predecessor-chain history need explicit coverage. Missing data is PENDING/EXCLUDED with reason codes, never a fabricated score. 251C adds approved finding/fix events and report chains; 251D only presents approved results; 251E separately authorizes scheduling/retention/production integration. No phase may automatically modify a model, weights, strategy, stop or trade.

At 17:00 Asia/Taipei a calendar-date report refers to that day's completed TW session and the most recently completed US session. Each market's 3/10 lookback uses its own actual session table. Holiday reports preserve the previous session identity without counting it twice. The existing US holiday helper is reused for candidate dates but cannot certify early/exceptional closures; TW calendar provenance remains missing. Offline fixture session tables exercise DST, holidays and early closes; they are not a production exchange calendar.

Report revisions append new identity/hash bindings. Never replace a previous report, source snapshot or old fix status. Dated finding/fix events are append-only; a late review references frozen earlier versions. The previous-calendar-day report ID/hash is separate from the same-day supersedes hash. Missing yesterday produces a PENDING manifest, not a skipped link. Every non-genesis predecessor must resolve to retained evidence. Hot indexes may be rebuilt but cannot redefine immutable history.

The JSON entity schemas describe metadata/reference **views**, not raw payload copies. `source_refs` bind original path, source record ID, schema and content hash. Future adapters must verify referenced hashes, row identity, feature availability and outcome availability by cutoff; this offline phase never dereferences or mutates production sources. New fields may be PENDING in historical records; backwards filling them from later knowledge is forbidden. Corrections belong to hindsight outcome/review revisions.

## Frozen v1 component definitions (specification only)

- **common**: All eligible components are 0..100. Compute per market/symbol/strategy/horizon; never mix daily tactical and research-position horizons. Report exclusions and eligible/expected counts. No engine is implemented in A.
- **prediction.trend**: 100 for matching frozen UP/DOWN/FLAT label, otherwise 0. Realized close minus frozen reference price is FLAT within +/-0.1 frozen ATR14; outside that band UP/DOWN. Horizon must match. No same-day proxy for a one-month prediction.
- **prediction.atr_target**: 100 * max(0, 1 - abs(frozen forecast target - horizon final close) / frozen ATR14). ATR14 is Wilder ATR from 14 completed pre-prediction sessions with point-in-time corporate-action basis. Missing/nonpositive ATR => PENDING. Execution targets/support/resistance must never masquerade as forecast targets.
- **prediction.range_coverage**: 100 if the full realized horizon low/high lies within the frozen predicted interval, otherwise 0. Missing intrahorizon extrema => PENDING; disclose interval width relative to ATR so wide intervals cannot hide poor precision.
- **prediction.confidence_calibration**: 100 * (1 - mean((p - y)^2)), Brier complement, p is explicitly probability of the same direction-correct event and y is that event 0/1. Require 3 pairs for the 3-session window and 10 for the 10-session window per stock/strategy/horizon; small samples are descriptive only; strategy confidence or textual confidence is UNMAPPED until an approved adapter establishes semantics.
- **improvement.finding_confirmed**: 100 only when the linked finding is CONFIRMED with immutable error evidence and a dated confirmation; PROPOSED/PENDING cannot count as confirmation.
- **improvement.d3_effect**: At fix effective session +3 completed trading sessions, compare eligible post-fix prediction metric to frozen matched pre-fix cohort using delta S; score clip(50 + delta S, 0, 100). Require all 3 sessions and matched market/symbol/strategy/horizon/regime, disclose cohort size and no causal claim without a control.
- **improvement.d10_effect**: Same matched-cohort specification at +10 completed trading sessions; immature or missing baseline => PENDING, not zero.
- **improvement.non_recurrence**: 100 * (1 - recurrence_count / observable_opportunities) over the 10 completed post-fix sessions, using the same predeclared finding detector/version; no observable opportunities => N/A, composite PENDING.
- **strategy.common**: Advisory hypothetical exposure only, never actual holdings. Freeze entry/exit/hedge, benchmark, fees, slippage, session horizon, corporate-action basis and assumptions before evaluation. Missing inputs => PENDING; missing intraday order => EXCLUDED AMBIGUOUS_INTRABAR_ORDER. No automatic changes.
- **strategy.direction_exposure**: 100 * clip(1 - abs(frozen recommended signed normalized exposure - hindsight best permitted signed normalized exposure) / 2, 0, 1), using exposure domain [-1,1] and the same declared allowed-position universe. Unavailable exposure mapping => PENDING.
- **strategy.opportunity_capture**: 100 * clip(hypothetical net profit / best feasible positive net profit within the frozen opportunity/constraint set, 0, 1). No positive feasible opportunity => N/A; do not invent an entry from future prices.
- **strategy.risk_avoidance**: 100 * clip(1 - hypothetical MAE / frozen risk budget, 0, 1). Budget must be positive and fixed before prediction; no path/budget => PENDING. Include avoided-loss evidence for a no-trade recommendation.
- **strategy.entry_hedge_timing**: 100 * clip(1 - abs(actual hypothetical entry-or-hedge execution price - hindsight best feasible price) / frozen ATR14, 0, 1). Apply the predeclared trigger/fill model and average required event scores; unobserved event order or absent benchmark => PENDING.
- **strategy.relative_market**: clip(50 + 50 * (hypothetical net return - matched benchmark total return) / frozen ATR14-percent, 0, 100). Match currency/session/exposure conventions; missing/nonpositive scale => PENDING.
- **aggregation**: Per-window category weighted sum with the frozen component weights, then 35% last-3-session category + 65% last-10-session category, then 40% prediction +20% improvement +40% strategy. Overlap of the last 3 sessions is intentional. Missing any required component/window, or improvement N/A => PENDING/null; no reweighting.

<!-- BEGIN CANONICAL CONTRACT -->
Canonical JSON SHA-256: `ed8f41ea4622394aa4007dbce390dfbc3d5c2aedbf56c3378a2ab0c0c0505590`

### Frozen v1 weights (percent)

| Group | Components |
|---|---|
| prediction | trend=45%, atr_target=35%, range_coverage=10%, confidence_calibration=10% |
| improvement | finding_confirmed=25%, d3_effect=20%, d10_effect=40%, non_recurrence=15% |
| strategy | direction_exposure=25%, opportunity_capture=25%, risk_avoidance=25%, entry_hedge_timing=15%, relative_market=10% |
| time | last_3_sessions=35%, last_10_sessions=65% |
| composite | prediction=40%, improvement=20%, strategy=40% |

### Canonical ownership (logical views, no parallel raw store)

| Entity | Schema owner | Storage owner | Binding |
|---|---|---|---|
| prediction_snapshot | `app/prediction/schemas.py` | `app/dashboard/window_snapshot_archive.py` | projection |
| feature_snapshot | `app/history/schemas.py` | `app/history/historical_store.py` | extension |
| market_outcome | `app/evaluation/schemas.py` | `app/evaluation/actual_outcome.py` | projection |
| forecast_evaluation | `app/evaluation/schemas.py` | `app/evaluation/evaluator.py` | projection |
| strategy_counterfactual | `app/history/schemas.py` | `app/history/historical_store.py` | extension |
| finding_ledger | `app/calibration/schemas.py` | `app/history/historical_store.py` | extension |
| fix_ledger | `app/calibration/schemas.py` | `app/history/historical_store.py` | extension |
| fix_evaluation | `app/evaluation/schemas.py` | `app/history/historical_store.py` | extension |
| daily_scorecard | `app/history/schemas.py` | `app/history/historical_store.py` | extension |
| report_manifest | `app/runtime/batch_audit_bundle.py` | `app/dashboard/window_snapshot_archive.py` | extension |
| delivery_ledger | `app/runtime/batch_audit_bundle.py` | `app/runtime/batch_audit_bundle.py` | projection |

### Requirement inventory

Counts measure structural presence only. Dates, denominators and missing rates are in the aggregate inventory; metadata and semantic gaps are per field in the JSON contract.

| Market | Field | Classification | Source | Gap |
|---|---|---|---|---|
| TW | atr_at_prediction | MISSING | `artifacts/archive/window_snapshots/tw::payload.structured_pre_open_cards.atr_at_prediction` | No per-row frozen provenance at audited path; do not reconstruct as contemporaneous evidence. |
| TW | chip | PARTIAL | `artifacts/archive/window_snapshots/tw::payload.structured_pre_open_cards.chip_summary` | Container/text/reference is structurally present; usable values, source freshness and point-in-time availability are not certified by this metadata-only inventory. |
| TW | confidence | PARTIAL | `artifacts/archive/window_snapshots/tw::payload.structured_pre_open_cards.prediction_snapshot_v2.confidence` | Structural presence only; complete point-in-time semantics/coverage must be validated. |
| TW | fallback | PARTIAL | `artifacts/archive/window_snapshots/tw::payload.structured_pre_open_cards.technical_data.history_fallback.used` | No-error/false and fallback-not-recorded must not be conflated; source-specific reason semantics differ. |
| TW | feature_as_of | PARTIAL | `artifacts/archive/window_snapshots/tw::payload.structured_pre_open_cards.prediction_snapshot_v2.no_lookahead.last_input_market_timestamp` | Structural presence only; complete point-in-time semantics/coverage must be validated. |
| TW | feature_available_at | MISSING | `artifacts/archive/window_snapshots/tw::payload.structured_pre_open_cards.feature_available_at` | No per-row frozen provenance at audited path; do not reconstruct as contemporaneous evidence. |
| TW | generated_at | AMBIGUOUS | `artifacts/archive/window_snapshots/tw::payload.structured_pre_open_cards.prediction_snapshot_v2.generated_at` | Field declared but null in prediction_snapshot_v2; archive/admission time must not be relabeled as original prediction generation time. |
| TW | git_sha | MISSING | `artifacts/archive/window_snapshots/tw::payload.structured_pre_open_cards.git_sha` | No per-row frozen provenance at audited path; do not reconstruct as contemporaneous evidence. |
| TW | latency | MISSING | `artifacts/archive/window_snapshots/tw::payload.structured_pre_open_cards.latency_ms` | No per-row frozen provenance at audited path; do not reconstruct as contemporaneous evidence. |
| TW | market_features | PARTIAL | `artifacts/archive/window_snapshots/tw::payload.structured_pre_open_cards.market_context` | Container/text/reference is structurally present; usable values, source freshness and point-in-time availability are not certified by this metadata-only inventory. |
| TW | missingness | AVAILABLE | `artifacts/archive/window_snapshots/tw::payload.structured_pre_open_cards.missing_fields` | Source field exists in sampled rows; content completeness is not implied. |
| TW | model_version | PARTIAL | `artifacts/archive/window_snapshots/tw::payload.structured_pre_open_cards.prediction_snapshot_v2.method_version` | Structural presence only; complete point-in-time semantics/coverage must be validated. |
| TW | news | PARTIAL | `artifacts/archive/window_snapshots/tw::payload.structured_pre_open_cards.news_evidence` | Structural presence only; complete point-in-time semantics/coverage must be validated. |
| TW | prediction_id | PARTIAL | `artifacts/archive/window_snapshots/tw::payload.structured_pre_open_cards.prediction_snapshot_v2.prediction_identity` | Structural presence only; complete point-in-time semantics/coverage must be validated. |
| TW | range_high | PARTIAL | `artifacts/archive/window_snapshots/tw::payload.structured_pre_open_cards.prediction_snapshot_v2.range_forecast.high` | Structural presence only; complete point-in-time semantics/coverage must be validated. |
| TW | range_low | PARTIAL | `artifacts/archive/window_snapshots/tw::payload.structured_pre_open_cards.prediction_snapshot_v2.range_forecast.low` | Structural presence only; complete point-in-time semantics/coverage must be validated. |
| TW | schema_version | PARTIAL | `artifacts/archive/window_snapshots/tw::payload.structured_pre_open_cards.prediction_snapshot_v2.schema_version` | Structural presence only; complete point-in-time semantics/coverage must be validated. |
| TW | session | PARTIAL | `artifacts/archive/window_snapshots/tw::payload.structured_pre_open_cards.prediction_snapshot_v2.effective_trading_date` | Structural presence only; complete point-in-time semantics/coverage must be validated. |
| TW | strategy | PARTIAL | `artifacts/archive/window_snapshots/tw::payload.structured_pre_open_cards.strategies.daily_tactical.strategy_type` | Structural presence only; complete point-in-time semantics/coverage must be validated. |
| TW | target_price | PARTIAL | `artifacts/archive/window_snapshots/tw::payload.structured_pre_open_cards.prediction_snapshot_v2.point_forecast.price` | Structural presence only; complete point-in-time semantics/coverage must be validated. |
| TW | technical | PARTIAL | `artifacts/archive/window_snapshots/tw::payload.structured_pre_open_cards.technical_data` | Structural presence only; complete point-in-time semantics/coverage must be validated. |
| TW | trend | PARTIAL | `artifacts/archive/window_snapshots/tw::payload.structured_pre_open_cards.prediction_snapshot_v2.direction_forecast` | Structural presence only; complete point-in-time semantics/coverage must be validated. |
| TW | window | PARTIAL | `artifacts/archive/window_snapshots/tw::payload.structured_pre_open_cards.prediction_snapshot_v2.window` | Structural presence only; complete point-in-time semantics/coverage must be validated. |
| TW | realized_prices | PARTIAL | `artifacts/archive/formal_forecast_snapshots/actual_outcome` | TW archived OHLCV or US quote snapshots are not uniformly certified final session bars. |
| TW | subsequent_price_path | PARTIAL | `data/historical/*_daily.csv` | Daily prices do not establish within-bar target/stop ordering; US retained history not proven by quote snapshots. |
| TW | notification_artifacts | PARTIAL | `artifacts/runtime/delivery_provenance` | Latest channel receipts are not full historical daily-report delivery coverage. |
| TW | report_artifacts | PARTIAL | `artifacts/archive/window_snapshots/tw` | Immutable window revisions exist; no 17:00 predecessor/hash daily-report chain. |
| TW | finding_tracking | PARTIAL | `artifacts/runtime/tw/evidence_regression_ledger/v1` | CalibrationFinding and evidence ledgers exist but no confirmed issue lifecycle linked to interventions. |
| TW | fix_tracking | MISSING | `artifacts/runtime/tw/evidence_regression_ledger/v1` | No approved/effective fix ledger with frozen pre-fix cohort and D+3/D+10 outcomes. |
| TW | benchmark_cost_basis | MISSING | `data/historical/*_daily.csv` | Point-in-time benchmark/corporate actions/fees/slippage/exposure assumptions not audited as a joined source. |
| TW | trading_calendar | MISSING | `artifacts/archive/window_snapshots/tw` | US trading_calendar.py provides holidays but not exchange-complete closures/early closes; TW authoritative calendar adapter absent. |
| US | atr_at_prediction | MISSING | `artifacts/archive/window_snapshots/us::payload.items.atr_at_prediction` | No per-row frozen provenance at audited path; do not reconstruct as contemporaneous evidence. |
| US | chip | MISSING | `artifacts/archive/window_snapshots/us::payload.items.chip_summary` | Structural presence only; complete point-in-time semantics/coverage must be validated. |
| US | confidence | AMBIGUOUS | `artifacts/archive/window_snapshots/us::payload.items.strategies.daily_tactical.confidence` | Strategy confidence is not a calibrated forecast-event probability. |
| US | fallback | PARTIAL | `artifacts/archive/window_snapshots/us::payload.items.fetch_error` | No-error/false and fallback-not-recorded must not be conflated; source-specific reason semantics differ. |
| US | feature_as_of | AMBIGUOUS | `artifacts/archive/window_snapshots/us::payload.items.source_timestamp` | source_timestamp does not prove each feature became available before prediction. |
| US | feature_available_at | MISSING | `artifacts/archive/window_snapshots/us::payload.items.feature_available_at` | No per-row frozen provenance at audited path; do not reconstruct as contemporaneous evidence. |
| US | generated_at | PARTIAL | `artifacts/archive/window_snapshots/us::payload.items.strategies.daily_tactical.generated_at` | Structural presence only; complete point-in-time semantics/coverage must be validated. |
| US | git_sha | MISSING | `artifacts/archive/window_snapshots/us::payload.items.git_sha` | No per-row frozen provenance at audited path; do not reconstruct as contemporaneous evidence. |
| US | latency | MISSING | `artifacts/archive/window_snapshots/us::payload.items.latency_ms` | No per-row frozen provenance at audited path; do not reconstruct as contemporaneous evidence. |
| US | market_features | PARTIAL | `artifacts/archive/window_snapshots/us::payload.items.market_context_ref` | Container/text/reference is structurally present; usable values, source freshness and point-in-time availability are not certified by this metadata-only inventory. |
| US | missingness | AVAILABLE | `artifacts/archive/window_snapshots/us::payload.items.prediction.missing_fields` | Source field exists in sampled rows; content completeness is not implied. |
| US | model_version | PARTIAL | `artifacts/archive/window_snapshots/us::payload.items.prediction.model_version` | Structural presence only; complete point-in-time semantics/coverage must be validated. |
| US | news | PARTIAL | `artifacts/archive/window_snapshots/us::payload.items.news` | Structural presence only; complete point-in-time semantics/coverage must be validated. |
| US | prediction_id | MISSING | `artifacts/archive/window_snapshots/us::payload.items.prediction.prediction_identity` | Structural presence only; complete point-in-time semantics/coverage must be validated. |
| US | range_high | PARTIAL | `artifacts/archive/window_snapshots/us::payload.items.prediction.predicted_session_high` | Structural presence only; complete point-in-time semantics/coverage must be validated. |
| US | range_low | PARTIAL | `artifacts/archive/window_snapshots/us::payload.items.prediction.predicted_session_low` | Structural presence only; complete point-in-time semantics/coverage must be validated. |
| US | schema_version | PARTIAL | `artifacts/archive/window_snapshots/us::payload.items.schema_version` | Available on archive/payload envelope, not on prediction row; explicit envelope adapter required. |
| US | session | PARTIAL | `artifacts/archive/window_snapshots/us::payload.items.prediction.effective_trading_date` | Available on archive/payload envelope, not on prediction row; explicit envelope adapter required. |
| US | strategy | PARTIAL | `artifacts/archive/window_snapshots/us::payload.items.strategies.daily_tactical.strategy_type` | Structural presence only; complete point-in-time semantics/coverage must be validated. |
| US | target_price | MISSING | `artifacts/archive/window_snapshots/us::payload.items.prediction.point_forecast.price` | Structural presence only; complete point-in-time semantics/coverage must be validated. |
| US | technical | PARTIAL | `artifacts/archive/window_snapshots/us::payload.items.technical` | Structural presence only; complete point-in-time semantics/coverage must be validated. |
| US | trend | AMBIGUOUS | `artifacts/archive/window_snapshots/us::payload.items.prediction.one_month_trend` | one_month_trend cannot stand in for session direction. |
| US | window | PARTIAL | `artifacts/archive/window_snapshots/us::payload.items.prediction.window` | Available on archive/payload envelope, not on prediction row; explicit envelope adapter required. |
| US | realized_prices | PARTIAL | `artifacts/archive/window_snapshots/us` | TW archived OHLCV or US quote snapshots are not uniformly certified final session bars. |
| US | subsequent_price_path | MISSING | `artifacts/archive/window_snapshots/us` | Daily prices do not establish within-bar target/stop ordering; US retained history not proven by quote snapshots. |
| US | notification_artifacts | PARTIAL | `artifacts/runtime/us_stock/delivery_provenance` | Latest channel receipts are not full historical daily-report delivery coverage. |
| US | report_artifacts | PARTIAL | `artifacts/archive/window_snapshots/us` | Immutable window revisions exist; no 17:00 predecessor/hash daily-report chain. |
| US | finding_tracking | PARTIAL | `artifacts/runtime/us_stock/evidence_regression_ledger/v1` | CalibrationFinding and evidence ledgers exist but no confirmed issue lifecycle linked to interventions. |
| US | fix_tracking | MISSING | `artifacts/runtime/us_stock/evidence_regression_ledger/v1` | No approved/effective fix ledger with frozen pre-fix cohort and D+3/D+10 outcomes. |
| US | benchmark_cost_basis | MISSING | `artifacts/archive/window_snapshots/us` | Point-in-time benchmark/corporate actions/fees/slippage/exposure assumptions not audited as a joined source. |
| US | trading_calendar | PARTIAL | `artifacts/archive/window_snapshots/us` | US trading_calendar.py provides holidays but not exchange-complete closures/early closes; TW authoritative calendar adapter absent. |

### Normative policies

- **report_timezone**: Asia/Taipei
- **report_time**: 17:00:00
- **report_frequency**: daily calendar-date manifest; market evaluation uses completed trading sessions only
- **calendar**: Explicit versioned exchange session table with aware opens/closes, coverage_through and hash; fail closed without coverage. Existing US holiday helper is not sufficient authority for exceptional/early closes.
- **tw_cutoff**: Only report-date TW session if officially completed by cutoff; on closed days carry prior completed session explicitly, never duplicate observations.
- **us_cutoff**: Latest US session actually completed by cutoff, not the NY wall date; honor America/New_York DST and early closes.
- **rolling**: Last 3 and last 10 distinct eligible market sessions ending at cutoff; the windows overlap by design. Never calendar-day subtraction or repeat stale sessions.
- **predecessor**: Previous calendar report date exact ID and SHA-256 of full immutable envelope excluding content_hash; first report explicit GENESIS. Missing predecessor => PENDING; never silently skip a missing day.
- **revision**: Logical record_id stable; positive revision increments by exactly one; supersedes_hash binds prior version. Append-only exclusive create; same identity/hash idempotent, different content forbidden. Daily predecessor and same-day supersedes are different links.
- **leakage**: For every feature: event as_of <= available_at <= prediction_at. Late corrected features create research revisions, cannot enter frozen prediction. Outcomes observed after session close, available by review cutoff. Missing timezone or available_at blocks ELIGIBLE.
- **hindsight**: Counterfactual hindsight_evidence_refs never enter feature_snapshot/frozen_signal_refs; freeze benchmark, costs, horizon, exposure and tie-break rules before comparison. No execution claims from recommendations.
- **sample_policy**: 3/3 and 10/10 distinct completed session coverage required for their respective aggregates; missing/excluded samples remain in denominators. Calibration requires 3 paired event probabilities for the 3-session window and 10 for the 10-session window per stock/strategy/horizon; disclose count and descriptive-only small-sample status; statistical strength is not implied. Preserve existing 30/100 model-change gates.
- **na_policy**: No eligible implemented fix => improvement N/A and composite PENDING/null. Immature D+3/D+10 => PENDING/null. Any unavailable required component => PENDING/null; never redistribute weights or convert missing to zero.
- **reason_codes**: MISSING_PREDICTION, MISSING_FEATURE_AS_OF, MISSING_AVAILABLE_AT, MISSING_ATR, UNMAPPED_CONFIDENCE, HORIZON_MISMATCH, MISSING_OUTCOME, IMMATURE_D3, IMMATURE_D10, NO_IMPLEMENTED_FIX, INSUFFICIENT_SESSIONS, LOW_MEMORY, BROWSER_BUSY, SOURCE_FALLBACK, STALE_SOURCE, UNKNOWN_CALENDAR, SUSPENDED, CORPORATE_ACTION_UNKNOWN, AMBIGUOUS_INTRABAR_ORDER, MISSING_PREDECESSOR, MISSING_BENCHMARK_COSTS
- **system_vs_user**: System retains source hashes, provenance, calendar/version, findings/fix events, exclusions and all revisions; LINE/Email expose only 3 scores/statuses, sample counts, three next-action categories and report ID/hash/link. No raw features, positions, recipient identifiers or source documents.
- **retention**: Reuse immutable window/formal archives as authorities; hot indexes are rebuildable references. Warm compressed content-addressed evidence, cold large raw/provider data outside Git with checksum/ACL/retention/legal policy approval. Never copy raw into contracts, never delete/move production artifacts in A. Exact retention durations require owner approval in E.
- **automation**: No scoring engine, scheduler, delivery, deployment, model/weight/strategy mutation or production DB integration in A.

<!-- END CANONICAL CONTRACT -->

## Validation and safety

Run `python3 scripts/orchestrator/validate_ai_dev_251a_prediction_regression_contract_v1.py` or `python3 -m unittest discover -s tests -p test_prediction_regression_data_contract.py` offline. Fixtures are explicitly synthetic. Tests validate required fields/types, weights, immutable/idempotent revisions, predecessor ID/hash, as-of/available-at constraints, PENDING semantics, TW/US cutoff calendar coverage and deterministic output. No scoring, clients, production pipeline, browser, notifier, scheduler or DB writer is imported by the contract module. The inventory command requires an explicit root and only reads its documented allowlist; it outputs no rows and is never run by CI against production.

No scheduled task, production DB write, LINE/Email send, Dashboard deployment, Selenium run, artifact deletion/move, or strategy/weight adjustment is included. Large raw data stay outside Git; retention migrations require phase-E review. Local tests may create temporary synthetic fixtures only. Namespace search covered registry, scripts/docs, local/remote branch names, all-state GitHub PR/issue title/body search and completed Git subjects. AI-DEV-251A–E were unused at selection; origin/main was e3bdafdaacbb6472eaca911942b24cbd571cc68b; no second fetch was performed.
