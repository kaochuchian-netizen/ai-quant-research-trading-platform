# Formal Forecast Snapshot Accumulation Runbook

## What This Does

The snapshot archiver copies the current real formal prediction runtime artifact into a dated archive, creates a read-only actual outcome snapshot from local historical OHLCV, produces a null-safe review snapshot, and refreshes the snapshot index.

## Command

```bash
./venv/bin/python scripts/orchestrator/archive_formal_forecast_daily_snapshot.py --pretty
```

Optional flags:

- `--date YYYY-MM-DD` selects an explicit snapshot date.
- `--dry-run` prints planned paths without writing archive files.
- `--overwrite` replaces same-date files when intentionally re-running the archive.

## Validation

```bash
./venv/bin/python scripts/orchestrator/validate_formal_forecast_snapshot_accumulation_v1.py --pretty
```

Run the Dashboard builder before validation when the Dashboard UI changed:

```bash
./venv/bin/python scripts/orchestrator/build_four_window_dashboard_route_preview.py --pretty
```

## Policies

- Do not create fake historical prediction snapshots.
- Do not archive example artifacts as formal snapshots.
- Do not fill missing actual outcome fields with placeholder numbers.
- Do not calculate fake hit rates.
- Keep next-day review fields null until a next trading-day actual exists.
- Treat sample accumulation as evidence collection, not model validation.

## Safety

This runbook is file-only. It does not write DB state, alter scheduler behavior, send LINE/Email, publish production delivery, execute `python3 main.py`, or trade.
