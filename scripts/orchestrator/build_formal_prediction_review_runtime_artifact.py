#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, sys
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from analysis.forecast.formal_forecast_value_engine import evaluate_prediction_stock, stable_json

DEFAULT_OUTPUT = ROOT / "artifacts/runtime/formal_prediction_review_runtime_latest.json"
PREDICTION = ROOT / "artifacts/runtime/formal_prediction_runtime_latest.json"
RUNTIME_DATA = ROOT / "templates/four_window_dashboard_runtime_data.example.json"
TAIPEI = ZoneInfo("Asia/Taipei")
NOW = datetime(2026, 7, 6, 15, 1, tzinfo=TAIPEI)

def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

def parse_day(value: str | None) -> date:
    return date.fromisoformat(value) if value else NOW.date()

def prediction_stocks() -> list[dict[str, Any]]:
    prediction = load_json(PREDICTION)
    if prediction.get("artifact_type") == "formal_prediction_runtime" and prediction.get("is_example") is False:
        return [s for s in prediction.get("stocks", []) if isinstance(s, dict) and s.get("stock_id")]
    runtime = load_json(RUNTIME_DATA)
    return [{"stock_id": str(s.get("stock_id")), "stock_name": s.get("stock_name")} for s in runtime.get("stock_universe", []) if isinstance(s, dict) and s.get("stock_id")]

def build(review_date: date) -> dict[str, Any]:
    stocks = [evaluate_prediction_stock(s, review_date) for s in prediction_stocks()]
    reviewable_count = sum(1 for s in stocks if s.get("hit_miss_status") in {"hit", "partial_hit", "miss"})
    return {
        "schema_version": "formal_prediction_review_runtime_v1",
        "artifact_type": "formal_prediction_review_runtime",
        "generated_at": NOW.isoformat(),
        "runtime_window": "prediction_review_1500",
        "market": "TW",
        "source_mode": "deterministic_local_read_only_prediction_actual_evaluation",
        "is_example": False,
        "producer_name": "build_formal_prediction_review_runtime_artifact.py",
        "producer_version": "formal_prediction_review_runtime_v1",
        "review_window_days": 7,
        "review_date": review_date.isoformat(),
        "stock_universe_count": len(stocks),
        "reviewable_stock_count": reviewable_count,
        "stocks": stocks,
        "safety": {"external_api_called": False, "external_credentialed_api_called": False, "secrets_read": False, "db_write": False, "notification_sent": False, "production_pipeline_executed": False, "python_main_executed": False, "trading_or_order_executed": False, "fabricated_review_metrics": False, "production_rating_action_confidence_weight_mutated": False},
    }

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    ap.add_argument("--date")
    ap.add_argument("--pretty", action="store_true")
    args = ap.parse_args()
    data = build(parse_day(args.date))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(stable_json(data), encoding="utf-8")
    print(stable_json({"ok": True, "output": str(args.output), "artifact_type": data["artifact_type"], "stock_universe_count": data["stock_universe_count"], "reviewable_stock_count": data["reviewable_stock_count"], "review_metrics_fabricated": False}), end="")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
