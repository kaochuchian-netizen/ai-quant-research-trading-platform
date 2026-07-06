#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "artifacts/runtime/formal_prediction_review_runtime_latest.json"
PREDICTION = ROOT / "artifacts/runtime/formal_prediction_runtime_latest.json"
RUNTIME_DATA = ROOT / "templates/four_window_dashboard_runtime_data.example.json"
TAIPEI = ZoneInfo("Asia/Taipei")
NOW = datetime(2026, 7, 6, 15, 1, tzinfo=TAIPEI)
REVIEW_FIELDS = ["actual_high", "actual_low", "actual_close", "direction_result", "high_low_forecast_error", "hit_miss_status", "seven_day_hit_rate", "confidence_calibration", "factor_effectiveness", "error_reasons", "recommendation_for_improvement"]

def stable(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"

def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))

def parse_day(value: str | None) -> date:
    return date.fromisoformat(value) if value else NOW.date()

def stock_universe() -> list[dict[str, Any]]:
    prediction = load_json(PREDICTION)
    if prediction.get("artifact_type") == "formal_prediction_runtime":
        return [{"stock_id": str(s.get("stock_id")), "stock_name": s.get("stock_name")} for s in prediction.get("stocks", []) if isinstance(s, dict) and s.get("stock_id")]
    runtime = load_json(RUNTIME_DATA)
    return [{"stock_id": str(s.get("stock_id")), "stock_name": s.get("stock_name")} for s in runtime.get("stock_universe", []) if isinstance(s, dict) and s.get("stock_id")]

def build_stock(stock: dict[str, Any], review_date: date) -> dict[str, Any]:
    missing = list(REVIEW_FIELDS)
    return {
        "stock_id": str(stock.get("stock_id")),
        "stock_name": stock.get("stock_name"),
        "review_date": review_date.isoformat(),
        "review_window_start": (review_date - timedelta(days=6)).isoformat(),
        "review_window_end": review_date.isoformat(),
        "actual_high": None,
        "actual_low": None,
        "actual_close": None,
        "direction_result": None,
        "high_low_forecast_error": None,
        "hit_miss_status": None,
        "seven_day_hit_rate": None,
        "confidence_calibration": None,
        "factor_effectiveness": None,
        "error_reasons": [],
        "recommendation_for_improvement": None,
        "source_evidence": [{"source_type": "formal_prediction_runtime", "status": "available" if PREDICTION.exists() else "missing"}, {"source_type": "actual_outcome", "status": "insufficient_data"}, {"source_type": "historical_price", "status": "not_compared_in_safe_stub"}],
        "data_quality": {"completeness": "insufficient_data", "freshness": "missing_actual_outcome", "confidence_basis": "no comparable prediction and actual outcome pair", "blocking_missing_fields": missing},
        "missing_fields": missing,
        "insufficient_data_reasons": ["no_comparable_formal_prediction_and_actual_outcome", "no_safe_actual_outcome_artifact_available_for_review", "review_metrics_must_not_be_fabricated"],
        "created_at": NOW.isoformat(),
    }

def build(review_date: date) -> dict[str, Any]:
    stocks = [build_stock(s, review_date) for s in stock_universe()]
    return {"schema_version": "formal_prediction_review_runtime_v1", "artifact_type": "formal_prediction_review_runtime", "generated_at": NOW.isoformat(), "runtime_window": "prediction_review_1500", "market": "TW", "source_mode": "safe_local_read_only_existing_artifacts", "is_example": False, "producer_name": "build_formal_prediction_review_runtime_artifact.py", "producer_version": "formal_prediction_review_runtime_v1", "review_window_days": 7, "review_date": review_date.isoformat(), "stock_universe_count": len(stocks), "stocks": stocks, "safety": {"external_api_called": False, "secrets_read": False, "db_write": False, "notification_sent": False, "production_pipeline_executed": False, "python_main_executed": False, "trading_or_order_executed": False, "fabricated_review_metrics": False}}

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    ap.add_argument("--date")
    ap.add_argument("--pretty", action="store_true")
    args = ap.parse_args()
    data = build(parse_day(args.date))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(stable(data), encoding="utf-8")
    print(stable({"ok": True, "output": str(args.output), "artifact_type": data["artifact_type"], "stock_universe_count": data["stock_universe_count"], "review_metrics_fabricated": False}), end="")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
