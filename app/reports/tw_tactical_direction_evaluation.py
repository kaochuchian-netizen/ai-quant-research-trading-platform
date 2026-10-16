"""Versioned public-safe projection of a frozen TW tactical direction result.

This module is an admission projection only.  It neither creates a forecast nor
changes the canonical 07:00 or 15:00 evidence.  In particular, research-v2 is
not a source for this projection.
"""
from __future__ import annotations

import math
from typing import Any

VERSION = "tw_tactical_direction_evaluation_v1"
DIRECTIONS = {"bullish", "bearish", "neutral"}


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        value = float(value) if value is not None else None
    except (TypeError, ValueError):
        return None
    return value if value is not None and math.isfinite(value) else None


def _insufficient(reason: str, *, identity: dict[str, Any]) -> dict[str, Any]:
    return {"status": "INSUFFICIENT_EVIDENCE", "result": None, "reason_code": reason,
            "identity": identity}


def _not_applicable(reason: str, *, identity: dict[str, Any]) -> dict[str, Any]:
    return {"status": "NOT_APPLICABLE", "result": "not_applicable", "reason_code": reason,
            "identity": identity}


def _actual_direction(open_price: float, close_price: float) -> str:
    if close_price > open_price:
        return "bullish"
    if close_price < open_price:
        return "bearish"
    return "neutral"


def project_tactical_direction_evaluation(card: dict[str, Any]) -> dict[str, Any]:
    """Admit a stored tactical direction result only when frozen identity agrees.

    ``prediction_evaluation_v2`` is deliberately ignored: it is research
    evidence with different forecast semantics.
    """
    identity = {
        "source_snapshot_id": card.get("source_snapshot_id"),
        "prediction_snapshot_id": card.get("prediction_snapshot_id"),
        "prediction_payload_hash": card.get("prediction_payload_hash"),
        "symbol": str(card.get("symbol") or card.get("stock_id") or ""),
        "trading_date": card.get("trading_date"),
    }
    source_id = identity["source_snapshot_id"]
    prediction_snapshot_id = identity["prediction_snapshot_id"]
    if not source_id or not identity["symbol"] or card.get("prediction_source_window") != "pre_open_0700":
        return _insufficient("TACTICAL_FROZEN_IDENTITY_MISSING", identity=identity)
    if prediction_snapshot_id and prediction_snapshot_id != source_id:
        return _insufficient("TACTICAL_FROZEN_IDENTITY_MISMATCH", identity=identity)

    prediction = str(card.get("predicted_direction") or "").lower()
    if prediction not in DIRECTIONS:
        if str(card.get("prediction_status") or "").lower() in {"no_trade", "unavailable"} or str(card.get("plan_status") or "").lower() == "no_trade":
            return _not_applicable("NO_CANONICAL_TACTICAL_DIRECTION_FORECAST", identity=identity)
        return _insufficient("TACTICAL_DIRECTION_FORECAST_MISSING", identity=identity)

    open_price = _number(card.get("actual_open"))
    low = _number(card.get("actual_low"))
    high = _number(card.get("actual_high"))
    close = _number(card.get("actual_close"))
    if None in (open_price, low, high, close) or low > high or not low <= close <= high:
        return _insufficient("ACTUAL_OUTCOME_MISSING_OR_INVALID", identity=identity)
    stored_hit = card.get("direction_hit")
    if not isinstance(stored_hit, bool):
        return _insufficient("TACTICAL_DIRECTION_RESULT_MISSING", identity=identity)
    computed_hit = (
        close > open_price if prediction == "bullish" else
        close < open_price if prediction == "bearish" else
        abs(close - open_price) / open_price <= 0.005 if open_price else False
    )
    if computed_hit != stored_hit:
        return _insufficient("TACTICAL_DIRECTION_RESULT_INCONSISTENT", identity=identity)
    return {
        "schema_version": VERSION,
        "status": "EVALUATED",
        "result": "hit" if stored_hit else "miss",
        "reason_code": None,
        "scope": "TW_FROZEN_TACTICAL_DIRECTION",
        "identity": identity,
        "forecast": prediction,
        "actual": _actual_direction(open_price, close),
        "actual_open": open_price,
        "actual_close": close,
    }
