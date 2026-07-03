# Real Historical Artifact Ingestion Runbook

## How to scan existing artifacts safely
Use explicit paths and dry-run stdout output:
```bash
./venv/bin/python scripts/orchestrator/ingest_real_historical_artifacts.py --pretty --scan-path <path>
```
Do not run production pipelines to create missing artifacts.

## How to run dry-run ingestion
Default mode is deterministic offline sample mode:
```bash
./venv/bin/python scripts/orchestrator/ingest_real_historical_artifacts.py --pretty
```
For a prepared input file:
```bash
./venv/bin/python scripts/orchestrator/ingest_real_historical_artifacts.py --pretty --input templates/real_historical_artifact_input.example.json
```

## How to identify malformed / stale / duplicate artifacts
Check `completeness_summary.status_counts`, `by_artifact_type`, and `deduplication_summary`. Malformed JSON is represented as `artifact_status=malformed`; stale and duplicate records are counted instead of failing ingestion.

## How to verify sample_mode vs real_history mode
Check top-level `sample_mode` and each record `source_kind`. Offline examples use `source_kind=offline_sample`. Real scans should have scan/runtime source kinds and must still be treated as advisory until enough records exist.

## How to generate rolling evaluation artifact
```bash
./venv/bin/python scripts/orchestrator/build_rolling_evaluation_artifact.py --pretty
./venv/bin/python scripts/orchestrator/build_rolling_evaluation_artifact.py --pretty --history-store <store.json>
```

## How to interpret insufficient sample
Below 5 usable records is insufficient. From 5 to 19 is unstable. Do not claim calibration quality, factor effectiveness, or strategy readiness from sparse history.

## Why not to mutate production strategy
This release only builds ingestion and evaluation foundations. It does not change confidence, forecast weights, rating/action rules, scheduler, delivery, dashboard publish, or trading behavior.

## How to prepare for future controlled retention activation
Confirm validators pass, examples remain deterministic, `production_publish_allowed=false`, and output paths are explicit. AI-DEV-130 should activate controlled shadow-mode retention without changing delivery or strategy behavior.
