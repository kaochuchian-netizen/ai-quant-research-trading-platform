# Scheduled LINE Runner

This document defines the scheduled pre-open LINE runner boundary.

## Entry Points

- Manual dry-run:
  - `python3 scripts/run_pipeline.py pre_open --dry-run --limit 1`
  - Does not initialize SQLite, update historical CSV, write analysis results, send LINE, or run backtest auto updates.
- Scheduled production runner:
  - `run_stock_analysis.sh`
  - Calls `venv/bin/python scripts/run_pipeline.py pre_open --production-approved`
  - This is the only scheduled shell entrypoint for the production pre-open path.
- Legacy manual entrypoint:
  - `main.py`
  - Remains dry-run only and raises an error without `--dry-run`.

## Safety Boundary

- `main.py` must not become a production runner.
- `scripts/run_pipeline.py pre_open` without `--dry-run` or `--production-approved` must fail.
- `--production-approved` must not be combined with `--dry-run`.
- `--production-approved` is only allowed for the `pre_open` pipeline.
- Do not execute `run_stock_analysis.sh` during validation unless an operator explicitly approves a production notification run.
- Do not execute `python3 scripts/run_pipeline.py pre_open --production-approved` during validation unless an operator explicitly approves a production notification run.

## Validation

Use the read-only validator:

```bash
python3 scripts/orchestrator/validate_scheduled_runner.py --pretty
```

The validator only reads source files. It checks that:

- `run_stock_analysis.sh` calls `scripts/run_pipeline.py pre_open --production-approved`
- `run_stock_analysis.sh` no longer calls `main.py`
- `scripts/run_pipeline.py` exposes `--production-approved`
- `app/pipelines/runner.py` enforces production approval
- `main.py` still keeps the dry-run-only safety guard

This validation does not run the pipeline, send LINE, read secrets, write DB data,
modify cron, or modify production data.
