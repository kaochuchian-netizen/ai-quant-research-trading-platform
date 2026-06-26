#!/usr/bin/env python3
"""Generate a deterministic daily report forecast dry-run payload.

This script is research-only. It reads the daily report forecast contract example
and emits a synthetic 07:00 pre-open payload for downstream contract validation.
It does not read production databases, call external services, send notifications,
or require credentials.
"""

from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any


DEFAULT_CONTRACT_PATH = Path("templates/daily_report_forecast_contract.example.json")


def load_contract(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"contract file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"contract file is not valid JSON: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit("contract JSON root must be an object")
    return data


def build_per_stock_forecasts(contract: dict[str, Any]) -> list[dict[str, Any]]:
    stock_universe = contract.get("stock_universe", [])
    if not isinstance(stock_universe, list):
        stock_universe = []

    forecasts: list[dict[str, Any]] = []
    for stock in stock_universe:
        if not isinstance(stock, dict):
            continue
        stock_id = str(stock.get("stock_id", "UNKNOWN"))
        stock_name = str(stock.get("stock_name", "Synthetic Example"))
        forecasts.append({
            "stock_id": stock_id,
            "stock_name": stock_name,
            "forecast_status": "dry_run_generated",
            "same_day_high_low": deepcopy(contract.get("same_day_high_low", {})),
            "next_day_high_low": deepcopy(contract.get("next_day_high_low", {})),
            "one_month_trend": deepcopy(contract.get("one_month_trend", {})),
            "three_month_trend": deepcopy(contract.get("three_month_trend", {})),
            "confidence": deepcopy(contract.get("confidence", {})),
            "interval_bounds": deepcopy(contract.get("interval_bounds", {})),
            "evidence_sources": deepcopy(contract.get("evidence_sources", [])),
            "risk_flags": deepcopy(contract.get("risk_flags", [])),
            "review_required": True,
            "research_only": True,
            "no_trading_instruction": True,
            "no_order_execution": True,
        })
    return forecasts


def build_payload(contract: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": contract.get("schema_version", 1),
        "report_date": contract.get("report_date", "2026-06-26"),
        "market": contract.get("market", "TW"),
        "report_window": "pre_open_0700",
        "generated_at": contract.get("generated_at", "2026-06-26T07:00:00+08:00"),
        "dry_run": True,
        "stock_universe": deepcopy(contract.get("stock_universe", [])),
        "forecast_horizons": deepcopy(contract.get("forecast_horizons", [])),
        "per_stock_forecasts": build_per_stock_forecasts(contract),
        "same_day_high_low": deepcopy(contract.get("same_day_high_low", {})),
        "next_day_high_low": deepcopy(contract.get("next_day_high_low", {})),
        "one_month_trend": deepcopy(contract.get("one_month_trend", {})),
        "three_month_trend": deepcopy(contract.get("three_month_trend", {})),
        "confidence": deepcopy(contract.get("confidence", {})),
        "interval_bounds": deepcopy(contract.get("interval_bounds", {})),
        "evidence_sources": deepcopy(contract.get("evidence_sources", [])),
        "risk_flags": deepcopy(contract.get("risk_flags", [])),
        "output_channels": {
            "dashboard": {
                "enabled_for_dry_run": True,
                "detail_ready": True,
                "delivery_status": "not_sent",
            },
            "email": {
                "enabled_for_dry_run": True,
                "detail_ready": True,
                "delivery_status": "not_sent",
            },
            "line_reminder": {
                "enabled_for_dry_run": True,
                "reminder_only": True,
                "full_report_carried": False,
                "delivery_status": "not_sent",
            },
        },
        "dashboard_detail_ready": True,
        "email_detail_ready": True,
        "line_reminder_only": True,
        "review_required": True,
        "no_trading_instruction": True,
        "no_order_execution": True,
        "research_only": True,
        "dry_run_notes": [
            "synthetic_fixture_values_only",
            "no_production_database_read",
            "no_external_api_call",
            "no_notification_sent",
            "not_a_trading_or_order_instruction",
        ],
        "downstream_usage": {
            "dashboard": "contract_preview_only",
            "email": "draft_payload_preview_only",
            "line_reminder": "reminder_shape_preview_only",
            "dify_n8n": "future_draft_input_only_not_called_by_this_generator",
        },
    }


def write_payload(payload: dict[str, Any], pretty: bool, output: Path | None) -> str:
    indent = 2 if pretty else None
    rendered = json.dumps(payload, ensure_ascii=False, indent=indent, sort_keys=True)
    if pretty:
        rendered += "\n"
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
    return rendered


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a daily report forecast dry-run JSON payload.")
    parser.add_argument("--contract", default=str(DEFAULT_CONTRACT_PATH), help="Path to contract example JSON.")
    parser.add_argument("--output", default=None, help="Optional output path for the generated JSON.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args()

    contract = load_contract(Path(args.contract))
    payload = build_payload(contract)
    rendered = write_payload(payload, pretty=args.pretty, output=Path(args.output) if args.output else None)
    sys.stdout.write(rendered)
    if not rendered.endswith("\n"):
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
