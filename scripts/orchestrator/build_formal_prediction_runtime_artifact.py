#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "artifacts/runtime/formal_prediction_runtime_latest.json"
RUNTIME_DATA = ROOT / "templates/four_window_dashboard_runtime_data.example.json"
DB = ROOT / "data/stock_analysis.db"
TAIPEI = ZoneInfo("Asia/Taipei")
NOW = datetime(2026, 7, 6, 7, 1, tzinfo=TAIPEI)
FORECAST_FIELDS = ["same_day_high_prediction", "same_day_low_prediction", "next_day_high_prediction", "next_day_low_prediction", "one_month_trend", "three_month_trend", "confidence_score"]
SOURCE_TYPES = ["local_summary", "historical_price", "technical_snapshot", "chip_summary", "news_summary"]

def stable(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"

def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))

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

def source_evidence_for(row: dict[str, Any]) -> list[dict[str, str]]:
    evidence = []
    for source_type in SOURCE_TYPES:
        status = "insufficient_data"
        if source_type == "local_summary" and row:
            status = "available_for_context_only"
        elif source_type == "technical_snapshot" and row.get("technical_summary"):
            status = "available_for_context_only"
        elif source_type == "chip_summary" and row.get("chip_summary"):
            status = "available_for_context_only"
        elif source_type == "news_summary" and row.get("news_summary"):
            status = "available_for_context_only"
        evidence.append({"source_type": source_type, "status": status})
    return evidence

def build_stock(stock: dict[str, Any], analysis: dict[str, Any], run_date: date) -> dict[str, Any]:
    missing = list(FORECAST_FIELDS)
    context_bits = [analysis.get(k) for k in ("technical_summary", "chip_summary", "news_summary", "adr_summary", "risk_summary") if analysis.get(k)]
    evidence_summary = "local_summary available for context only; insufficient_data for formal high/low prediction values." if context_bits else "insufficient_data: no contract-backed high/low prediction model output is available."
    return {
        "stock_id": str(stock.get("stock_id")),
        "stock_name": stock.get("stock_name") or analysis.get("stock_name"),
        "prediction_date": run_date.isoformat(),
        "next_trading_date": (run_date + timedelta(days=1)).isoformat(),
        "same_day_high_prediction": None,
        "same_day_low_prediction": None,
        "next_day_high_prediction": None,
        "next_day_low_prediction": None,
        "one_month_trend": None,
        "three_month_trend": None,
        "confidence_score": None,
        "confidence_level": None,
        "evidence_summary": evidence_summary,
        "key_factors": [x for x in ["technical_snapshot" if analysis.get("technical_summary") else None, "chip_summary" if analysis.get("chip_summary") else None, "news_summary" if analysis.get("news_summary") else None] if x],
        "risk_notes": ["資料待接: formal prediction values remain null until a safe model output exists."],
        "source_evidence": source_evidence_for(analysis),
        "data_quality": {"completeness": "insufficient_data", "freshness": "context_available" if analysis else "missing_context", "confidence_basis": "no formal prediction model output; local summary is context only", "blocking_missing_fields": missing},
        "missing_fields": missing,
        "insufficient_data_reasons": ["no_contract_backed_high_low_prediction_output", "no_safe_formal_forecast_model_result", "local_summary_must_not_be_recast_as_prediction"],
        "model_version": "safe_null_formal_prediction_v1",
        "created_at": NOW.isoformat(),
    }

def build(run_date: date) -> dict[str, Any]:
    analysis = latest_analysis_rows()
    universe = stock_universe_from_runtime() or [{"stock_id": sid, "stock_name": row.get("stock_name")} for sid, row in sorted(analysis.items())]
    stocks = [build_stock(stock, analysis.get(str(stock.get("stock_id")), {}), run_date) for stock in universe]
    return {"schema_version": "formal_prediction_runtime_v1", "artifact_type": "formal_prediction_runtime", "generated_at": NOW.isoformat(), "runtime_window": "pre_open_0700", "market": "TW", "source_mode": "safe_local_read_only_existing_artifacts", "is_example": False, "producer_name": "build_formal_prediction_runtime_artifact.py", "producer_version": "formal_prediction_runtime_v1", "data_cutoff_at": datetime.combine(run_date, datetime.min.time(), tzinfo=TAIPEI).replace(hour=7).isoformat(), "stock_universe_count": len(stocks), "stocks": stocks, "safety": {"external_api_called": False, "secrets_read": False, "db_write": False, "sqlite_opened_read_only": DB.exists(), "notification_sent": False, "production_pipeline_executed": False, "python_main_executed": False, "trading_or_order_executed": False, "fabricated_forecast_values": False}}

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    ap.add_argument("--date")
    ap.add_argument("--pretty", action="store_true")
    args = ap.parse_args()
    data = build(parse_day(args.date))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(stable(data), encoding="utf-8")
    print(stable({"ok": True, "output": str(args.output), "artifact_type": data["artifact_type"], "stock_universe_count": data["stock_universe_count"], "null_forecast_fields": True, "fabricated_forecast_values": False}), end="")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
