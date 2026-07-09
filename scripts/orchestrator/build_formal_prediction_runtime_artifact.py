#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, sqlite3, sys
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from analysis.forecast.formal_forecast_value_engine import MODEL_VERSION, compute_baseline, stable_json

DEFAULT_OUTPUT = ROOT / "artifacts/runtime/formal_prediction_runtime_latest.json"
RUNTIME_DATA = ROOT / "templates/four_window_dashboard_runtime_data.example.json"
DB = ROOT / "data/stock_analysis.db"
TAIPEI = ZoneInfo("Asia/Taipei")
NOW = datetime.now(TAIPEI).replace(microsecond=0)

def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

def parse_day(value: str | None) -> date:
    return date.fromisoformat(value) if value else NOW.date()

def stock_universe_from_runtime() -> list[dict[str, Any]]:
    rows = load_json(RUNTIME_DATA).get("stock_universe", [])
    return [{"stock_id": str(row.get("stock_id")), "stock_name": row.get("stock_name")} for row in rows if isinstance(row, dict) and row.get("stock_id")]

def latest_analysis_rows() -> dict[str, dict[str, Any]]:
    if not DB.exists():
        return {}
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        cur = con.cursor()
        cur.execute("select name from sqlite_master where type='table' and name='analysis_results'")
        if not cur.fetchone():
            return {}
        cur.execute("pragma table_info(analysis_results)")
        cols = {r["name"] for r in cur.fetchall()}
        wanted = ["stock_id", "stock_name", "created_at", "technical_summary", "chip_summary", "news_summary", "adr_summary", "risk_summary"]
        select_cols = [c for c in wanted if c in cols]
        cur.execute("select " + ", ".join(select_cols) + " from analysis_results where created_at in (select max(created_at) from analysis_results) order by stock_id")
        return {str(dict(row)["stock_id"]): dict(row) for row in cur.fetchall() if dict(row).get("stock_id")}
    finally:
        con.close()

def build(run_date: date) -> dict[str, Any]:
    analysis = latest_analysis_rows()
    universe = stock_universe_from_runtime() or [{"stock_id": sid, "stock_name": row.get("stock_name")} for sid, row in sorted(analysis.items())]
    stocks = [compute_baseline(str(stock.get("stock_id")), stock.get("stock_name") or analysis.get(str(stock.get("stock_id")), {}).get("stock_name"), run_date, analysis.get(str(stock.get("stock_id")), {})) for stock in universe]
    forecast_value_count = sum(1 for stock in stocks for key in ["same_day_high_prediction", "same_day_low_prediction", "next_day_high_prediction", "next_day_low_prediction"] if stock.get(key) is not None)
    return {
        "schema_version": "formal_prediction_runtime_v1",
        "artifact_type": "formal_prediction_runtime",
        "generated_at": NOW.isoformat(),
        "runtime_window": "pre_open_0700",
        "market": "TW",
        "source_mode": "deterministic_local_read_only_historical_ohlcv",
        "is_example": False,
        "producer_name": "build_formal_prediction_runtime_artifact.py",
        "producer_version": "formal_prediction_runtime_v1",
        "model_version": MODEL_VERSION,
        "data_cutoff_at": datetime.combine(run_date, datetime.min.time(), tzinfo=TAIPEI).replace(hour=7).isoformat(),
        "stock_universe_count": len(stocks),
        "forecast_value_count": forecast_value_count,
        "stocks": stocks,
        "safety": {"external_api_called": False, "external_credentialed_api_called": False, "secrets_read": False, "db_write": False, "sqlite_opened_read_only": DB.exists(), "notification_sent": False, "production_pipeline_executed": False, "python_main_executed": False, "trading_or_order_executed": False, "fabricated_forecast_values": False, "production_rating_action_confidence_weight_mutated": False},
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
    print(stable_json({"ok": True, "output": str(args.output), "artifact_type": data["artifact_type"], "stock_universe_count": data["stock_universe_count"], "forecast_value_count": data["forecast_value_count"], "model_version": MODEL_VERSION, "fabricated_forecast_values": False}), end="")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
