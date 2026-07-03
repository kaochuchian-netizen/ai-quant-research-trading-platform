# AI-DEV-129 Real Historical Artifact Ingestion & Rolling Evaluation V1

## 1. Purpose
AI-DEV-129 establishes an offline-first foundation for ingesting existing real artifacts, normalizing them into a deterministic historical store, and building rolling evaluation summaries. It prepares calibration, factor effectiveness, and dashboard intelligence to use real history instead of deterministic samples.

## 2. Scope
This release adds artifact scanning, classification, normalization, a historical store contract, deduplication, completeness reporting, rolling windows, rolling evaluation, rolling calibration readiness, rolling factor readiness, dashboard-ready advisory summaries, examples, validation, and runbook documentation.

## 3. Non-goals
- No production trading
- No simulation order
- No production order
- No scheduler mutation
- No LINE/Email delivery
- No production DB write
- No production confidence mutation
- No production forecast weight mutation
- No production rating/action mutation
- No production dashboard publish
- No write to /var/www/stock-ai-dashboard
- No automatic strategy change
- No automatic weight update
- No production artifact retention activation yet
- No backtesting.py runtime execution

## 4. Architecture
The deterministic flow is: scanner -> classifier -> normalizer -> historical store -> deduplication -> completeness -> rolling windows -> rolling evaluation, calibration readiness, factor readiness, and dashboard-ready summary.

## 5. Historical artifact source types
Supported families include approved delivery, prediction snapshots, actual outcomes, evaluations, source coverage, source evidence, feature attribution, stock explanations, confidence calibration, factor recommendation, dashboard intelligence, incident diagnostics, content quality diagnostics, and unknown artifacts.

## 6. Historical store schema
`HistoricalArtifactRecord` stores run identity, artifact type/status, source path/kind, generated time, scheduler window, pipeline type, stock identity, prediction target, content state, fingerprint, dedupe key, lineage, summary, diagnostics, and `advisory_only`. `HistoricalArtifactStore` stores records, indexes, completeness summary, deduplication summary, and safety summary.

## 7. Ingestion modes
`ingest_real_historical_artifacts.py` defaults to dry-run offline sample mode and prints JSON to stdout. It can also read an explicit input file, scan explicit paths, or write to an explicit output path. It refuses `/var/www/stock-ai-dashboard` and never writes production DB.

## 8. Artifact scanner
The scanner is read-only and best-effort. It handles JSON, JSONL, Markdown, and text, classifies malformed JSON without crashing, marks unknown artifacts unsupported, and ignores oversized files.

## 9. Artifact normalizer
The normalizer maps known artifact structures into the store contract. Missing fields remain null or unavailable. Offline samples are clearly marked `source_kind=offline_sample` and `sample_mode=true`.

## 10. Deduplication / idempotency
Deduplication uses stable fingerprints and logical keys from run id, scheduler window, pipeline type, stock id, prediction target, artifact type, and generated time. Re-ingesting the same artifact counts duplicates without retaining duplicate logical records.

## 11. Completeness report
Completeness is summarized by scheduler window, stock id, artifact type, and artifact status. It identifies missing, pending, stale, duplicate, malformed, partial, and insufficient data instead of pretending quality is complete.

## 12. Rolling window policy
Rolling windows include `last_7_records`, `last_20_records`, `last_60_records`, `last_7_trading_days`, `last_20_trading_days`, and `all_available`. Usable records below 5 are insufficient; 5-19 are unstable; 20+ are usable; 60+ provide stronger confidence.

## 13. Rolling evaluation
Rolling evaluation reports direction hit rates, close direction hit rates, average returns, high/low error, pending outcomes, missing outcomes, insufficient data, and summary readiness. Offline samples are demo data only.

## 14. Rolling calibration readiness
Calibration readiness reports usable confidence records, bucket readiness, weighted ECE if available, and status. It does not claim over-confidence or under-confidence when real sample size is insufficient.

## 15. Rolling factor effectiveness readiness
Factor readiness summarizes factor/source group availability and recommendation readiness. It always keeps `production_mutation_allowed=false` and recommends data collection when history is sparse.

## 16. Dashboard-ready real-history summary
The dashboard-ready summary is advisory only and includes real-history availability, sample mode, rolling window names, key metrics, data gaps, pending reviews, diagnostics, operator actions, `advisory_only=true`, and `production_publish_allowed=false`.

## 17. Safety boundary
Validation and builders do not run production pipelines, send LINE/Email, publish dashboards, write production DB, read secrets, trade, run `python3 main.py`, start n8n/Dify, or run backtesting.py.

## 18. Validation commands
```bash
./venv/bin/python -m py_compile \
  app/history/schemas.py \
  app/history/artifact_scanner.py \
  app/history/artifact_classifier.py \
  app/history/artifact_normalizer.py \
  app/history/historical_store.py \
  app/history/deduplication.py \
  app/history/completeness.py \
  app/rolling/schemas.py \
  app/rolling/rolling_windows.py \
  app/rolling/rolling_evaluation.py \
  app/rolling/rolling_calibration.py \
  app/rolling/rolling_factor_effectiveness.py \
  app/rolling/rolling_dashboard_summary.py \
  scripts/orchestrator/ingest_real_historical_artifacts.py \
  scripts/orchestrator/build_rolling_evaluation_artifact.py \
  scripts/orchestrator/validate_real_historical_ingestion_v1.py
./venv/bin/python scripts/orchestrator/validate_real_historical_ingestion_v1.py --pretty
./venv/bin/python scripts/orchestrator/ingest_real_historical_artifacts.py --pretty
./venv/bin/python scripts/orchestrator/build_rolling_evaluation_artifact.py --pretty
./venv/bin/python scripts/orchestrator/validate_ai_branch.py --base main --head HEAD --pretty
```

## 19. How this connects
- AI-DEV-122 Prediction Data Foundation supplies prediction, outcome, evaluation, and source coverage artifacts.
- AI-DEV-123 Multi-Source Connector & Explainability supplies evidence, attribution, and explanation artifacts.
- AI-DEV-124 Confidence Calibration can consume rolling readiness before calibration claims.
- AI-DEV-125 Factor Effectiveness & Adaptive Recommendation can use real history without mutating weights.
- AI-DEV-126 Dashboard Intelligence can later display real-history summaries.
- AI-DEV-127 Production Pipeline Guard diagnostics become historical diagnostic records.
- AI-DEV-128 Multi-window Report Content Contract produces sanitized artifacts and content diagnostics.
- Future backtesting.py strategy research can use exported offline stores only.
- Future controlled retention activation is the expected AI-DEV-130 follow-up.
