#!/usr/bin/env python3
"""Convert Daily Report Forecast V1 fixture results into review ingestion records.

The helper reads fixture JSON only. It does not call external APIs, send
notifications, read production databases, or run production pipelines.
"""

from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Any


DEFAULT_INPUT = Path("templates/daily_report_forecast_review_ingestion_input.example.json")
INGESTION_VERSION = "daily_report_forecast_review_ingestion_v1"
RECORD_TYPE = "daily_report_forecast_prediction_review"


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


def source_forecast_result(data: dict[str, Any]) -> dict[str, Any]:
    source = data.get("source_forecast_result", data)
    if not isinstance(source, dict):
        raise SystemExit("source_forecast_result must be an object")
    return source


def date_part(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    if len(text) >= 10:
        candidate = text[:10]
        try:
            date.fromisoformat(candidate)
        except ValueError:
            return text
        return candidate
    return text


def safety_block(*, include_fixture: bool = True) -> dict[str, bool]:
    data = {
        "advisory_only": True,
        "research_only": True,
        "no_trade": True,
        "no_order": True,
        "no_trading_instruction": True,
        "no_order_execution": True,
        "requires_human_review": True,
    }
    if include_fixture:
        data = {"fixture_only": True, **data}
    return data


def pending_actual_outcome(forecast_target: str) -> dict[str, Any]:
    if forecast_target == "one_month_trend_interval":
        values = {
            "actual_return": None,
            "actual_trend": None,
            "actual_close": None,
        }
    else:
        values = {
            "actual_high": None,
            "actual_low": None,
            "actual_close": None,
            "actual_return": None,
            "actual_direction": None,
        }
    return {
        "outcome_status": "pending",
        "source_status": "not_collected",
        "pending_reason": "fixture_review_window_not_backfilled",
        "values": values,
    }


def evaluation_metrics(forecast: dict[str, Any], forecast_target: str) -> dict[str, Any]:
    return {
        "evaluation_status": "pending",
        "interval_hit": None if forecast_target != "one_month_trend_interval" else None,
        "high_inside_interval": None,
        "low_inside_interval": None,
        "direction_match": None,
        "trend_match": None,
        "absolute_error": None,
        "high_forecast_error": None,
        "low_forecast_error": None,
        "confidence_bucket": forecast.get("confidence_bucket"),
        "calibration_bucket": "pending",
    }


def forecast_snapshot(forecast: dict[str, Any], forecast_target: str) -> dict[str, Any]:
    snapshot = {
        "forecast_type": forecast.get("forecast_type"),
        "forecast_target": forecast_target,
        "confidence_score": forecast.get("confidence_score"),
        "confidence_bucket": forecast.get("confidence_bucket"),
        "basis": deepcopy(forecast.get("basis", [])),
        "review_due": forecast.get("review_due"),
    }
    if forecast_target == "one_month_trend_interval":
        snapshot["trend"] = forecast.get("trend")
        snapshot["trend_interval"] = deepcopy(forecast.get("interval"))
    else:
        snapshot["price_interval"] = deepcopy(forecast.get("price_interval"))
    return snapshot


def build_record(
    *,
    source: dict[str, Any],
    stock: dict[str, Any],
    forecast_key: str,
    forecast_horizon: str,
    forecast_target: str,
    review_window: str,
) -> dict[str, Any]:
    forecast = stock.get(forecast_key)
    if not isinstance(forecast, dict):
        forecast = {}
    review_due = forecast.get("review_due")
    target_date = source.get("run_date") if forecast_horizon == "same_day" else date_part(review_due)
    stock_id = str(stock.get("stock_id", ""))
    record_id = "-".join([
        "daily-report-forecast-review",
        str(source.get("run_date", "unknown")),
        stock_id,
        forecast_horizon,
    ])
    return {
        "record_id": record_id,
        "record_type": RECORD_TYPE,
        "record_status": "pending_actual_outcome",
        "stock_id": stock_id,
        "stock_name": str(stock.get("stock_name", "")),
        "forecast_version": source.get("forecast_version"),
        "source_forecast_run_id": source.get("run_id"),
        "run_date": source.get("run_date"),
        "timezone": source.get("timezone"),
        "forecast_horizon": forecast_horizon,
        "forecast_target": forecast_target,
        "target_date": target_date,
        "review_window": review_window,
        "review_due": review_due,
        "forecast_snapshot": forecast_snapshot(forecast, forecast_target),
        "actual_outcome": pending_actual_outcome(forecast_target),
        "evaluation_metrics": evaluation_metrics(forecast, forecast_target),
        "source_metadata": {
            "report_window": source.get("report_window"),
            "generated_at": source.get("generated_at"),
            "data_cutoff": source.get("data_cutoff"),
            "signals_used": deepcopy(stock.get("signals_used", [])),
            "original_prediction_review": deepcopy(stock.get("prediction_review", {})),
        },
        "safety": safety_block(include_fixture=True),
    }


def build_records(source: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    stocks = source.get("stocks", [])
    if not isinstance(stocks, list):
        return records
    for stock in stocks:
        if not isinstance(stock, dict):
            continue
        records.append(build_record(
            source=source,
            stock=stock,
            forecast_key="same_day_forecast",
            forecast_horizon="same_day",
            forecast_target="same_day_high_low_interval",
            review_window="same_day_close",
        ))
        records.append(build_record(
            source=source,
            stock=stock,
            forecast_key="next_day_forecast",
            forecast_horizon="next_day",
            forecast_target="next_day_high_low_interval",
            review_window="next_trading_day_close",
        ))
        records.append(build_record(
            source=source,
            stock=stock,
            forecast_key="one_month_trend_forecast",
            forecast_horizon="one_month",
            forecast_target="one_month_trend_interval",
            review_window="one_month_close",
        ))
    return records


def build_result(data: dict[str, Any]) -> dict[str, Any]:
    source = source_forecast_result(data)
    records = build_records(source)
    stock_ids = sorted({record["stock_id"] for record in records})
    return {
        "schema_version": 1,
        "ingestion_version": INGESTION_VERSION,
        "run_id": data.get("run_id", f"{source.get('run_id', 'forecast')}-review-ingestion"),
        "generated_at": data.get("generated_at", source.get("generated_at")),
        "source_forecast_run_id": source.get("run_id"),
        "source_forecast_version": source.get("forecast_version"),
        "run_date": source.get("run_date"),
        "timezone": source.get("timezone", "Asia/Taipei"),
        "review_records": records,
        "aggregate_summary": {
            "stock_count": len(stock_ids),
            "review_record_count": len(records),
            "pending_actual_outcome_count": sum(1 for record in records if record.get("record_status") == "pending_actual_outcome"),
            "review_windows": [
                "same_day_close",
                "next_trading_day_close",
                "one_month_close",
            ],
            "fixture_only": True,
        },
        "validation_status": {
            "status": "valid_fixture_example",
            "validated_by": "validate_daily_report_forecast_review_ingestion_result.py",
            "errors": [],
        },
        "runtime_action_performed": False,
        "notification_sent": False,
        "production_pipeline_run": False,
        "safety": {
            **safety_block(include_fixture=True),
            "external_api_called": False,
            "notification_sent": False,
            "production_pipeline_run": False,
            "production_db_modified": False,
            "trading_or_order_run": False,
            "secrets_read_or_modified": False,
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
    parser = argparse.ArgumentParser(description="Generate Daily Report Forecast review ingestion fixture result.")
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
