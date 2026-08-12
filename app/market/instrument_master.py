"""Versioned canonical instrument metadata; no task-local taxonomy truth."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
MASTER_PATH = ROOT / "config/governance/instrument_master_v1.json"


@lru_cache(maxsize=1)
def load_instrument_master() -> dict[str, Any]:
    return json.loads(MASTER_PATH.read_text(encoding="utf-8"))


def instrument_metadata(market: str, symbol: str) -> dict[str, Any]:
    master = load_instrument_master()
    row = dict((master.get("instruments") or {}).get(f"{market.upper()}:{symbol}") or {})
    if not row:
        return {"symbol": str(symbol), "market": market.upper(), "status": "MISSING", "reason_code": "SYMBOL_MAPPING_FAILED"}
    kind = row["instrument_type"]
    row.update({
        "status": "AVAILABLE", "metadata_version": master["version"],
        "fundamentals_applicability": "NOT_APPLICABLE" if kind == "etf" else "APPLICABLE",
        "company_events_applicability": "NOT_APPLICABLE" if kind == "etf" else "APPLICABLE",
        "adr_applicability": "APPLICABLE" if row.get("adr_symbol") else "NOT_APPLICABLE",
    })
    return row
