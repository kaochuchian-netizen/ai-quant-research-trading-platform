#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analysis.forecast.formal_forecast_backtest_engine import build_backtest_report, render_markdown, stable_json

DEFAULT_JSON = ROOT / "artifacts/runtime/formal_forecast_backtest_report_latest.json"
DEFAULT_MD = ROOT / "artifacts/runtime/formal_forecast_backtest_report_latest.md"
RUNTIME_DATA = ROOT / "templates/four_window_dashboard_runtime_data.example.json"
PREDICTION = ROOT / "artifacts/runtime/formal_prediction_runtime_latest.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def parse_day(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def stock_universe() -> list[dict[str, Any]]:
    prediction = load_json(PREDICTION)
    stocks = prediction.get("stocks") if isinstance(prediction.get("stocks"), list) else []
    if stocks:
        return [{"stock_id": str(s.get("stock_id")), "stock_name": s.get("stock_name")} for s in stocks if s.get("stock_id")]
    runtime = load_json(RUNTIME_DATA)
    rows = runtime.get("stock_universe") if isinstance(runtime.get("stock_universe"), list) else []
    return [{"stock_id": str(s.get("stock_id")), "stock_name": s.get("stock_name")} for s in rows if s.get("stock_id")]


def main() -> int:
    parser = argparse.ArgumentParser(description="Build deterministic_baseline_v1 backtest and calibration report.")
    parser.add_argument("--output-json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_MD)
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--lookback-days", type=int, default=120)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    report = build_backtest_report(stock_universe(), start_date=parse_day(args.start_date), end_date=parse_day(args.end_date), lookback_days=args.lookback_days)
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(stable_json(report), encoding="utf-8")
    args.output_md.write_text(render_markdown(report), encoding="utf-8")
    summary = {
        "ok": True,
        "artifact_type": report["artifact_type"],
        "method_under_test": report["method_under_test"],
        "output_json": str(args.output_json),
        "output_md": str(args.output_md),
        "stock_universe_count": report["stock_universe_count"],
        "eligible_sample_count": report["metrics"].get("eligible_sample_count"),
        "same_day_interval_hit_rate": report["metrics"].get("same_day_interval_hit_rate"),
        "next_day_interval_hit_rate": report["metrics"].get("next_day_interval_hit_rate"),
        "recommendation_count": len(report["calibration_analysis"].get("recommendations", [])),
        "safety": report["safety_policy"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
