#!/usr/bin/env python3
"""Explicit read-only allowlist inventory; stdout contains aggregates, never rows."""
from __future__ import annotations

import argparse
import collections
import csv
import json
from pathlib import Path

FIELDS = {
    "TW": {
        "prediction_id": "prediction_snapshot_v2.prediction_identity",
        "generated_at": "prediction_snapshot_v2.generated_at",
        "session": "prediction_snapshot_v2.effective_trading_date",
        "window": "prediction_snapshot_v2.window",
        "strategy": "strategies.daily_tactical.strategy_type",
        "trend": "prediction_snapshot_v2.direction_forecast",
        "target_price": "prediction_snapshot_v2.point_forecast.price",
        "range_low": "prediction_snapshot_v2.range_forecast.low",
        "range_high": "prediction_snapshot_v2.range_forecast.high",
        "confidence": "prediction_snapshot_v2.confidence",
        "technical": "technical_data", "news": "news_evidence", "chip": "chip_summary",
        "market_features": "market_context", "fallback": "technical_data.history_fallback.used",
        "missingness": "missing_fields", "latency": "latency_ms",
        "feature_as_of": "prediction_snapshot_v2.no_lookahead.last_input_market_timestamp",
        "feature_available_at": "feature_available_at", "atr_at_prediction": "atr_at_prediction",
        "git_sha": "git_sha", "model_version": "prediction_snapshot_v2.method_version",
        "schema_version": "prediction_snapshot_v2.schema_version",
    },
    "US": {
        "prediction_id": "prediction.prediction_identity", "generated_at": "strategies.daily_tactical.generated_at",
        "session": "prediction.effective_trading_date", "window": "prediction.window",
        "strategy": "strategies.daily_tactical.strategy_type", "trend": "prediction.one_month_trend",
        "target_price": "prediction.point_forecast.price", "range_low": "prediction.predicted_session_low",
        "range_high": "prediction.predicted_session_high", "confidence": "strategies.daily_tactical.confidence",
        "technical": "technical", "news": "news", "chip": "chip_summary",
        "market_features": "market_context_ref", "fallback": "fetch_error", "missingness": "prediction.missing_fields",
        "latency": "latency_ms", "feature_as_of": "source_timestamp",
        "feature_available_at": "feature_available_at", "atr_at_prediction": "atr_at_prediction",
        "git_sha": "git_sha", "model_version": "prediction.model_version", "schema_version": "schema_version",
    },
}


def at(row, key):
    for part in key.split("."):
        if not isinstance(row, dict) or part not in row:
            return None
        row = row[part]
    return row


def missing(value):
    # Empty explicit missingness arrays and false fallback flags are present.
    return value is None or value == "" or (isinstance(value, dict) and not value)


def read_json(path, root):
    if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("inventory_symlink_or_escape")
    if path.stat().st_size > 20_000_000:
        raise ValueError("inventory_file_too_large")
    return json.loads(path.read_text(encoding="utf-8"))


def inventory(root: Path):
    result = {"schema_version": "prediction_regression_inventory_v1", "aggregate_only": True,
              "scope": "allowlisted on-disk artifacts; not a claim of complete production history",
              "production_mutation": "NONE", "families": {}}
    for market in ("TW", "US"):
        relative = f"artifacts/archive/window_snapshots/{market.lower()}"
        files = sorted((root / relative).rglob("*.json"))
        counts = collections.Counter(); dates = []; rows = 0; malformed = 0; admitted = 0
        for path in files:
            try:
                j = read_json(path, root)
                if j.get("effective_trading_date"):
                    dates.append(str(j["effective_trading_date"])[:10])
                admitted += j.get("admitted") is True
                payload = j.get("payload") or {}
                selected = payload.get("structured_pre_open_cards", []) if market == "TW" else payload.get("items", [])
                for row in selected:
                    if not isinstance(row, dict): continue
                    rows += 1
                    counts.update(k for k, v in FIELDS[market].items() if missing(at(row, v)))
            except (ValueError, OSError, TypeError):
                malformed += 1
        result["families"][market + "_window_snapshots"] = {
            "source": relative, "files": len(files), "admitted_files": admitted, "malformed_files": malformed,
            "row_selection": "payload.structured_pre_open_cards" if market == "TW" else "payload.items",
            "rows": rows, "date_range": [min(dates), max(dates)] if dates else None,
            "fields": {k: {"path": v, "missing_count": counts[k],
                            "denominator": rows, "missing_rate": round(counts[k] / rows, 6) if rows else None}
                       for k, v in FIELDS[market].items()},
        }
    for family, relative in {
        "formal_prediction": "artifacts/archive/formal_forecast_snapshots/prediction",
        "formal_outcome": "artifacts/archive/formal_forecast_snapshots/actual_outcome",
        "formal_review": "artifacts/archive/formal_forecast_snapshots/review",
        "delivery_receipts": "artifacts/runtime/delivery_receipts",
        "delivery_provenance_tw": "artifacts/runtime/delivery_provenance",
        "delivery_provenance_us": "artifacts/runtime/us_stock/delivery_provenance",
        "evidence_tw": "artifacts/runtime/tw/evidence_regression_ledger/v1",
        "evidence_us": "artifacts/runtime/us_stock/evidence_regression_ledger/v1",
    }.items():
        files = sorted((root / relative).rglob("*.json")); dates = []; rows = 0; malformed = 0
        counts = collections.Counter(); fields = ["generated_at", "schema_version"]
        if family == "formal_outcome": fields = ["actual_open", "actual_high", "actual_low", "actual_close", "actual_volume"]
        elif family == "formal_prediction": fields = ["confidence_score", "same_day_high_prediction", "same_day_low_prediction", "model_version"]
        for path in files:
            try:
                j = read_json(path, root)
                d = j.get("outcome_date") or j.get("prediction_snapshot_date") or j.get("trading_date") or j.get("generated_at")
                if d: dates.append(str(d)[:10])
                selected = j.get("stocks", [j])
                for row in selected:
                    rows += 1; counts.update(k for k in fields if missing(row.get(k)))
            except (ValueError, OSError, TypeError): malformed += 1
        result["families"][family] = {"source": relative, "files": len(files), "rows": rows,
            "malformed_files": malformed, "date_range": [min(dates), max(dates)] if dates else None,
            "fields": {k: {"missing_count": counts[k], "denominator": rows,
                            "missing_rate": round(counts[k] / rows, 6) if rows else None} for k in fields}}
    files = sorted((root / "data/historical").glob("*_daily.csv")); counts = collections.Counter(); dates = []; rows = 0
    for path in files:
        if path.is_symlink(): raise ValueError("inventory_symlink")
        with path.open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                rows += 1
                if row.get("date"): dates.append(row["date"][:10])
                counts.update(k for k in ("date", "open", "high", "low", "close", "volume") if missing(row.get(k)))
    result["families"]["historical_ohlcv"] = {"source": "data/historical/*_daily.csv", "files": len(files),
        "rows": rows, "date_range": [min(dates), max(dates)] if dates else None,
        "fields": {k: {"missing_count": counts[k], "denominator": rows,
                       "missing_rate": round(counts[k] / rows, 6) if rows else None}
                   for k in ("date", "open", "high", "low", "close", "volume")}}
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(inventory(args.root), sort_keys=True, indent=2))
