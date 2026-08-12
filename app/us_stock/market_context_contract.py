"""Canonical boundary between US market-context providers and consumers."""
from __future__ import annotations

from typing import Any

SCHEMA_VERSION = "us_market_context_v2"
EXPECTED_RAW_SCHEMA = "yfinance_us_context_items_v1"


def normalize_us_market_context(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize the production ``fetch_context`` shape exactly once.

    Legacy consumer-shaped fixtures are deliberately rejected.  A shape change
    must be handled here and covered by a production-shape fixture, not guessed
    by every downstream consumer.
    """
    if not isinstance(raw, dict) or not isinstance(raw.get("items"), dict):
        return {
            "schema_version": SCHEMA_VERSION,
            "normalization_status": "FAILED",
            "failure_reason": "SCHEMA_MISMATCH",
            "raw_schema": "unknown_or_legacy",
            "broad_market": {}, "growth_technology": {},
            "sector_context": {"semiconductors": {}},
            "source_provenance": {},
        }
    items = raw["items"]

    def item(symbol: str) -> dict[str, Any]:
        value = items.get(symbol)
        if not isinstance(value, dict):
            return {"symbol": symbol, "status": "MISSING", "failure_reason": "SCHEMA_MISMATCH"}
        premarket = value.get("premarket") if isinstance(value.get("premarket"), dict) else {}
        change = premarket.get("change_pct") if premarket.get("change_pct") is not None else value.get("change_pct")
        return {
            "symbol": symbol,
            "status": "AVAILABLE" if isinstance(change, (int, float)) else "MISSING",
            "change_pct": change,
            "last_price": value.get("last_price"),
            "previous_close": value.get("previous_close"),
            "timestamp": premarket.get("timestamp") or value.get("source_timestamp"),
            "source": premarket.get("source") or "yfinance",
            "freshness": premarket.get("freshness") or ("current" if change is not None else "unavailable"),
            "failure_reason": None if isinstance(change, (int, float)) else value.get("error") or "UPSTREAM_ERROR",
        }

    spy, qqq, soxx, vix = item("SPY"), item("QQQ"), item("SOXX"), item("^VIX")
    required = (spy, qqq, soxx)
    ok = all(value["status"] == "AVAILABLE" for value in required)
    return {
        "schema_version": SCHEMA_VERSION,
        "normalization_status": "VALID" if ok else "PARTIAL",
        "failure_reason": None if ok else "UPSTREAM_ERROR",
        "raw_schema": EXPECTED_RAW_SCHEMA,
        "broad_market": spy,
        "growth_technology": qqq,
        "sector_context": {"semiconductors": soxx},
        "volatility_context": vix,
        "market_environment_score": raw.get("market_environment_score"),
        "market_regime": raw.get("market_regime"),
        "risk_environment": raw.get("risk_environment"),
        "source_provenance": {
            "provider": "YFinanceUSClient.fetch_context",
            "observed_at": raw.get("source_timestamp"),
            "raw_schema": EXPECTED_RAW_SCHEMA,
            "canonical_schema": SCHEMA_VERSION,
        },
    }


def canonical_ticker(canonical: dict[str, Any], symbol: str) -> dict[str, Any]:
    if symbol == "SPY":
        return canonical.get("broad_market") or {}
    if symbol == "QQQ":
        return canonical.get("growth_technology") or {}
    if symbol == "SOXX":
        return ((canonical.get("sector_context") or {}).get("semiconductors") or {})
    if symbol == "^VIX":
        return canonical.get("volatility_context") or {}
    return {}
