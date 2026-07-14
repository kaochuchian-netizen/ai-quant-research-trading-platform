#!/usr/bin/env python3
"""Fail when stock-level presentation fields collapse to identical text."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.dashboard.decision_presentation import decision_presentation_v2

US_RUNTIME = ROOT / "artifacts/runtime/us_stock/us_pre_market_2000_latest.json"
TW_RUNTIME = ROOT / "artifacts/runtime/tw_daily_tactical/tw_daily_tactical_latest.json"
FIELDS_BY_MARKET = {"US": ["reason", "risk", "news", "sec", "review"], "TW": ["reason", "risk", "review"]}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def cards(market: str) -> list[dict[str, Any]]:
    if market == "US":
        data = read_json(US_RUNTIME)
        return [card for card in data.get("dashboard_ready_contract", {}).get("cards", []) if isinstance(card, dict)]
    data = read_json(TW_RUNTIME)
    return [card for card in data.get("cards", []) if isinstance(card, dict)]


def values(market: str, card: dict[str, Any]) -> dict[str, str]:
    presentation = decision_presentation_v2(market, card)
    rv3 = presentation.get("research_v3", {})
    return {
        "reason": "；".join(presentation.get("reasons", [])),
        "risk": "；".join(presentation.get("risks", [])),
        "news": str(rv3.get("material_news", "")),
        "sec": str(rv3.get("sec", "")),
        "review": str(rv3.get("review", "")),
    }


def audit_market(market: str) -> dict[str, Any]:
    market_cards = cards(market)
    result: dict[str, Any] = {}
    errors: list[str] = []
    for field in FIELDS_BY_MARKET[market]:
        field_values = [values(market, card)[field] for card in market_cards]
        unique_values = sorted(set(field_values))
        duplicated = len(field_values) > 1 and len(unique_values) == 1
        result[field] = {
            "stock_count": len(field_values),
            "unique_count": len(unique_values),
            "duplicated_100_percent": duplicated,
            "examples": unique_values[:5],
        }
        if duplicated:
            errors.append(f"{market}: {field} is identical across {len(field_values)} stocks")
    return {"fields": result, "errors": errors}


def build_validation() -> dict[str, Any]:
    us = audit_market("US")
    tw = audit_market("TW")
    errors = [*us["errors"], *tw["errors"]]
    return {
        "ok": not errors,
        "schema_version": "decision_presentation_uniqueness_validation_v1",
        "task_id": "AI-DEV-177",
        "US": us["fields"],
        "TW": tw["fields"],
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args()
    result = build_validation()
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None, sort_keys=True))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
