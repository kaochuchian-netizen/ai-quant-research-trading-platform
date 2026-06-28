#!/usr/bin/env python3
"""Generate a deterministic Daily Report Forecast V1 fixture result.

The helper reads fixture input only. It does not call external APIs, send
notifications, read production databases, or run production pipelines.
"""

from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any


DEFAULT_INPUT = Path("templates/daily_report_forecast_v1_input.example.json")


def load_input(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"input file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"input file is not valid JSON: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit("input JSON root must be an object")
    return data


def round_price(value: float) -> float:
    return round(value, 1)


def confidence_bucket(score: float) -> str:
    if score >= 0.75:
        return "high"
    if score >= 0.5:
        return "medium"
    return "low"


def average_signal_strength(signals: list[dict[str, Any]]) -> float:
    strengths = [float(item.get("strength", 0.0)) for item in signals if isinstance(item, dict)]
    if not strengths:
        return 0.5
    return round(sum(strengths) / len(strengths), 2)


def signal_ids(signals: list[dict[str, Any]]) -> list[str]:
    return [str(item.get("signal_id")) for item in signals if isinstance(item, dict) and item.get("signal_id")]


def build_price_forecast(
    *,
    horizon: str,
    reference_price: float,
    interval_pct: float,
    confidence_score: float,
    basis: list[str],
    review_due: str,
    unit: str,
) -> dict[str, Any]:
    low = round_price(reference_price * (1 - interval_pct))
    high = round_price(reference_price * (1 + interval_pct))
    return {
        "horizon": horizon,
        "forecast_type": "high_low_interval",
        "price_interval": {
            "low": low,
            "high": high,
            "unit": unit,
            "interval_method": "fixture_reference_price_pct_band",
            "contains_reference_price": low <= reference_price <= high,
        },
        "confidence_score": confidence_score,
        "confidence_bucket": confidence_bucket(confidence_score),
        "basis": basis,
        "review_due": "2026-06-26T15:00:00+08:00" if horizon == "same_day" else review_due,
    }


def build_stock(stock: dict[str, Any]) -> dict[str, Any]:
    reference_price = float(stock.get("reference_price", 0.0))
    unit = str(stock.get("currency", "TWD"))
    assumptions = stock.get("fixture_assumptions", {})
    if not isinstance(assumptions, dict):
        assumptions = {}
    signals = [item for item in stock.get("signals_used", []) if isinstance(item, dict)]
    basis = signal_ids(signals)
    avg_strength = average_signal_strength(signals)
    same_day_confidence = round(min(0.9, max(0.35, avg_strength)), 2)
    next_day_confidence = round(max(0.3, same_day_confidence - 0.05), 2)
    one_month_confidence = round(max(0.3, same_day_confidence - 0.07), 2)
    same_day = build_price_forecast(
        horizon="same_day",
        reference_price=reference_price,
        interval_pct=float(assumptions.get("same_day_interval_pct", 0.018)),
        confidence_score=same_day_confidence,
        basis=basis,
        review_due="2026-06-26T15:00:00+08:00",
        unit=unit,
    )
    next_day = build_price_forecast(
        horizon="next_day",
        reference_price=reference_price,
        interval_pct=float(assumptions.get("next_day_interval_pct", 0.026)),
        confidence_score=next_day_confidence,
        basis=basis,
        review_due="2026-06-29T15:00:00+08:00",
        unit=unit,
    )
    trend_band = assumptions.get("one_month_trend_band", {})
    if not isinstance(trend_band, dict):
        trend_band = {}
    one_month_review_due = "2026-07-26"
    return {
        "stock_id": str(stock.get("stock_id", "")),
        "stock_name": str(stock.get("stock_name", "")),
        "reference_price": reference_price,
        "same_day_forecast": same_day,
        "next_day_forecast": next_day,
        "one_month_trend_forecast": {
            "horizon": "one_month",
            "forecast_type": "trend_interval",
            "trend": str(assumptions.get("one_month_trend", "neutral")),
            "confidence_score": one_month_confidence,
            "confidence_bucket": confidence_bucket(one_month_confidence),
            "interval": {
                "lower": float(trend_band.get("lower", -0.05)),
                "upper": float(trend_band.get("upper", 0.05)),
                "unit": str(trend_band.get("unit", "return_pct")),
                "interval_method": "fixture_trend_band",
            },
            "basis": basis,
            "review_due": one_month_review_due,
        },
        "signals_used": deepcopy(signals),
        "prediction_review": {
            "review_status": "pending",
            "same_day_review_due": same_day["review_due"],
            "next_day_review_due": next_day["review_due"],
            "one_month_review_due": one_month_review_due,
            "actual_outcome": {
                "same_day_high": None,
                "same_day_low": None,
                "next_day_high": None,
                "next_day_low": None,
                "one_month_trend": None,
            },
            "evaluation_metrics": {
                "same_day_interval_hit": None,
                "next_day_interval_hit": None,
                "one_month_trend_match": None,
                "calibration_bucket": "pending",
            },
            "review_notes": [
                "fixture_forecast_pending_actual_outcome",
                "preserve_original_forecast_snapshot",
            ],
        },
        "safety": {
            "advisory_only": True,
            "research_only": True,
            "no_trade": True,
            "no_order": True,
            "no_trading_instruction": True,
            "no_order_execution": True,
            "requires_human_review": True,
        },
    }


def build_result(data: dict[str, Any]) -> dict[str, Any]:
    stocks = [build_stock(item) for item in data.get("stocks", []) if isinstance(item, dict)]
    confidence_scores: list[float] = []
    for stock in stocks:
        confidence_scores.extend([
            stock["same_day_forecast"]["confidence_score"],
            stock["next_day_forecast"]["confidence_score"],
            stock["one_month_trend_forecast"]["confidence_score"],
        ])
    average_confidence = round(sum(confidence_scores) / len(confidence_scores), 2) if confidence_scores else 0.0
    return {
        "schema_version": 1,
        "run_id": data.get("run_id", "daily-report-forecast-v1-fixture"),
        "run_date": data.get("run_date"),
        "timezone": data.get("timezone", "Asia/Taipei"),
        "report_window": "pre_open",
        "forecast_version": "daily_report_forecast_v1",
        "generated_at": data.get("generated_at"),
        "data_cutoff": data.get("data_cutoff"),
        "stocks": stocks,
        "aggregate_summary": {
            "stock_count": len(stocks),
            "forecast_count": len(stocks) * 3,
            "average_confidence_score": average_confidence,
            "highest_risk_flags": [
                "fixture_only",
                "requires_human_review",
            ],
        },
        "validation_status": {
            "status": "valid_fixture_example",
            "validated_by": "validate_daily_report_forecast_v1_result.py",
            "errors": [],
        },
        "runtime_action_performed": False,
        "notification_sent": False,
        "production_pipeline_run": False,
        "safety": {
            "fixture_only": True,
            "advisory_only": True,
            "research_only": True,
            "no_trade": True,
            "no_order": True,
            "no_trading_instruction": True,
            "no_order_execution": True,
            "requires_human_review": True,
            "external_api_called": False,
            "notification_sent": False,
            "production_pipeline_run": False,
        },
    }


def write_result(result: dict[str, Any], output: Path, pretty: bool) -> str:
    rendered = json.dumps(result, ensure_ascii=False, indent=2 if pretty else None)
    if pretty:
        rendered += "\n"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    return rendered


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate deterministic Daily Report Forecast V1 fixture result.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", required=True)
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    fixture = load_input(Path(args.input))
    result = build_result(fixture)
    rendered = write_result(result, Path(args.output), args.pretty)
    sys.stdout.write(rendered)
    if not rendered.endswith("\n"):
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
