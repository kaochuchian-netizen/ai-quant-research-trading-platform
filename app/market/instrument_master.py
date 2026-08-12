"""Versioned canonical instrument metadata; no task-local taxonomy truth."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
MASTER_PATH = ROOT / "config/governance/instrument_master_v1.json"
FORMAL_UNIVERSE_PATH = ROOT / "config/governance/formal_instrument_universe_v1.json"


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


def load_formal_instrument_universe() -> dict[str, Any]:
    return json.loads(FORMAL_UNIVERSE_PATH.read_text(encoding="utf-8"))


def validate_instrument_master_coverage(
    market: str, symbols: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Enforce formal watchlist subset-of-master and applicability invariants."""
    market = market.upper()
    universe = load_formal_instrument_universe()
    requested = [str(value) for value in (symbols if symbols is not None else (universe.get("markets") or {}).get(market, []))]
    errors: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    required = ("symbol", "display_name", "market", "exchange", "instrument_type", "source", "effective_date")
    for symbol in requested:
        row = instrument_metadata(market, symbol)
        rows.append(row)
        if row.get("status") != "AVAILABLE":
            errors.append({"symbol": symbol, "reason_code": "SYMBOL_MAPPING_FAILED"})
            continue
        missing = [field for field in required if not row.get(field)]
        if row.get("instrument_type") == "company":
            missing.extend(field for field in ("sector", "industry", "peer_group") if not row.get(field))
        if row.get("instrument_type") == "etf" and row.get("fundamentals_applicability") != "NOT_APPLICABLE":
            errors.append({"symbol": symbol, "reason_code": "ETF_APPLICABILITY_INVALID"})
        if row.get("adr_symbol") is None and row.get("adr_applicability") != "NOT_APPLICABLE":
            errors.append({"symbol": symbol, "reason_code": "ADR_APPLICABILITY_INVALID"})
        if missing:
            errors.append({"symbol": symbol, "reason_code": "INCOMPLETE_INSTRUMENT_METADATA", "fields": sorted(set(missing))})
    return {
        "schema_version": "instrument_master_coverage_v1",
        "market": market, "formal_symbols": requested,
        "covered_symbols": sum(row.get("status") == "AVAILABLE" for row in rows),
        "total_symbols": len(requested), "status": "PASS" if not errors else "FAIL",
        "errors": errors, "master_version": load_instrument_master().get("version"),
        "universe_version": universe.get("version"),
    }
