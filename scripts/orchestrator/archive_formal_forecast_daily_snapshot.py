#!/usr/bin/env python3
"""Archive formal forecast daily prediction / actual / review snapshots.

AI-DEV-155 intentionally creates file-based archive artifacts only. It does not
write DB state, run the production pipeline, send notifications, or mutate the
forecast formula.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import asdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.forecast.formal_forecast_value_engine import load_historical_rows, normalize_stock_id, stable_json

PREDICTION_RUNTIME = ROOT / "artifacts/runtime/formal_prediction_runtime_latest.json"
ARCHIVE_ROOT = ROOT / "artifacts/archive/formal_forecast_snapshots"
PREDICTION_DIR = ARCHIVE_ROOT / "prediction"
ACTUAL_DIR = ARCHIVE_ROOT / "actual_outcome"
REVIEW_DIR = ARCHIVE_ROOT / "review"
INDEX_DIR = ARCHIVE_ROOT / "index"
INDEX_JSON = INDEX_DIR / "formal_forecast_snapshot_index_latest.json"
INDEX_MD = INDEX_DIR / "formal_forecast_snapshot_index_latest.md"
MODEL_VERSION = "deterministic_baseline_v1"
SCHEMA_VERSION = "formal_forecast_snapshot_accumulation_v1"


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any], *, overwrite: bool) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        return "exists_skipped"
    path.write_text(stable_json(payload), encoding="utf-8")
    return "written"


def write_text(path: Path, text: str, *, overwrite: bool = True) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        return "exists_skipped"
    path.write_text(text, encoding="utf-8")
    return "written"


def infer_snapshot_date(prediction: dict[str, Any], override: str | None) -> date:
    if override:
        return date.fromisoformat(override)
    for stock in prediction.get("stocks", []):
        if isinstance(stock, dict) and stock.get("prediction_date"):
            return date.fromisoformat(str(stock["prediction_date"]))
    cutoff = str(prediction.get("data_cutoff_at") or "")
    if len(cutoff) >= 10:
        return date.fromisoformat(cutoff[:10])
    return date.today()


def validate_prediction_runtime(prediction: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if prediction.get("artifact_type") != "formal_prediction_runtime":
        errors.append("prediction artifact_type must be formal_prediction_runtime")
    if prediction.get("is_example") is not False:
        errors.append("prediction artifact must be formal runtime artifact, not example")
    if prediction.get("model_version") != MODEL_VERSION:
        errors.append("top-level model_version must be deterministic_baseline_v1")
    if not isinstance(prediction.get("stocks"), list) or not prediction.get("stocks"):
        errors.append("prediction stocks must be non-empty")
    for stock in prediction.get("stocks", []):
        if not isinstance(stock, dict):
            errors.append("prediction stock entry must be object")
            continue
        if stock.get("model_version") != MODEL_VERSION:
            errors.append(f"{stock.get('stock_id')}: stock model_version must be deterministic_baseline_v1")
        method = stock.get("method_metadata") if isinstance(stock.get("method_metadata"), dict) else {}
        if method.get("method") != MODEL_VERSION:
            errors.append(f"{stock.get('stock_id')}: method_metadata.method must be deterministic_baseline_v1")
    return errors


def prediction_snapshot(prediction: dict[str, Any], snapshot_day: date) -> dict[str, Any]:
    out = json.loads(json.dumps(prediction, ensure_ascii=False))
    out["snapshot_metadata"] = {
        "schema_version": SCHEMA_VERSION,
        "snapshot_type": "prediction",
        "snapshot_date": snapshot_day.isoformat(),
        "source_runtime_artifact": "artifacts/runtime/formal_prediction_runtime_latest.json",
        "is_fake_backfilled_forecast": False,
        "overwrite_policy": "skip_existing_unless_overwrite_flag",
        "db_write": False,
        "notification_sent": False,
        "production_pipeline_executed": False,
    }
    return out


def _row_dict(row: Any | None) -> dict[str, Any]:
    if row is None:
        return {"open": None, "high": None, "low": None, "close": None, "volume": None}
    return {
        "open": row.open,
        "high": row.high,
        "low": row.low,
        "close": row.close,
        "volume": row.volume,
    }


def actual_outcome_snapshot(prediction: dict[str, Any], snapshot_day: date, generated_at: str) -> dict[str, Any]:
    stocks: list[dict[str, Any]] = []
    any_backfilled = False
    for stock in prediction.get("stocks", []):
        stock_id = str(stock.get("stock_id"))
        rows = load_historical_rows(stock_id)
        row = next((r for r in rows if r.day == snapshot_day), None)
        values = _row_dict(row)
        missing_fields: list[str] = []
        reasons: list[str] = []
        if row is None:
            missing_fields = ["actual_open", "actual_high", "actual_low", "actual_close", "actual_volume"]
            reasons = ["historical_ohlcv_outcome_date_unavailable"]
        else:
            any_backfilled = True
        stocks.append({
            "schema_version": "formal_actual_outcome_stock_v1",
            "stock_id": stock_id,
            "stock_name": stock.get("stock_name"),
            "outcome_date": snapshot_day.isoformat(),
            "actual_open": values["open"],
            "actual_high": values["high"],
            "actual_low": values["low"],
            "actual_close": values["close"],
            "actual_volume": values["volume"],
            "source_evidence": [{
                "source_type": "historical_ohlcv_csv",
                "path": f"data/historical/{normalize_stock_id(stock_id)}_daily.csv",
                "read_mode": "read_only",
                "status": "available" if row else "missing",
                "row_count": len(rows),
            }],
            "data_quality": {
                "completeness": "actual_available" if row else "insufficient_data",
                "freshness": "historical_ohlcv_archive",
                "blocking_missing_fields": missing_fields,
            },
            "missing_fields": missing_fields,
            "insufficient_data_reasons": reasons,
            "created_at": generated_at,
        })
    return {
        "schema_version": "formal_actual_outcome_snapshot_v1",
        "artifact_type": "formal_actual_outcome_snapshot",
        "generated_at": generated_at,
        "outcome_date": snapshot_day.isoformat(),
        "market": prediction.get("market", "TW"),
        "source_mode": "read_only_historical_ohlcv",
        "source_evidence": ["data/historical/*_daily.csv"],
        "is_backfilled_actual": bool(any_backfilled),
        "db_write": False,
        "external_api_called": False,
        "stocks": stocks,
    }


def _next_row_after(rows: list[Any], day: date) -> Any | None:
    for row in rows:
        if row.day > day:
            return row
    return None


def _interval_result(actual_high: float | None, actual_low: float | None, predicted_high: Any, predicted_low: Any) -> str | None:
    if actual_high is None or actual_low is None or not isinstance(predicted_high, (int, float)) or not isinstance(predicted_low, (int, float)):
        return None
    high_ok = actual_high <= float(predicted_high)
    low_ok = actual_low >= float(predicted_low)
    return "hit" if high_ok and low_ok else "partial_hit" if high_ok or low_ok else "miss"


def _error(actual: float | None, predicted: Any) -> tuple[float | None, float | None]:
    if actual is None or not isinstance(predicted, (int, float)) or float(predicted) <= 0:
        return None, None
    abs_error = round(actual - float(predicted), 4)
    pct_error = round(abs_error / float(predicted), 6)
    return abs_error, pct_error


def review_snapshot(prediction: dict[str, Any], actual_snapshot: dict[str, Any], snapshot_day: date, generated_at: str) -> dict[str, Any]:
    actual_by_id = {str(s.get("stock_id")): s for s in actual_snapshot.get("stocks", []) if isinstance(s, dict)}
    stocks: list[dict[str, Any]] = []
    for pred in prediction.get("stocks", []):
        stock_id = str(pred.get("stock_id"))
        actual = actual_by_id.get(stock_id, {})
        rows = load_historical_rows(stock_id)
        same_day_result = _interval_result(actual.get("actual_high"), actual.get("actual_low"), pred.get("same_day_high_prediction"), pred.get("same_day_low_prediction"))
        high_abs, high_pct = _error(actual.get("actual_high"), pred.get("same_day_high_prediction"))
        low_abs, low_pct = _error(actual.get("actual_low"), pred.get("same_day_low_prediction"))
        next_row = _next_row_after(rows, snapshot_day)
        next_result = _interval_result(next_row.high if next_row else None, next_row.low if next_row else None, pred.get("next_day_high_prediction"), pred.get("next_day_low_prediction"))
        reasons: list[str] = []
        if same_day_result is None:
            reasons.append("same_day_prediction_or_actual_unavailable")
        if next_result is None:
            reasons.append("next_day_actual_outcome_unavailable")
        prev = None
        for idx, row in enumerate(rows):
            if row.day == snapshot_day and idx > 0:
                prev = rows[idx - 1]
                break
        predicted_direction = pred.get("one_month_trend")
        actual_direction = None
        direction_result = "insufficient_data"
        if actual.get("actual_close") is not None and prev and predicted_direction in {"bullish", "bearish", "neutral"}:
            actual_direction = "bullish" if float(actual["actual_close"]) > prev.close else "bearish" if float(actual["actual_close"]) < prev.close else "neutral"
            direction_result = "neutral" if predicted_direction == "neutral" or actual_direction == "neutral" else "correct" if predicted_direction == actual_direction else "incorrect"
        else:
            reasons.append("direction_actual_or_prediction_missing")
        stocks.append({
            "schema_version": "formal_prediction_review_snapshot_stock_v1",
            "stock_id": stock_id,
            "stock_name": pred.get("stock_name"),
            "prediction_snapshot_date": snapshot_day.isoformat(),
            "actual_outcome_date": snapshot_day.isoformat(),
            "method_version": pred.get("model_version"),
            "same_day_interval_result": same_day_result,
            "next_day_interval_result": next_result,
            "high_error_abs": high_abs,
            "low_error_abs": low_abs,
            "high_error_pct": high_pct,
            "low_error_pct": low_pct,
            "direction_result": direction_result,
            "predicted_direction": predicted_direction,
            "actual_direction": actual_direction,
            "hit_miss_status": same_day_result or "insufficient_data",
            "insufficient_data_reasons": sorted(set(reasons)),
            "created_at": generated_at,
        })
    return {
        "schema_version": "formal_prediction_review_snapshot_v1",
        "artifact_type": "formal_prediction_review_snapshot",
        "generated_at": generated_at,
        "prediction_snapshot_date": snapshot_day.isoformat(),
        "actual_outcome_date": snapshot_day.isoformat(),
        "method_version": MODEL_VERSION,
        "market": prediction.get("market", "TW"),
        "review_mode": "null_safe_file_archive_evaluation",
        "fake_hit_rate_generated": False,
        "db_write": False,
        "external_api_called": False,
        "stocks": stocks,
    }


def _json_files(path: Path) -> list[Path]:
    return sorted(path.glob("*.json")) if path.exists() else []


def _load_many(paths: list[Path]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for path in paths:
        try:
            data = read_json(path)
        except Exception:
            continue
        data["_archive_path"] = str(path.relative_to(ROOT))
        out.append(data)
    return out


def build_index(generated_at: str) -> dict[str, Any]:
    pred_files = _json_files(PREDICTION_DIR)
    actual_files = _json_files(ACTUAL_DIR)
    review_files = _json_files(REVIEW_DIR)
    predictions = _load_many(pred_files)
    actuals = _load_many(actual_files)
    reviews = _load_many(review_files)
    eligible_same = 0
    eligible_next = 0
    method_versions: set[str] = set()
    snapshot_rows: list[dict[str, Any]] = []
    for pred in predictions:
        snap = pred.get("snapshot_metadata") if isinstance(pred.get("snapshot_metadata"), dict) else {}
        date_value = str(snap.get("snapshot_date") or "")
        method_versions.add(str(pred.get("model_version") or "unknown"))
        snapshot_rows.append({
            "snapshot_date": date_value,
            "prediction_snapshot_path": pred.get("_archive_path"),
            "actual_outcome_snapshot_path": None,
            "review_snapshot_path": None,
            "method_version": pred.get("model_version"),
        })
    for row in snapshot_rows:
        day = row["snapshot_date"]
        for actual in actuals:
            if actual.get("outcome_date") == day:
                row["actual_outcome_snapshot_path"] = actual.get("_archive_path")
        for review in reviews:
            if review.get("prediction_snapshot_date") == day:
                row["review_snapshot_path"] = review.get("_archive_path")
    for review in reviews:
        for stock in review.get("stocks", []):
            if not isinstance(stock, dict):
                continue
            if stock.get("same_day_interval_result") in {"hit", "partial_hit", "miss"}:
                eligible_same += 1
            if stock.get("next_day_interval_result") in {"hit", "partial_hit", "miss"}:
                eligible_next += 1
    current = eligible_same
    if current >= 100:
        gate = "ready_for_formula_change"
    elif current >= 30:
        gate = "ready_for_shadow_tuning"
    else:
        gate = "blocked_insufficient_sample"
    latest_prediction = max((r.get("snapshot_date") for r in snapshot_rows if r.get("prediction_snapshot_path")), default=None)
    latest_actual = max((a.get("outcome_date") for a in actuals if a.get("outcome_date")), default=None)
    latest_review = max((r.get("prediction_snapshot_date") for r in reviews if r.get("prediction_snapshot_date")), default=None)
    missing_dates = [r["snapshot_date"] for r in snapshot_rows if not r.get("actual_outcome_snapshot_path") or not r.get("review_snapshot_path")]
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_type": "formal_forecast_snapshot_index",
        "generated_at": generated_at,
        "snapshot_count": len(set([*pred_files, *actual_files, *review_files])),
        "prediction_snapshot_count": len(pred_files),
        "actual_outcome_snapshot_count": len(actual_files),
        "review_snapshot_count": len(review_files),
        "eligible_same_day_sample_count": eligible_same,
        "eligible_next_day_sample_count": eligible_next,
        "method_versions": sorted(method_versions),
        "latest_prediction_snapshot_date": latest_prediction,
        "latest_actual_outcome_snapshot_date": latest_actual,
        "latest_review_snapshot_date": latest_review,
        "calibration_gate_progress": {
            "current_eligible_sample_count": current,
            "ready_for_shadow_tuning_threshold": 30,
            "ready_for_formula_change_threshold": 100,
            "current_gate_status": gate,
            "remaining_samples_to_shadow_tuning": max(30 - current, 0),
            "remaining_samples_to_formula_change": max(100 - current, 0),
        },
        "missing_dates": missing_dates,
        "limitations": [
            "prediction snapshots are archived only from real formal runtime artifacts; fake historical prediction backfill is forbidden",
            "actual outcome snapshots may use read-only historical OHLCV and must be explicitly marked",
            "next-day outcomes remain insufficient_data until a later trading-day actual is available",
            "snapshot count is sample accumulation, not model performance",
        ],
        "snapshots": snapshot_rows,
        "safety_policy": {
            "db_write": False,
            "scheduler_modified": False,
            "external_notification_sent": False,
            "production_pipeline_executed": False,
            "python_main_executed": False,
            "trading_or_order_executed": False,
            "deterministic_baseline_formula_mutated": False,
            "production_rating_action_confidence_weight_mutated": False,
        },
    }


def markdown_index(index: dict[str, Any]) -> str:
    gate = index["calibration_gate_progress"]
    rows = [
        "# Formal Forecast Snapshot Index",
        "",
        f"Generated at: {index['generated_at']}",
        "",
        "## Counts",
        f"- Prediction snapshots: {index['prediction_snapshot_count']}",
        f"- Actual outcome snapshots: {index['actual_outcome_snapshot_count']}",
        f"- Review snapshots: {index['review_snapshot_count']}",
        f"- Eligible same-day samples: {index['eligible_same_day_sample_count']}",
        f"- Eligible next-day samples: {index['eligible_next_day_sample_count']}",
        "",
        "## Calibration Gate Progress",
        f"- Current gate: {gate['current_gate_status']}",
        f"- Shadow tuning threshold: {gate['ready_for_shadow_tuning_threshold']}",
        f"- Formula change threshold: {gate['ready_for_formula_change_threshold']}",
        f"- Remaining to shadow tuning: {gate['remaining_samples_to_shadow_tuning']}",
        f"- Remaining to formula change: {gate['remaining_samples_to_formula_change']}",
        "",
        "## Policy",
        "- No fake historical prediction snapshots.",
        "- Actual outcomes may be sourced from read-only historical OHLCV only when marked.",
        "- Snapshot accumulation is not model performance.",
    ]
    return "\n".join(rows) + "\n"


def run(args: argparse.Namespace) -> dict[str, Any]:
    generated_at = now_utc()
    prediction = read_json(PREDICTION_RUNTIME)
    errors = validate_prediction_runtime(prediction)
    if errors:
        return {"ok": False, "errors": errors}
    snapshot_day = infer_snapshot_date(prediction, args.date)
    pred_path = PREDICTION_DIR / f"formal_prediction_runtime_{snapshot_day.isoformat()}.json"
    actual_path = ACTUAL_DIR / f"formal_actual_outcome_{snapshot_day.isoformat()}.json"
    review_path = REVIEW_DIR / f"formal_prediction_review_{snapshot_day.isoformat()}.json"
    pred_payload = prediction_snapshot(prediction, snapshot_day)
    actual_payload = actual_outcome_snapshot(prediction, snapshot_day, generated_at)
    review_payload = review_snapshot(prediction, actual_payload, snapshot_day, generated_at)
    planned_paths = [pred_path, actual_path, review_path, INDEX_JSON, INDEX_MD]
    if args.dry_run:
        return {
            "ok": True,
            "dry_run": True,
            "snapshot_date": snapshot_day.isoformat(),
            "planned_paths": [str(p.relative_to(ROOT)) for p in planned_paths],
            "side_effects": {"files_written": False, "db_write": False, "notification_sent": False, "production_pipeline_executed": False},
        }
    statuses = {
        str(pred_path.relative_to(ROOT)): write_json(pred_path, pred_payload, overwrite=args.overwrite),
        str(actual_path.relative_to(ROOT)): write_json(actual_path, actual_payload, overwrite=args.overwrite),
        str(review_path.relative_to(ROOT)): write_json(review_path, review_payload, overwrite=args.overwrite),
    }
    index = build_index(generated_at)
    statuses[str(INDEX_JSON.relative_to(ROOT))] = write_json(INDEX_JSON, index, overwrite=True)
    statuses[str(INDEX_MD.relative_to(ROOT))] = write_text(INDEX_MD, markdown_index(index), overwrite=True)
    return {
        "ok": True,
        "dry_run": False,
        "snapshot_date": snapshot_day.isoformat(),
        "written_status": statuses,
        "index_path": str(INDEX_JSON.relative_to(ROOT)),
        "index_markdown_path": str(INDEX_MD.relative_to(ROOT)),
        "prediction_snapshot_count": index["prediction_snapshot_count"],
        "actual_outcome_snapshot_count": index["actual_outcome_snapshot_count"],
        "review_snapshot_count": index["review_snapshot_count"],
        "eligible_same_day_sample_count": index["eligible_same_day_sample_count"],
        "eligible_next_day_sample_count": index["eligible_next_day_sample_count"],
        "current_gate_status": index["calibration_gate_progress"]["current_gate_status"],
        "side_effects": {"db_write": False, "notification_sent": False, "production_pipeline_executed": False, "python_main_executed": False, "trading_or_order_executed": False},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", help="Snapshot date in YYYY-MM-DD. Defaults to formal prediction artifact prediction_date.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing same-date snapshot files.")
    parser.add_argument("--dry-run", action="store_true", help="Print planned snapshot writes without writing files.")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    result = run(args)
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
